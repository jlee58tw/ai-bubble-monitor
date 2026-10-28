"use client";
import { Hypothesis, Loading, PageIntro, Panel, SourceStatus } from "@/components/Panel";
import { dt, tx } from "@/lib/i18n";
import { ApiError, useApi } from "@/components/useApi";

type Row = { id: number; model: string; harness: string | null; value: number; ci_low: number | null; ci_high: number | null; result_date: string | null; source_url: string; extra: Record<string, unknown> | null };
type Group = { benchmark: string; benchmark_version: string; split: string; metric: string; n: number; latest_result_date: string | null; note: string | null; rows: Row[] };
type Resp = { groups: Group[]; sources: Record<string, { last_status: string; last_success_at: string | null; message: string | null }> };
const fmt = (m: string, v: number) => (m.endsWith("_min") ? (v >= 60 ? `${(v / 60).toFixed(1)} 小時` : `${v.toFixed(1)} 分鐘`) : `${v.toFixed(2)}%`);

const METRIC_LBL: Record<string, string> = { p50_horizon_min: "50% 成功率時間長度", p80_horizon_min: "80% 成功率時間長度", resolved_pct: "解題率 %", accuracy_pct: "正確率 %" };
export default function Benchmarks() {
  const { data, error } = useApi<Resp>("/api/benchmarks");
  return (
    <div className="space-y-4">
      <PageIntro emoji="🧪" title="技術進展與 AI 代理可靠度"
        what={<>公開基準測試的成績：例如 METR「AI 能獨立完成多長的任務」（以人類花費時間計），以及 Terminal-Bench 等代理任務成功率。用來觀察技術是否持續進步、足以支撐商業化。</>}
        how={<>每張表是一個「基準 × 版本 × 子集 × 指標」，<b>不同表之間不能互相比較或排名</b>（題目、測試框架、計分方式都不同）。數值越高＝表現越好；95% 信賴區間 (CI) 越窄＝結果越確定。模型名稱保留原文。</>} />
      <div className="panel p-2.5 text-[12px] text-term-amber">⚠ 每張表只代表一個基準 × 版本 × 子集 × 指標；跨表分數絕不比較或排名。</div>
      {error ? <ApiError error={error} /> : null}
      <SourceStatus sources={data?.sources} />
      <Loading show={!data && !error} />
      <div className="grid gap-3 xl:grid-cols-2">
        {(data?.groups ?? []).map((g) => (
          <Panel key={`${g.benchmark}|${g.benchmark_version}|${g.split}|${g.metric}`}
            title={`${g.benchmark.toUpperCase()} · ${g.benchmark_version}${g.split !== "-" ? ` · ${g.split}` : ""} · ${METRIC_LBL[g.metric] ?? g.metric}（共 ${g.n} 筆，最新 ${dt(g.latest_result_date)}）`}>
            <p className="text-[11px] text-term-muted mb-1">{tx(g.note)}</p>
            <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
              <thead className="text-term-muted text-left whitespace-nowrap"><tr><th>#</th><th>模型（原名）</th><th>測試框架／代理</th><th className="text-right">數值</th><th className="text-right">95% 信賴區間</th><th>日期</th></tr></thead>
              <tbody>{g.rows.slice(0, 12).map((r, i) => (
                <tr key={r.id} className="border-t border-term-border" title={r.extra ? JSON.stringify(r.extra).slice(0, 400) : ""}>
                  <td className="text-term-muted">{i + 1}</td><td className="text-white">{r.model}</td>
                  <td className="text-term-muted max-w-[220px] truncate">{r.harness ?? "—"}</td>
                  <td className="text-right text-white">{fmt(g.metric, r.value)}</td>
                  <td className="text-right text-term-muted">{r.ci_low !== null && r.ci_high !== null ? `${fmt(g.metric, r.ci_low)}–${fmt(g.metric, r.ci_high)}` : "—"}</td>
                  <td className="text-term-muted">{dt(r.result_date)}</td>
                </tr>))}</tbody>
            </table></div>
            <a className="src text-[10px]" href={g.rows[0]?.source_url} target="_blank" rel="noreferrer">來源 ↗</a>
          </Panel>))}
      </div>
      <Hypothesis>基準成績只反映特定測試情境，不代表真實世界的商業價值；也不是投資建議。</Hypothesis>
    </div>
  );
}
