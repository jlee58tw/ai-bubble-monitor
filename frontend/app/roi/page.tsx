"use client";
import { useEffect, useState } from "react";
import { Hypothesis, PageIntro, Panel } from "@/components/Panel";
import { dt, tx } from "@/lib/i18n";
import { ApiError, useApi } from "@/components/useApi";

type In = { success_probability: number; review_minutes: number; reviewer_hourly_rate: number; inference_cost: number; tool_cost: number;
  rework_cost: number; rework_share: number; failure_recovery_cost: number; baseline_human_cost: number; task_volume: number };
type Out = { per_task: Record<string, number>; effective_roi: number | null; totals: Record<string, number>;
  break_even_success_probability: number | null; break_even_note: string | null; formulas: Record<string, string>; assumptions: Record<string, string> };
type Bench = { groups: { benchmark: string; benchmark_version: string; split: string; metric: string; rows: { model: string; value: number; result_date: string | null }[] }[] };

const DEF: In = { success_probability: 0.6, review_minutes: 15, reviewer_hourly_rate: 60, inference_cost: 0.5, tool_cost: 0.1,
  rework_cost: 20, rework_share: 0.7, failure_recovery_cost: 40, baseline_human_cost: 30, task_volume: 1000 };
const FIELDS: { k: keyof In; label: string; step: number; max?: number; unit: string }[] = [
  { k: "success_probability", label: "AI 代理成功率 p", step: 0.01, max: 1, unit: "0–1" },
  { k: "review_minutes", label: "每件任務人工審查時間", step: 1, unit: "分鐘" },
  { k: "reviewer_hourly_rate", label: "審查人員時薪", step: 1, unit: "美元／小時" },
  { k: "inference_cost", label: "每件任務 AI 推論成本", step: 0.01, unit: "美元" },
  { k: "tool_cost", label: "每件任務工具成本（API、沙盒、搜尋…）", step: 0.01, unit: "美元" },
  { k: "rework_cost", label: "重工成本（修好一件失敗任務）", step: 1, unit: "美元" },
  { k: "rework_share", label: "可重工比例 s（失敗任務中能修好的比例）", step: 0.01, max: 1, unit: "0–1" },
  { k: "failure_recovery_cost", label: "失敗補救成本／損失（修不好的失敗）", step: 1, unit: "美元" },
  { k: "baseline_human_cost", label: "每件任務純人工執行成本（基準）", step: 1, unit: "美元" },
  { k: "task_volume", label: "任務量", step: 1, unit: "件／期" },
];
const usd = (v: number | undefined) => (v === undefined ? "—" : `${v < 0 ? "−" : ""}US$${Math.abs(v).toLocaleString("zh-TW", { maximumFractionDigits: 2 })}`);

export default function Roi() {
  const [x, setX] = useState<In>(DEF);
  const [q, setQ] = useState(new URLSearchParams(Object.entries(DEF).map(([k, v]) => [k, String(v)])).toString());
  useEffect(() => { const t = setTimeout(() => setQ(new URLSearchParams(Object.entries(x).map(([k, v]) => [k, String(v)])).toString()), 150); return () => clearTimeout(t); }, [x]);
  const { data: r, error } = useApi<Out>(`/api/roi?${q}`);
  const bench = useApi<Bench>("/api/benchmarks");
  const refs = (bench.data?.groups ?? []).filter((g) => g.metric.endsWith("pct") || g.metric.includes("accuracy") || g.metric.includes("resolved"))
    .map((g) => ({ g, top: g.rows[0] })).filter((t) => t.top).slice(0, 6);
  const t = r?.per_task;
  const be = r?.break_even_success_probability;
  return (
    <div className="space-y-4">
      <PageIntro emoji="🧮" title="AI 可靠度投資報酬 (ROI) 情境模擬器"
        what={<>如果把一件工作交給 AI 代理，算上推論費、工具費、人工審查、失敗後重做或補救的成本，到底比純人工便宜多少？這是一個<b>情境試算工具</b>，所有輸入都是你自己的假設，不是觀測資料。</>}
        how={<>在左邊調整數字，右邊即時算出<b>有效任務成本</b>與<b>有效 ROI</b>（正數＝比人工省、負數＝比人工貴）。「損益兩平成功率」告訴你 AI 至少要多可靠才划算。靜態快照版只能顯示預設範例的結果。</>} />
      <div className="panel p-3 text-[12px] space-y-1">
        <div><span className="text-term-amber font-semibold">有效任務成本 (Effective Task Cost)</span>＝AI 推論成本＋工具成本＋人工審查成本＋預期重工成本＋預期失敗損失</div>
        <div><span className="text-term-amber font-semibold">有效 ROI (Effective ROI)</span>＝（人工基準成本 − 有效任務成本）÷ 人工基準成本</div>
      </div>
      <p className="text-[11px] text-term-muted">情境工具：每個輸入都是你的假設，不是觀測資料。由 API（<code>/api/roi</code>）計算。</p>
      {error ? <ApiError error={error} /> : null}
      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="輸入（每件任務）">
          <div className="space-y-2">{FIELDS.map((f) => (
            <label key={f.k} className="flex items-center justify-between gap-3 text-xs">
              <span>{f.label} <span className="text-term-muted">[{f.unit}]</span></span>
              <input type="number" step={f.step} min={0} max={f.max} value={x[f.k]}
                onChange={(e) => { let v = parseFloat(e.target.value); if (Number.isNaN(v)) v = 0; if (f.max !== undefined) v = Math.min(v, f.max); setX({ ...x, [f.k]: Math.max(v, 0) }); }}
                className="w-28 shrink-0 bg-black border border-term-border text-white px-1 py-0.5 font-mono text-right" />
            </label>))}
            <button className="btn" onClick={() => setX(DEF)}>還原範例數值</button>
          </div>
        </Panel>
        <Panel title="結果" info="有效 ROI 為正＝用 AI 比純人工便宜；為負＝反而更貴。">
          <div className="grid grid-cols-2 gap-3 font-mono">
            <div><div className="label">有效任務成本</div><div className="text-3xl font-extrabold text-white">{usd(t?.effective_task_cost)}</div></div>
            <div><div className="label">有效 ROI</div><div className={`text-3xl font-extrabold ${r?.effective_roi == null ? "" : r.effective_roi >= 0 ? "text-term-up" : "text-term-down"}`}>{r == null ? "—" : r.effective_roi === null ? "不適用（基準成本為 0）" : `${(r.effective_roi * 100).toFixed(1)}%`}</div></div>
          </div>
          <table className="w-full text-[11px] font-mono mt-3"><tbody>
            {[["AI 推論成本", "ai_inference_cost"], ["工具成本", "tool_cost"], ["人工審查成本", "human_review_cost"], ["預期重工成本 *", "expected_rework_cost"], ["預期失敗損失 *", "expected_failure_loss"]].map(([l, k]) => (
              <tr key={k} className="border-t border-term-border"><td>{l}</td><td className="text-right">{usd(t?.[k])}</td></tr>))}
            <tr className="border-t border-term-border text-white"><td>＝ 有效任務成本</td><td className="text-right">{usd(t?.effective_task_cost)}</td></tr>
            <tr className="border-t border-term-border"><td>人工基準成本</td><td className="text-right">{usd(t?.baseline_human_cost)}</td></tr>
            <tr className="border-t border-term-border"><td>有效任務成本 × 任務量</td><td className="text-right">{usd(r?.totals.effective_task_cost)}</td></tr>
            <tr className="border-t border-term-border"><td>人工基準成本 × 任務量</td><td className="text-right">{usd(r?.totals.baseline_human_cost)}</td></tr>
            <tr className="border-t border-term-border"><td>淨節省 × 任務量</td><td className={`text-right ${(r?.totals.net_savings ?? 0) >= 0 ? "text-term-up" : "text-term-down"}`}>{usd(r?.totals.net_savings)}</td></tr>
            <tr className="border-t border-term-border text-white"><td>損益兩平成功率（ROI＝0）</td>
              <td className="text-right">{be != null && be > 0 && be <= 1 ? be.toFixed(3) : tx(r?.break_even_note) || "—"}</td></tr>
          </tbody></table>
        </Panel>
      </div>
      <Hypothesis>* 建模假設（兩個「預期」項目的算法；上方有效任務成本與 ROI 的定義為規格）：
        預期重工成本＝(1 − p) × s × 重工成本；預期失敗損失＝(1 − p) × (1 − s) × 失敗補救成本。
        每件失敗任務不是被重工（比例 s），就是變成失敗損失（比例 1 − s），不會兩者都算。人工審查成本＝審查分鐘 ÷ 60 × 時薪，每件任務都計入。
        損益兩平 p 是讓「有效任務成本＝人工基準成本」的成功率。</Hypothesis>
      <Panel title="僅供參考：公開基準測試最高分（不等於你的任務成功率）">
        <p className="text-[11px] text-term-muted mb-1">基準測試的通過率來自特定題組與測試框架，不能直接套用到你的工作；按下按鈕只是把 p 設成該值做「如果…會怎樣」的試算。</p>
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono"><tbody>{refs.map(({ g, top }) => (
          <tr key={`${g.benchmark}${g.split}${g.metric}`} className="border-t border-term-border">
            <td>{g.benchmark} · {g.benchmark_version}{g.split !== "-" ? ` · ${g.split}` : ""}</td><td className="text-white">{top.model}</td><td className="text-right">{top.value.toFixed(1)}%</td><td className="text-term-muted">{dt(top.result_date)}</td>
            <td><button className="btn" onClick={() => setX({ ...x, success_probability: Math.round(top.value) / 100 })}>用作 p</button></td></tr>))}</tbody></table></div>
      </Panel>
    </div>
  );
}
