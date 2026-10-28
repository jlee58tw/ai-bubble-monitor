"""Taiwan Stock Exchange (TWSE) adapter - government open data.

Sources (both published by TWSE; open data under the Taiwan Government Open Data License, attribution required):
  * https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL  - P/E, dividend yield, P/B (latest trading day)
  * https://openapi.twse.com.tw/v1/opendata/t187ap03_L         - listed-company profile (common shares issued)
  * https://openapi.twse.com.tw/v1/opendata/t187ap05_L         - listed-company MONTHLY REVENUE (latest month, with
                                                                the prior month and the same month a year earlier)
  * https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=YYYYMM01&stockNo=XXXX
                                                              - daily OHLC for one stock-month (robots.txt: Allow /)
Rate limit: TWSE blocks bursts, so www.twse.com.tw requests are spaced >= TWSE_MIN_INTERVAL_S (default 3 s).
Dates are ROC calendar ("115/10/22" or "1151022" = 2026-10-22).
Missing / '--' values are skipped, never zero-filled.
"""
from __future__ import annotations

import datetime as dt
import re

import httpx

from ..config import get_settings
from ..logging_setup import get_logger
from ..registry.registry import Registry
from .base import (ObservationRecord, Provider, ProviderError, ProviderResult, ProviderStatus,
                   RateLimiter, get_with_retry)

log = get_logger(__name__)
OPENAPI = "https://openapi.twse.com.tw/v1"
BWIBBU_URL = f"{OPENAPI}/exchangeReport/BWIBBU_ALL"
PROFILE_URL = f"{OPENAPI}/opendata/t187ap03_L"
MONTHLY_REV_URL = f"{OPENAPI}/opendata/t187ap05_L"
STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={ym}01&stockNo={code}"
STOCK_DAY_PAGE = "https://www.twse.com.tw/zh/trading/historical/stock-day.html"
LICENSE = "TWSE open data (政府資料開放授權條款)"


def roc_date(s: str) -> dt.date:
    """'115/10/22' or '1151022' -> 2026-10-22."""
    s = s.strip()
    m = re.fullmatch(r"(\d{2,3})/(\d{1,2})/(\d{1,2})", s) or re.fullmatch(r"(\d{2,3})(\d{2})(\d{2})", s)
    if not m:
        raise ValueError(f"bad ROC date {s!r}")
    y, mo, d = (int(x) for x in m.groups())
    return dt.date(y + 1911, mo, d)


def num(s) -> float | None:
    if s is None:
        return None
    s = str(s).replace(",", "").strip()
    if s in ("", "--", "-", "N/A", "X0.00"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _rec(metric, code, value, unit, day, url, ref, meth, conf="high"):
    return ObservationRecord(metric_id=metric, entity_id=code, value=value, unit=unit, period_start=None,
                             period_end=day, publication_date=day, fiscal_period=None, source_type="twse",
                             classification="reported", confidence=conf, source_url=url,
                             methodology=meth, source_ref=ref)


def parse_stock_day(doc: dict, code: str, url: str) -> list[ObservationRecord]:
    """One stock-month of STOCK_DAY JSON -> tw_price_close records."""
    if doc.get("stat") != "OK":
        raise ValueError(f"TWSE STOCK_DAY stat={doc.get('stat')!r}")
    fields = doc["fields"]
    i_date, i_close = fields.index("日期"), fields.index("收盤價")
    out = []
    for row in doc.get("data", []):
        v = num(row[i_close])
        if v is None:
            continue
        d = roc_date(row[i_date])
        out.append(_rec("tw_price_close", code, v, "TWD", d, url, f"TWSE:STOCK_DAY:{code}",
                        f"{LICENSE}. STOCK_DAY 收盤價 (close), unadjusted."))
    return out


def parse_bwibbu(rows: list[dict], codes: set[str]) -> list[ObservationRecord]:
    out = []
    for r in rows:
        code = r.get("Code")
        if code not in codes:
            continue
        d = roc_date(r["Date"])
        pe, dy, pb = num(r.get("PEratio")), num(r.get("DividendYield")), num(r.get("PBratio"))
        meth = f"{LICENSE}. BWIBBU_ALL, exchange-computed."
        if pe is not None:
            out.append(_rec("tw_pe_trailing", code, pe, "ratio", d, BWIBBU_URL, "TWSE:BWIBBU_ALL:PEratio",
                            meth + " Trailing 4-quarter EPS basis (not forward)."))
        if pb is not None:
            out.append(_rec("tw_pb_ratio", code, pb, "ratio", d, BWIBBU_URL, "TWSE:BWIBBU_ALL:PBratio", meth))
        if dy is not None:
            out.append(_rec("tw_dividend_yield", code, dy / 100.0, "pct", d, BWIBBU_URL,
                            "TWSE:BWIBBU_ALL:DividendYield", meth + " Published in %, stored as fraction."))
    return out


def parse_profile(rows: list[dict], codes: set[str]) -> list[ObservationRecord]:
    out = []
    for r in rows:
        code = r.get("公司代號")
        if code not in codes:
            continue
        v = num(r.get("已發行普通股數或TDR原股發行股數"))
        if v is None or v <= 0:
            continue
        d = roc_date(r["出表日期"])
        out.append(_rec("tw_shares_outstanding", code, v, "shares", d, PROFILE_URL,
                        "TWSE:t187ap03_L:已發行普通股數或TDR原股發行股數",
                        f"{LICENSE}. Listed-company profile, snapshot dated 出表日期."))
    return out


def _ym(roc_ym: str) -> tuple[dt.date, dt.date]:
    """'11509' -> (2026-09-01, 2026-09-30)."""
    y, m = int(roc_ym[:-2]) + 1911, int(roc_ym[-2:])
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return dt.date(y, m, 1), nxt - dt.timedelta(days=1)


def _shift(d: dt.date, months: int) -> tuple[dt.date, dt.date]:
    k = d.year * 12 + d.month - 1 + months
    s = dt.date(k // 12, k % 12 + 1, 1)
    nxt = dt.date((k + 1) // 12, (k + 1) % 12 + 1, 1)
    return s, nxt - dt.timedelta(days=1)


def parse_monthly_revenue(rows: list[dict], codes: set[str]) -> list[ObservationRecord]:
    """t187ap05_L -> tw_monthly_revenue (TWD; the file is in NT$ thousands) for the data month, the prior month and
    the same month a year earlier, plus the exchange-published YoY and cumulative YoY (% -> fraction).
    publication_date = 出表日期 (table date; companies must file by the 10th, so this is conservative)."""
    out = []
    for r in rows:
        code = r.get("公司代號")
        if code not in codes:
            continue
        pub = roc_date(r["出表日期"])
        start, end = _ym(r["資料年月"])
        meth = f"{LICENSE}. t187ap05_L 上市公司每月營業收入彙總表 (NT$ thousands x 1000), as of 出表日期 {pub}."
        for field, (s0, e0), tag in (("營業收入-當月營收", (start, end), "current month"),
                                     ("營業收入-上月營收", _shift(start, -1), "prior-month comparative"),
                                     ("營業收入-去年當月營收", _shift(start, -12), "prior-year comparative")):
            v = num(r.get(field))
            if v is None:
                continue
            out.append(ObservationRecord(
                metric_id="tw_monthly_revenue", entity_id=code, value=v * 1000.0, unit="TWD", period_start=s0,
                period_end=e0, publication_date=pub, fiscal_period=None, source_type="twse",
                classification="reported", confidence="high", source_url=MONTHLY_REV_URL,
                methodology=f"{meth} Field {field} ({tag}).", source_ref=f"TWSE:t187ap05_L:{field}"))
        for metric, field in (("tw_monthly_revenue_yoy", "營業收入-去年同月增減(%)"),
                              ("tw_revenue_ytd_yoy", "累計營業收入-前期比較增減(%)")):
            v = num(r.get(field))
            if v is None:
                continue
            out.append(ObservationRecord(
                metric_id=metric, entity_id=code, value=v / 100.0, unit="pct",
                period_start=start if metric == "tw_monthly_revenue_yoy" else dt.date(start.year, 1, 1),
                period_end=end, publication_date=pub, fiscal_period=None, source_type="twse",
                classification="reported", confidence="high", source_url=MONTHLY_REV_URL,
                methodology=f"{meth} Field {field}; published in %, stored as fraction.",
                source_ref=f"TWSE:t187ap05_L:{field}"))
    return out


def month_starts(today: dt.date, n: int) -> list[str]:
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


class TwseProvider(Provider):
    name = "twse"
    description = "Taiwan Stock Exchange open data (prices, P/E, P/B, yield, shares)"

    def __init__(self, client: httpx.Client | None = None, today: dt.date | None = None,
                 months: int | None = None, min_interval_s: float | None = None):
        s = get_settings()
        self._client = client
        self.today = today
        self.months = months or s.twse_history_months
        self.throttle_backoff_s = 10.0
        self.limiter = RateLimiter(1.0 / max(min_interval_s if min_interval_s is not None
                                             else s.twse_min_interval_s, 0.001))

    def status(self) -> ProviderStatus:
        return ProviderStatus(self.name, True)

    def fetch(self, registry: Registry, entity_ids: list[str] | None = None) -> ProviderResult:
        res = ProviderResult()
        metrics = registry.metrics_for_provider(self.name)
        codes = sorted({e for m in metrics for e in m.entities})
        if entity_ids:
            codes = [c for c in codes if c in entity_ids]
        if not codes:
            return res
        cs = set(codes)
        client = self._client or httpx.Client(timeout=60, headers={
            "User-Agent": f"ai-bubble-monitor research ({get_settings().sec_user_agent or 'no contact set'})"})
        try:
            for url, parser in ((BWIBBU_URL, parse_bwibbu), (PROFILE_URL, parse_profile),
                                (MONTHLY_REV_URL, parse_monthly_revenue)):
                try:
                    rows = get_with_retry(client, url, self.limiter).json()
                    allowed = {(m.id, e) for m in metrics for e in m.entities}
                    recs = [r for r in parser(rows, cs) if (r.metric_id, r.entity_id) in allowed]
                    want = {e for (mid, e) in allowed if mid in {r.metric_id for r in recs}} or cs
                    res.records.extend(recs); res.fetched += len(rows)
                    for c in want - {r.entity_id for r in recs}:
                        res.errors.append(ProviderError(f"{url.rsplit('/', 1)[-1]}: no row/value for {c}",
                                                        level="warning", entity_id=c))
                except Exception as exc:  # noqa: BLE001
                    res.errors.append(ProviderError(f"TWSE fetch failed: {exc}", context={"url": url}))
            today = self.today or dt.date.today()
            # daily prices only for entities registered on tw_price_close (monthly-revenue-only names skip
            # the throttled per-stock-month STOCK_DAY endpoint)
            price_codes = {e for m in metrics if m.id == "tw_price_close" for e in m.entities} or set(codes)
            for code in [c for c in codes if c in price_codes]:
                for ym in month_starts(today, self.months):
                    url = STOCK_DAY_URL.format(ym=ym, code=code)
                    try:
                        # TWSE throttles with "307 Temporary Redirect": back off and retry instead of
                        # silently losing the month (audit 2026-10-28: October was lost -> closes stale).
                        doc = get_with_retry(client, url, self.limiter, retries=4, backoff_s=self.throttle_backoff_s,
                                             retry_statuses=(307,)).json()
                        if doc.get("stat") != "OK" and "沒有符合" in str(doc.get("stat")):
                            continue  # no trading data that month (e.g. future month)
                        recs = parse_stock_day(doc, code, url)
                        res.records.extend(recs); res.fetched += len(recs)
                    except Exception as exc:  # noqa: BLE001
                        res.errors.append(ProviderError(f"STOCK_DAY {code} {ym} failed: {exc}",
                                                        entity_id=code, metric_id="tw_price_close",
                                                        context={"url": url}))
                log.info("twse_stock_done", code=code)
        finally:
            if self._client is None:
                client.close()
        return res
