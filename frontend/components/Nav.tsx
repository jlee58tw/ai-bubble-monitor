"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "OVERVIEW" },
  { href: "/capex", label: "HYPERSCALER CAPEX" },
  { href: "/pipeline", label: "DATA SOURCES / PIPELINE" },
  { href: "/ai-monetization", label: "AI MONETIZATION", ph: true },
  { href: "/valuation", label: "VALUATION", ph: true },
  { href: "/supply-chain", label: "SEMIS / SUPPLY CHAIN", ph: true },
  { href: "/credit", label: "CREDIT / FUNDING", ph: true },
];
export default function Nav() {
  const p = usePathname();
  return (
    <header className="border-b border-term-border bg-black">
      <div className="flex items-center gap-6 px-4 py-2">
        <div className="font-mono font-bold text-term-amber tracking-widest">AI BUBBLE MONITOR</div>
        <nav className="flex gap-1 text-xs font-mono">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href}
              className={`px-2 py-1 ${p === l.href ? "bg-term-amber text-black" : "text-term-muted hover:text-white"}`}>
              {l.label}{l.ph ? <span className="ml-1 text-[9px] opacity-70">[PH]</span> : null}
            </Link>
          ))}
        </nav>
        <div className="ml-auto text-[10px] font-mono text-term-muted">RESEARCH ONLY · NOT INVESTMENT ADVICE</div>
      </div>
    </header>
  );
}
