// Server component: rendered at build time into every page of the static (GitHub Pages) export.
import fs from "node:fs";
import path from "node:path";

type Meta = { snapshot_at_taipei: string; latest_ingestion_taipei: string | null; risk_score: number | null; risk_coverage: number | null;
  risk_low: number | null; risk_high: number | null; computed_for: string | null; git_commit: string };

export default function SnapshotBanner() {
  if (process.env.NEXT_PUBLIC_STATIC_SNAPSHOT !== "1") return null;
  const meta = JSON.parse(fs.readFileSync(path.join(process.cwd(), "public", "snapshot", "meta.json"), "utf8")) as Meta;
  const f = (v: number | null, d = 2) => (v === null ? "—" : v.toFixed(d));
  return (
    <div id="static-snapshot-banner" className="border-b border-term-amber bg-black px-4 py-2 font-mono text-[11px] text-term-amber">
      <b>STATIC SNAPSHOT — NOT LIVE（靜態快照，非即時資料）</b> · snapshot {meta.snapshot_at_taipei} (Asia/Taipei)
      · latest ingestion {meta.latest_ingestion_taipei ?? "—"} (Asia/Taipei) · risk score <span id="snap-risk">{f(meta.risk_score)}</span>
      {" "}(coverage <span id="snap-coverage">{meta.risk_coverage === null ? "—" : `${(meta.risk_coverage * 100).toFixed(1)}%`}</span>,
      range {f(meta.risk_low)}–{f(meta.risk_high)}, computed for {meta.computed_for ?? "—"}) · commit {meta.git_commit}
      <span className="text-term-muted"> · Every value keeps its classification (reported / derived / estimated / disclosed / guidance) and source link.
      Refresh, watchlist edits, as-of queries and non-default backtest parameters need the local app. Research prototype, not investment advice.</span>
    </div>
  );
}
