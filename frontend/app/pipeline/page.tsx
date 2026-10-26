"use client";
import { StatusPill } from "@/components/Badges";
import { ApiError, useApi } from "@/components/useApi";
import type { MetricDef } from "@/lib/api";

interface Status {
  refresh_in_progress: boolean;
  providers: { provider: string; configured: boolean; reason: string | null; last_run_status: string | null; last_run_at: string | null; last_success_at: string | null }[];
  series: { metric_id: string; entity_id: string; metric_status: string; state: string; latest_period_end: string | null; latest_publication_date: string | null; last_ingested_at: string | null; rows: number }[];
}
interface Run { id: number; provider: string; trigger: string; status: string; started_at: string; finished_at: string | null; records_fetched: number; records_inserted: number; records_revised: number; records_unchanged: number; error_count: number; message: string | null }
interface Err { id: number; run_id: number; created_at: string; level: string; entity_id: string | null; metric_id: string | null; message: string }

export default function Pipeline() {
  const st = useApi<Status>("/api/ingestion/status");
  const runs = useApi<Run[]>("/api/ingestion/runs?limit=20");
  const errs = useApi<Err[]>("/api/ingestion/errors?limit=50");
  const metrics = useApi<MetricDef[]>("/api/metrics");
  if (st.error) return <ApiError error={st.error} />;
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">DATA SOURCES & PIPELINE HEALTH</h1>
      <section className="panel p-3">
        <h2 className="font-mono text-xs text-term-amber mb-2">PROVIDERS</h2>
        <table className="w-full text-[11px] font-mono"><thead className="text-term-muted text-left"><tr><th>provider</th><th>configured</th><th>last run</th><th>last run at (UTC)</th><th>last success (UTC)</th><th>note</th></tr></thead>
          <tbody>{st.data?.providers.map((p) => (
            <tr key={p.provider} className="border-t border-term-border"><td>{p.provider}</td><td><StatusPill s={p.configured ? "connected" : "unavailable"} /></td>
              <td><StatusPill s={p.last_run_status} /></td><td>{p.last_run_at ?? "never"}</td><td>{p.last_success_at ?? "never"}</td><td className="text-term-muted">{p.reason}</td></tr>))}
          </tbody></table>
      </section>
      <section className="panel p-3">
        <h2 className="font-mono text-xs text-term-amber mb-2">METRIC REGISTRY</h2>
        <table className="w-full text-[11px] font-mono"><thead className="text-term-muted text-left"><tr><th>id</th><th>status</th><th>provider</th><th>class</th><th>AI-specific</th><th>rows</th><th>warning</th></tr></thead>
          <tbody>{metrics.data?.map((m) => (
            <tr key={m.id} className="border-t border-term-border" title={m.description}><td>{m.id}</td><td><StatusPill s={m.status} /></td><td>{m.provider ?? "—"}</td>
              <td>{m.default_classification}</td><td>{m.is_ai_specific ? "yes" : "no"}</td><td>{m.observation_rows}</td><td className="text-term-amber">{m.warning}</td></tr>))}
          </tbody></table>
      </section>
      <section className="panel p-3">
        <h2 className="font-mono text-xs text-term-amber mb-2">SERIES FRESHNESS (stale: quarterly &gt; 120d since period end, daily &gt; 7d)</h2>
        <div className="grid gap-1 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
          {st.data?.series.map((s) => (
            <div key={s.metric_id + s.entity_id} className="flex items-center gap-2 text-[11px] font-mono border-b border-term-border py-0.5">
              <StatusPill s={s.state} /><span className="w-40 truncate">{s.metric_id}</span><span className="w-16">{s.entity_id}</span>
              <span className="text-term-muted">end {s.latest_period_end ?? "—"} · filed {s.latest_publication_date ?? "—"} · {s.rows} rows</span>
            </div>))}
        </div>
      </section>
      <section className="panel p-3">
        <h2 className="font-mono text-xs text-term-amber mb-2">INGESTION RUNS</h2>
        <table className="w-full text-[11px] font-mono"><thead className="text-term-muted text-left"><tr><th>#</th><th>provider</th><th>trigger</th><th>status</th><th>started (UTC)</th><th>fetched</th><th>new</th><th>revised</th><th>unchanged</th><th>errors</th><th>message</th></tr></thead>
          <tbody>{runs.data?.map((r) => (
            <tr key={r.id} className="border-t border-term-border"><td>{r.id}</td><td>{r.provider}</td><td>{r.trigger}</td><td><StatusPill s={r.status} /></td><td>{r.started_at}</td>
              <td>{r.records_fetched}</td><td>{r.records_inserted}</td><td>{r.records_revised}</td><td>{r.records_unchanged}</td><td>{r.error_count}</td><td className="text-term-muted">{r.message}</td></tr>))}
          </tbody></table>
      </section>
      <section className="panel p-3">
        <h2 className="font-mono text-xs text-term-amber mb-2">ERROR LOG</h2>
        {errs.data?.length === 0 ? <div className="text-[11px] text-term-muted font-mono">no errors recorded</div> : (
          <table className="w-full text-[11px] font-mono"><tbody>{errs.data?.map((e) => (
            <tr key={e.id} className="border-t border-term-border"><td>run {e.run_id}</td><td><StatusPill s={e.level === "error" ? "failed" : "partial"} /></td><td>{e.entity_id}</td><td>{e.metric_id}</td><td>{e.message}</td><td className="text-term-muted">{e.created_at}</td></tr>))}
          </tbody></table>)}
      </section>
      <p className="text-[10px] text-term-muted font-mono">Full source inventory, connectivity test results and limitations: docs/DATA_SOURCES.md</p>
    </div>
  );
}
