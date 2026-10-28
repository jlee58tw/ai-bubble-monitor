"use client";
import Link from "next/link";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { StatusPill } from "@/components/Badges";
import DimBars from "@/components/DimBars";
import Gauge from "@/components/Gauge";
import { Hypothesis, Info, Loading, PageIntro, Panel, tsTaipei } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import { ANIM, GRID, TICK, TT } from "@/lib/chart";
import { DIM_ZH, dt, indName, indWhy, riskLevel, tx } from "@/lib/i18n";

type Ind = { id: string; name: string; status: string; value: number | null; score: number | null; as_of: string | null; detail: string | null; thresholds: { benign: number; stretched: number } | null; rationale: string; weight_in_total: number };
type Dim = { id: string; name: string; weight: number; coverage: number; score: number | null; score_low: number; score_high: number; indicators: Ind[] };
type Risk = { coverage: number; min_coverage: number; score: number | null; score_low: number; score_high: number; precise_score_withheld: boolean; dimensions: Dim[]; config_hash: string; computed_for: string; label: string };
type Snap = { id: number; computed_at: string; config_hash: string; coverage: number; score: number | null; score_low: number; score_high: number };

function Range({ low, high, score }: { low: number; high: number; score: number | null }) {
  const lv = riskLevel(score);
  return (
    <div className="relative h-2.5 rounded-full my-1.5 bg-gradient-to-r from-green-500/25 via-yellow-500/25 via-60% to-red-500/30" title={`可能範圍 ${low.toFixed(1)}–${high.toFixed(1)}`}>
      <div className="absolute h-full rounded-full bg-sky-400/40" style={{ left: `${low}%`, width: `${Math.max(high - low, 0.5)}%` }} />
      {score !== null ? <div className="absolute h-4 -top-[3px] w-1 rounded-full shadow transition-all duration-1000" style={{ left: `${score}%`, background: lv.hex }} /> : null}
    </div>
  );
}
const fv = (v: number | null) => (v === null ? "—" : Math.abs(v) < 5 ? v.toFixed(3) : v.toFixed(2));
function Light({ s }: { s: number | null }) { const lv = riskLevel(s); return <span className="inline-block w-2.5 h-2.5 rounded-full mr-1 align-middle" style={{ background: lv.hex }} title={lv.label} />; }

export default function RiskPage() {
  const { data, error } = useApi<Risk>("/api/risk");
  const hist = useApi<Snap[]>("/api/risk/history");
  return (
    <div className="space-y-5">
      <PageIntro emoji="🎯" title="AI 泡沫風險分數（研究原型）"
        what={<>把 19 個公開指標換算成 0–100 分（0＝溫和、100＝研究假設的過熱門檻），再依六大面向的權重加總。這頁列出每個指標的數值、門檻與分數。</>}
        how={<>每列指標：<b>數值</b>落在「溫和→過熱」兩個門檻之間的位置就是分數。彩色小圓點是燈號（綠＜40、黃 40–59、橘 60–79、紅 ≥80）。狀態為「無資料／資料不足」的指標不計分，只會把總分的<b>可能範圍</b>拉寬。</>} />
      <Hypothesis>{tx(data?.label) || "門檻皆為研究假設，不是經驗證的預測。"} <Link className="src" href="/methodology">看方法論 →</Link></Hypothesis>
      {error ? <ApiError error={error} /> : null}
      <Loading show={!data && !error} />
      {data ? (
        <div className="grid gap-4 lg:grid-cols-5">
          <Panel title={`總分 · 計算基準日 ${dt(data.computed_for)} · 設定版本 ${data.config_hash}`} className="lg:col-span-2"
            info="總分＝各可用指標分數依權重加總。缺少的指標在範圍中以 0–100 兩端計入，所以範圍會變寬，但絕不當成 0 風險。">
            <Gauge score={data.precise_score_withheld ? null : data.score} low={data.score_low} high={data.score_high} coverage={data.coverage} minCoverage={data.min_coverage} />
            {data.precise_score_withheld || data.score === null
              ? <div className="mt-2 text-term-amber text-sm">暫不公布：覆蓋率低於 {(data.min_coverage * 100).toFixed(0)}%</div> : null}
          </Panel>
          <Panel title="六大面向一覽" className="lg:col-span-3"><DimBars dims={data.dimensions} /></Panel>
        </div>) : null}
      <div className="grid gap-4 xl:grid-cols-2">
        {(data?.dimensions ?? []).map((d) => (
          <Panel key={d.id} title={`${DIM_ZH[d.id]?.name ?? d.name} · 權重 ${d.weight}%`} info={DIM_ZH[d.id]?.plain}>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs items-end">
              <div><span className="label">分數 </span><span className="text-xl font-bold font-mono" style={{ color: riskLevel(d.score).hex }}>{d.score === null ? "無資料" : d.score.toFixed(1)}</span>
                <span className="ml-1 text-[11px]" style={{ color: riskLevel(d.score).hex }}>{riskLevel(d.score).label}</span></div>
              <div><span className="label">可能範圍 </span><span className="font-mono">{d.score_low.toFixed(1)}–{d.score_high.toFixed(1)}</span></div>
              <div><span className="label">覆蓋率 </span><span className="font-mono">{(d.coverage * 100).toFixed(0)}%</span></div>
            </div>
            <Range low={d.score_low} high={d.score_high} score={d.score} />
            <div className="overflow-x-auto">
            <table className="w-full text-[11px] mt-2 min-w-[560px]">
              <thead className="text-term-muted text-left"><tr><th>指標</th><th>狀態</th><th className="text-right">數值</th><th className="text-right">溫和→過熱 <Info text="指標數值等於「溫和」門檻＝0 分，等於「過熱」門檻＝100 分，中間線性內插。" /></th><th className="text-right">分數</th><th>資料日期</th></tr></thead>
              <tbody>{d.indicators.map((i) => (
                <tr key={i.id} className="border-t border-term-border align-top">
                  <td className="text-white py-1">{indName(i.id, i.name)} <Info text={indWhy(i.id, i.rationale)} />
                    {i.detail ? <div className="text-[10px] text-term-muted font-mono break-all">{tx(i.detail)}</div> : null}</td>
                  <td><StatusPill s={i.status} /></td>
                  <td className="text-right font-mono">{fv(i.value)}</td>
                  <td className="text-right text-term-muted font-mono">{i.thresholds && i.thresholds.benign != null ? `${i.thresholds.benign} → ${i.thresholds.stretched}` : "—"}</td>
                  <td className="text-right font-mono whitespace-nowrap"><Light s={i.score} /><span style={{ color: riskLevel(i.score).hex }}>{i.score === null ? "無資料" : i.score.toFixed(0)}</span></td>
                  <td className="text-term-muted font-mono">{i.as_of ? dt(i.as_of) : "—"}</td>
                </tr>))}</tbody>
            </table></div>
          </Panel>))}
      </div>
      <Panel title="歷次快照（只有設定版本相同的快照可以互相比較）" info="每次重新計算會存一筆快照；改了門檻或權重，設定版本（hash）就會改變，前後不可比。">
        {(hist.data ?? []).length === 0 ? <div className="text-xs text-term-muted">尚無歷史快照。</div> : null}
        <ResponsiveContainer width="100%" height={200}><LineChart data={(hist.data ?? []).map((s) => ({ ...s, t: tsTaipei(s.computed_at) }))}>
          <CartesianGrid stroke={GRID} strokeDasharray="2 4" /><XAxis dataKey="t" tick={TICK} /><YAxis domain={[0, 100]} tick={TICK} />
          <Tooltip {...TT} formatter={(v: number) => v?.toFixed?.(2) ?? v} /><Legend />
          <Line {...ANIM} name="風險分數" dataKey="score" stroke="#f97316" strokeWidth={2} /><Line {...ANIM} name="範圍下緣" dataKey="score_low" stroke="#94a3b8" strokeDasharray="3 3" /><Line {...ANIM} name="範圍上緣" dataKey="score_high" stroke="#94a3b8" strokeDasharray="3 3" />
        </LineChart></ResponsiveContainer>
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono"><thead className="text-term-muted text-left"><tr><th>#</th><th>計算時間</th><th>設定版本</th><th className="text-right">覆蓋率</th><th className="text-right">分數</th><th className="text-right">可能範圍</th></tr></thead>
          <tbody>{(hist.data ?? []).map((s) => <tr key={s.id} className="border-t border-term-border"><td>{s.id}</td><td>{tsTaipei(s.computed_at)}</td><td>{s.config_hash}</td><td className="text-right">{(s.coverage * 100).toFixed(1)}%</td><td className="text-right">{s.score?.toFixed(2) ?? "暫不公布"}</td><td className="text-right">{s.score_low.toFixed(1)}–{s.score_high.toFixed(1)}</td></tr>)}</tbody></table></div>
      </Panel>
    </div>
  );
}
