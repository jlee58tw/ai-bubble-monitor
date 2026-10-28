// 伺服器元件：靜態匯出（GitHub Pages）時於建置階段寫入每一頁。
import fs from "node:fs";
import path from "node:path";

type Meta = { snapshot_at_taipei: string; latest_ingestion_taipei: string | null; risk_score: number | null; risk_coverage: number | null;
  risk_low: number | null; risk_high: number | null; computed_for: string | null; git_commit: string };

export default function SnapshotBanner() {
  if (process.env.NEXT_PUBLIC_STATIC_SNAPSHOT !== "1") return null;
  const meta = JSON.parse(fs.readFileSync(path.join(process.cwd(), "public", "snapshot", "meta.json"), "utf8")) as Meta;
  const f = (v: number | null, d = 2) => (v === null ? "—" : v.toFixed(d));
  return (
    <div id="static-snapshot-banner" className="border-b border-amber-500/40 bg-gradient-to-r from-amber-500/15 via-orange-500/10 to-transparent px-4 py-2 text-[12px] text-term-amber">
      <b>📸 靜態快照，非即時資料</b>（STATIC SNAPSHOT — NOT LIVE）· 快照時間 {meta.snapshot_at_taipei}（台北時間）
      · 最近資料抓取 {meta.latest_ingestion_taipei ?? "—"}（台北時間）· 風險分數 <span id="snap-risk" className="font-mono font-bold">{f(meta.risk_score)}</span>
      {"（"}覆蓋率 <span id="snap-coverage" className="font-mono">{meta.risk_coverage === null ? "—" : `${(meta.risk_coverage * 100).toFixed(1)}%`}</span>，
      可能範圍 {f(meta.risk_low)}–{f(meta.risk_high)}，計算基準日 {meta.computed_for ?? "—"}）· 版本 {meta.git_commit}
      <span className="text-term-muted"> · 每個數值都保留分類（已公布／推導／估計／公司揭露／公司指引）與來源連結。重新抓取、編輯追蹤清單、指定日期查詢與非預設回測參數需在本機執行。研究原型，非投資建議。</span>
    </div>
  );
}
