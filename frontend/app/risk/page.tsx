"use client";
import Link from "next/link";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { StatusPill } from "@/components/Badges";
import { Hypothesis, Loading, Panel, tsTaipei } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";

type Ind = { id: string; name: string; status: string; value: number | null; score: number | null; as_of: string | null; detail: string | null; thresholds: { benign: number; stretched: number } | null; rationale: string; weight_in_total: number };
type Dim = { id: string; name: string; weight: number; coverage: number; score: number | null; score_low: number; score_high: number; indicators: Ind[] };
type Risk = { coverage: number; min_coverage: number; score: number | null; score_low: number; score_high: number; precise_score_withheld: boolean; dimensions: Dim[]; config_hash: string; computed_for: string; label: string };
type Snap = { id: number; computed_at: string; config_hash: string; coverage: number; score: number | null; score_low: number; score_high: number };

const col = (s: number | null) => (s === null ? "text-term-muted" : s >= 70 ? "text-term-down" : s >= 40 ? "text-term-amber" : "text-term-up");
function Range({ low, high, score }: { low: number; high: number; score: number | null }) {
  return (
    <div className="relative h-2 bg-[#161b22] border border-term-border my-1">
      <div className="absolute h-full bg-term-amber/30" style={{ left: `${low}%`, width: `${Math.max(high - low, 0.5)}%` }} />
      {score !== null ? <div className="absolute h-3 -top-0.5 w-0.5 bg-white" style={{ left: `${score}%` }} /> : null}
    </div>
  );
}
const fv = (v: number | null) => (v === null ? "—" : Math.abs(v) < 5 ? v.toFixed(3) : v.toFixed(2));

export default function RiskPage() {
  const { data, error } = useApi<Risk>("/api/risk");
  const hist = useApi<Snap[]>("/api/risk/history");
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">AI BUBBLE RISK SCORE <span className="text-xs text-term-muted">(Phase 2 research prototype)</span></h1>
      <Hypothesis>{data?.label ?? "Thresholds are research hypotheses, not validated predictors."} <Link className="src" href="/methodology">Methodology →</Link></Hypothesis>
      {error ? <ApiError error={error} /> : null}
      <Loading show={!data && !error} />
      {data ? (
        <Panel title={`OVERALL · computed for ${data.computed_for} · config ${data.config_hash}`}>
          <div className="grid gap-4 md:grid-cols-3 font-mono">
            <div><div className="label">score (0 benign – 100 stretched)</div>
              {data.precise_score_withheld || data.score === null
                ? <div className="text-2xl text-term-amber">WITHHELD <span className="text-xs">coverage below {(data.min_coverage * 100).toFixed(0)}%</span></div>
                : <div className={`text-4xl ${col(data.score)}`}>{data.score.toFixed(1)}</div>}</div>
            <div><div className="label">possible range given missing data</div><div className="text-xl text-white">{data.score_low.toFixed(1)} – {data.score_high.toFixed(1)}</div>
              <Range low={data.score_low} high={data.score_high} score={data.score} /></div>
            <div><div className="label">data coverage (weighted)</div><div className={`text-xl ${data.coverage < data.min_coverage ? "text-term-down" : "text-white"}`}>{(data.coverage * 100).toFixed(1)}%</div>
              <div className="text-[10px] text-term-muted">min for precise score: {(data.min_coverage * 100).toFixed(0)}%. Missing indicators span 0–100 in the range; never counted as 0 risk.</div></div>
          </div>
        </Panel>) : null}
      <div className="grid gap-3 xl:grid-cols-2">
        {(data?.dimensions ?? []).map((d) => (
          <Panel key={d.id} title={`${d.name.toUpperCase()} · weight ${d.weight}%`}>
            <div className="flex gap-6 font-mono text-xs items-end">
              <div><span className="label">score </span><span className={`text-lg ${col(d.score)}`}>{d.score === null ? "N/A" : d.score.toFixed(1)}</span></div>
              <div><span className="label">range </span>{d.score_low.toFixed(1)}–{d.score_high.toFixed(1)}</div>
              <div><span className="label">coverage </span>{(d.coverage * 100).toFixed(0)}%</div>
            </div>
            <Range low={d.score_low} high={d.score_high} score={d.score} />
            <table className="w-full text-[11px] font-mono mt-2">
              <thead className="text-term-muted text-left"><tr><th>indicator</th><th>status</th><th className="text-right">value</th><th className="text-right">benign→stretched</th><th className="text-right">score</th><th>as of</th></tr></thead>
              <tbody>{d.indicators.map((i) => (
                <tr key={i.id} className="border-t border-term-border align-top" title={`${i.rationale}\n${i.detail ?? ""}`}>
                  <td className="text-white">{i.name}<div className="text-[10px] text-term-muted">{i.detail}</div></td>
                  <td><StatusPill s={i.status} /></td>
                  <td className="text-right">{fv(i.value)}</td>
                  <td className="text-right text-term-muted">{i.thresholds && i.thresholds.benign != null ? `${i.thresholds.benign} → ${i.thresholds.stretched}` : "—"}</td>
                  <td className={`text-right ${col(i.score)}`}>{i.score === null ? "—" : i.score.toFixed(0)}</td>
                  <td className="text-term-muted">{i.as_of ?? "—"}</td>
                </tr>))}</tbody>
            </table>
          </Panel>))}
      </div>
      <Panel title="SNAPSHOT HISTORY (only snapshots with the same config hash are comparable)">
        <ResponsiveContainer width="100%" height={180}><LineChart data={(hist.data ?? []).map((s) => ({ ...s, t: tsTaipei(s.computed_at) }))}>
          <CartesianGrid stroke="#232a35" strokeDasharray="2 4" /><XAxis dataKey="t" tick={{ fill: "#7d8590", fontSize: 10 }} /><YAxis domain={[0, 100]} tick={{ fill: "#7d8590", fontSize: 10 }} />
          <Tooltip contentStyle={{ background: "#11151c", border: "1px solid #232a35", fontSize: 11 }} />
          <Line isAnimationActive={false} dataKey="score" stroke="#ffb000" /><Line isAnimationActive={false} dataKey="score_low" stroke="#7d8590" strokeDasharray="3 3" /><Line isAnimationActive={false} dataKey="score_high" stroke="#7d8590" strokeDasharray="3 3" />
        </LineChart></ResponsiveContainer>
        <table className="w-full text-[11px] font-mono"><thead className="text-term-muted text-left"><tr><th>#</th><th>computed</th><th>config</th><th className="text-right">coverage</th><th className="text-right">score</th><th className="text-right">range</th></tr></thead>
          <tbody>{(hist.data ?? []).map((s) => <tr key={s.id} className="border-t border-term-border"><td>{s.id}</td><td>{tsTaipei(s.computed_at)}</td><td>{s.config_hash}</td><td className="text-right">{(s.coverage * 100).toFixed(1)}%</td><td className="text-right">{s.score?.toFixed(2) ?? "WITHHELD"}</td><td className="text-right">{s.score_low.toFixed(1)}–{s.score_high.toFixed(1)}</td></tr>)}</tbody></table>
      </Panel>
    </div>
  );
}
