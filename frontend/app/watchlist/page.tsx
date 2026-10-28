"use client";
import { useState } from "react";
import { Loading, Panel, tsTaipei } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import { apiSend, MetricDef, Observation } from "@/lib/api";
import { STATIC } from "@/lib/static";

type W = { id: number; entity_id: string | null; entity_name: string | null; metric_id: string | null; metric_name: string | null;
  metric_status: string | null; status_reason: string | null; note: string | null; created_at: string; status: string; latest: Observation[];
  latest_filing: { form: string; publication_date: string; observation_date: string | null; source_url: string } | null };
type E = { id: string; name: string };
const SC: Record<string, string> = { ok: "text-term-up", missing: "text-term-down", unavailable: "text-term-down", placeholder: "text-term-amber" };

export default function Watchlist() {
  const { data, error, loading, reload } = useApi<W[]>("/api/watchlist");
  const ents = useApi<E[]>("/api/entities"); const mets = useApi<MetricDef[]>("/api/metrics");
  const [f, setF] = useState({ entity_id: "", metric_id: "", note: "" }); const [msg, setMsg] = useState<string | null>(null);
  const add = () => apiSend("/api/watchlist", "POST", { entity_id: f.entity_id || null, metric_id: f.metric_id || null, note: f.note || null })
    .then(() => { setMsg("added"); setF({ entity_id: "", metric_id: "", note: "" }); reload(); }).catch((e) => setMsg(String(e)));
  const del = (id: number) => apiSend(`/api/watchlist/${id}`, "DELETE").then(() => reload()).catch((e) => setMsg(String(e)));
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">WATCHLIST</h1>
      <p className="text-[10px] text-term-muted font-mono">Stored in the database (table watchlist_items). Shows the latest current (non-superseded) observation per series; missing or unavailable data is shown as such, never as zero.</p>
      {error ? <ApiError error={error} /> : null}<Loading show={loading} />
      <Panel title="ADD">
        <div className="flex flex-wrap gap-2 text-xs font-mono items-center">
          <select value={f.entity_id} onChange={(e) => setF({ ...f, entity_id: e.target.value })} className="bg-black border border-term-border px-1">
            <option value="">(any entity)</option>{ents.data?.map((e) => <option key={e.id} value={e.id}>{e.id} — {e.name}</option>)}</select>
          <select value={f.metric_id} onChange={(e) => setF({ ...f, metric_id: e.target.value })} className="bg-black border border-term-border px-1 max-w-md">
            <option value="">(any metric)</option>{mets.data?.map((m) => <option key={m.id} value={m.id}>{m.id} [{m.status}]</option>)}</select>
          <input placeholder="note (optional)" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} className="bg-black border border-term-border px-1 w-56" />
          <button className="btn" disabled={STATIC || (!f.entity_id && !f.metric_id)} onClick={add}>ADD</button>
          {msg ? <span className="text-term-muted">{msg}</span> : null}
        </div>
      </Panel>
      <Panel title={`ITEMS (${data?.length ?? 0})`}>
        {data && data.length === 0 ? <div className="text-xs font-mono text-term-muted">Watchlist is empty.</div> : null}
        <table className="w-full text-[11px] font-mono"><thead className="text-term-muted"><tr><th className="text-left">entity</th><th className="text-left">metric</th><th>status</th>
          <th className="text-left">latest value(s)</th><th>latest filing</th><th className="text-left">note</th><th>added (Taipei)</th><th /></tr></thead>
          <tbody>{data?.map((w) => (
            <tr key={w.id} className="border-t border-term-border align-top">
              <td>{w.entity_id ?? "any"}<div className="text-term-muted">{w.entity_name}</div></td>
              <td>{w.metric_id ?? "any"}<div className="text-term-muted">{w.metric_name}</div></td>
              <td className={`text-center ${SC[w.status] ?? ""}`}>{w.status.toUpperCase()}{w.status_reason ? <div className="text-term-muted">{w.status_reason}</div> : null}</td>
              <td>{w.latest.length === 0 ? <span className="text-term-down">no data</span> : w.latest.slice(0, 8).map((o) => (
                <div key={o.id}>{w.metric_id ? "" : `${o.metric_id} `}{w.entity_id ? "" : `${o.entity_id} `}<span className="text-white">{o.value.toLocaleString(undefined, { maximumFractionDigits: 4 })}</span> {o.unit}
                  <span className="text-term-muted"> obs {o.observation_date} · pub {o.publication_date} · {o.classification}</span></div>))}
                {w.latest.length > 8 ? <div className="text-term-muted">+{w.latest.length - 8} more series</div> : null}</td>
              <td className="text-center">{w.latest_filing ? <a className="src" href={w.latest_filing.source_url} target="_blank" rel="noreferrer">{w.latest_filing.form} {w.latest_filing.publication_date}</a> : "—"}</td>
              <td>{w.note}</td><td className="text-center">{tsTaipei(w.created_at)}</td>
              <td>{STATIC ? null : <button className="btn" onClick={() => del(w.id)}>REMOVE</button>}</td></tr>))}</tbody></table>
      </Panel>
    </div>
  );
}
