"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import ThemeToggle from "./ThemeToggle";

export const LINKS: { href: string; label: string; icon: string }[] = [
  { href: "/", label: "總覽", icon: "🏠" },
  { href: "/risk", label: "風險分數", icon: "🎯" },
  { href: "/alerts", label: "警示", icon: "🚨" },
  { href: "/capex", label: "資本支出", icon: "🏗️" },
  { href: "/valuation", label: "估值", icon: "📈" },
  { href: "/supply-chain", label: "供應鏈／GPU", icon: "🔌" },
  { href: "/pricing", label: "模型定價", icon: "🏷️" },
  { href: "/benchmarks", label: "能力基準", icon: "🧪" },
  { href: "/ai-monetization", label: "AI 變現", icon: "💰" },
  { href: "/credit", label: "信用與利率", icon: "🏦" },
  { href: "/roi", label: "ROI 模擬", icon: "🧮" },
  { href: "/backtest", label: "歷史回測", icon: "⏪" },
  { href: "/events", label: "財報事件", icon: "📅" },
  { href: "/watchlist", label: "追蹤清單", icon: "⭐" },
  { href: "/methodology", label: "方法論", icon: "📐" },
  { href: "/pipeline", label: "資料管線", icon: "🛠️" },
];
export default function Nav() {
  const p = usePathname();
  const [open, setOpen] = useState(false);
  const active = (h: string) => p === h || p === `${h}/` || (h !== "/" && p?.endsWith(h));
  return (
    <header className="sticky top-0 z-40 border-b border-term-border bg-term-bg/85 backdrop-blur">
      <div className="flex items-center gap-3 px-4 py-2">
        <Link href="/" className="font-bold tracking-wide whitespace-nowrap"><span className="grad-text text-lg">AI 泡沫監測站</span></Link>
        <span className="hidden md:inline text-[11px] text-term-muted whitespace-nowrap">研究用途 · 非投資建議</span>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          <button className="lg:hidden btn" aria-label="選單" onClick={() => setOpen(!open)}>{open ? "✕ 關閉" : "☰ 選單"}</button>
        </div>
      </div>
      <nav className={`${open ? "flex" : "hidden"} lg:flex flex-wrap gap-1 px-3 pb-2 text-[13px]`}>
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} onClick={() => setOpen(false)}
            className={`px-2.5 py-1 rounded-full transition-colors whitespace-nowrap ${active(l.href)
              ? "bg-gradient-to-r from-violet-600 to-cyan-500 text-white shadow" : "text-term-muted hover:text-term-strong hover:bg-term-panel"}`}>
            <span className="mr-1">{l.icon}</span>{l.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
