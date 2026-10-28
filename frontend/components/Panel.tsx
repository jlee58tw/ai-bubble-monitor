import { st } from "@/lib/i18n";

export function Panel({ title, children, className = "", info }: { title: React.ReactNode; children: React.ReactNode; className?: string; info?: string }) {
  return (
    <section className={`panel p-4 animate-fade-up ${className}`}>
      <h2 className="text-sm font-semibold text-term-strong mb-3 flex items-center gap-1.5">
        <span className="inline-block w-1 h-4 rounded-full bg-gradient-to-b from-violet-500 to-cyan-400" />{title}{info ? <Info text={info} /> : null}
      </h2>{children}
    </section>
  );
}
export function Loading({ show }: { show: boolean }) {
  return show ? <div className="text-term-muted text-xs p-2 animate-glow">載入中…</div> : null;
}
export function Hypothesis({ children }: { children: React.ReactNode }) {
  return <div className="panel p-3 text-[12px] text-term-amber border-dashed !border-amber-500/40 bg-amber-500/5">⚠️ {children}</div>;
}
/** ⓘ 說明：滑鼠移上（或手機點一下）顯示白話解釋 */
export function Info({ text }: { text: string }) {
  return (
    <span className="relative group inline-flex align-middle" tabIndex={0} title={text}>
      <span className="cursor-help text-term-info text-[12px] font-normal select-none">ⓘ</span>
      <span className="pointer-events-none absolute left-1/2 top-5 z-50 w-72 -translate-x-1/2 rounded-lg border border-term-border bg-term-panel p-2.5 text-[12px] font-normal leading-relaxed text-term-fg opacity-0 shadow-xl transition-opacity group-hover:opacity-100 group-focus:opacity-100">{text}</span>
    </span>
  );
}
/** 每頁頂端：「這頁在看什麼？」與「怎麼讀」 */
export function PageIntro({ title, emoji, what, how }: { title: string; emoji?: string; what: React.ReactNode; how: React.ReactNode }) {
  return (
    <div className="space-y-3 animate-fade-up">
      <h1 className="text-2xl md:text-3xl font-bold tracking-tight"><span className="mr-2">{emoji}</span><span className="grad-text">{title}</span></h1>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="panel p-3 !border-violet-500/30"><div className="text-[12px] font-semibold text-violet-400 mb-1">🔍 這頁在看什麼？</div><div className="text-[13px] leading-relaxed">{what}</div></div>
        <div className="panel p-3 !border-cyan-500/30"><div className="text-[12px] font-semibold text-cyan-500 mb-1">📖 怎麼讀</div><div className="text-[13px] leading-relaxed">{how}</div></div>
      </div>
    </div>
  );
}
/** 台北時間（UTC+8）：2026/10/28 23:00 */
export const tsTaipei = (iso: string | null | undefined) => {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`); // API 的時間為無時區的 UTC
  return d.toLocaleString("sv-SE", { timeZone: "Asia/Taipei", hour12: false }).slice(0, 16).replace(/-/g, "/") + "（台北時間）";
};
export function SourceStatus({ sources }: { sources: Record<string, { last_status: string; last_success_at: string | null; message: string | null }> | undefined }) {
  if (!sources) return null;
  return (
    <div className="flex flex-wrap gap-3 text-[11px] text-term-muted">
      {Object.entries(sources).map(([k, v]) => (
        <span key={k} title={v.message ?? ""}>資料來源 {k}：<span className={v.last_status === "success" ? "text-term-up" : "text-term-down"}>{st(v.last_status)}</span>
          {" · 最近成功 "}{tsTaipei(v.last_success_at)}</span>
      ))}
    </div>
  );
}
