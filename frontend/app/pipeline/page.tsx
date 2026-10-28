"use client";
import { StatusPill } from "@/components/Badges";
import { PageIntro, Panel, tsTaipei } from "@/components/Panel";
import { CLS_ZH, dt, ent, metricName, metricWarn, tx } from "@/lib/i18n";
import { ApiError, useApi } from "@/components/useApi";
import type { MetricDef } from "@/lib/api";

interface Status {
  refresh_in_progress: boolean;
  providers: { provider: string; configured: boolean; reason: string | null; last_run_status: string | null; last_run_at: string | null; last_success_at: string | null }[];
  series: { metric_id: string; entity_id: string; metric_status: string; state: string; latest_period_end: string | null; latest_publication_date: string | null; last_ingested_at: string | null; rows: number }[];
}
interface Run { id: number; provider: string; trigger: string; status: string; started_at: string; finished_at: string | null; records_fetched: number; records_inserted: number; records_revised: number; records_unchanged: number; error_count: number; message: string | null }
interface Err { id: number; run_id: number; created_at: string; level: string; entity_id: string | null; metric_id: string | null; message: string }

const PROV_ZH: Record<string, string> = {
  sec_edgar: "SEC EDGAR 財報（XBRL 公司事實）", fred: "FRED 聯準會經濟資料", sec_filing_xbrl: "SEC 申報檔 XBRL", sec_prospectus: "SEC 公開說明書（S-1）",
  curated_media: "人工整理的公開來源", sec_earnings_release: "SEC 財報新聞稿（8-K）", twse: "臺灣證券交易所", tiingo: "Tiingo 美股收盤價", alphavantage: "Alpha Vantage（選用）",
};
const prov = (p: string | null | undefined) => (p ? PROV_ZH[p] ?? p : "—");
const ts = (s: string | null | undefined) => (s ? tsTaipei(s) : "從未");

export default function Pipeline() {
  const st = useApi<Status>("/api/ingestion/status");
  const runs = useApi<Run[]>("/api/ingestion/runs?limit=20");
  const errs = useApi<Err[]>("/api/ingestion/errors?limit=50");
  const metrics = useApi<MetricDef[]>("/api/metrics");
  if (st.error) return <ApiError error={st.error} />;
  const ser = st.data?.series ?? [];
  const cnt = (k: string) => ser.filter((x) => x.state === k).length;
  return (
    <div className="space-y-4">
      <PageIntro emoji="🛠️" title="資料來源與管線健康度"
        what={<>每個資料來源有沒有接上、最後一次抓取是否成功、每條資料序列是否過期，以及抓取紀錄與錯誤。</>}
        how={<><b className="text-term-up">最新</b>＝資料在預期更新週期內；<b className="text-term-amber">過期</b>＝季資料距期末超過 120 天、日資料超過 7 天；<b className="text-term-down">缺資料／無資料</b>＝沒有可用數值（不會被當成 0）。執行訊息與錯誤保留原始英文，方便除錯。</>} />
      <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
        {([["fresh", "最新", "text-term-up"], ["stale", "過期", "text-term-amber"], ["missing", "缺資料", "text-term-down"], ["unavailable", "無資料", "text-term-muted"]] as const).map(([k, l, c]) => (
          <div key={k} className="panel p-3 animate-fade-up"><div className="label">{l}的序列</div><div className={`text-3xl font-extrabold ${c}`}>{cnt(k)}</div><div className="text-[11px] text-term-muted">共 {ser.length} 條序列</div></div>))}
      </div>
      <Panel title="資料提供者">
        <div className="overflow-x-auto"><table className="w-full text-[12px]"><thead className="text-term-muted text-left whitespace-nowrap"><tr><th>提供者</th><th>設定</th><th>最後執行</th><th>最後執行時間（台北）</th><th>最後成功（台北）</th><th>備註</th></tr></thead>
          <tbody>{st.data?.providers.map((p) => (
            <tr key={p.provider} className="border-t border-term-border"><td title={p.provider}>{prov(p.provider)}</td><td><StatusPill s={p.configured ? "connected" : "unavailable"} /></td>
              <td>{p.last_run_status ? <StatusPill s={p.last_run_status} /> : <span className="text-term-muted">從未執行</span>}</td><td className="font-mono">{ts(p.last_run_at)}</td><td className="font-mono">{ts(p.last_success_at)}</td><td className="text-term-muted">{tx(p.reason)}</td></tr>))}
          </tbody></table></div>
      </Panel>
      <Panel title="指標登錄表" info="系統追蹤的所有指標、資料分類與筆數；滑鼠移到列上可看原始英文說明。">
        <div className="overflow-x-auto max-h-[520px]"><table className="w-full text-[12px]"><thead className="text-term-muted text-left whitespace-nowrap sticky top-0 bg-black"><tr><th>指標</th><th>狀態</th><th>提供者</th><th>分類</th><th>AI 專屬</th><th className="text-right">筆數</th><th>注意事項</th></tr></thead>
          <tbody>{metrics.data?.map((m) => (
            <tr key={m.id} className="border-t border-term-border" title={m.description}><td>{metricName(m.id, m.id)}<div className="text-[10px] text-term-muted font-mono">{m.id}</div></td><td><StatusPill s={m.status} /></td><td>{prov(m.provider)}</td>
              <td>{CLS_ZH[m.default_classification] ?? m.default_classification}</td><td>{m.is_ai_specific ? "是" : "否"}</td><td className="text-right font-mono">{m.observation_rows.toLocaleString("zh-TW")}</td><td className="text-term-amber">{metricWarn(m.id, m.warning)}</td></tr>))}
          </tbody></table></div>
      </Panel>
      <Panel title="序列新鮮度（過期：季資料距期末 > 120 天、日資料 > 7 天）">
        <div className="grid gap-1 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
          {ser.map((s) => (
            <div key={s.metric_id + s.entity_id} className="flex items-center gap-2 text-[11px] border-b border-term-border py-0.5">
              <StatusPill s={s.state} /><span className="w-40 truncate" title={s.metric_id}>{metricName(s.metric_id, s.metric_id)}</span><span className="w-20 truncate">{ent(s.entity_id)}</span>
              <span className="text-term-muted font-mono">期末 {dt(s.latest_period_end)} · 公布 {dt(s.latest_publication_date)} · {s.rows} 筆</span>
            </div>))}
        </div>
      </Panel>
      <Panel title="抓取紀錄">
        <div className="overflow-x-auto"><table className="w-full text-[12px]"><thead className="text-term-muted text-left whitespace-nowrap"><tr><th>#</th><th>提供者</th><th>觸發</th><th>狀態</th><th>開始（台北）</th><th>抓取</th><th>新增</th><th>修正</th><th>未變</th><th>錯誤</th><th>原始訊息（英文）</th></tr></thead>
          <tbody>{runs.data?.map((r) => (
            <tr key={r.id} className="border-t border-term-border"><td>{r.id}</td><td>{prov(r.provider)}</td><td>{r.trigger === "cli" ? "命令列" : r.trigger === "scheduler" ? "排程" : r.trigger}</td><td><StatusPill s={r.status} /></td><td className="font-mono whitespace-nowrap">{ts(r.started_at)}</td>
              <td>{r.records_fetched}</td><td>{r.records_inserted}</td><td>{r.records_revised}</td><td>{r.records_unchanged}</td><td>{r.error_count}</td><td className="text-term-muted font-mono text-[11px]">{r.message}</td></tr>))}
          </tbody></table></div>
      </Panel>
      <Panel title="錯誤紀錄">
        {errs.data?.length === 0 ? <div className="text-[12px] text-term-up">✅ 沒有錯誤紀錄</div> : (
          <div className="overflow-x-auto"><table className="w-full text-[12px]"><thead className="text-term-muted text-left"><tr><th>執行</th><th>層級</th><th>公司</th><th>指標</th><th>原始訊息（英文）</th><th>時間（台北）</th></tr></thead><tbody>{errs.data?.map((e) => (
            <tr key={e.id} className="border-t border-term-border"><td>第 {e.run_id} 次</td><td><StatusPill s={e.level === "error" ? "failed" : "partial"} /></td><td>{ent(e.entity_id)}</td><td>{metricName(e.metric_id, e.metric_id)}</td><td className="font-mono text-[11px]">{e.message}</td><td className="text-term-muted font-mono">{ts(e.created_at)}</td></tr>))}
          </tbody></table></div>)}
      </Panel>
      <p className="text-[11px] text-term-muted">完整來源清單、連線測試結果與限制：docs/DATA_SOURCES.md</p>
    </div>
  );
}
