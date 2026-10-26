"use client";
import { Loading, Panel, SourceStatus } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";

type Row = { id: number; model: string; harness: string | null; value: number; ci_low: number | null; ci_high: number | null; result_date: string | null; source_url: string; extra: Record<string, unknown> | null };
type Group = { benchmark: string; benchmark_version: string; split: string; metric: string; n: number; latest_result_date: string | null; note: string | null; rows: Row[] };
type Resp = { groups: Group[]; sources: Record<string, { last_status: string; last_success_at: string | null; message: string | null }> };
const fmt = (m: string, v: number) => (m.endsWith("_min") ? (v >= 60 ? `${(v / 60).toFixed(1)} h` : `${v.toFixed(1)} min`) : `${v.toFixed(2)}%`);

export default function Benchmarks() {
  const { data, error } = useApi<Resp>("/api/benchmarks");
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">AGENT RELIABILITY BENCHMARKS</h1>
      <div className="panel p-2 text-[11px] text-term-amber font-mono">⚠ Each table is one benchmark × version × split × metric. Scores are NEVER compared or ranked across tables — different task sets, harnesses and metrics.</div>
      {error ? <ApiError error={error} /> : null}
      <SourceStatus sources={data?.sources} />
      <Loading show={!data && !error} />
      <div className="grid gap-3 xl:grid-cols-2">
        {(data?.groups ?? []).map((g) => (
          <Panel key={`${g.benchmark}|${g.benchmark_version}|${g.split}|${g.metric}`}
            title={`${g.benchmark.toUpperCase()} · ${g.benchmark_version}${g.split !== "-" ? ` · ${g.split}` : ""} · ${g.metric} (n=${g.n}, latest ${g.latest_result_date ?? "—"})`}>
            <p className="text-[10px] text-term-muted mb-1">{g.note}</p>
            <table className="w-full text-[11px] font-mono">
              <thead className="text-term-muted text-left"><tr><th>#</th><th>model</th><th>harness / agent</th><th className="text-right">value</th><th className="text-right">95% CI</th><th>date</th></tr></thead>
              <tbody>{g.rows.slice(0, 12).map((r, i) => (
                <tr key={r.id} className="border-t border-term-border" title={r.extra ? JSON.stringify(r.extra).slice(0, 400) : ""}>
                  <td className="text-term-muted">{i + 1}</td><td className="text-white">{r.model}</td>
                  <td className="text-term-muted max-w-[220px] truncate">{r.harness ?? "—"}</td>
                  <td className="text-right text-white">{fmt(g.metric, r.value)}</td>
                  <td className="text-right text-term-muted">{r.ci_low !== null && r.ci_high !== null ? `${fmt(g.metric, r.ci_low)}–${fmt(g.metric, r.ci_high)}` : "—"}</td>
                  <td className="text-term-muted">{r.result_date ?? "—"}</td>
                </tr>))}</tbody>
            </table>
            <a className="src text-[10px]" href={g.rows[0]?.source_url} target="_blank" rel="noreferrer">source ↗</a>
          </Panel>))}
      </div>
    </div>
  );
}
