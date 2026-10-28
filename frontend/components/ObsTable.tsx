"use client";
import type { Observation } from "@/lib/api";
import { ClassBadge, ConfBadge } from "@/components/Badges";

export const fmtVal = (v: number, unit: string) => {
  if (unit === "USD") return `${v < 0 ? "-" : ""}$${(Math.abs(v) / 1e9).toLocaleString(undefined, { maximumFractionDigits: 3 })}B`;
  if (unit === "pct") return `${(v * 100).toFixed(1)}%`;
  if (unit === "TWD") return `NT$${(v / 1e9).toLocaleString(undefined, { maximumFractionDigits: 1 })}B`;
  return v.toLocaleString(undefined, { maximumFractionDigits: 3 }) + (unit ? ` ${unit}` : "");
};

/** One row per observation; always shows classification, publication date and the source link. */
export function ObsTable({ rows, showEntity = true, showMetric = false }: { rows: Observation[]; showEntity?: boolean; showMetric?: boolean }) {
  if (!rows.length) return <div className="text-xs font-mono text-term-down">NO DATA — not shown as zero.</div>;
  return (
    <table className="w-full text-[11px] font-mono">
      <thead className="text-term-muted"><tr>{showMetric ? <th className="text-left">metric</th> : null}{showEntity ? <th className="text-left">entity</th> : null}
        <th className="text-left">period</th><th className="text-right">value</th><th>class</th><th className="text-left">published</th><th className="text-left">source</th></tr></thead>
      <tbody>{rows.map((o) => (
        <tr key={o.id} className="border-t border-term-border" title={o.methodology ?? ""}>
          {showMetric ? <td>{o.metric_id}</td> : null}{showEntity ? <td>{o.entity_id}</td> : null}
          <td>{o.fiscal_period ?? o.period_end} <span className="text-term-muted">({o.period_end})</span></td>
          <td className={`text-right ${o.value < 0 ? "text-term-down" : ""}`}>{fmtVal(o.value, o.unit)}</td>
          <td className="text-center"><ClassBadge c={o.classification} /> <ConfBadge c={o.confidence} /></td>
          <td>{o.publication_date}</td>
          <td className="truncate max-w-[260px]">{o.source_url ? <a className="underline text-term-info" href={o.source_url} target="_blank" rel="noreferrer">{new URL(o.source_url).hostname}</a> : "—"}</td>
        </tr>))}</tbody>
    </table>
  );
}
