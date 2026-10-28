"use client";
import { Hypothesis, Loading, Panel } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import { ObsTable, fmtVal } from "@/components/ObsTable";
import type { Observation } from "@/lib/api";

type G = { status: string; items: { id: number; entity_id: string; target_period: string; value_low: number | null; value_high: number | null;
  publication_date: string; source_url: string; quote: string }[] };
const q = (m: string) => `/api/observations?metric_id=${m}`;

export default function AiMonetization() {
  const lab = useApi<Observation[]>(q("ai_lab_revenue,ai_lab_compute_cost,ai_lab_operating_income"));
  const media = useApi<Observation[]>(q("ai_lab_revenue_media,ai_lab_operating_income_media,ai_lab_run_rate_media"));
  const hyper = useApi<Observation[]>(q("azure_growth_yoy,ai_revenue_disclosed"));
  const g = useApi<G>("/api/guidance");
  const by = (rows: Observation[] | null, m: string) => (rows ?? []).filter((o) => o.metric_id === m);
  const rev = by(lab.data, "ai_lab_revenue"), cc = by(lab.data, "ai_lab_compute_cost"), op = by(lab.data, "ai_lab_operating_income");
  const err = lab.error || media.error || hyper.error || g.error;
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">AI MONETIZATION</h1>
      <Hypothesis>Classes are kept apart and never mixed in one number: <b>DISCLOSED</b> = company-disclosed in a pre-IPO SEC filing (S-1, unaudited quarterly);
        <b> REPORTED</b> = SEC 8-K earnings release; <b>QUALITATIVE</b> = lower-bound statement (&quot;exceeded&quot;); <b>ESTIMATED</b> = media-reported, not company financials.</Hypothesis>
      {err ? <ApiError error={err} /> : null}<Loading show={lab.loading} />
      <Panel title="ANTHROPIC — QUARTERLY STATEMENTS OF OPERATIONS (S-1, company-disclosed, USD)">
        <table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted"><tr><th className="text-left">quarter</th><th className="text-right">revenue</th><th className="text-right">compute &amp; infra</th>
            <th className="text-right">compute / revenue</th><th className="text-right">operating income (loss)</th></tr></thead>
          <tbody>{rev.map((r) => { const c = cc.find((x) => x.period_end === r.period_end); const o = op.find((x) => x.period_end === r.period_end);
            return (<tr key={r.id} className="border-t border-term-border"><td>{r.fiscal_period}</td><td className="text-right">{fmtVal(r.value, r.unit)}</td>
              <td className="text-right">{c ? fmtVal(c.value, c.unit) : "—"}</td><td className="text-right">{c ? `${((c.value / r.value) * 100).toFixed(0)}%` : "—"}</td>
              <td className={`text-right ${o && o.value < 0 ? "text-term-down" : ""}`}>{o ? fmtVal(o.value, o.unit) : "—"}</td></tr>); })}</tbody>
        </table>
        {rev[0]?.source_url ? <div className="text-[10px] font-mono text-term-muted mt-1">Source: <a className="underline" href={rev[0].source_url} target="_blank" rel="noreferrer">Anthropic, PBC Form S-1</a>, filed {rev[0].publication_date}. Compute/revenue is DERIVED here for display (risk input ai_lab_compute_intensity).</div> : null}
      </Panel>
      <Panel title="OPENAI / ANTHROPIC — MEDIA-REPORTED FIGURES (ESTIMATED, not company financials; hover a row for the verbatim quote)">
        <ObsTable rows={media.data ?? []} showMetric />
        <div className="text-[10px] font-mono text-term-amber mt-1">Run-rate definitions differ between outlets and companies; do not compare run-rate with quarterly revenue. OpenAI has filed no financial statements (UNAVAILABLE as disclosed data).</div>
      </Panel>
      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="HYPERSCALER AI / CLOUD DISCLOSURES (8-K earnings releases)">
          <ObsTable rows={hyper.data ?? []} showMetric />
          <div className="text-[10px] font-mono text-term-muted mt-1">AMZN figure is a LOWER BOUND (&quot;exceeded&quot;). MSFT/GOOGL/META/ORCL do not state AI revenue in their releases — UNAVAILABLE.</div>
        </Panel>
        <Panel title="CAPEX GUIDANCE (verbatim, 8-K EX-99.1)">
          {g.data?.items.length ? <table className="w-full text-[11px] font-mono"><tbody>{g.data.items.map((i) => (
            <tr key={i.id} className="border-t border-term-border" title={i.quote}><td>{i.entity_id}</td><td>FY{i.target_period}</td>
              <td className="text-right">{i.value_low != null ? fmtVal(i.value_low, "USD") : "—"}–{i.value_high != null ? fmtVal(i.value_high, "USD") : "—"}</td>
              <td>{i.publication_date}</td><td><a className="underline text-term-info" href={i.source_url} target="_blank" rel="noreferrer">8-K</a></td></tr>))}</tbody></table>
            : <div className="text-xs font-mono text-term-down">NO GUIDANCE STORED</div>}
          <div className="text-[10px] font-mono text-term-muted mt-1">Only META states capex guidance in its written release; MSFT/GOOGL/AMZN/ORCL give it on calls only — UNAVAILABLE (no transcript source).</div>
        </Panel>
      </div>
    </div>
  );
}
