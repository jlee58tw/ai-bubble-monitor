"use client";
import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ClassBadge, StatusPill } from "@/components/Badges";
import { Loading, Panel } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import type { Observation } from "@/lib/api";

const TW = ["2330", "2382", "2317"];
const US = ["NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META", "ORCL", "TSM"];
const ETF = ["QQQ", "SOXX", "SMH"];
const IDX = ["NDX", "COMP", "SOX"];
const IDX_NAME: Record<string, string> = { NDX: "NASDAQ-100", COMP: "NASDAQ Composite", SOX: "PHLX Semiconductor" };
const IDX_COLOR: Record<string, string> = { NDX: "#ffb000", COMP: "#58a6ff", SOX: "#3fb950" };
const USM = ["us_price_close", "us_drawdown_52w", "market_cap", "us_rel_return_1y_vs_ndx", "us_rel_return_1y_vs_sox", "us_shares_outstanding"];
const pct = (x?: number) => (x === undefined ? undefined : `${(x * 100).toFixed(1)}%`);
const TWM = ["tw_price_close", "tw_pe_trailing", "tw_pb_ratio", "tw_dividend_yield", "tw_market_cap", "tw_drawdown_52w", "tw_shares_outstanding"];
type MetricRow = { id: string; name: string; effective_status: string; unavailable_reason: string | null; warning: string | null; entities: string[] };

export default function Valuation() {
  const [code, setCode] = useState("2330");
  const latest = useApi<Observation[]>(`/api/observations?metric_id=${TWM.join(",")}&entity_id=${TW.join(",")}&start=2026-01-01`);
  const hist = useApi<Observation[]>(`/api/observations?metric_id=tw_price_close,tw_drawdown_52w&entity_id=${code}`);
  const metrics = useApi<MetricRow[]>("/api/metrics");
  const usObs = useApi<Observation[]>(`/api/observations?metric_id=${USM.join(",")}&entity_id=${[...US, ...ETF].join(",")}&start=2025-07-01&limit=50000`);
  const idxObs = useApi<Observation[]>(`/api/observations?metric_id=us_index_close,us_index_drawdown_52w&entity_id=${IDX.join(",")}&start=2021-01-01&limit=50000`);

  const last = useMemo(() => {
    const m: Record<string, Observation> = {};
    (latest.data ?? []).forEach((o) => { const k = `${o.entity_id}|${o.metric_id}`; if (!m[k] || o.period_end > m[k].period_end) m[k] = o; });
    return m;
  }, [latest.data]);
  const series = useMemo(() => {
    const m = new Map<string, Record<string, number | string>>();
    (hist.data ?? []).forEach((o) => { const r = m.get(o.period_end) ?? { d: o.period_end }; r[o.metric_id] = o.metric_id === "tw_drawdown_52w" ? o.value * 100 : o.value; m.set(o.period_end, r); });
    return [...m.values()].sort((a, b) => String(a.d).localeCompare(String(b.d)));
  }, [hist.data]);
  const mdef = (id: string) => metrics.data?.find((m) => m.id === id);
  const v = (e: string, m: string) => last[`${e}|${m}`];
  const usLast = useMemo(() => {
    const m: Record<string, Observation> = {};
    (usObs.data ?? []).forEach((o) => { const k = `${o.entity_id}|${o.metric_id}`; if (!m[k] || o.period_end > m[k].period_end) m[k] = o; });
    return m;
  }, [usObs.data]);
  const idxLast = useMemo(() => {
    const m: Record<string, Observation> = {};
    (idxObs.data ?? []).forEach((o) => { const k = `${o.entity_id}|${o.metric_id}`; if (!m[k] || o.period_end > m[k].period_end) m[k] = o; });
    return m;
  }, [idxObs.data]);
  const idxSeries = useMemo(() => {
    const m = new Map<string, Record<string, number | string>>();
    (idxObs.data ?? []).forEach((o) => {
      const r = m.get(o.period_end) ?? { d: o.period_end };
      if (o.metric_id === "us_index_drawdown_52w") r[`dd_${o.entity_id}`] = o.value * 100; else r[`px_${o.entity_id}`] = o.value;
      m.set(o.period_end, r);
    });
    return [...m.values()].sort((a, b) => String(a.d).localeCompare(String(b.d)));
  }, [idxObs.data]);
  const u = (e: string, m: string) => usLast[`${e}|${m}`];
  const why = (id: string) => mdef(id)?.unavailable_reason ?? mdef(id)?.warning ?? "";
  const cell = (e: string, id: string, fmt: (o: Observation) => string, covered = true) => {
    const o = u(e, id);
    if (o) return <span title={o.methodology ?? ""}>{fmt(o)}</span>;
    const st = covered ? (mdef(id)?.effective_status === "connected" ? "missing" : mdef(id)?.effective_status ?? "unavailable") : "unavailable";
    return <span title={covered ? why(id) : "Not covered: multi-class issuer, no single SEC share count"}><StatusPill s={st} /></span>;
  };

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">VALUATION</h1>
      {latest.error ? <ApiError error={latest.error} /> : null}
      <Panel title="TAIWAN AI SUPPLY CHAIN — TWSE OPEN DATA (REPORTED BY EXCHANGE; MARKET CAP & DRAWDOWN DERIVED)">
        <Loading show={!latest.data && !latest.error} />
        <table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted text-left"><tr><th>code</th><th className="text-right">close (TWD)</th><th className="text-right">trailing P/E</th><th className="text-right">P/B</th><th className="text-right">div. yield</th><th className="text-right">shares</th><th className="text-right">market cap</th><th className="text-right">vs 52w high</th><th>as of</th></tr></thead>
          <tbody>{TW.map((e) => {
            const c = v(e, "tw_price_close"), mc = v(e, "tw_market_cap"), dd = v(e, "tw_drawdown_52w");
            return (
              <tr key={e} className="border-t border-term-border">
                <td className="text-white">{e}</td>
                <td className="text-right">{c ? c.value.toLocaleString() : <StatusPill s="missing" />}</td>
                <td className="text-right">{v(e, "tw_pe_trailing")?.value.toFixed(2) ?? "—"}</td>
                <td className="text-right">{v(e, "tw_pb_ratio")?.value.toFixed(2) ?? "—"}</td>
                <td className="text-right">{v(e, "tw_dividend_yield") ? `${(v(e, "tw_dividend_yield").value * 100).toFixed(2)}%` : "—"}</td>
                <td className="text-right">{v(e, "tw_shares_outstanding")?.value.toLocaleString() ?? "—"}</td>
                <td className="text-right">{mc ? `${(mc.value / 1e12).toFixed(3)}T` : "—"} {mc ? <ClassBadge c="derived" /> : null}</td>
                <td className={`text-right ${dd && dd.value <= -0.2 ? "text-term-down" : ""}`}>{dd ? `${(dd.value * 100).toFixed(1)}%` : <StatusPill s="missing" />}</td>
                <td className="text-term-muted">{c?.period_end ?? "—"} {c?.source_url ? <a className="src" href={c.source_url} target="_blank" rel="noreferrer">TWSE ↗</a> : null}</td>
              </tr>);
          })}</tbody>
        </table>
        <p className="text-[10px] text-term-muted mt-1">P/E, P/B, yield: TWSE BWIBBU (exchange-computed, trailing). Market cap = close × listed common shares (TWSE company profile), nearest date within 45 days. Drawdown needs ≥358 days of closes.</p>
      </Panel>
      <Panel title={`${code} · CLOSE & DRAWDOWN FROM 52-WEEK HIGH`}>
        <div className="mb-2 flex gap-1">{TW.map((c) => <button key={c} className={`btn ${c === code ? "text-term-amber border-term-amber" : ""}`} onClick={() => setCode(c)}>{c}</button>)}</div>
        <div className="grid gap-3 lg:grid-cols-2">
          <ResponsiveContainer width="100%" height={240}><LineChart data={series}>
            <CartesianGrid stroke="#232a35" strokeDasharray="2 4" /><XAxis dataKey="d" tick={{ fill: "#7d8590", fontSize: 10 }} /><YAxis domain={["auto", "auto"]} tick={{ fill: "#7d8590", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#11151c", border: "1px solid #232a35", fontSize: 11 }} />
            <Line isAnimationActive={false} dataKey="tw_price_close" name="close" stroke="#ffb000" dot={false} connectNulls={false} /></LineChart></ResponsiveContainer>
          <ResponsiveContainer width="100%" height={240}><LineChart data={series.filter((r) => r.tw_drawdown_52w !== undefined)}>
            <CartesianGrid stroke="#232a35" strokeDasharray="2 4" /><XAxis dataKey="d" tick={{ fill: "#7d8590", fontSize: 10 }} /><YAxis unit="%" tick={{ fill: "#7d8590", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#11151c", border: "1px solid #232a35", fontSize: 11 }} formatter={(x: number) => `${x.toFixed(2)}%`} />
            <Line isAnimationActive={false} dataKey="tw_drawdown_52w" name="drawdown" stroke="#f85149" dot={false} /></LineChart></ResponsiveContainer>
        </div>
      </Panel>
      <Panel title="US BENCHMARK INDICES — FRED (NASDAQ, INC.; NO KEY; PRICE RETURN; DRAWDOWN DERIVED)">
        {idxObs.error ? <ApiError error={idxObs.error} /> : null}
        <Loading show={!idxObs.data && !idxObs.error} />
        <table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted text-left"><tr><th>index</th><th className="text-right">close</th><th className="text-right">vs 52w high</th><th>as of</th></tr></thead>
          <tbody>{IDX.map((e) => {
            const c = idxLast[`${e}|us_index_close`], dd = idxLast[`${e}|us_index_drawdown_52w`];
            return (
              <tr key={e} className="border-t border-term-border">
                <td className="text-white">{e} <span className="text-term-muted">{IDX_NAME[e]}</span></td>
                <td className="text-right">{c ? c.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : <StatusPill s="missing" />}</td>
                <td className={`text-right ${dd && dd.value <= -0.2 ? "text-term-down" : ""}`}>{dd ? pct(dd.value) : <StatusPill s="missing" />} {dd ? <ClassBadge c="derived" /> : null}</td>
                <td className="text-term-muted">{c?.period_end ?? "—"} {c?.source_url ? <a className="src" href={c.source_url} target="_blank" rel="noreferrer">FRED ↗</a> : null}</td>
              </tr>);
          })}</tbody>
        </table>
        <div className="grid gap-3 lg:grid-cols-2 mt-2">
          <ResponsiveContainer width="100%" height={220}><LineChart data={idxSeries}>
            <CartesianGrid stroke="#232a35" strokeDasharray="2 4" /><XAxis dataKey="d" tick={{ fill: "#7d8590", fontSize: 10 }} /><YAxis domain={["auto", "auto"]} tick={{ fill: "#7d8590", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#11151c", border: "1px solid #232a35", fontSize: 11 }} />
            {IDX.map((e) => <Line key={e} isAnimationActive={false} dataKey={`px_${e}`} name={e} stroke={IDX_COLOR[e]} dot={false} connectNulls={false} />)}</LineChart></ResponsiveContainer>
          <ResponsiveContainer width="100%" height={220}><LineChart data={idxSeries}>
            <CartesianGrid stroke="#232a35" strokeDasharray="2 4" /><XAxis dataKey="d" tick={{ fill: "#7d8590", fontSize: 10 }} /><YAxis unit="%" tick={{ fill: "#7d8590", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#11151c", border: "1px solid #232a35", fontSize: 11 }} formatter={(x: number) => `${x.toFixed(2)}%`} />
            {IDX.map((e) => <Line key={e} isAnimationActive={false} dataKey={`dd_${e}`} name={`${e} drawdown`} stroke={IDX_COLOR[e]} dot={false} connectNulls={false} />)}</LineChart></ResponsiveContainer>
        </div>
        <p className="text-[10px] text-term-muted mt-1">Source: Nasdaq, Inc. via FRED series NASDAQ100 / NASDAQCOM / NASDAQSOX (public CSV, no key; copyrighted, personal research use). Price-return levels; drawdown needs ≥358 days of history.</p>
      </Panel>
      <Panel title="US AI LEADERS + TSM ADR + ETF PROXIES">
        {usObs.error ? <ApiError error={usObs.error} /> : null}
        <table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted text-left"><tr><th>ticker</th><th className="text-right">close (USD)</th><th className="text-right">market cap</th><th className="text-right">vs 52w high</th><th className="text-right">1y rel. vs NDX</th><th className="text-right">1y rel. vs SOX</th><th className="text-right">SEC shares</th><th className="text-right">forward P/E</th><th>as of</th></tr></thead>
          <tbody>{[...US, ...ETF].map((e) => {
            const etf = ETF.includes(e), mcCovered = !etf && e !== "GOOGL" && e !== "META";
            const c = u(e, "us_price_close");
            return (
              <tr key={e} className="border-t border-term-border">
                <td className={etf ? "text-term-muted" : "text-white"}>{e}{etf ? " (ETF)" : ""}</td>
                <td className="text-right">{cell(e, "us_price_close", (o) => o.value.toFixed(2))}</td>
                <td className="text-right">{etf ? "—" : cell(e, "market_cap", (o) => `${(o.value / 1e12).toFixed(3)}T`, mcCovered)}</td>
                <td className="text-right">{cell(e, "us_drawdown_52w", (o) => pct(o.value) ?? "")}</td>
                <td className="text-right">{etf ? "—" : cell(e, "us_rel_return_1y_vs_ndx", (o) => pct(o.value) ?? "")}</td>
                <td className="text-right">{etf ? "—" : cell(e, "us_rel_return_1y_vs_sox", (o) => pct(o.value) ?? "")}</td>
                <td className="text-right">{etf ? "—" : cell(e, "us_shares_outstanding", (o) => `${(o.value / 1e9).toFixed(3)}B (${o.period_end})`, mcCovered)}</td>
                <td className="text-right">{etf ? "—" : <span title={why("forward_pe")}><StatusPill s={mdef("forward_pe")?.effective_status ?? "unavailable"} /></span>}</td>
                <td className="text-term-muted">{c?.period_end ?? "—"}</td>
              </tr>);
          })}</tbody>
        </table>
        <p className="text-[10px] text-term-muted mt-1">
          US daily prices need a free API key: TIINGO_API_KEY (recommended; official API, 10+ years) or ALPHAVANTAGE_API_KEY (~100 days only). Without a key they are UNAVAILABLE, never estimated. {mdef("us_price_close")?.unavailable_reason ? `Now: ${mdef("us_price_close")?.unavailable_reason}.` : ""}
          {" "}Market cap is DERIVED = raw close × latest SEC cover-page shares (dei:EntityCommonStockSharesOutstanding) dated on/before the price date, adjusted for later splits; TSM uses ordinary shares ÷ 5 per ADR; GOOGL / META UNAVAILABLE (multi-class, no single share count).
          {" "}Drawdown and relative returns use split-adjusted, price-return closes vs the FRED NASDAQ-100 / SOX indices. SOXX tracks the NYSE Semiconductor Index (not SOX). Forward P/E requires licensed consensus estimates — UNAVAILABLE.
        </p>
      </Panel>
    </div>
  );
}
