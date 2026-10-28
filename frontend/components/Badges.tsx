import type { Classification } from "@/lib/api";

const CLS: Record<string, string> = {
  reported: "border-term-up text-term-up", derived: "border-term-info text-term-info",
  guidance: "border-purple-400 text-purple-300", estimated: "border-orange-400 text-orange-300",
  qualitative: "border-pink-400 text-pink-300", disclosed: "border-yellow-400 text-yellow-300",
};
export function ClassBadge({ c }: { c: Classification | string }) {
  return <span className={`px-1 text-[10px] uppercase border font-mono ${CLS[c] ?? "border-term-border"}`}>{c}</span>;
}
const ST: Record<string, string> = {
  connected: "bg-green-900/40 text-term-up", fresh: "bg-green-900/40 text-term-up",
  unavailable: "bg-red-900/40 text-term-down", missing: "bg-red-900/40 text-term-down",
  placeholder: "bg-zinc-800 text-term-muted", stale: "bg-yellow-900/40 text-term-amber",
  success: "bg-green-900/40 text-term-up", partial: "bg-yellow-900/40 text-term-amber",
  failed: "bg-red-900/40 text-term-down", running: "bg-blue-900/40 text-term-info",
  skipped: "bg-zinc-800 text-term-amber", ok: "bg-green-900/40 text-term-up", insufficient: "bg-yellow-900/40 text-term-amber",
  current: "bg-green-900/40 text-term-up", scheduled: "bg-blue-900/40 text-term-info",
  documented_history: "bg-zinc-800 text-purple-300", warning: "bg-red-900/40 text-term-down", info: "bg-blue-900/40 text-term-info",
  withheld: "bg-yellow-900/40 text-term-amber",
};
export function StatusPill({ s }: { s: string | null }) {
  return <span className={`px-1.5 py-0.5 text-[10px] uppercase font-mono ${ST[s ?? ""] ?? "bg-zinc-800"}`}>{s ?? "n/a"}</span>;
}
export function ConfBadge({ c }: { c: string }) {
  return <span className="text-[10px] font-mono text-term-muted">conf:{c}</span>;
}
