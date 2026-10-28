"use client";
import type { Observation } from "@/lib/api";
import { ClassBadge, ConfBadge } from "@/components/Badges";
import { dt, ent, fmtObs, fp, metricName } from "@/lib/i18n";

export const fmtVal = (v: number, unit: string) => fmtObs(v, unit);

/** 每列一筆觀測值；一律顯示分類、公布日與資料來源連結。 */
export function ObsTable({ rows, showEntity = true, showMetric = false }: { rows: Observation[]; showEntity?: boolean; showMetric?: boolean }) {
  if (!rows.length) return <div className="text-xs text-term-down">無資料——不會以 0 顯示。</div>;
  return (
    <div className="overflow-x-auto">
    <table className="w-full text-[11px] font-mono">
      <thead className="text-term-muted"><tr>{showMetric ? <th className="text-left">指標</th> : null}{showEntity ? <th className="text-left">公司／對象</th> : null}
        <th className="text-left">期間</th><th className="text-right">數值</th><th>分類</th><th className="text-left">公布日</th><th className="text-left">來源</th></tr></thead>
      <tbody>{rows.map((o) => (
        <tr key={o.id} className="border-t border-term-border" title={o.methodology ?? ""}>
          {showMetric ? <td>{metricName(o.metric_id)}</td> : null}{showEntity ? <td>{ent(o.entity_id)}</td> : null}
          <td>{o.fiscal_period ? fp(o.fiscal_period) : dt(o.period_end)} <span className="text-term-muted">({dt(o.period_end)})</span></td>
          <td className={`text-right ${o.value < 0 ? "text-term-down" : ""}`}>{fmtVal(o.value, o.unit)}</td>
          <td className="text-center whitespace-nowrap"><ClassBadge c={o.classification} /> <ConfBadge c={o.confidence} /></td>
          <td>{dt(o.publication_date)}</td>
          <td className="truncate max-w-[260px]">{o.source_url ? <a className="underline text-term-info" href={o.source_url} target="_blank" rel="noreferrer">{new URL(o.source_url).hostname}</a> : "—"}</td>
        </tr>))}</tbody>
    </table>
    </div>
  );
}
