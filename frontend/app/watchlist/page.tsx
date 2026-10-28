"use client";
import { useState } from "react";
import { Loading, PageIntro, Panel, tsTaipei } from "@/components/Panel";
import { StatusPill } from "@/components/Badges";
import { CLS_ZH, UNIT_ZH, dt, ent, metricName, st, tx } from "@/lib/i18n";
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
    .then(() => { setMsg("已加入"); setF({ entity_id: "", metric_id: "", note: "" }); reload(); }).catch((e) => setMsg(String(e)));
  const del = (id: number) => apiSend(`/api/watchlist/${id}`, "DELETE").then(() => reload()).catch((e) => setMsg(String(e)));
  return (
    <div className="space-y-4">
      <PageIntro emoji="⭐" title="追蹤清單"
        what={<>你想特別盯著的公司或指標。每列顯示該序列最新、未被修訂取代的數值與最新一份 SEC 申報。清單存在資料庫（watchlist_items 表）。</>}
        how={<>狀態「正常」＝有最新資料；「缺資料／無資料」會照實標示，<b>絕不顯示成 0</b>。靜態快照版本只能瀏覽，不能新增或刪除。</>} />
      {error ? <ApiError error={error} /> : null}<Loading show={loading} />
      <Panel title="新增">
        <div className="flex flex-wrap gap-2 text-xs font-mono items-center">
          <select value={f.entity_id} onChange={(e) => setF({ ...f, entity_id: e.target.value })} className="bg-black border border-term-border px-1">
            <option value="">（任何公司）</option>{ents.data?.map((e) => <option key={e.id} value={e.id}>{e.id} — {ent(e.id) !== e.id ? ent(e.id) : e.name}</option>)}</select>
          <select value={f.metric_id} onChange={(e) => setF({ ...f, metric_id: e.target.value })} className="bg-black border border-term-border px-1 max-w-md">
            <option value="">（任何指標）</option>{mets.data?.map((m) => <option key={m.id} value={m.id}>{metricName(m.id)}［{st(m.status)}］</option>)}</select>
          <input placeholder="備註（選填）" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} className="bg-black border border-term-border px-1 w-56" />
          <button className="btn" disabled={STATIC || (!f.entity_id && !f.metric_id)} onClick={add}>加入</button>
          {msg ? <span className="text-term-muted">{msg}</span> : null}
        </div>
      </Panel>
      <Panel title={`清單項目（${data?.length ?? 0} 筆）`}>
        {data && data.length === 0 ? <div className="text-xs font-mono text-term-muted">追蹤清單是空的。</div> : null}
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono min-w-[760px]"><thead className="text-term-muted whitespace-nowrap"><tr><th className="text-left">公司</th><th className="text-left">指標</th><th>狀態</th>
          <th className="text-left">最新數值</th><th>最新申報</th><th className="text-left">備註</th><th>加入時間（台北）</th><th /></tr></thead>
          <tbody>{data?.map((w) => (
            <tr key={w.id} className="border-t border-term-border align-top">
              <td>{w.entity_id ?? "任何"}<div className="text-term-muted">{w.entity_id ? ent(w.entity_id) : ""}</div></td>
              <td>{w.metric_id ? metricName(w.metric_id, w.metric_name) : "任何"}</td>
              <td className={`text-center ${SC[w.status] ?? ""}`}><StatusPill s={w.status} />{w.status_reason ? <div className="text-term-muted">{tx(w.status_reason)}</div> : null}</td>
              <td>{w.latest.length === 0 ? <span className="text-term-down">無資料</span> : w.latest.slice(0, 8).map((o) => (
                <div key={o.id}>{w.metric_id ? "" : `${metricName(o.metric_id)} `}{w.entity_id ? "" : `${o.entity_id} `}<span className="text-white">{o.value.toLocaleString("zh-TW", { maximumFractionDigits: 4 })}</span> {UNIT_ZH[o.unit] ?? o.unit}
                  <span className="text-term-muted"> 觀測 {dt(o.observation_date)} · 公布 {dt(o.publication_date)} · {CLS_ZH[o.classification] ?? o.classification}</span></div>))}
                {w.latest.length > 8 ? <div className="text-term-muted">另有 {w.latest.length - 8} 個序列</div> : null}</td>
              <td className="text-center">{w.latest_filing ? <a className="src" href={w.latest_filing.source_url} target="_blank" rel="noreferrer">{w.latest_filing.form} {dt(w.latest_filing.publication_date)}</a> : "—"}</td>
              <td>{w.note}</td><td className="text-center">{tsTaipei(w.created_at)}</td>
              <td>{STATIC ? null : <button className="btn" onClick={() => del(w.id)}>移除</button>}</td></tr>))}</tbody></table></div>
      </Panel>
    </div>
  );
}
