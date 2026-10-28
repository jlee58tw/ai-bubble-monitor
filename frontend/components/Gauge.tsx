"use client";
import { useEffect, useState } from "react";
import { riskLevel } from "@/lib/i18n";

const BANDS = [{ from: 0, to: 40, c: "#22c55e" }, { from: 40, to: 60, c: "#eab308" }, { from: 60, to: 80, c: "#f97316" }, { from: 80, to: 100, c: "#ef4444" }];
const R = 120, CX = 150, CY = 150;
const pt = (v: number, r = R) => { const a = Math.PI * (1 - v / 100); return [CX + r * Math.cos(a), CY - r * Math.sin(a)]; };
const arc = (a: number, b: number, r = R) => { const [x1, y1] = pt(a, r), [x2, y2] = pt(b, r); return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`; };

/** 半圓儀表：風險分數（0–100）、可能範圍與覆蓋率。分數為 null 時顯示「暫不公布」而不是 0。 */
export default function Gauge({ score, low, high, coverage, minCoverage }: { score: number | null; low: number | null; high: number | null; coverage: number; minCoverage: number }) {
  const [shown, setShown] = useState(0);
  useEffect(() => { const t = setTimeout(() => setShown(score ?? 0), 80); return () => clearTimeout(t); }, [score]);
  const lv = riskLevel(score);
  const ang = -90 + (shown / 100) * 180;
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 300 175" className="w-full max-w-[420px]" role="img" aria-label={`風險分數 ${score ?? "暫不公布"}`}>
        <defs><filter id="glow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
        <path d={arc(0, 100)} stroke="var(--grid)" strokeWidth="26" fill="none" />
        {BANDS.map((b) => <path key={b.from} d={arc(b.from + 0.6, b.to - 0.6)} stroke={b.c} strokeOpacity={0.9} strokeWidth="22" fill="none" />)}
        {low != null && high != null ? <path d={arc(low, high, R - 22)} stroke="rgb(var(--c-info))" strokeOpacity={0.55} strokeWidth="6" strokeLinecap="round" fill="none" /> : null}
        {[0, 40, 60, 80, 100].map((v) => { const [x, y] = pt(v, R + 20); return <text key={v} x={x} y={y + 4} textAnchor="middle" fontSize="10" fill="var(--tick)">{v}</text>; })}
        {score != null ? (
          <g style={{ transform: `rotate(${ang}deg)`, transformOrigin: `${CX}px ${CY}px`, transition: "transform 1.4s cubic-bezier(.2,.8,.2,1)" }} filter="url(#glow)">
            <path d={`M ${CX - 5} ${CY} L ${CX} ${CY - R + 8} L ${CX + 5} ${CY} Z`} fill={lv.hex} />
          </g>) : null}
        <circle cx={CX} cy={CY} r="9" fill="rgb(var(--c-panel))" stroke={lv.hex} strokeWidth="3" />
      </svg>
      <div className="-mt-3 text-center">
        <div className="text-5xl font-extrabold font-mono" style={{ color: lv.hex }}>{score != null ? score.toFixed(1) : "暫不公布"}</div>
        <div className="mt-1 inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold" style={{ background: `${lv.hex}22`, color: lv.hex }}>
          <span className="w-2.5 h-2.5 rounded-full animate-glow" style={{ background: lv.hex }} />燈號：{lv.label}
        </div>
        <div className="mt-2 text-[12px] text-term-muted">可能範圍 {low?.toFixed(1) ?? "—"}–{high?.toFixed(1) ?? "—"}（藍色細弧）· 0＝溫和、100＝研究假設的過熱門檻</div>
        <div className="mt-3 w-64 mx-auto">
          <div className="flex justify-between text-[12px]"><span>資料覆蓋率</span><b className="font-mono">{(coverage * 100).toFixed(1)}%</b></div>
          <div className="relative h-2.5 mt-1 rounded-full bg-term-border overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400 transition-all duration-1000" style={{ width: `${coverage * 100}%` }} />
            <div className="absolute top-0 h-full w-0.5 bg-term-amber" style={{ left: `${minCoverage * 100}%` }} title="最低覆蓋率門檻" />
          </div>
          <div className="text-[11px] text-term-muted mt-1">黃線＝最低門檻 {(minCoverage * 100).toFixed(0)}%；低於門檻就不給點分數。</div>
        </div>
      </div>
    </div>
  );
}
