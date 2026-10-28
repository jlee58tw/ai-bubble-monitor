// Static-snapshot data layer (GitHub Pages build). Answers apiGet() paths from JSON baked by
// scripts/pages/bake_snapshot.py instead of the live API. Read-only; never contains secrets.
export const STATIC = process.env.NEXT_PUBLIC_STATIC_SNAPSHOT === "1";
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const ROOT = `${BASE_PATH}/snapshot`;

// Must match key_for() in scripts/pages/bake_snapshot.py.
export function keyFor(path: string): string {
  const [p, qs = ""] = path.split("?");
  const sp = new URLSearchParams(qs);
  const q = Array.from(sp.entries()).sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)).map(([k, v]) => `${k}=${v}`).join("&");
  const base = p.replace(/^\/+/, "").replace(/\//g, "_");
  return (q ? `${base}__${q}` : base).replace(/[^A-Za-z0-9.,=-]/g, "_") + ".json";
}

const cache = new Map<string, Promise<unknown>>();
function getJson<T>(url: string): Promise<T> {
  if (!cache.has(url)) {
    cache.set(url, fetch(url).then((r) => {
      if (!r.ok) throw new Error(`not included in the static snapshot (${r.status})`);
      return r.json();
    }));
  }
  return cache.get(url) as Promise<T>;
}

type ObsLike = { metric_id: string; entity_id: string; period_end: string; version: number; classification: string };
type ObsIndex = Record<string, Record<string, number[]>>;

async function observations(sp: URLSearchParams): Promise<ObsLike[]> {
  const idx = await getJson<ObsIndex>(`${ROOT}/obs/index.json`);
  const split = (k: string) => (sp.get(k) || "").split(",").map((s) => s.trim()).filter(Boolean);
  const metrics = split("metric_id").length ? split("metric_id") : Object.keys(idx);
  const ents = split("entity_id");
  const start = sp.get("start") || ""; const end = sp.get("end") || "";
  const cls = sp.get("classification") || "";
  const limit = Number(sp.get("limit") || 5000);
  if (sp.get("as_of") || sp.get("include_history") === "true") throw new Error("as_of / include_history are not available in the static snapshot");
  const sy = start ? Number(start.slice(0, 4)) : -Infinity; const ey = end ? Number(end.slice(0, 4)) : Infinity;
  const urls: string[] = [];
  for (const m of metrics) {
    const byEnt = idx[m] || {};
    for (const e of ents.length ? ents : Object.keys(byEnt)) {
      for (const y of byEnt[e] || []) if (y >= sy && y <= ey) urls.push(`${ROOT}/obs/${m}/${e}/${y}.json`);
    }
  }
  const parts = await Promise.all(urls.map((u) => getJson<ObsLike[]>(u)));
  const rows = parts.flat().filter((o) => (!start || o.period_end >= start) && (!end || o.period_end <= end) && (!cls || o.classification === cls));
  const c = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
  rows.sort((a, b) => c(a.metric_id, b.metric_id) || c(a.entity_id, b.entity_id) || c(a.period_end, b.period_end) || a.version - b.version);
  return rows.slice(0, limit);
}

// Pure formula (mirrors backend/app/services/roi.py); no stored data involved.
function roi(sp: URLSearchParams) {
  const D: Record<string, number> = { success_probability: 0.6, review_minutes: 15, reviewer_hourly_rate: 60, inference_cost: 0.5, tool_cost: 0.1,
    rework_cost: 20, rework_share: 0.7, failure_recovery_cost: 40, baseline_human_cost: 30, task_volume: 1000 };
  const x: Record<string, number> = {};
  for (const k of Object.keys(D)) { const v = sp.get(k); x[k] = v === null ? D[k] : Number(v); }
  for (const k of ["success_probability", "rework_share"]) if (!(x[k] >= 0 && x[k] <= 1)) throw new Error(`${k} must be between 0 and 1`);
  for (const k of Object.keys(x)) if (!(x[k] >= 0)) throw new Error(`${k} must be >= 0`);
  const p = x.success_probability, s = x.rework_share;
  const review = (x.review_minutes / 60) * x.reviewer_hourly_rate;
  const rework = (1 - p) * s * x.rework_cost;
  const failure = (1 - p) * (1 - s) * x.failure_recovery_cost;
  const etc = x.inference_cost + x.tool_cost + review + rework + failure;
  const b = x.baseline_human_cost;
  const fixed = x.inference_cost + x.tool_cost + review;
  const k = s * x.rework_cost + (1 - s) * x.failure_recovery_cost;
  let be: number | null = null; let note: string | null = null;
  if (k > 0) { be = 1 - (b - fixed) / k; note = be <= 0 ? "always profitable (even at p=0)" : be > 1 ? "never breaks even (even at p=1)" : null; }
  else note = "failure costs are zero: ROI does not depend on p" + (b > fixed ? "" : " (and never breaks even)");
  return getJson<{ formulas: unknown; assumptions: unknown }>(`${ROOT}/api/${keyFor("/api/roi")}`).then((d) => ({
    inputs: x,
    per_task: { ai_inference_cost: x.inference_cost, tool_cost: x.tool_cost, human_review_cost: review, expected_rework_cost: rework,
      expected_failure_loss: failure, effective_task_cost: etc, baseline_human_cost: b },
    effective_roi: b > 0 ? (b - etc) / b : null,
    totals: { effective_task_cost: etc * x.task_volume, baseline_human_cost: b * x.task_volume, net_savings: (b - etc) * x.task_volume },
    break_even_success_probability: be, break_even_note: note, formulas: d.formulas, assumptions: d.assumptions,
  }));
}

export async function staticGet<T>(path: string): Promise<T> {
  const [p, qs = ""] = path.split("?");
  const sp = new URLSearchParams(qs);
  if (p === "/api/observations") return (await observations(sp)) as T;
  if (p === "/api/roi") return (await roi(sp)) as T;
  try {
    return await getJson<T>(`${ROOT}/api/${keyFor(path)}`);
  } catch {
    throw new Error(`STATIC SNAPSHOT: ${path} was not baked (only the default parameters / listed options are included; run the app locally for other inputs)`);
  }
}

export function staticCsv(name: string): string {
  return `${ROOT}/csv/${name}`;
}
