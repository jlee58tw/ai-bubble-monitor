"use client";
import { useState } from "react";
import { Hypothesis, Loading, Panel, tsTaipei } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";

type Ev = { id: number; entity_id: string; form: string; event_type: string; accession_number: string; observation_date: string | null;
  publication_date: string; lag_days: number | null; acceptance_datetime_utc: string | null; items: string | null; source_url: string;
  observations_from_filing: number };
type Resp = { events: Ev[]; coverage: { entity_id: string; earliest_filing: string; latest_filing: string; events: number; note: string }[];
  not_connected: { entity_id: string; name: string; reason: string }[]; last_run: { status: string; started_at: string; message: string | null } | null;
  source: string; definitions: Record<string, string> };
type G = { status: string; reason: string | null; items: Record<string, unknown>[] };

export default function Events() {
  const [ent, setEnt] = useState(""); const [typ, setTyp] = useState("");
  const q = new URLSearchParams({ ...(ent ? { entity_id: ent } : {}), ...(typ ? { event_type: typ } : {}), limit: "400" }).toString();
  const { data: r, error, loading } = useApi<Resp>(`/api/events?${q}`);
  const g = useApi<G>("/api/guidance");
  return (
    <div className="space-y-4">
      <h1 className="font-mono text-term-amber text-lg">EARNINGS &amp; FILING EVENTS</h1>
      <p className="text-[10px] text-term-muted font-mono">Source: {r?.source}. Last fetch: {r?.last_run ? `${r.last_run.status.toUpperCase()} ${tsTaipei(r.last_run.started_at)}` : "never"}.
        Observation date = period end / event date; publication date = EDGAR filing date (what the point-in-time engine uses).</p>
      {error ? <ApiError error={error} /> : null}<Loading show={loading} />
      <div className="grid gap-3 lg:grid-cols-3">
        <Panel title="COVERAGE (stored events per company)">
          <table className="w-full text-[11px] font-mono"><tbody>{r?.coverage.map((c) => (
            <tr key={c.entity_id} className="border-t border-term-border"><td>{c.entity_id}</td><td>{c.earliest_filing} → {c.latest_filing}</td><td className="text-right">{c.events}</td></tr>))}
            {r?.not_connected.map((c) => <tr key={c.entity_id} className="border-t border-term-border text-term-down"><td>{c.entity_id}</td><td colSpan={2}>UNAVAILABLE — {c.reason}</td></tr>)}</tbody></table>
          <div className="text-[10px] text-term-muted font-mono mt-1">{r?.coverage[0]?.note}</div>
        </Panel>
        <Panel title="GUIDANCE" className="lg:col-span-2">
          {g.data?.status === "placeholder" ? <div className="text-xs font-mono"><span className="text-term-amber">[PLACEHOLDER]</span> {g.data.reason}</div>
            : <pre className="text-[10px]">{JSON.stringify(g.data?.items, null, 1)}</pre>}
          <div className="text-[10px] text-term-muted font-mono mt-2">{r && Object.entries(r.definitions).map(([k, v]) => <div key={k}><b>{k}</b>: {v}</div>)}</div>
        </Panel>
      </div>
      <Panel title={`EVENTS (${r?.events.length ?? 0})`}>
        <div className="flex gap-2 mb-2 text-xs font-mono">
          <select value={ent} onChange={(e) => setEnt(e.target.value)} className="bg-black border border-term-border px-1"><option value="">all companies</option>
            {r?.coverage.map((c) => <option key={c.entity_id}>{c.entity_id}</option>)}</select>
          <select value={typ} onChange={(e) => setTyp(e.target.value)} className="bg-black border border-term-border px-1"><option value="">all types</option>
            <option value="periodic_report">periodic_report (10-Q/10-K/20-F)</option><option value="earnings_release_8k">earnings_release_8k (8-K Item 2.02)</option></select>
        </div>
        <div className="overflow-x-auto max-h-[600px]"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted sticky top-0 bg-black"><tr><th className="text-left">company</th><th>form</th><th>type</th><th>observation date</th><th>publication date</th>
            <th>lag (days)</th><th>accepted (Taipei)</th><th>8-K items</th><th>stored obs. from filing</th><th>source</th></tr></thead>
          <tbody>{r?.events.map((e) => (
            <tr key={e.id} className="border-t border-term-border text-center"><td className="text-left">{e.entity_id}</td><td>{e.form}</td><td>{e.event_type}</td>
              <td>{e.observation_date ?? "—"}</td><td className="text-white">{e.publication_date}</td><td>{e.lag_days ?? "—"}</td>
              <td>{e.acceptance_datetime_utc ? tsTaipei(e.acceptance_datetime_utc) : "—"}</td><td>{e.items ?? ""}</td>
              <td>{e.observations_from_filing || "—"}</td><td><a className="src" href={e.source_url} target="_blank" rel="noreferrer">EDGAR</a></td></tr>))}</tbody></table></div>
      </Panel>
      <Hypothesis>Earnings-release 8-Ks are identified only by EDGAR&apos;s Item 2.02 tag; their content (including any guidance) is not parsed.
        Guidance figures will only appear with a source URL and verbatim quote; none are inferred or estimated.</Hypothesis>
    </div>
  );
}
