"use client";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ClassBadge, ConfBadge, StatusPill } from "@/components/Badges";
import { ApiError, useApi } from "@/components/useApi";
import { API_BASE, apiGet, apiPost, type Observation } from "@/lib/api";
import { fmtValue } from "@/lib/format";

const COMPANIES = ["MSFT", "GOOGL", "AMZN", "META", "ORCL"];
const COLORS: Record<string, string> = { MSFT: "#58a6ff", GOOGL: "#3fb950", AMZN: "#ffb000", META: "#d2a8ff", ORCL: "#f85149",
  capex_yoy: "#ffb000", revenue_yoy: "#58a6ff", ocf_yoy: "#3fb950", fcf_yoy: "#d2a8ff" };
const GROWTH = ["capex_yoy", "revenue_yoy", "ocf_yoy", "fcf_yoy"];
const ABS = ["capex_total", "revenue", "operating_cash_flow", "fcf"];

type RunStatus = { refresh_in_progress: boolean };

export default function CapexPage() {
  const [company, setCompany] = useState("MSFT");
  const [compare, setCompare] = useState<string[]>(COMPANIES);
  const [start, setStart] = useState("2021-01-01");
  const [end, setEnd] = useState("");
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null);
  const range = `&start=${start}${end ? `&end=${end}` : ""}`;
  const single = useApi<Observation[]>(`/api/observations?metric_id=${[...GROWTH, ...ABS, "capex_to_ocf", "capex_to_revenue"].join(",")}&entity_id=${company}${range}`);
  const multi = useApi<Observation[]>(compare.length ? `/api/observations?metric_id=capex_total&entity_id=${compare.join(",")}${range}` : null);

  const growth = useMemo(() => pivot(single.data, GROWTH, (o) => o.value * 100), [single.data]);
  const abs = useMemo(() => pivot(single.data, ABS, (o) => o.value / 1e9), [single.data]);
  const cross = useMemo(() => {
    const m = new Map<string, Record<string, number | string>>();
    (multi.data ?? []).forEach((o) => {
      const k = o.period_end; const row = m.get(k) ?? { period: k };
      row[o.entity_id] = o.value / 1e9; m.set(k, row);
    });
    return [...m.values()].sort((a, b) => String(a.period).localeCompare(String(b.period)));
  }, [multi.data]);

  async function refresh() {
    try {
      await apiPost("/api/refresh?provider=sec_edgar");
      setRefreshMsg("refresh started…");
      const poll = setInterval(async () => {
        const s = await apiGet<RunStatus>("/api/health");
        if (!s.refresh_in_progress) {
          clearInterval(poll);
          const runs = await apiGet<{ provider: string; status: string; records_inserted: number; records_revised: number }[]>("/api/ingestion/runs?limit=2");
          setRefreshMsg(`done: ${runs.map((r) => `${r.provider}=${r.status} (+${r.records_inserted} new, ${r.records_revised} revised)`).join(", ")}`);
          single.reload(); multi.reload();
        }
      }, 1500);
    } catch (e) { setRefreshMsg(String(e)); }
  }

  const csvHref = `${API_BASE}/api/observations.csv?metric_id=${[...ABS, ...GROWTH, "capex_to_ocf", "capex_to_revenue"].join(",")}&entity_id=${company}${range}`;
  const table = (single.data ?? []).filter((o) => o.metric_id === "capex_total").slice().reverse();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <h1 className="font-mono text-term-amber text-lg">HYPERSCALER CAPEX</h1>
        <label className="label">company
          <select value={company} onChange={(e) => setCompany(e.target.value)} className="ml-2 bg-black border border-term-border text-white font-mono text-xs px-1 py-0.5">
            {COMPANIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="label">from <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="ml-1 bg-black border border-term-border text-white text-xs px-1" /></label>
        <label className="label">to <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="ml-1 bg-black border border-term-border text-white text-xs px-1" /></label>
        <a className="btn" href={csvHref}>⬇ CSV</a>
        <button className="btn" onClick={refresh}>⟳ REFRESH FROM SEC EDGAR</button>
        {refreshMsg ? <span className="text-[11px] font-mono text-term-muted">{refreshMsg}</span> : null}
      </div>
      <div className="panel p-2 text-[11px] text-term-amber font-mono">
        ⚠ Values are TOTAL COMPANY capex (cash purchases of PP&E, excl. finance leases) — not AI capex. Quarters marked DERIVED were computed from year-to-date cash-flow filings.
      </div>
      {single.error ? <ApiError error={single.error} /> : null}

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title={`${company} · YoY GROWTH (%) — CAPEX vs REVENUE vs OCF vs FCF`}>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={growth}>
              <CartesianGrid stroke="#232a35" strokeDasharray="2 4" />
              <XAxis dataKey="period" tick={{ fill: "#7d8590", fontSize: 10 }} />
              <YAxis tick={{ fill: "#7d8590", fontSize: 10 }} unit="%" />
              <Tooltip contentStyle={{ background: "#11151c", border: "1px solid #232a35", fontSize: 11 }} formatter={(v: number) => `${v.toFixed(1)}%`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <ReferenceLine y={0} stroke="#7d8590" />
              {GROWTH.map((k) => <Line isAnimationActive={false} key={k} dataKey={k} stroke={COLORS[k]} dot={false} strokeWidth={k === "capex_yoy" ? 2.5 : 1.5} connectNulls={false} />)}
            </LineChart>
          </ResponsiveContainer>
          <p className="text-[10px] text-term-muted">Gaps = no value (e.g. FCF YoY is not computed from a negative base). Never zero-filled.</p>
        </Panel>
        <Panel title={`${company} · QUARTERLY LEVELS ($B)`}>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={abs}>
              <CartesianGrid stroke="#232a35" strokeDasharray="2 4" />
              <XAxis dataKey="period" tick={{ fill: "#7d8590", fontSize: 10 }} />
              <YAxis tick={{ fill: "#7d8590", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#11151c", border: "1px solid #232a35", fontSize: 11 }} formatter={(v: number) => `$${v.toFixed(2)}B`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <ReferenceLine y={0} stroke="#7d8590" />
              <Line isAnimationActive={false} dataKey="capex_total" stroke="#ffb000" strokeWidth={2.5} dot={false} />
              <Line isAnimationActive={false} dataKey="revenue" stroke="#58a6ff" dot={false} />
              <Line isAnimationActive={false} dataKey="operating_cash_flow" stroke="#3fb950" dot={false} />
              <Line isAnimationActive={false} dataKey="fcf" stroke="#d2a8ff" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel title="CROSS-COMPANY QUARTERLY CAPEX ($B, by fiscal period end)">
        <div className="flex gap-2 mb-2">
          {COMPANIES.map((c) => (
            <label key={c} className="text-xs font-mono flex items-center gap-1">
              <input type="checkbox" checked={compare.includes(c)} onChange={() => setCompare((p) => p.includes(c) ? p.filter((x) => x !== c) : [...p, c])} />
              <span style={{ color: COLORS[c] }}>{c}</span>
            </label>
          ))}
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={cross}>
            <CartesianGrid stroke="#232a35" strokeDasharray="2 4" />
            <XAxis dataKey="period" tick={{ fill: "#7d8590", fontSize: 10 }} />
            <YAxis tick={{ fill: "#7d8590", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#11151c", border: "1px solid #232a35", fontSize: 11 }} formatter={(v: number) => `$${v.toFixed(2)}B`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {compare.map((c) => <Bar isAnimationActive={false} key={c} dataKey={c} fill={COLORS[c]} />)}
          </BarChart>
        </ResponsiveContainer>
        <p className="text-[10px] text-term-muted">ORCL fiscal quarters end Feb/May/Aug/Nov, so its bars sit on different dates.</p>
      </Panel>

      <Panel title={`${company} · CAPEX OBSERVATIONS WITH SOURCES`}>
        <div className="overflow-x-auto">{single.data === null && !single.error ? <div className="text-term-muted font-mono text-xs p-2">loading…</div> : null}
          <table className="w-full text-[11px] font-mono">
            <thead className="text-term-muted text-left">
              <tr><th>fiscal period</th><th>period</th><th className="text-right">capex</th><th>class</th><th>conf</th><th>filed (pub. date)</th><th>ver</th><th>concept</th><th>source</th></tr>
            </thead>
            <tbody>
              {table.map((o) => (
                <tr key={o.id} className="border-t border-term-border" title={o.methodology ?? ""}>
                  <td>{o.fiscal_period}</td><td>{o.period_start} → {o.period_end}</td>
                  <td className="text-right text-white">{fmtValue(o.value, o.unit)}</td>
                  <td><ClassBadge c={o.classification} /></td><td><ConfBadge c={o.confidence} /></td>
                  <td>{o.publication_date}</td><td>{o.version > 1 ? <StatusPill s={`rev v${o.version}`} /> : "v1"}</td>
                  <td className="text-term-muted">{o.source_ref?.replace("us-gaap:", "")}</td>
                  <td>{o.source_url ? <a className="src" href={o.source_url} target="_blank" rel="noreferrer">EDGAR ↗</a> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {single.data !== null && table.length === 0 ? <div className="text-term-down font-mono text-xs p-2">NO DATA for this selection.</div> : null}
        </div>
      </Panel>
    </div>
  );
}

function pivot(rows: Observation[] | null, metrics: string[], f: (o: Observation) => number) {
  const m = new Map<string, Record<string, number | string>>();
  (rows ?? []).filter((o) => metrics.includes(o.metric_id)).forEach((o) => {
    const k = o.period_end; const row = m.get(k) ?? { period: o.fiscal_period ?? k, _end: k };
    row[o.metric_id] = f(o); m.set(k, row);
  });
  return [...m.values()].sort((a, b) => String(a._end).localeCompare(String(b._end)));
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="panel p-3"><h2 className="font-mono text-xs text-term-amber mb-2">{title}</h2>{children}</section>;
}
