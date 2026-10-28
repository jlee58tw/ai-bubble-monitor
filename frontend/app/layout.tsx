import "./globals.css";
import type { Metadata } from "next";
import Nav from "@/components/Nav";
import SnapshotBanner from "@/components/SnapshotBanner";

export const metadata: Metadata = { title: "AI 泡沫監測站｜AI Bubble Monitor", description: "AI 變現能力撐得起資本支出嗎？研究用途，非投資建議。" };

const THEME_INIT = `try{if(localStorage.getItem("theme")==="light"){var e=document.documentElement;e.classList.remove("dark");e.classList.add("light")}}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant-TW" className="dark" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: THEME_INIT }} /></head>
      <body className="min-h-screen font-sans text-sm">
        <SnapshotBanner />
        <Nav />
        <main className="p-3 md:p-5 max-w-[1800px] mx-auto">{children}</main>
        <footer className="px-4 py-4 text-[12px] text-term-muted border-t border-term-border space-y-1">
          <div>⚠️ 缺資料一律標示為「無資料／缺資料」，絕不當成零風險。公司總資本支出 ≠ AI 資本支出。</div>
          <div>研究原型：所有門檻都是研究假設，不是預測，也不是投資建議。</div>
        </footer>
      </body>
    </html>
  );
}
