"use client";
import { DIM_ZH, riskLevel } from "@/lib/i18n";
import { Info } from "./Panel";

export type Dim = { id: string; name: string; weight: number; coverage: number; score: number | null; indicators: { status: string }[] };

/** 六大維度彩色長條：沒有分數的維度明確顯示「無資料」，不畫成 0。 */
export default function DimBars({ dims }: { dims: Dim[] }) {
  return (
    <div className="space-y-3">
      {dims.map((d, i) => {
        const lv = riskLevel(d.score), z = DIM_ZH[d.id];
        return (
          <div key={d.id} className="animate-fade-up" style={{ animationDelay: `${i * 80}ms` }}>
            <div className="flex items-center gap-2 text-[13px]">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: lv.hex }} />
              <span className="font-semibold">{z?.name ?? d.name}</span>{z ? <Info text={z.plain} /> : null}
              <span className="ml-auto font-mono font-bold" style={{ color: lv.hex }}>{d.score != null ? d.score.toFixed(1) : "無資料"}</span>
              <span className="text-[11px] px-1.5 rounded-full" style={{ background: `${lv.hex}22`, color: lv.hex }}>{lv.label}</span>
            </div>
            <div className="relative h-3 mt-1 rounded-full bg-term-border/70 overflow-hidden">
              {d.score != null
                ? <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${Math.max(d.score, 1.5)}%`, background: `linear-gradient(90deg, #22c55e, ${lv.hex})` }} />
                : <div className="h-full w-full bg-[repeating-linear-gradient(45deg,transparent,transparent_6px,rgba(148,163,184,.25)_6px,rgba(148,163,184,.25)_12px)]" title="無資料（不是 0 分）" />}
            </div>
            <div className="text-[11px] text-term-muted mt-0.5">權重 {d.weight}% · 覆蓋率 {(d.coverage * 100).toFixed(0)}%{d.score == null ? " · 可用指標不足，不給分（不代表零風險）" : ""}</div>
          </div>);
      })}
    </div>
  );
}
