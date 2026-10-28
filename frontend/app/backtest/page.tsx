"use client";
import { ANIM } from "@/lib/chart";
import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Hypothesis, Loading, Panel } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import { API_BASE } from "@/lib/api";
import { STATIC, staticCsv } from "@/lib/static";

type Eval = { status: string; reason?: string; n_signal_known_days: number; n_independent_windows: number; n_on?: number; n_off?: number;
  hits_on?: number; hits_off?: number; hit_rate_on?: number | null; hit_rate_off?: number | null; base_rate?: number;
  ci95_on_overlap_adjusted?: [number, number] | null; lift_vs_base?: number | null };
type Lead = { peak_date: string; trigger_date: string; max_drawdown: number; status: string; signal_on_since?: string;
  lead_days_to_trigger?: number; lead_days_to_peak?: number; left_censored?: boolean; peak_at_history_start: boolean };
type Sig = { id: string; name: string; threshold: number; status: string; reason?: string; days_known: number; share_on: number | null;
  per_series: Record<string, Eval>; lead_times: Record<string, Lead[]> };
type Bt = { computed_for: string; config_hash: string; label: string; caveats: string[]; params: Record<string, number>;
  window: { start: string | null; end: string | null; trading_days: number };
  series_status: Record<string, { status: string; days?: number; reason?: string; source?: string }>;
  excluded_indicators: { id: string; status: string }[];
  episodes: Record<string, { peak_date: string; trigger_date: string; trough_date: string; max_drawdown: number; recovered_date: string | null; peak_at_history_start: boolean }[]>;
  signals: Sig[];
  daily: { date: string; coverage: number; composite_partial: number | null; close: Record<string, number | null> }[];
  history_monthly: { date: string; coverage: number; composite_partial: number | null; score_low: number; score_high: number }[] };

const pct = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
const STAT: Record<string, string> = { small_sample: "text-term-amber", no_variation: "text-term-muted", insufficient_data: "text-term-down", computed: "text-white" };

export default function Backtest() {
  const [p, setP] = useState({ horizon: 20, drawdown: 0.1, composite_threshold: 60, indicator_threshold: 70 });
  const q = new URLSearchParams(Object.entries(p).map(([k, v]) => [k, String(v)])).toString();
  const { data: r, error, loading } = useApi<Bt>(`/api/backtest?${q}`);
  const [selRaw, setSel] = useState<string | null>(null);
  const sel = selRaw ?? (r && r.episodes["US_AI_BASKET"] ? "US_AI_BASKET" : "TW_BASKET");
  const daily = (r?.daily ?? []).map((d) => ({ date: d.date, composite: d.composite_partial, price: d.close[sel] ?? null }));
  const hist = (r?.history_monthly ?? []).map((h) => ({ ...h, band: [h.score_low, h.score_high], cov: h.coverage * 100 }));
  const series = r ? Object.keys(r.episodes) : [];
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">HISTORICAL SIGNAL BACKTEST (POINT-IN-TIME)</h1>
      <div className="panel p-3 border-term-down font-mono text-[11px] space-y-1">
        <div className="text-term-down">NOT EVIDENCE OF PREDICTIVE VALIDITY. {r?.label}</div>
        <ul className="list-disc ml-4 text-term-muted">{(r?.caveats ?? []).map((c) => <li key={c}>{c}</li>)}</ul>
      </div>
      {error ? <ApiError error={error} /> : null}<Loading show={loading} />
      <Panel title="PARAMETERS">
        <div className="flex flex-wrap gap-4 text-xs font-mono items-end">
          {([["horizon", "Forward window (trading days)", 1], ["drawdown", "Decline counted as hit (0–1)", 0.01],
            ["composite_threshold", "Composite ON if ≥", 1], ["indicator_threshold", "Indicator ON if ≥", 1]] as const).map(([k, l, st]) => (
            <label key={k} className="flex flex-col gap-1"><span className="text-term-muted">{l}</span>
              <input type="number" step={st} value={p[k]} onChange={(e) => { const v = parseFloat(e.target.value); if (!Number.isNaN(v)) setP({ ...p, [k]: v }); }}
                className="w-28 bg-black border border-term-border text-white px-1 py-0.5 text-right" /></label>))}
          <a className="btn" href={STATIC ? staticCsv("backtest_default.csv") : `${API_BASE}/api/backtest.csv?${q}`}>DOWNLOAD CSV (daily)</a>
          <span className="text-term-muted">window {r?.window.start ?? "—"} → {r?.window.end ?? "—"} · {r?.window.trading_days ?? 0} trading days · config {r?.config_hash}</span>
        </div>
      </Panel>
      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="OUTCOME SERIES">
          <table className="w-full text-[11px] font-mono"><tbody>{r && Object.entries(r.series_status).map(([k, v]) => (
            <tr key={k} className="border-t border-term-border"><td>{k}</td><td className={v.status === "ok" ? "text-term-up" : "text-term-down"}>{v.status.toUpperCase()}</td>
              <td className="text-term-muted">{v.days != null ? `${v.days} days · ` : ""}{v.source ?? v.reason}</td></tr>))}</tbody></table>
          <div className="text-[10px] text-term-muted font-mono mt-2">Excluded from point-in-time reconstruction (range widened, never scored as 0):{" "}
            {r?.excluded_indicators.map((x) => `${x.id} (${x.status})`).join(", ")}</div>
        </Panel>
        <Panel title={`PIT COMPOSITE (PARTIAL COVERAGE) vs ${sel} CLOSE`}>
          <div className="flex gap-1 mb-1">{series.map((s) => <button key={s} className={`btn ${s === sel ? "!bg-term-amber !text-black" : ""}`} onClick={() => setSel(s)}>{s}</button>)}</div>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={daily}><CartesianGrid stroke="#222" /><XAxis dataKey="date" tick={{ fontSize: 9 }} minTickGap={40} />
              <YAxis yAxisId="s" domain={[0, 100]} tick={{ fontSize: 9 }} /><YAxis yAxisId="p" orientation="right" tick={{ fontSize: 9 }} domain={["auto", "auto"]} />
              <Tooltip contentStyle={{ background: "#000", fontSize: 11 }} />
              <Line {...ANIM} yAxisId="s" dataKey="composite" stroke="#ffb000" dot={false} name="composite (partial)" connectNulls={false} />
              <Line {...ANIM} yAxisId="p" dataKey="price" stroke="#4aa3ff" dot={false} name={`${sel} close`} />
            </ComposedChart>
          </ResponsiveContainer>
        </Panel>
      </div>
      <Panel title="SIGNAL EVALUATION — hit = signal ON and close falls ≥ X% within H trading days">
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted"><tr><th className="text-left">signal</th><th>series</th><th>status</th><th>days known</th><th>~indep. windows</th>
            <th>ON days</th><th>hit rate ON</th><th>95% CI (overlap-adj.)</th><th>hit rate OFF</th><th>base rate</th><th className="text-left">note</th></tr></thead>
          <tbody>{r?.signals.map((s) => s.status !== "computed" ? (
            <tr key={s.id} className="border-t border-term-border"><td>{s.id} <span className="text-term-muted">≥{s.threshold}</span></td><td>all</td>
              <td className="text-term-down">INSUFFICIENT DATA</td><td colSpan={8} className="text-term-muted">{s.reason}</td></tr>
          ) : Object.entries(s.per_series).map(([k, e], i) => (
            <tr key={s.id + k} className="border-t border-term-border text-center">
              <td className="text-left">{i === 0 ? <>{s.id} <span className="text-term-muted">≥{s.threshold} · ON {pct(s.share_on, 0)}</span></> : ""}</td>
              <td>{k}</td><td className={STAT[e.status]}>{e.status.toUpperCase()}</td><td>{e.n_signal_known_days}</td><td>{e.n_independent_windows}</td>
              <td>{e.n_on ?? "—"}</td><td>{pct(e.hit_rate_on)}</td><td>{e.ci95_on_overlap_adjusted ? `${pct(e.ci95_on_overlap_adjusted[0], 0)}–${pct(e.ci95_on_overlap_adjusted[1], 0)}` : "—"}</td>
              <td>{pct(e.hit_rate_off)}</td><td>{pct(e.base_rate)}</td><td className="text-left text-term-muted">{e.reason}</td></tr>)))}</tbody></table></div>
      </Panel>
      <Panel title={`CORRECTION EPISODES — ${sel} (≥ X% from running peak, within available history) AND SIGNAL LEAD TIMES · pick series above`}>
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted"><tr><th className="text-left">series</th><th>peak</th><th>confirmed (≤ −X%)</th><th>max DD</th>
            {r?.signals.filter((s) => s.status === "computed").map((s) => <th key={s.id} title={s.name} className="max-w-[90px] break-words">{s.id.replace(/_/g, " ")}</th>)}</tr></thead>
          <tbody>{series.filter((k) => k === sel).flatMap((k) => (r?.episodes[k] ?? []).map((ep, j) => (
            <tr key={k + j} className="border-t border-term-border text-center"><td className="text-left">{k}</td>
              <td>{ep.peak_date}{ep.peak_at_history_start ? " *" : ""}</td><td>{ep.trigger_date}</td><td className="text-term-down">{pct(ep.max_drawdown)}</td>
              {r?.signals.filter((s) => s.status === "computed").map((s) => { const l = s.lead_times[k]?.[j];
                return <td key={s.id} className={l?.status === "preceded" ? "text-white" : "text-term-muted"}>
                  {!l ? "—" : l.status === "preceded" ? `${l.left_censored ? "≥" : ""}${l.lead_days_to_trigger}d` : l.status === "no_preceding_signal" ? "no signal" : "insufficient"}</td>; })}
            </tr>)))}</tbody></table></div>
        <div className="text-[10px] text-term-muted font-mono mt-2">Lead = calendar days from start of the signal&apos;s ON run to the confirmation date. “≥” = signal already ON on the first evaluable day (left-censored).
          A signal that was ON for most of the window “precedes” almost every episode by construction — compare with the ON share and base rate before reading anything into it. * peak on first day of stored history.</div>
      </Panel>
      <Panel title="LONG-RUN POINT-IN-TIME COMPOSITE (month-end, since 2010) — context only; outcomes start with stored prices (US 2015, TWSE ~13 months)">
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={hist}><CartesianGrid stroke="#222" /><XAxis dataKey="date" tick={{ fontSize: 9 }} minTickGap={40} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 9 }} /><Tooltip contentStyle={{ background: "#000", fontSize: 11 }} />
            <Area {...ANIM} dataKey="band" stroke="none" fill="#ffb000" fillOpacity={0.12} name="range if missing = 0…100" />
            <Line {...ANIM} dataKey="composite_partial" stroke="#ffb000" dot={false} name="composite (partial)" />
            <Line {...ANIM} dataKey="cov" stroke="#888" strokeDasharray="3 3" dot={false} name="coverage %" />
          </ComposedChart>
        </ResponsiveContainer>
      </Panel>
      <Hypothesis>Methodology: for each date d, every indicator reading the observations table is recomputed with only rows whose publication_date ≤ d, using the
        version current on d (later revisions invisible). The official risk score requires coverage ≥ min_coverage and is withheld at every past date, so the
        &quot;composite (partial)&quot; uses only available point-in-time indicators and is NOT the published risk score. Outcomes use realized TWSE closes and, when stored, split-adjusted US closes (Tiingo, price return only, no dividends); US tickers were chosen with hindsight.
        Overlapping windows mean far fewer independent observations than days. Full notes: /methodology.</Hypothesis>
    </div>
  );
}
