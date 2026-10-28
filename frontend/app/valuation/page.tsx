"use client";
import { ANIM, GRID, TICK, TT } from "@/lib/chart";
import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ClassBadge, StatusPill } from "@/components/Badges";
import { Hypothesis, Loading, PageIntro, Panel } from "@/components/Panel";
import { dt, ent, tx } from "@/lib/i18n";
import { ApiError, useApi } from "@/components/useApi";
import type { Observation } from "@/lib/api";

const TW = ["2330", "2382", "2317"];
const US = ["NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META", "ORCL", "TSM"];
const ETF = ["QQQ", "SOXX", "SMH"];
const IDX = ["NDX", "COMP", "SOX"];
const IDX_NAME: Record<string, string> = { NDX: "那斯達克 100 指數", COMP: "那斯達克綜合指數", SOX: "費城半導體指數" };
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
  const why = (id: string) => tx(mdef(id)?.unavailable_reason ?? mdef(id)?.warning ?? "");
  const cell = (e: string, id: string, fmt: (o: Observation) => string, covered = true) => {
    const o = u(e, id);
    if (o) return <span title={o.methodology ?? ""}>{fmt(o)}</span>;
    const st = covered ? (mdef(id)?.effective_status === "connected" ? "missing" : mdef(id)?.effective_status ?? "unavailable") : "unavailable";
    return <span title={covered ? why(id) : "不涵蓋：多類股發行公司，SEC 沒有單一股數"}><StatusPill s={st} /></span>;
  };

  return (
    <div className="space-y-4">
      <PageIntro emoji="📈" title="估值與市場壓力"
        what={<>台灣 AI 供應鏈（台積電、廣達、鴻海）的本益比 (P/E)、股價淨值比 (P/B)、市值，以及美股 AI 龍頭與那斯達克／費半指數距 52 週高點的回檔幅度。</>}
        how={<><b>本益比</b>越高＝市場願意為每 1 元獲利付越多錢；<b>距 52 週高點</b>為 −20% 以下（紅字）通常被視為進入修正／空頭區。圖表可切換個股，線段中斷代表當天無資料，不補值。</>} />
      {latest.error ? <ApiError error={latest.error} /> : null}
      <Panel title="台灣 AI 供應鏈：證交所開放資料（交易所公布；市值與回檔為推導）" info="本益比、股價淨值比、殖利率由證交所計算公布；市值＝收盤價 × 上市普通股數。">
        <Loading show={!latest.data && !latest.error} />
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted text-left whitespace-nowrap"><tr><th>代號</th><th className="text-right">收盤價（新台幣）</th><th className="text-right">本益比 (P/E)</th><th className="text-right">股價淨值比 (P/B)</th><th className="text-right">殖利率</th><th className="text-right">股數</th><th className="text-right">市值</th><th className="text-right">距 52 週高點</th><th>資料日期</th></tr></thead>
          <tbody>{TW.map((e) => {
            const c = v(e, "tw_price_close"), mc = v(e, "tw_market_cap"), dd = v(e, "tw_drawdown_52w");
            return (
              <tr key={e} className="border-t border-term-border">
                <td className="text-white whitespace-nowrap">{e} <span className="text-term-muted">{ent(e)}</span></td>
                <td className="text-right">{c ? c.value.toLocaleString() : <StatusPill s="missing" />}</td>
                <td className="text-right">{v(e, "tw_pe_trailing")?.value.toFixed(2) ?? "—"}</td>
                <td className="text-right">{v(e, "tw_pb_ratio")?.value.toFixed(2) ?? "—"}</td>
                <td className="text-right">{v(e, "tw_dividend_yield") ? `${(v(e, "tw_dividend_yield").value * 100).toFixed(2)}%` : "—"}</td>
                <td className="text-right">{v(e, "tw_shares_outstanding")?.value.toLocaleString() ?? "—"}</td>
                <td className="text-right">{mc ? `${(mc.value / 1e12).toFixed(2)} 兆元` : "—"} {mc ? <ClassBadge c="derived" /> : null}</td>
                <td className={`text-right ${dd && dd.value <= -0.2 ? "text-term-down" : ""}`}>{dd ? `${(dd.value * 100).toFixed(1)}%` : <StatusPill s="missing" />}</td>
                <td className="text-term-muted whitespace-nowrap">{dt(c?.period_end)} {c?.source_url ? <a className="src" href={c.source_url} target="_blank" rel="noreferrer">證交所 ↗</a> : null}</td>
              </tr>);
          })}</tbody>
        </table></div>
        <p className="text-[10px] text-term-muted mt-1">本益比、股價淨值比、殖利率：證交所 BWIBBU（交易所計算，近四季）。市值＝收盤價 × 上市普通股數（證交所公司基本資料，取 45 天內最接近日期）。回檔需至少 358 天收盤價。</p>
      </Panel>
      <Panel title={`${code} ${ent(code)} · 收盤價與距 52 週高點回檔`} info="回檔＝今日收盤價 ÷ 過去 52 週最高收盤價 − 1。">
        <div className="mb-2 flex gap-1">{TW.map((c) => <button key={c} className={`btn ${c === code ? "text-term-amber border-term-amber" : ""}`} onClick={() => setCode(c)}>{c} {ent(c)}</button>)}</div>
        <div className="grid gap-3 lg:grid-cols-2">
          <ResponsiveContainer width="100%" height={240}><LineChart data={series}>
            <CartesianGrid stroke={GRID} strokeDasharray="2 4" /><XAxis dataKey="d" tick={TICK} /><YAxis domain={["auto", "auto"]} tick={TICK} />
            <Tooltip {...TT} />
            <Line {...ANIM} dataKey="tw_price_close" name="收盤價" stroke="#ffb000" dot={false} connectNulls={false} /></LineChart></ResponsiveContainer>
          <ResponsiveContainer width="100%" height={240}><LineChart data={series.filter((r) => r.tw_drawdown_52w !== undefined)}>
            <CartesianGrid stroke={GRID} strokeDasharray="2 4" /><XAxis dataKey="d" tick={TICK} /><YAxis unit="%" tick={TICK} />
            <Tooltip {...TT} formatter={(x: number) => `${x.toFixed(2)}%`} />
            <Line {...ANIM} dataKey="tw_drawdown_52w" name="距 52 週高點" stroke="#f85149" dot={false} /></LineChart></ResponsiveContainer>
        </div>
      </Panel>
      <Panel title="美國基準指數：FRED（Nasdaq, Inc.；免金鑰；價格報酬；回檔為推導）">
        {idxObs.error ? <ApiError error={idxObs.error} /> : null}
        <Loading show={!idxObs.data && !idxObs.error} />
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted text-left whitespace-nowrap"><tr><th>指數</th><th className="text-right">收盤</th><th className="text-right">距 52 週高點</th><th>資料日期</th></tr></thead>
          <tbody>{IDX.map((e) => {
            const c = idxLast[`${e}|us_index_close`], dd = idxLast[`${e}|us_index_drawdown_52w`];
            return (
              <tr key={e} className="border-t border-term-border">
                <td className="text-white">{e} <span className="text-term-muted">{IDX_NAME[e]}</span></td>
                <td className="text-right">{c ? c.value.toLocaleString("zh-TW", { maximumFractionDigits: 2 }) : <StatusPill s="missing" />}</td>
                <td className={`text-right ${dd && dd.value <= -0.2 ? "text-term-down" : ""}`}>{dd ? pct(dd.value) : <StatusPill s="missing" />} {dd ? <ClassBadge c="derived" /> : null}</td>
                <td className="text-term-muted whitespace-nowrap">{dt(c?.period_end)} {c?.source_url ? <a className="src" href={c.source_url} target="_blank" rel="noreferrer">FRED ↗</a> : null}</td>
              </tr>);
          })}</tbody>
        </table></div>
        <div className="grid gap-3 lg:grid-cols-2 mt-2">
          <ResponsiveContainer width="100%" height={220}><LineChart data={idxSeries}>
            <CartesianGrid stroke={GRID} strokeDasharray="2 4" /><XAxis dataKey="d" tick={TICK} /><YAxis domain={["auto", "auto"]} tick={TICK} />
            <Tooltip {...TT} />
            {IDX.map((e) => <Line key={e} {...ANIM} dataKey={`px_${e}`} name={IDX_NAME[e]} stroke={IDX_COLOR[e]} dot={false} connectNulls={false} />)}</LineChart></ResponsiveContainer>
          <ResponsiveContainer width="100%" height={220}><LineChart data={idxSeries}>
            <CartesianGrid stroke={GRID} strokeDasharray="2 4" /><XAxis dataKey="d" tick={TICK} /><YAxis unit="%" tick={TICK} />
            <Tooltip {...TT} formatter={(x: number) => `${x.toFixed(2)}%`} />
            {IDX.map((e) => <Line key={e} {...ANIM} dataKey={`dd_${e}`} name={`${IDX_NAME[e]} 回檔`} stroke={IDX_COLOR[e]} dot={false} connectNulls={false} />)}</LineChart></ResponsiveContainer>
        </div>
        <p className="text-[10px] text-term-muted mt-1">來源：Nasdaq, Inc.，經 FRED 序列 NASDAQ100／NASDAQCOM／NASDAQSOX（公開 CSV、免金鑰；有著作權，僅供個人研究）。價格報酬指數；回檔需至少 358 天歷史。</p>
      </Panel>
      <Panel title="美股 AI 龍頭＋台積電 ADR＋ETF 代理指標" info="市值＝收盤價 × SEC 封面頁最新股數（推導）。遠期本益比需要付費的分析師共識預估，因此無資料。">
        {usObs.error ? <ApiError error={usObs.error} /> : null}
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted text-left whitespace-nowrap"><tr><th>代號</th><th className="text-right">收盤價（美元）</th><th className="text-right">市值</th><th className="text-right">距 52 週高點</th><th className="text-right">1 年相對那指 100</th><th className="text-right">1 年相對費半</th><th className="text-right">SEC 股數</th><th className="text-right">遠期本益比</th><th>資料日期</th></tr></thead>
          <tbody>{[...US, ...ETF].map((e) => {
            const etf = ETF.includes(e), mcCovered = !etf && e !== "GOOGL" && e !== "META";
            const c = u(e, "us_price_close");
            return (
              <tr key={e} className="border-t border-term-border">
                <td className={etf ? "text-term-muted" : "text-white"}>{e}{etf ? "（ETF）" : ""} <span className="text-term-muted">{etf ? "" : ent(e)}</span></td>
                <td className="text-right">{cell(e, "us_price_close", (o) => o.value.toFixed(2))}</td>
                <td className="text-right">{etf ? "—" : cell(e, "market_cap", (o) => `${(o.value / 1e12).toFixed(2)} 兆美元`, mcCovered)}</td>
                <td className="text-right">{cell(e, "us_drawdown_52w", (o) => pct(o.value) ?? "")}</td>
                <td className="text-right">{etf ? "—" : cell(e, "us_rel_return_1y_vs_ndx", (o) => pct(o.value) ?? "")}</td>
                <td className="text-right">{etf ? "—" : cell(e, "us_rel_return_1y_vs_sox", (o) => pct(o.value) ?? "")}</td>
                <td className="text-right">{etf ? "—" : cell(e, "us_shares_outstanding", (o) => `${(o.value / 1e8).toFixed(1)} 億股（${dt(o.period_end)}）`, mcCovered)}</td>
                <td className="text-right">{etf ? "—" : <span title={why("forward_pe")}><StatusPill s={mdef("forward_pe")?.effective_status ?? "unavailable"} /></span>}</td>
                <td className="text-term-muted">{dt(c?.period_end)}</td>
              </tr>);
          })}</tbody>
        </table></div>
        <p className="text-[10px] text-term-muted mt-1">
          美股每日股價需要免費 API 金鑰：TIINGO_API_KEY（建議；官方 API，10 年以上歷史）或 ALPHAVANTAGE_API_KEY（僅約 100 天）。沒有金鑰時一律顯示「無資料」，絕不估計。{mdef("us_price_close")?.unavailable_reason ? `目前：${tx(mdef("us_price_close")?.unavailable_reason)}。` : ""}
          {" "}市值為<b>推導</b>＝原始收盤價 × 價格日當天或之前最新的 SEC 封面頁股數（dei:EntityCommonStockSharesOutstanding），並調整之後的分割；台積電 ADR 以普通股 ÷ 5 計；GOOGL／META 為多類股，無單一股數，因此無資料。
          {" "}回檔與相對報酬使用分割調整後的價格報酬收盤價，對比 FRED 那斯達克 100／費城半導體指數。SOXX 追蹤的是 NYSE 半導體指數（不是費半）。遠期本益比需授權的共識預估——無資料。
        </p>
      </Panel>
      <Hypothesis>估值高低本身不等於泡沫，也不代表會下跌；這裡只陳列公開數字，不是投資建議。</Hypothesis>
    </div>
  );
}
