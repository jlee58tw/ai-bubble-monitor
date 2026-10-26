"use client";
import { ClassBadge, StatusPill } from "@/components/Badges";
import { Loading, Panel } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";

type Alert = { id: string; severity: string; category: string; title: string; detail: string; as_of: string | null; classification: string | null; source_url: string | null };

export default function Alerts() {
  const { data, error } = useApi<Alert[]>("/api/alerts");
  const cats = [...new Set((data ?? []).map((a) => a.category))];
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">ALERTS <span className="text-xs text-term-muted">in-app only · recomputed from stored real data on each load · thresholds in risk.yaml</span></h1>
      {error ? <ApiError error={error} /> : null}
      <Loading show={!data && !error} />
      {data && data.length === 0 ? <div className="text-term-muted text-xs font-mono">No alert conditions met.</div> : null}
      {cats.map((c) => (
        <Panel key={c} title={c.toUpperCase()}>
          <table className="w-full text-[11px] font-mono"><tbody>{(data ?? []).filter((a) => a.category === c).map((a) => (
            <tr key={a.id} className="border-t border-term-border align-top">
              <td className="w-20"><StatusPill s={a.severity} /></td>
              <td className="text-white">{a.title}<div className="text-term-muted">{a.detail}</div></td>
              <td className="w-24">{a.classification ? <ClassBadge c={a.classification} /> : null}</td>
              <td className="w-24 text-term-muted">{a.as_of ?? "—"}</td>
              <td className="w-16">{a.source_url ? <a className="src" href={a.source_url} target="_blank" rel="noreferrer">src ↗</a> : null}</td>
            </tr>))}</tbody></table>
        </Panel>))}
    </div>
  );
}
