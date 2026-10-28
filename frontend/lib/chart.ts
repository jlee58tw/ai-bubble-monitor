/** 全站統一的圖表配色與樣式（跟隨深／淺色主題）。 */
export const PALETTE = ["#60aaff", "#f59e0b", "#a78bfa", "#34d399", "#f472b6", "#22d3ee", "#fb923c", "#e879f9", "#a3e635", "#94a3b8"];
export const TT = {
  contentStyle: { background: "var(--tt-bg)", border: "1px solid var(--tt-border)", borderRadius: 10, fontSize: 12, boxShadow: "0 8px 24px rgba(0,0,0,.25)" },
  labelStyle: { color: "rgb(var(--c-strong))", fontWeight: 600 },
  itemStyle: { color: "rgb(var(--c-fg))" },
  cursor: { stroke: "var(--tt-border)", strokeWidth: 1 },
};
export const GRID = "var(--grid)";
export const TICK = { fill: "var(--tick)", fontSize: 11 };
export const ANIM = { isAnimationActive: true, animationDuration: 900, animationEasing: "ease-out" as const };
/** 圖表 Y 軸：美元 → 億美元 */
export const yiTick = (v: number) => `${Math.round(v / 1e8).toLocaleString("zh-TW")} 億`;
