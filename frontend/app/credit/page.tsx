"use client";
import { Hypothesis, Loading, Panel } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import type { Observation } from "@/lib/api";

const SERIES = [
  { m: "us10y_yield", label: "US 10Y Treasury (DGS10)", fred: "DGS10" },
  { m: "us2y_yield", label: "US 2Y Treasury (DGS2)", fred: "DGS2" },
  { m: "us_10y2y_spread", label: "10Y − 2Y spread (T10Y2Y)", fred: "T10Y2Y" },
  { m: "baa_10y_spread", label: "Moody's Baa corporate − 10Y (BAA10Y)", fred: "BAA10Y" },
];

export default function Credit() {
  const start = new Date(Date.now() - 400 * 864e5).toISOString().slice(0, 10);
  const { data, error, loading } = useApi<Observation[]>(`/api/observations?metric_id=${SERIES.map((s) => s.m).join(",")}&start=${start}`);
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">CREDIT / FUNDING</h1>
      {error ? <ApiError error={error} /> : null}<Loading show={loading} />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{SERIES.map((s) => {
        const rows = (data ?? []).filter((o) => o.metric_id === s.m).sort((a, b) => a.period_end.localeCompare(b.period_end));
        const last = rows[rows.length - 1]; const yr = rows.filter((o) => o.period_end >= start);
        const lo = Math.min(...yr.map((o) => o.value)), hi = Math.max(...yr.map((o) => o.value));
        return (
          <Panel key={s.m} title={s.label}>
            {last ? <div className="font-mono"><div className="text-2xl text-white">{last.value.toFixed(2)}<span className="text-xs text-term-muted"> %</span></div>
              <div className="text-[10px] text-term-muted">as of {last.period_end} · ~13-month range {lo.toFixed(2)}–{hi.toFixed(2)}</div>
              <div className="text-[10px] mt-1"><a className="underline text-term-info" href={`https://fred.stlouisfed.org/series/${s.fred}`} target="_blank" rel="noreferrer">FRED {s.fred}</a> · reported</div></div>
              : <div className="text-xs font-mono text-term-down">NO DATA</div>}
          </Panel>);
      })}</div>
      <Hypothesis>A Baa spread below ~1.5 pp is historically tight (risk input credit_spreads = fully stretched). Tight spreads mean cheap funding for AI build-outs, not safety.</Hypothesis>
      <Panel title="UNAVAILABLE">
        <ul className="list-disc pl-5 text-xs font-mono text-term-down">
          <li>ICE BofA high-yield / IG OAS — licence requires ICE pre-approval for redistribution; not stored.</li>
          <li>Hyperscaler debt issuance &amp; finance-lease liabilities by deal — no free machine-readable source connected.</li>
          <li>Private credit / data-center ABS volumes — no free official source.</li>
        </ul>
        <div className="text-[10px] text-term-amber font-mono mt-2">Absence of data here must not be read as absence of risk.</div>
      </Panel>
    </div>
  );
}
