import Link from "next/link";
import { riskLevel } from "@/lib/i18n";
import { Info } from "./Panel";

/** KPI 卡：大數字 + 一句白話解讀 + 燈號（依該指標分數）。value 為 null 時顯示「無資料」。 */
export default function KpiCard({ title, value, plain, score, asOf, info, href }: {
  title: string; value: string | null; plain: string; score?: number | null; asOf?: string | null; info?: string; href?: string;
}) {
  const lv = riskLevel(score ?? null);
  const showLight = score !== undefined;
  return (
    <div className="panel p-4 relative overflow-hidden animate-fade-up group">
      <div className="absolute -right-8 -top-8 w-28 h-28 rounded-full blur-2xl opacity-25 group-hover:opacity-40 transition-opacity" style={{ background: showLight ? lv.hex : "#7c3aed" }} />
      <div className="flex items-center gap-1.5 text-[12px] text-term-muted">
        {showLight ? <span className="w-2.5 h-2.5 rounded-full" style={{ background: lv.hex }} title={`燈號：${lv.label}`} /> : null}
        <span>{title}</span>{info ? <Info text={info} /> : null}
      </div>
      <div className={`mt-1 text-3xl font-extrabold font-mono ${value == null ? "text-term-down" : "text-term-strong"}`}>{value ?? "無資料"}</div>
      <div className="mt-1.5 text-[13px] leading-snug">{plain}</div>
      <div className="mt-2 flex items-center justify-between text-[11px] text-term-muted">
        <span>{asOf ? `資料日期 ${asOf}` : ""}{showLight ? ` · 燈號 ${lv.label}` : ""}</span>
        {href ? <Link href={href} className="src">看細節 →</Link> : null}
      </div>
    </div>
  );
}
