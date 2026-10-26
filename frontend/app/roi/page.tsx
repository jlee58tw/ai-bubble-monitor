"use client";
import { useEffect, useState } from "react";
import { Hypothesis, Panel } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";

type In = { success_probability: number; review_minutes: number; reviewer_hourly_rate: number; inference_cost: number; tool_cost: number;
  rework_cost: number; rework_share: number; failure_recovery_cost: number; baseline_human_cost: number; task_volume: number };
type Out = { per_task: Record<string, number>; effective_roi: number | null; totals: Record<string, number>;
  break_even_success_probability: number | null; break_even_note: string | null; formulas: Record<string, string>; assumptions: Record<string, string> };
type Bench = { groups: { benchmark: string; benchmark_version: string; split: string; metric: string; rows: { model: string; value: number; result_date: string | null }[] }[] };

const DEF: In = { success_probability: 0.6, review_minutes: 15, reviewer_hourly_rate: 60, inference_cost: 0.5, tool_cost: 0.1,
  rework_cost: 20, rework_share: 0.7, failure_recovery_cost: 40, baseline_human_cost: 30, task_volume: 1000 };
const FIELDS: { k: keyof In; label: string; step: number; max?: number; unit: string }[] = [
  { k: "success_probability", label: "Agent success probability p", step: 0.01, max: 1, unit: "0–1" },
  { k: "review_minutes", label: "Human review time per task", step: 1, unit: "minutes" },
  { k: "reviewer_hourly_rate", label: "Reviewer hourly rate", step: 1, unit: "USD/h" },
  { k: "inference_cost", label: "AI inference cost per task", step: 0.01, unit: "USD" },
  { k: "tool_cost", label: "Tool cost per task (APIs, sandboxes, search…)", step: 0.01, unit: "USD" },
  { k: "rework_cost", label: "Rework cost (fixing a failed task)", step: 1, unit: "USD" },
  { k: "rework_share", label: "Rework share s (failed tasks fixable by rework)", step: 0.01, max: 1, unit: "0–1" },
  { k: "failure_recovery_cost", label: "Failure recovery cost / loss (unfixable failure)", step: 1, unit: "USD" },
  { k: "baseline_human_cost", label: "Baseline manual execution cost per task", step: 1, unit: "USD" },
  { k: "task_volume", label: "Task volume", step: 1, unit: "tasks / period" },
];
const usd = (v: number | undefined) => (v === undefined ? "—" : `${v < 0 ? "-" : ""}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`);

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
      <h1 className="font-mono text-term-amber text-lg">RELIABILITY ROI SCENARIO SIMULATOR</h1>
      <div className="panel p-3 font-mono text-[11px] space-y-1">
        <div><span className="text-term-amber">Effective Task Cost</span> = AI Inference Cost + Tool Cost + Human Review Cost + Expected Rework Cost + Expected Failure Loss</div>
        <div><span className="text-term-amber">Effective ROI</span> = (Baseline Human Cost − Effective Task Cost) / Baseline Human Cost</div>
      </div>
      <p className="text-[10px] text-term-muted font-mono">Scenario tool: every input is your own assumption, not observed data. Computed by the API (<code>/api/roi</code>).</p>
      {error ? <ApiError error={error} /> : null}
      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="INPUTS (per task)">
          <div className="space-y-2">{FIELDS.map((f) => (
            <label key={f.k} className="flex items-center justify-between gap-3 text-xs">
              <span>{f.label} <span className="text-term-muted">[{f.unit}]</span></span>
              <input type="number" step={f.step} min={0} max={f.max} value={x[f.k]}
                onChange={(e) => { let v = parseFloat(e.target.value); if (Number.isNaN(v)) v = 0; if (f.max !== undefined) v = Math.min(v, f.max); setX({ ...x, [f.k]: Math.max(v, 0) }); }}
                className="w-28 bg-black border border-term-border text-white px-1 py-0.5 font-mono text-right" />
            </label>))}
            <button className="btn" onClick={() => setX(DEF)}>reset example values</button>
          </div>
        </Panel>
        <Panel title="OUTPUTS">
          <div className="grid grid-cols-2 gap-3 font-mono">
            <div><div className="label">Effective Task Cost</div><div className="text-2xl text-white">{usd(t?.effective_task_cost)}</div></div>
            <div><div className="label">Effective ROI</div><div className={`text-2xl ${r?.effective_roi == null ? "" : r.effective_roi >= 0 ? "text-term-up" : "text-term-down"}`}>{r == null ? "—" : r.effective_roi === null ? "n/a (baseline = 0)" : `${(r.effective_roi * 100).toFixed(1)}%`}</div></div>
          </div>
          <table className="w-full text-[11px] font-mono mt-3"><tbody>
            {[["AI inference cost", "ai_inference_cost"], ["Tool cost", "tool_cost"], ["Human review cost", "human_review_cost"], ["Expected rework cost *", "expected_rework_cost"], ["Expected failure loss *", "expected_failure_loss"]].map(([l, k]) => (
              <tr key={k} className="border-t border-term-border"><td>{l}</td><td className="text-right">{usd(t?.[k])}</td></tr>))}
            <tr className="border-t border-term-border text-white"><td>= Effective Task Cost</td><td className="text-right">{usd(t?.effective_task_cost)}</td></tr>
            <tr className="border-t border-term-border"><td>Baseline human cost</td><td className="text-right">{usd(t?.baseline_human_cost)}</td></tr>
            <tr className="border-t border-term-border"><td>Total ETC × volume</td><td className="text-right">{usd(r?.totals.effective_task_cost)}</td></tr>
            <tr className="border-t border-term-border"><td>Total baseline × volume</td><td className="text-right">{usd(r?.totals.baseline_human_cost)}</td></tr>
            <tr className="border-t border-term-border"><td>Net savings × volume</td><td className={`text-right ${(r?.totals.net_savings ?? 0) >= 0 ? "text-term-up" : "text-term-down"}`}>{usd(r?.totals.net_savings)}</td></tr>
            <tr className="border-t border-term-border text-white"><td>Break-even success probability (ROI = 0)</td>
              <td className="text-right">{be != null && be > 0 && be <= 1 ? be.toFixed(3) : r?.break_even_note ?? "—"}</td></tr>
          </tbody></table>
        </Panel>
      </div>
      <Hypothesis>* Modeling assumptions (how the two expected terms are computed; the ETC and ROI definitions above are the spec):
        Expected Rework Cost = (1 − p) × s × rework cost; Expected Failure Loss = (1 − p) × (1 − s) × failure recovery cost.
        Each failed task is either reworked (share s) or becomes a failure loss (share 1 − s), never both. Human Review Cost = review minutes / 60 × hourly rate, applied to every task.
        Break-even p solves Effective Task Cost = Baseline Human Cost.</Hypothesis>
      <Panel title="REFERENCE ONLY — PUBLIC BENCHMARK TOP SCORES (not your task's success probability)">
        <p className="text-[10px] text-term-muted mb-1">Benchmark pass rates come from specific task sets and harnesses; they do not transfer to your workload. Clicking sets p for a what-if only.</p>
        <table className="w-full text-[11px] font-mono"><tbody>{refs.map(({ g, top }) => (
          <tr key={`${g.benchmark}${g.split}${g.metric}`} className="border-t border-term-border">
            <td>{g.benchmark} · {g.benchmark_version}{g.split !== "-" ? ` · ${g.split}` : ""}</td><td className="text-white">{top.model}</td><td className="text-right">{top.value.toFixed(1)}%</td><td className="text-term-muted">{top.result_date}</td>
            <td><button className="btn" onClick={() => setX({ ...x, success_probability: Math.round(top.value) / 100 })}>use as p</button></td></tr>))}</tbody></table>
      </Panel>
    </div>
  );
}
