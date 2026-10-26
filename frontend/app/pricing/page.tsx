"use client";
import { useMemo, useState } from "react";
import { StatusPill } from "@/components/Badges";
import { Loading, Panel, SourceStatus, tsTaipei } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";

type Row = { id: number; vendor: string; model_id: string; model_label: string; tier: string; price_type: string; usd_per_mtok: number;
  price_status: string; effective_from: string | null; effective_to: string | null; first_seen_at: string; last_seen_at: string;
  source_url: string; raw_text: string | null; note: string | null; open_weight: boolean };
type Resp = { rows: Row[]; notes: string[]; sources: Record<string, { last_status: string; last_success_at: string | null; message: string | null }> };
const VENDORS = ["openai", "anthropic", "google", "openrouter"];
const TYPES = ["input", "output", "cached_input"];

export default function Pricing() {
  const [vendor, setVendor] = useState("anthropic");
  const [q, setQ] = useState("");
  const { data, error } = useApi<Resp>(`/api/model-prices?vendor=${vendor}`);
  const grouped = useMemo(() => {
    const m = new Map<string, { label: string; tier: string; status: string; ef: string | null; et: string | null; first: string; url: string; raw: string[]; note: string | null; p: Record<string, number> }>();
    (data?.rows ?? []).filter((r) => !q || r.model_id.toLowerCase().includes(q.toLowerCase()) || r.model_label.toLowerCase().includes(q.toLowerCase())).forEach((r) => {
      const k = `${r.model_id}|${r.tier}|${r.price_status}|${r.effective_from}`;
      const g = m.get(k) ?? { label: r.model_label, tier: r.tier, status: r.price_status, ef: r.effective_from, et: r.effective_to, first: r.first_seen_at, url: r.source_url, raw: [], note: r.note, p: {} };
      g.p[r.price_type] = r.usd_per_mtok; if (r.price_status !== "current" && r.raw_text) g.raw.push(r.raw_text);
      m.set(k, g);
    });
    return [...m.entries()];
  }, [data, q]);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="font-mono text-term-amber text-lg">MODEL API PRICING</h1>
        {VENDORS.map((v) => <button key={v} className={`btn ${v === vendor ? "text-term-amber border-term-amber" : ""}`} onClick={() => setVendor(v)}>{v}{v === "openrouter" ? " (open-weight)" : ""}</button>)}
        <input placeholder="filter model…" value={q} onChange={(e) => setQ(e.target.value)} className="bg-black border border-term-border text-white text-xs px-1 py-0.5 font-mono" />
      </div>
      {error ? <ApiError error={error} /> : null}
      <SourceStatus sources={data?.sources} />
      <Panel title={`${vendor.toUpperCase()} · USD PER 1M TOKENS (LIST / STANDARD TIER, AS PUBLISHED)`}>
        <Loading show={!data && !error} />
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted text-left"><tr><th>model</th><th>tier</th><th>status</th>{TYPES.map((t) => <th key={t} className="text-right">{t}</th>)}<th>effective</th><th>first observed</th><th>source</th></tr></thead>
          <tbody>{grouped.map(([k, g]) => (
            <tr key={k} className="border-t border-term-border align-top" title={g.raw.join(" | ") || g.note || ""}>
              <td className="text-white">{g.label}</td><td className="text-term-muted">{g.tier}</td><td><StatusPill s={g.status} /></td>
              {TYPES.map((t) => <td key={t} className="text-right">{g.p[t] !== undefined ? `$${g.p[t]}` : "—"}</td>)}
              <td className="text-term-muted">{g.ef || g.et ? `${g.ef ?? "…"} → ${g.et ?? "…"}` : "—"}</td>
              <td className="text-term-muted">{tsTaipei(g.first)}</td>
              <td><a className="src" href={g.url} target="_blank" rel="noreferrer">↗</a></td>
            </tr>))}</tbody>
        </table></div>
        {data && grouped.length === 0 ? <div className="text-term-down font-mono text-xs p-2">NO DATA (source not fetched or blocked).</div> : null}
      </Panel>
      <div className="text-[10px] text-term-muted font-mono space-y-1">
        {(data?.notes ?? []).map((n) => <p key={n}>{n}</p>)}
        <p>SCHEDULED = future price stated on the vendor page; DOCUMENTED_HISTORY = past price stated in the vendor's own docs (hover row for the quoted text). No other historical prices are shown — this app only knows prices from its first observation onward. OpenRouter rows are models with a Hugging Face id (open weights); OpenRouter routes to third-party hosts, prices shown are OpenRouter's listed price.</p>
      </div>
    </div>
  );
}
