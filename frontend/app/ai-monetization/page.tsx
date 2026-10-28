"use client";
import { Hypothesis, Loading, PageIntro, Panel } from "@/components/Panel";
import { dt, ent, fp } from "@/lib/i18n";
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
      <PageIntro emoji="💰" title="AI 變現與定價力"
        what={<>AI 公司到底賺了多少錢？這頁整理 Anthropic 上市前申報 (S-1) 的季度損益、媒體報導的 OpenAI／Anthropic 營收估計、雲端巨頭在財報新聞稿中揭露的 AI／雲端數字，以及資本支出指引。</>}
        how={<>重點看 <b>算力成本 ÷ 營收</b>：越接近 100%，代表賺來的錢大多又花回算力上。不同來源的數字<b>分開呈現、絕不混算</b>：公司揭露、已公布、定性（下限）、估計（媒體）各有標籤。</>} />
      <Hypothesis>資料分類分開呈現、不混成同一個數字：<b>公司揭露</b>＝上市前 SEC 申報（S-1，未經查核的季度數字）；<b>已公布</b>＝SEC 8-K 財報新聞稿；<b>定性</b>＝下限性陳述（如「超過」）；<b>估計</b>＝媒體報導，不是公司財報。</Hypothesis>
      {err ? <ApiError error={err} /> : null}<Loading show={lab.loading} />
      <Panel title="Anthropic 季度損益（S-1，公司揭露，美元）" info="算力與基礎設施成本 ÷ 營收是本站推導的顯示值，也是風險指標 ai_lab_compute_intensity 的輸入。">
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted whitespace-nowrap"><tr><th className="text-left">季度</th><th className="text-right">營收</th><th className="text-right">算力與基礎設施成本</th>
            <th className="text-right">算力成本 ÷ 營收</th><th className="text-right">營業利益（虧損）</th></tr></thead>
          <tbody>{rev.map((r) => { const c = cc.find((x) => x.period_end === r.period_end); const o = op.find((x) => x.period_end === r.period_end);
            return (<tr key={r.id} className="border-t border-term-border"><td>{fp(r.fiscal_period)}</td><td className="text-right">{fmtVal(r.value, r.unit)}</td>
              <td className="text-right">{c ? fmtVal(c.value, c.unit) : "—"}</td><td className="text-right">{c ? <span className="inline-flex items-center gap-2 justify-end"><span className="hidden sm:inline-block w-16 h-1.5 rounded-full bg-term-border overflow-hidden"><span className="block h-full bg-gradient-to-r from-amber-400 to-red-500" style={{ width: `${Math.min((c.value / r.value) * 100, 100)}%` }} /></span>{((c.value / r.value) * 100).toFixed(0)}%</span> : "—"}</td>
              <td className={`text-right ${o && o.value < 0 ? "text-term-down" : ""}`}>{o ? fmtVal(o.value, o.unit) : "—"}</td></tr>); })}</tbody>
        </table></div>
        {rev[0]?.source_url ? <div className="text-[11px] text-term-muted mt-1">來源：<a className="underline" href={rev[0].source_url} target="_blank" rel="noreferrer">Anthropic, PBC Form S-1</a>，申報日 {dt(rev[0].publication_date)}。算力成本 ÷ 營收為本站<b>推導</b>的顯示值（風險指標 ai_lab_compute_intensity 的輸入）。</div> : null}
      </Panel>
      <Panel title="OpenAI／Anthropic 媒體報導數字（估計，非公司財報；滑鼠移到列上可看原文引述）">
        <ObsTable rows={media.data ?? []} showMetric />
        <div className="text-[11px] text-term-amber mt-1">「年化營收 (run-rate)」的定義因媒體與公司而異，不要拿來跟季度營收比較。OpenAI 沒有申報任何財務報表（公司揭露資料：無資料）。</div>
      </Panel>
      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="雲端巨頭 AI／雲端揭露（8-K 財報新聞稿）">
          <ObsTable rows={hyper.data ?? []} showMetric />
          <div className="text-[11px] text-term-muted mt-1">亞馬遜的數字是<b>下限</b>（原文為「超過」）。微軟／Google／Meta／甲骨文的新聞稿沒有寫出 AI 營收——無資料。</div>
        </Panel>
        <Panel title="資本支出指引（原文引述，8-K EX-99.1）" info="公司指引＝公司對未來的預估，不是實際發生的數字。滑鼠移到列上可看英文原文。">
          {g.data?.items.length ? <table className="w-full text-[11px] font-mono"><tbody>{g.data.items.map((i) => (
            <tr key={i.id} className="border-t border-term-border" title={`原文：${i.quote}`}><td>{ent(i.entity_id)}</td><td>FY{i.target_period} 全年</td>
              <td className="text-right">{i.value_low != null ? fmtVal(i.value_low, "USD") : "—"}–{i.value_high != null ? fmtVal(i.value_high, "USD") : "—"}</td>
              <td>{dt(i.publication_date)}</td><td><a className="underline text-term-info" href={i.source_url} target="_blank" rel="noreferrer">8-K</a></td></tr>))}</tbody></table>
            : <div className="text-xs font-mono text-term-down">尚未儲存任何指引</div>}
          <div className="text-[11px] text-term-muted mt-1">只有 Meta 在書面新聞稿寫出資本支出指引；微軟／Google／亞馬遜／甲骨文只在法說會口頭說明——無資料（沒有逐字稿來源）。</div>
        </Panel>
      </div>
    </div>
  );
}
