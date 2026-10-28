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
          <p className="text-xs">See <a className="src" href="/roi">/roi</a> (computed by <code>/api/roi</code>). Spec definitions: Effective Task Cost = AI Inference Cost + Tool Cost + Human Review Cost + Expected Rework Cost + Expected Failure Loss; Effective ROI = (Baseline Human Cost − Effective Task Cost) / Baseline Human Cost.</p>
          <p className="text-xs text-term-amber mt-1">Modeling assumptions (expected terms only): Expected Rework Cost = (1 − p) × rework share × rework cost; Expected Failure Loss = (1 − p) × (1 − rework share) × failure recovery cost; Human Review Cost = review minutes / 60 × hourly rate. Inputs are user scenario values.</p>
        </Panel>
        <Panel title="HISTORICAL BACKTEST (point-in-time) — see /backtest">
          <ul className="text-xs list-disc ml-4 space-y-1">
            <li>No look-ahead: at each past date d, indicators reading the observations table are recomputed from rows with publication_date ≤ d, using the version current on d (later revisions and restatements are invisible until published). Derived rows carry the latest publication date of their inputs.</li>
            <li>Dataset-based indicators (model prices, GPU list prices, METR/benchmarks) have no stored history before first collection: marked not_point_in_time and excluded. Missing indicators widen the 0–100 range and are never scored as zero risk.</li>
            <li>Past coverage is below min_coverage, so the official risk score is withheld at every past date. The backtest reports a clearly labelled partial-coverage composite plus individual indicator signals.</li>
            <li>Signal ON = composite ≥ 60 or indicator score ≥ 70 (same research thresholds as the live engine, not fitted). Unknown days are excluded, never treated as OFF.</li>
            <li>Outcome: forward minimum close over H = 20 trading days ≤ −10% (TWSE 2330/2382/2317 and an equal-weight basket; ~13 months). Reported: hit rate when ON/OFF vs base rate, an approximate Wilson 95% interval with effective n = n/H for overlapping windows, and lead time from the start of the ON run to each ≥10% correction from the running peak (left-censored runs shown as “≥”).</li>
            <li>Status labels: insufficient_data (too few days or signal never ON), no_variation (always ON — no timing information), small_sample (computed but only ~12 independent windows). Nothing here demonstrates predictive validity. US price outcomes are unavailable without an Alpha Vantage key.</li>
          </ul>
        </Panel>
        <Panel title="FILING EVENTS, GUIDANCE, WATCHLIST">
          <p className="text-xs">Events come from SEC EDGAR submissions metadata (10-Q/10-K/20-F and 8-K Item 2.02): observation date = report period / event date, publication date = filing date. Only the EDGAR “recent” block is loaded, so each company’s earliest stored date is shown. Guidance stays a placeholder until a source with URL + verbatim quote is connected; nothing is inferred. The watchlist is stored in the database and only displays stored observations.</p>
        </Panel>
      </>) : null}
    </div>
  );
}
