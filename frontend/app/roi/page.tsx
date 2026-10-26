"use client";
import { useMemo, useState } from "react";
import { Hypothesis, Panel } from "@/components/Panel";
import { useApi } from "@/components/useApi";
import { computeRoi, type In } from "@/lib/roi";

type Bench = { groups: { benchmark: string; benchmark_version: string; split: string; metric: string; rows: { model: string; value: number; result_date: string | null }[] }[] };
const DEF: In = { p: 0.6, reviewMin: 15, rate: 60, inference: 0.5, recovery: 40, baseline: 50, volume: 1000 };
const FIELDS: { k: keyof In; label: string; step: number; min: number; max?: number; unit: string }[] = [
  { k: "p", label: "Success probability p (task fully correct without rework)", step: 0.01, min: 0, max: 1, unit: "0–1" },
  { k: "reviewMin", label: "Human review time per task", step: 1, min: 0, unit: "minutes" },
  { k: "rate", label: "Reviewer loaded hourly cost", step: 1, min: 0, unit: "USD/h" },
  { k: "inference", label: "Inference cost per attempt", step: 0.01, min: 0, unit: "USD" },
  { k: "recovery", label: "Failure recovery cost (when the agent fails)", step: 1, min: 0, unit: "USD" },
  { k: "baseline", label: "Baseline manual cost per task (no agent)", step: 1, min: 0, unit: "USD" },
  { k: "volume", label: "Task volume", step: 1, min: 0, unit: "tasks / period" },
];
const usd = (v: number) => `${v < 0 ? "-" : ""}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

export default function Roi() {
  const [x, setX] = useState<In>(DEF);
  const r = useMemo(() => computeRoi(x), [x]);
  const bench = useApi<Bench>("/api/benchmarks");
  const refs = (bench.data?.groups ?? []).filter((g) => g.metric.endsWith("pct") || g.metric.includes("accuracy") || g.metric.includes("resolved"))
    .map((g) => ({ g, top: g.rows[0] })).filter((t) => t.top).slice(0, 6);
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">RELIABILITY ROI SCENARIO SIMULATOR</h1>
      <Hypothesis>Scenario tool. All inputs are YOUR assumptions; nothing here is observed data. Formulas are stated below (the original spec text was not available in the repo, so they are documented assumptions).</Hypothesis>
      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="INPUTS (per task)">
          <div className="space-y-2">{FIELDS.map((f) => (
            <label key={f.k} className="flex items-center justify-between gap-3 text-xs">
              <span>{f.label} <span className="text-term-muted">[{f.unit}]</span></span>
              <input type="number" step={f.step} min={f.min} max={f.max} value={x[f.k]}
                onChange={(e) => { let v = parseFloat(e.target.value); if (Number.isNaN(v)) v = 0; if (f.max !== undefined) v = Math.min(v, f.max); setX({ ...x, [f.k]: Math.max(v, f.min) }); }}
                className="w-28 bg-black border border-term-border text-white px-1 py-0.5 font-mono text-right" />
            </label>))}
            <button className="btn" onClick={() => setX(DEF)}>reset example values</button>
          </div>
        </Panel>
        <Panel title="OUTPUTS">
          <div className="grid grid-cols-2 gap-3 font-mono">
            <div><div className="label">Effective Task Cost (ETC)</div><div className="text-2xl text-white">{usd(r.etc)}</div></div>
            <div><div className="label">Effective ROI</div><div className={`text-2xl ${r.roi === null ? "" : r.roi >= 0 ? "text-term-up" : "text-term-down"}`}>{r.roi === null ? "n/a" : `${(r.roi * 100).toFixed(1)}%`}</div></div>
            <div><div className="label">review cost / task</div>{usd(r.review)}</div>
            <div><div className="label">expected failure cost / task</div>{usd(r.failure)}</div>
            <div><div className="label">total ETC × volume</div>{usd(r.totalEtc)}</div>
            <div><div className="label">total baseline × volume</div>{usd(r.totalBaseline)}</div>
            <div><div className="label">net savings × volume</div><span className={r.savings >= 0 ? "text-term-up" : "text-term-down"}>{usd(r.savings)}</span></div>
            <div><div className="label">break-even success probability</div>{r.breakEvenP === null ? "n/a" : r.breakEvenP <= 0 ? "≤0 (profitable even at p=0)" : r.breakEvenP > 1 ? "> 1 (never breaks even)" : r.breakEvenP.toFixed(3)}</div>
          </div>
          <div className="mt-3 text-[11px] font-mono text-term-muted space-y-1">
            <p>ETC = inference + (review_min / 60) × reviewer_rate + (1 − p) × failure_recovery</p>
            <p>Effective ROI = (baseline_manual − ETC) / ETC</p>
            <p>Totals = per-task value × task volume. Break-even p solves ETC = baseline.</p>
          </div>
        </Panel>
      </div>
      <Panel title="REFERENCE ONLY — PUBLIC BENCHMARK TOP SCORES (not your task's success probability)">
        <p className="text-[10px] text-term-muted mb-1">Benchmark pass rates come from specific task sets and harnesses; they do not transfer to your workload. Clicking sets p for a what-if only.</p>
        <table className="w-full text-[11px] font-mono"><tbody>{refs.map(({ g, top }) => (
          <tr key={`${g.benchmark}${g.split}${g.metric}`} className="border-t border-term-border">
            <td>{g.benchmark} · {g.benchmark_version}{g.split !== "-" ? ` · ${g.split}` : ""}</td><td className="text-white">{top.model}</td><td className="text-right">{top.value.toFixed(1)}%</td><td className="text-term-muted">{top.result_date}</td>
            <td><button className="btn" onClick={() => setX({ ...x, p: Math.round(top.value) / 100 })}>use as p</button></td></tr>))}</tbody></table>
      </Panel>
    </div>
  );
}
