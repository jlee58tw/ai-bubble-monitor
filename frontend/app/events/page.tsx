"use client";
import { useState } from "react";
import { Hypothesis, Loading, PageIntro, Panel, tsTaipei } from "@/components/Panel";
import { StatusPill } from "@/components/Badges";
import { EVENT_TYPE_ZH, dt, ent as entZh, st, tx, usdYi } from "@/lib/i18n";
import { ApiError, useApi } from "@/components/useApi";

type Ev = { id: number; entity_id: string; form: string; event_type: string; accession_number: string; observation_date: string | null;
  publication_date: string; lag_days: number | null; acceptance_datetime_utc: string | null; items: string | null; source_url: string;
  observations_from_filing: number };
type Resp = { events: Ev[]; coverage: { entity_id: string; earliest_filing: string; latest_filing: string; events: number; note: string }[];
  not_connected: { entity_id: string; name: string; reason: string }[]; last_run: { status: string; started_at: string; message: string | null } | null;
  source: string; definitions: Record<string, string> };
type G = { status: string; reason: string | null; items: { id: number; entity_id: string; target_period: string; value_low: number | null; value_high: number | null; publication_date: string; source_url: string; quote: string }[] };

const DEF_ZH: Record<string, string> = { observation_date: "觀測日", publication_date: "公布日", earnings_release_8k: "財報新聞稿 8-K" };

export default function Events() {
  const [ent, setEnt] = useState(""); const [typ, setTyp] = useState("");
  const q = new URLSearchParams({ ...(ent ? { entity_id: ent } : {}), ...(typ ? { event_type: typ } : {}), limit: "400" }).toString();
  const { data: r, error, loading } = useApi<Resp>(`/api/events?${q}`);
  const g = useApi<G>("/api/guidance");
  return (
    <div className="space-y-4">
      <PageIntro emoji="📅" title="財報與申報事件"
        what={<>美國上市公司向 SEC 申報的時間軸：季報／年報（10-Q／10-K／20-F）與財報新聞稿（8-K Item 2.02）。用來確保回測只用「當時已經公開」的資料。</>}
        how={<><b>觀測日</b>＝財報期末或事件日；<b>公布日</b>＝申報在 EDGAR 公開的日期；兩者相差的天數就是「延遲」。台股與未上市公司沒有 EDGAR 代碼，標示為無資料。</>} />
      <p className="text-[11px] text-term-muted">來源：{tx(r?.source)}。最後抓取：{r?.last_run ? `${st(r.last_run.status)} ${tsTaipei(r.last_run.started_at)}` : "從未"}。
        觀測日＝期末／事件日；公布日＝EDGAR 申報日（時點回測引擎使用的日期）。</p>
      {error ? <ApiError error={error} /> : null}<Loading show={loading} />
      <div className="grid gap-3 lg:grid-cols-3">
        <Panel title="涵蓋範圍（各公司已儲存事件數）">
          <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono"><tbody>{r?.coverage.map((c) => (
            <tr key={c.entity_id} className="border-t border-term-border"><td>{entZh(c.entity_id)}</td><td>{dt(c.earliest_filing)} → {dt(c.latest_filing)}</td><td className="text-right">{c.events}</td></tr>))}
            {r?.not_connected.map((c) => <tr key={c.entity_id} className="border-t border-term-border text-term-down"><td>{entZh(c.entity_id)}</td><td colSpan={2}>無資料——{tx(c.reason)}</td></tr>)}</tbody></table></div>
          <div className="text-[11px] text-term-muted mt-1">{tx(r?.coverage[0]?.note)}</div>
        </Panel>
        <Panel title="公司指引（原文引述）" className="lg:col-span-2" info="只收錄有來源網址與原文引述的指引數字，不推測、不估計。">
          {g.data?.status === "placeholder" ? <div className="text-xs"><StatusPill s="placeholder" /> {tx(g.data.reason)}</div>
            : <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono"><thead className="text-term-muted text-left whitespace-nowrap"><tr><th>公司</th><th>目標年度</th><th className="text-right">區間</th><th>公布日</th><th>來源</th></tr></thead><tbody>{(g.data?.items ?? []).map((i) => (
              <tr key={i.id} className="border-t border-term-border" title={`原文：${i.quote}`}><td>{entZh(i.entity_id)}</td><td>FY{i.target_period}</td>
                <td className="text-right text-white">{usdYi(i.value_low, 0)} – {usdYi(i.value_high, 0)}</td><td>{dt(i.publication_date)}</td>
                <td><a className="src" href={i.source_url} target="_blank" rel="noreferrer">8-K ↗</a></td></tr>))}</tbody></table></div>}
          <div className="text-[11px] text-term-muted mt-2">{r && Object.entries(r.definitions).map(([k, v]) => <div key={k}><b>{DEF_ZH[k] ?? k}</b>：{tx(v)}</div>)}</div>
        </Panel>
      </div>
      <Panel title={`事件列表（${r?.events.length ?? 0} 筆）`}>
        <div className="flex gap-2 mb-2 text-xs font-mono">
          <select value={ent} onChange={(e) => setEnt(e.target.value)} className="bg-black border border-term-border px-1"><option value="">全部公司</option>
            {r?.coverage.map((c) => <option key={c.entity_id} value={c.entity_id}>{entZh(c.entity_id)}</option>)}</select>
          <select value={typ} onChange={(e) => setTyp(e.target.value)} className="bg-black border border-term-border px-1"><option value="">全部類型</option>
            <option value="periodic_report">定期財報（10-Q／10-K／20-F）</option><option value="earnings_release_8k">財報新聞稿（8-K Item 2.02）</option></select>
        </div>
        <div className="overflow-x-auto max-h-[600px]"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted sticky top-0 bg-black whitespace-nowrap"><tr><th className="text-left">公司</th><th>表單</th><th>類型</th><th>觀測日</th><th>公布日</th>
            <th>延遲（天）</th><th>受理時間（台北）</th><th>8-K 項目</th><th>此申報的觀測筆數</th><th>來源</th></tr></thead>
          <tbody>{r?.events.map((e) => (
            <tr key={e.id} className="border-t border-term-border text-center"><td className="text-left">{entZh(e.entity_id)}</td><td>{e.form}</td><td>{EVENT_TYPE_ZH[e.event_type] ?? e.event_type}</td>
              <td>{dt(e.observation_date)}</td><td className="text-white">{dt(e.publication_date)}</td><td>{e.lag_days ?? "—"}</td>
              <td>{e.acceptance_datetime_utc ? tsTaipei(e.acceptance_datetime_utc) : "—"}</td><td>{e.items ?? ""}</td>
              <td>{e.observations_from_filing || "—"}</td><td><a className="src" href={e.source_url} target="_blank" rel="noreferrer">EDGAR</a></td></tr>))}</tbody></table></div>
      </Panel>
      <Hypothesis>財報新聞稿 8-K 只靠 EDGAR 的 Item 2.02 標籤辨識，內容（包括指引）不會自動解析。指引數字只有在附來源網址與原文引述時才會出現，絕不推測或估計。</Hypothesis>
    </div>
  );
}
