"use client";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ClassBadge, StatusPill } from "@/components/Badges";
import { Loading, Panel, SourceStatus } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import type { Observation } from "@/lib/api";

type Gpu = { rows: { id: number; sku: string; gpu_model: string; gpu_count: number; price_kind: string; region: string; usd_per_hour: number; usd_per_gpu_hour: number; effective_from: string | null; last_seen_at: string; source_url: string }[];
  placeholders: { id: string; name: string; status: string; limitation: string }[]; notes: string[]; sources: Record<string, { last_status: string; last_success_at: string | null; message: string | null }> };

export default function SupplyChain() {
  const dc = useApi<Observation[]>("/api/observations?metric_id=nvda_datacenter_revenue&entity_id=NVDA");
  const gpu = useApi<Gpu>("/api/gpu-prices");
  const data = (dc.data ?? []).map((o) => ({ q: o.fiscal_period, v: o.value / 1e9, c: o.classification }));
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">SEMIS / SUPPLY CHAIN · GPU</h1>
      {dc.error ? <ApiError error={dc.error} /> : null}
      <Panel title="NVIDIA DATA CENTER SEGMENT REVENUE (USD B) — SEC 10-Q/10-K XBRL, DIMENSIONAL FACT nvda:DataCenterMember">
        <Loading show={!dc.data && !dc.error} />
        <ResponsiveContainer width="100%" height={260}><BarChart data={data}>
          <CartesianGrid stroke="#232a35" strokeDasharray="2 4" /><XAxis dataKey="q" tick={{ fill: "#7d8590", fontSize: 10 }} /><YAxis tick={{ fill: "#7d8590", fontSize: 10 }} />
          <Tooltip contentStyle={{ background: "#11151c", border: "1px solid #232a35", fontSize: 11 }} formatter={(x: number) => `$${x.toFixed(3)}B`} />
          <Bar isAnimationActive={false} dataKey="v" fill="#58a6ff" /></BarChart></ResponsiveContainer>
        <table className="w-full text-[11px] font-mono mt-2"><thead className="text-term-muted text-left"><tr><th>fiscal period</th><th>period</th><th className="text-right">revenue</th><th>class</th><th>filed</th><th>source</th></tr></thead>
          <tbody>{(dc.data ?? []).slice().reverse().map((o) => (
            <tr key={o.id} className="border-t border-term-border"><td>{o.fiscal_period}</td><td>{o.period_start} → {o.period_end}</td>
              <td className="text-right text-white">${(o.value / 1e9).toFixed(3)}B</td><td><ClassBadge c={o.classification} /></td><td>{o.publication_date}</td>
              <td>{o.source_url ? <a className="src" href={o.source_url} target="_blank" rel="noreferrer">EDGAR ↗</a> : "—"}</td></tr>))}</tbody></table>
        <p className="text-[10px] text-term-muted">Q4 values are DERIVED as fiscal-year (10-K) minus Q1–Q3; other quarters are reported 3-month facts.</p>
      </Panel>
      <Panel title="GPU CLOUD PRICES — AZURE RETAIL PRICES API (LIST PRICE, LINUX, EASTUS)">
        {gpu.error ? <ApiError error={gpu.error} /> : null}
        <SourceStatus sources={gpu.data?.sources} />
        <table className="w-full text-[11px] font-mono mt-2"><thead className="text-term-muted text-left"><tr><th>GPU</th><th>VM SKU</th><th>kind</th><th className="text-right">$/hour (VM)</th><th className="text-right">$/GPU-hour</th><th>price effective since</th><th>source</th></tr></thead>
          <tbody>{(gpu.data?.rows ?? []).map((r) => (
            <tr key={r.id} className="border-t border-term-border"><td className="text-white">{r.gpu_count}× {r.gpu_model}</td><td>{r.sku}</td><td>{r.price_kind}</td>
              <td className="text-right">{r.usd_per_hour.toFixed(3)}</td><td className="text-right text-white">{r.usd_per_gpu_hour.toFixed(3)}</td><td>{r.effective_from ?? "—"}</td>
              <td><a className="src" href={r.source_url} target="_blank" rel="noreferrer">Azure ↗</a></td></tr>))}</tbody></table>
        {(gpu.data?.notes ?? []).map((n) => <p key={n} className="text-[10px] text-term-muted">{n}</p>)}
        {(gpu.data?.placeholders ?? []).map((p) => (
          <div key={p.id} className="mt-2 border border-dashed border-term-border p-2 text-[11px] font-mono"><StatusPill s={p.status} /> {p.name}<div className="text-term-muted mt-1">{p.limitation}</div></div>))}
      </Panel>
      <div className="panel p-3 border-dashed text-[11px] font-mono"><StatusPill s="unavailable" /> TSMC monthly revenue — not connected in Phase 2. Absence of data is not absence of risk.</div>
    </div>
  );
}
