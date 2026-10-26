import "./globals.css";
import type { Metadata } from "next";
import Nav from "@/components/Nav";

export const metadata: Metadata = { title: "AI Bubble Monitor", description: "Does AI monetization justify capex?" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen font-sans text-sm">
        <Nav />
        <main className="p-4">{children}</main>
        <footer className="px-4 py-3 text-[10px] text-term-muted font-mono border-t border-term-border">
          Missing data is shown as UNAVAILABLE / MISSING and is never treated as zero risk. Total company capex is not AI capex.
        </footer>
      </body>
    </html>
  );
}
