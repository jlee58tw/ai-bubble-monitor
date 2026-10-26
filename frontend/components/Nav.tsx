"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "OVERVIEW" },
  { href: "/risk", label: "RISK SCORE" },
  { href: "/alerts", label: "ALERTS" },
  { href: "/capex", label: "CAPEX" },
  { href: "/valuation", label: "VALUATION" },
  { href: "/supply-chain", label: "SUPPLY CHAIN / GPU" },
  { href: "/pricing", label: "MODEL PRICING" },
  { href: "/benchmarks", label: "BENCHMARKS" },
  { href: "/roi", label: "ROI SIM" },
  { href: "/methodology", label: "METHODOLOGY" },
  { href: "/pipeline", label: "PIPELINE" },
  { href: "/ai-monetization", label: "AI MONETIZATION", ph: true },
  { href: "/credit", label: "CREDIT", ph: true },
];
export default function Nav() {
  const p = usePathname();
  return (
    <header className="border-b border-term-border bg-black">
      <div className="flex items-center gap-6 px-4 py-2">
        <div className="font-mono font-bold text-term-amber tracking-widest">AI BUBBLE MONITOR</div>
        <nav className="flex flex-wrap gap-1 text-xs font-mono">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href}
              className={`px-2 py-1 ${p === l.href ? "bg-term-amber text-black" : "text-term-muted hover:text-white"}`}>
              {l.label}{l.ph ? <span className="ml-1 text-[9px] opacity-70">[PH]</span> : null}
            </Link>
          ))}
        </nav>
        <div className="ml-auto hidden 2xl:block text-[10px] font-mono text-term-muted">RESEARCH ONLY · NOT INVESTMENT ADVICE</div>
      </div>
    </header>
  );
}
