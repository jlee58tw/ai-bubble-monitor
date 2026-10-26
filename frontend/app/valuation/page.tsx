"use client";
import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ClassBadge, StatusPill } from "@/components/Badges";
import { Loading, Panel } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import type { Observation } from "@/lib/api";

const TW = ["2330", "2382", "2317"];
const US = ["NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META", "ORCL", "TSM"];
const TWM = ["tw_price_close", "tw_pe_trailing", "tw_pb_ratio", "tw_dividend_yield", "tw_market_cap", "tw_drawdown_52w", "tw_shares_outstanding"];
type MetricRow = { id: string; name: string; effective_status: string; unavailable_reason: string | null; warning: string | null; entities: string[] };

export default function Valuation() {
  const [code, setCode] = useState("2330");
  const latest = useApi<Observation[]>(`/api/observations?metric_id=${TWM.join(",")}&entity_id=${TW.join(",")}&start=2026-01-01`);
  const hist = useApi<Observation[]>(`/api/observations?metric_id=tw_price_close,tw_drawdown_52w&entity_id=${code}`);
  const metrics = useApi<MetricRow[]>("/api/metrics");
  const usObs = useApi<Observation[]>(`/api/observations?metric_id=us_price_close,us_drawdown_52w&entity_id=${US.join(",")}&start=2026-01-01`);

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
  const usHas = (e: string) => (usObs.data ?? []).some((o) => o.entity_id === e);

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
      <Panel title="US AI LEADERS + TSM ADR">
        <table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted text-left"><tr><th>ticker</th><th>daily close / drawdown</th><th>market cap</th><th>forward P/E</th></tr></thead>
          <tbody>{US.map((e) => (
            <tr key={e} className="border-t border-term-border">
              <td className="text-white">{e}</td>
              <td>{usHas(e) ? <StatusPill s="connected" /> : <span title={mdef("us_price_close")?.unavailable_reason ?? mdef("us_price_close")?.warning ?? ""}><StatusPill s={mdef("us_price_close")?.effective_status ?? "unavailable"} /></span>}</td>
              <td><span title={mdef("market_cap")?.unavailable_reason ?? mdef("market_cap")?.warning ?? ""}><StatusPill s={mdef("market_cap")?.effective_status ?? "unavailable"} /></span></td>
              <td><span title={mdef("forward_pe")?.unavailable_reason ?? mdef("forward_pe")?.warning ?? ""}><StatusPill s={mdef("forward_pe")?.effective_status ?? "unavailable"} /></span></td>
            </tr>))}</tbody>
        </table>
        <p className="text-[10px] text-term-muted mt-1">US prices use the official Alpha Vantage API and need a free key (ALPHAVANTAGE_API_KEY); without it they are UNAVAILABLE, never estimated. {mdef("us_price_close")?.unavailable_reason ?? ""} Forward P/E requires licensed consensus estimates — UNAVAILABLE.</p>
      </Panel>
    </div>
  );
}
