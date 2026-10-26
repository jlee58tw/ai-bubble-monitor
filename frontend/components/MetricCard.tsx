import type { Card } from "@/lib/api";
import { changeColor, fmtChange, fmtPct, fmtValue } from "@/lib/format";
import { ClassBadge, ConfBadge, StatusPill } from "./Badges";

export default function MetricCard({ c }: { c: Card }) {
  const cur = c.current, prev = c.previous;
  if (!cur) {
    return (
      <div className="panel p-3 border-dashed opacity-90">
        <div className="flex justify-between items-start">
          <div className="label">{c.entity_id} · {c.metric_name}</div><StatusPill s={c.status} />
        </div>
        <div className="mt-2 font-mono text-lg text-term-down">{c.status === "missing" ? "NO DATA" : "UNAVAILABLE"}</div>
        <div className="mt-1 text-[11px] text-term-muted">{c.warning ?? "No connected source."} Missing ≠ zero risk.</div>
      </div>
    );
  }
  return (
    <div className="panel p-3">
      <div className="flex justify-between items-start gap-2">
        <div className="label">{c.entity_id} · {c.metric_name}</div>
        <ClassBadge c={cur.classification} />
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="font-mono text-2xl text-white">{fmtValue(cur.value, c.unit)}</span>
        <span className="text-[11px] text-term-muted font-mono">{cur.fiscal_period ?? cur.period_end}</span>
      </div>
      <div className="mt-1 grid grid-cols-2 gap-x-2 text-[11px] font-mono">
        <span className="text-term-muted">prev {prev ? `(${prev.fiscal_period ?? prev.period_end})` : ""}</span>
        <span className="text-right">{prev ? fmtValue(prev.value, c.unit) : "—"}</span>
        <span className="text-term-muted">chg</span>
        <span className={`text-right ${changeColor(c.abs_change)}`}>
          {fmtChange(c.abs_change, c.unit)}{c.pct_change !== null ? ` (${fmtPct(c.pct_change)})` : ""}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] font-mono text-term-muted">
        <span>period end {cur.period_end}</span><span>· filed {cur.publication_date}</span>
        <ConfBadge c={cur.confidence} />
        {cur.source_url ? <a className="src" href={cur.source_url} target="_blank" rel="noreferrer">source ↗</a> : <span>src: {cur.source_type}</span>}
      </div>
      {c.warning ? <div className="mt-1 text-[10px] text-term-amber">⚠ {c.warning}</div> : null}
    </div>
  );
}
