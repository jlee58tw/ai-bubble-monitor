export function fmtValue(v: number | null | undefined, unit: string): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (unit === "USD") {
    const a = Math.abs(v);
    if (a >= 1e9) return `${v < 0 ? "-" : ""}$${(a / 1e9).toFixed(2)}B`;
    if (a >= 1e6) return `${v < 0 ? "-" : ""}$${(a / 1e6).toFixed(1)}M`;
    return `$${v.toFixed(0)}`;
  }
  if (unit === "pct") return `${(v * 100).toFixed(1)}%`;
  if (unit === "ratio") return `${v.toFixed(3)}x`;
  if (unit === "pct_points") return `${v.toFixed(2)}%`;
  return v.toLocaleString();
}
export function fmtChange(v: number | null, unit: string): string {
  if (v === null || v === undefined) return "—";
  const s = v > 0 ? "+" : "";
  if (unit === "pct") return `${s}${(v * 100).toFixed(1)}pp`;
  if (unit === "pct_points") return `${s}${v.toFixed(2)}pp`;
  if (unit === "ratio") return `${s}${v.toFixed(3)}x`;
  return `${s}${fmtValue(v, unit)}`;
}
export const fmtPct = (v: number | null) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);
export const changeColor = (v: number | null) => (v === null ? "text-term-muted" : v > 0 ? "text-term-up" : v < 0 ? "text-term-down" : "");
