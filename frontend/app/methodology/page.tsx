"use client";
import { Hypothesis, Loading, Panel } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";

type Cfg = { version: number; min_coverage: number; dimensions: { id: string; name: string; weight: number }[];
  indicators: { id: string; dimension: string; name: string; calc: string; args?: Record<string, unknown>; max_age_days?: number; thresholds?: { benign: number; stretched: number }; rationale: string; status?: string; reason?: string }[];
  alerts: Record<string, unknown> };
type Resp = { config_hash: string; config: Cfg; rules: string[] };

export default function Methodology() {
  const { data, error } = useApi<Resp>("/api/methodology");
  const c = data?.config;
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">METHODOLOGY</h1>
      <Hypothesis>Every threshold below is a RESEARCH HYPOTHESIS chosen by the builder, not a validated predictor of a bubble or a crash. Weights and thresholds live in backend/app/registry/risk.yaml; changing them changes the config hash, and snapshots with different hashes are not compared.</Hypothesis>
      {error ? <ApiError error={error} /> : null}
      <Loading show={!data && !error} />
      {data ? (<>
        <Panel title={`SCORING RULES · config ${data.config_hash} · v${c?.version}`}>
          <ul className="list-disc pl-5 text-xs space-y-1">{data.rules.map((r) => <li key={r}>{r}</li>)}</ul>
        </Panel>
        <Panel title="DATA CLASSIFICATION">
          <ul className="list-disc pl-5 text-xs space-y-1">
            <li><b>reported</b> — value as filed/published by the issuer, exchange or official body (SEC XBRL, TWSE, FRED, vendor price pages).</li>
            <li><b>derived</b> — computed by this app from reported values (YoY, ratios, market cap = price × shares, drawdown, Q4 = FY − Q1..Q3). Formula is stored with each observation.</li>
            <li><b>estimated</b> — forecasts/consensus. None are ingested (consensus estimates are licensed).</li>
            <li><b>unavailable / placeholder</b> — no terms-compliant source. Shown explicitly, never imputed, never counted as 0 risk.</li>
          </ul>
        </Panel>
        {c?.dimensions.map((d) => (
          <Panel key={d.id} title={`${d.name.toUpperCase()} · weight ${d.weight}%`}>
            <table className="w-full text-[11px] font-mono">
              <thead className="text-term-muted text-left"><tr><th>indicator</th><th>calc</th><th className="text-right">benign (0)</th><th className="text-right">stretched (100)</th><th className="text-right">max age (d)</th><th>hypothesis / rationale</th></tr></thead>
              <tbody>{c.indicators.filter((i) => i.dimension === d.id).map((i) => (
                <tr key={i.id} className="border-t border-term-border align-top">
                  <td className="text-white">{i.name}<div className="text-term-muted text-[10px]">{i.id}</div></td>
                  <td className="text-term-muted">{i.calc}</td>
                  <td className="text-right">{i.thresholds?.benign ?? "—"}</td><td className="text-right">{i.thresholds?.stretched ?? "—"}</td>
                  <td className="text-right">{i.max_age_days ?? "—"}</td>
                  <td className="max-w-[520px]">{i.rationale}</td>
                </tr>))}</tbody>
            </table>
          </Panel>))}
        <Panel title="ALERT RULES (in-app only, computed from stored real data on each request)">
          <table className="text-[11px] font-mono">{Object.entries(c?.alerts ?? {}).map(([k, v]) => <tr key={k}><td className="pr-4 text-term-muted">{k}</td><td>{JSON.stringify(v)}</td></tr>)}</table>
        </Panel>
        <Panel title="RELIABILITY ROI SIMULATOR FORMULAS">
          <p className="text-xs">See <a className="src" href="/roi">/roi</a>. Effective Task Cost = inference cost + review hours × reviewer rate + (1 − p) × failure recovery cost. Effective ROI = (baseline manual cost − ETC) / ETC. Scenario only; inputs are user assumptions.</p>
        </Panel>
      </>) : null}
    </div>
  );
}
