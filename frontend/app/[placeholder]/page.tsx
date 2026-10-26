import { notFound } from "next/navigation";

const PAGES: Record<string, { title: string; needs: string[] }> = {
  "ai-monetization": { title: "AI MONETIZATION", needs: ["Company-disclosed AI revenue / run-rate (qualitative, earnings calls)", "Cloud segment revenue (dimensional XBRL — needs filing-level parser)", "Pricing / usage indicators (no source connected)"] },
  credit: { title: "CREDIT / FUNDING", needs: ["Hyperscaler debt issuance & finance-lease liabilities", "Private credit / data-center ABS data (no source)"] },
};

export function generateStaticParams() {
  return Object.keys(PAGES).map((placeholder) => ({ placeholder }));
}

export default async function Placeholder({ params }: { params: Promise<{ placeholder: string }> }) {
  const { placeholder } = await params;
  const p = PAGES[placeholder];
  if (!p) notFound();
  return (
    <div className="panel p-6 border-dashed max-w-3xl">
      <div className="text-[10px] font-mono text-term-down mb-1">PLACEHOLDER — NOT IMPLEMENTED (PHASE 2+)</div>
      <h1 className="font-mono text-term-amber text-lg">{p.title}</h1>
      <p className="mt-2 text-xs text-term-muted">This page intentionally shows no numbers. Data it would need:</p>
      <ul className="mt-2 list-disc pl-5 text-xs font-mono">{p.needs.map((n) => <li key={n}>{n}</li>)}</ul>
      <p className="mt-3 text-[11px] text-term-amber">Absence of data here must not be read as absence of risk.</p>
    </div>
  );
}
