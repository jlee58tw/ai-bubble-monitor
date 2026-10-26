export function Panel({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return <section className={`panel p-3 ${className}`}><h2 className="font-mono text-xs text-term-amber mb-2">{title}</h2>{children}</section>;
}
export function Loading({ show }: { show: boolean }) {
  return show ? <div className="text-term-muted font-mono text-xs p-2">loading…</div> : null;
}
export function Hypothesis({ children }: { children: React.ReactNode }) {
  return <div className="panel p-2 text-[11px] text-term-amber font-mono border-dashed">⚠ {children}</div>;
}
export const tsTaipei = (iso: string | null | undefined) => {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`); // API datetimes are naive UTC
  return d.toLocaleString("sv-SE", { timeZone: "Asia/Taipei", hour12: false }).slice(0, 16) + " (UTC+8)";
};
export function SourceStatus({ sources }: { sources: Record<string, { last_status: string; last_success_at: string | null; message: string | null }> | undefined }) {
  if (!sources) return null;
  return (
    <div className="flex flex-wrap gap-3 text-[10px] font-mono text-term-muted">
      {Object.entries(sources).map(([k, v]) => (
        <span key={k} title={v.message ?? ""}>{k}: <span className={v.last_status === "success" ? "text-term-up" : "text-term-down"}>{v.last_status}</span>
          {" · last ok "}{tsTaipei(v.last_success_at)}</span>
      ))}
    </div>
  );
}
