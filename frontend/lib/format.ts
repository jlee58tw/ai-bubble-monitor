import { fmtObs, num, pctZh } from "./i18n";
/** 依單位格式化（中文單位：億美元、新台幣、倍、%）。資料本身不變。 */
export function fmtValue(v: number | null | undefined, unit: string): string { return fmtObs(v, unit); }
export function fmtChange(v: number | null, unit: string): string {
  if (v === null || v === undefined) return "—";
  const s = v > 0 ? "+" : "";
  if (unit === "pct") return `${s}${num(v * 100, 1)} 個百分點`;
  if (unit === "pct_points") return `${s}${num(v, 2)} 個百分點`;
  if (unit === "ratio") return `${s}${num(v, 3)} 倍`;
  return `${s}${fmtObs(v, unit)}`;
}
export const fmtPct = (v: number | null) => pctZh(v, 1, true);
export const changeColor = (v: number | null) => (v === null ? "text-term-muted" : v > 0 ? "text-term-up" : v < 0 ? "text-term-down" : "");
