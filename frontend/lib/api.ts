export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type Classification = "reported" | "guidance" | "estimated" | "derived" | "qualitative";

export interface Observation {
  id: number; metric_id: string; entity_id: string; value: number; unit: string;
  fiscal_period: string | null; period_start: string | null; period_end: string; observation_date: string;
  publication_date: string; ingestion_ts: string; source_url: string | null; source_type: string;
  classification: Classification; confidence: "high" | "medium" | "low"; methodology: string | null;
  source_ref: string | null; version: number; supersedes_id: number | null;
}
export interface MetricDef {
  id: string; name: string; description: string; unit: string; frequency: string; category: string;
  default_classification: Classification; provider: string | null; status: "connected" | "unavailable" | "placeholder";
  is_ai_specific: boolean; warning: string | null; methodology: string | null; entities: string[]; observation_rows: number;
}
export interface Card {
  metric_id: string; metric_name: string; entity_id: string; unit: string;
  status: "connected" | "unavailable" | "placeholder" | "missing"; warning: string | null; is_ai_specific: boolean;
  current: Observation | null; previous: Observation | null; abs_change: number | null; pct_change: number | null;
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${path}`);
  return r.json();
}
export async function apiPost<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { method: "POST" });
  if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json();
}
