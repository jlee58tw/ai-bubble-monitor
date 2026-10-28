import type { Classification } from "@/lib/api";
import { CLS_HELP, CLS_ZH, CONF_ZH, st } from "@/lib/i18n";

const CLS: Record<string, string> = {
  reported: "border-emerald-400/70 text-term-up bg-emerald-500/10", derived: "border-sky-400/70 text-term-info bg-sky-500/10",
  guidance: "border-purple-400/70 text-purple-400 bg-purple-500/10", estimated: "border-orange-400/70 text-orange-400 bg-orange-500/10",
  qualitative: "border-pink-400/70 text-pink-400 bg-pink-500/10", disclosed: "border-yellow-400/70 text-yellow-500 bg-yellow-500/10",
};
export function ClassBadge({ c }: { c: Classification | string }) {
  return <span title={CLS_HELP[c] ?? c} className={`px-1.5 py-px rounded-full text-[10px] border whitespace-nowrap ${CLS[c] ?? "border-term-border"}`}>{CLS_ZH[c] ?? c}</span>;
}
const G = "bg-emerald-500/15 text-term-up", R = "bg-red-500/15 text-term-down", Y = "bg-amber-500/15 text-term-amber", B = "bg-sky-500/15 text-term-info", Z = "bg-zinc-500/15 text-term-muted";
const ST: Record<string, string> = {
  connected: G, fresh: G, success: G, ok: G, current: G, computed: G,
  unavailable: R, missing: R, failed: R, warning: R, error: R,
  stale: Y, partial: Y, insufficient: Y, insufficient_data: Y, withheld: Y, small_sample: Y, no_variation: Y, skipped: Y,
  running: B, scheduled: B, info: B, placeholder: Z, documented_history: "bg-purple-500/15 text-purple-400", not_point_in_time: Z,
};
export function StatusPill({ s }: { s: string | null }) {
  return <span className={`px-2 py-0.5 rounded-full text-[10px] whitespace-nowrap ${ST[s ?? ""] ?? Z}`}>{st(s)}</span>;
}
export function ConfBadge({ c }: { c: string }) {
  return <span className="text-[10px] text-term-muted whitespace-nowrap" title="資料可信度">可信度：{CONF_ZH[c] ?? c}</span>;
}
