import type { Card } from "@/lib/api";
import { changeColor, fmtChange, fmtPct, fmtValue } from "@/lib/format";
import { dt, ent, fp, metricName, metricWarn } from "@/lib/i18n";
import { ClassBadge, ConfBadge, StatusPill } from "./Badges";

export default function MetricCard({ c }: { c: Card }) {
  const cur = c.current, prev = c.previous;
  const warn = metricWarn(c.metric_id, c.warning);
  if (!cur) {
    return (
      <div className="panel p-3 border-dashed opacity-90">
        <div className="flex justify-between items-start gap-2">
          <div className="label">{ent(c.entity_id)} · {metricName(c.metric_id, c.metric_name)}</div><StatusPill s={c.status} />
        </div>
        <div className="mt-2 text-lg font-semibold text-term-down">{c.status === "missing" ? "缺資料" : "無資料"}</div>
        <div className="mt-1 text-[11px] text-term-muted">{warn ?? "沒有已接入的資料來源。"} 缺資料 ≠ 零風險。</div>
      </div>
    );
  }
  return (
    <div className="panel p-3 animate-fade-up">
      <div className="flex justify-between items-start gap-2">
        <div className="label">{ent(c.entity_id)} · {metricName(c.metric_id, c.metric_name)}</div>
        <ClassBadge c={cur.classification} />
      </div>
      <div className="mt-1 flex items-baseline gap-2 flex-wrap">
        <span className="font-mono text-2xl font-semibold text-white">{fmtValue(cur.value, c.unit)}</span>
        <span className="text-[11px] text-term-muted font-mono">{cur.fiscal_period ? fp(cur.fiscal_period) : dt(cur.period_end)}</span>
      </div>
      <div className="mt-1 grid grid-cols-2 gap-x-2 text-[11px] font-mono">
        <span className="text-term-muted">前期 {prev ? `(${prev.fiscal_period ? fp(prev.fiscal_period) : dt(prev.period_end)})` : ""}</span>
        <span className="text-right">{prev ? fmtValue(prev.value, c.unit) : "—"}</span>
        <span className="text-term-muted">變動</span>
        <span className={`text-right ${changeColor(c.abs_change)}`}>
          {fmtChange(c.abs_change, c.unit)}{c.pct_change !== null ? `（${fmtPct(c.pct_change)}）` : ""}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] text-term-muted">
        <span>期末 {dt(cur.period_end)}</span><span>· 公布 {dt(cur.publication_date)}</span>
        <ConfBadge c={cur.confidence} />
        {cur.source_url ? <a className="src" href={cur.source_url} target="_blank" rel="noreferrer">資料來源 ↗</a> : <span>來源：{cur.source_type}</span>}
      </div>
      {warn ? <div className="mt-1 text-[10px] text-term-amber">⚠ {warn}</div> : null}
    </div>
  );
}
