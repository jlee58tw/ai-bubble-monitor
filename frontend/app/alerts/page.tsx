"use client";
import { ClassBadge, StatusPill } from "@/components/Badges";
import { Hypothesis, Loading, PageIntro, Panel } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import { ALERT_CAT_ZH, dt, tx } from "@/lib/i18n";

type Alert = { id: string; severity: string; category: string; title: string; detail: string; as_of: string | null; classification: string | null; source_url: string | null };
const ICON: Record<string, string> = { capex: "🏗️", valuation: "📉", pricing: "🏷️", risk: "🎯", data_quality: "🛠️" };

export default function Alerts() {
  const { data, error } = useApi<Alert[]>("/api/alerts");
  const cats = [...new Set((data ?? []).map((a) => a.category))];
  const n = (s: string) => (data ?? []).filter((a) => a.severity === s).length;
  return (
    <div className="space-y-5">
      <PageIntro emoji="🚨" title="警示"
        what={<>依固定規則，從已儲存的真實資料即時計算的提醒：例如資本支出年增遠高於營收年增、自由現金流轉負、股價距 52 週高點回檔超過 20%、模型預定調價。門檻設定在 risk.yaml。</>}
        how={<><b className="text-term-down">警示</b>＝規則被觸發，值得留意；<b className="text-term-info">資訊</b>＝背景變化。每則都附資料分類與原始來源。警示只代表「條件成立」，不是預測。</>} />
      {error ? <ApiError error={error} /> : null}
      <Loading show={!data && !error} />
      {data ? (
        <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
          {[["全部", data.length, "#a78bfa"], ["警示", n("warning"), "#ef4444"], ["資訊", n("info"), "#60aaff"], ["類別", cats.length, "#22d3ee"]].map(([t, v, c]) => (
            <div key={t as string} className="panel p-3"><div className="text-[12px] text-term-muted">{t}</div><div className="text-3xl font-extrabold font-mono" style={{ color: c as string }}>{v}</div></div>))}
        </div>) : null}
      {data && data.length === 0 ? <div className="text-term-muted text-xs">目前沒有觸發任何警示條件。</div> : null}
      {cats.map((c) => (
        <Panel key={c} title={`${ICON[c] ?? ""} ${ALERT_CAT_ZH[c] ?? c}`}>
          <div className="space-y-2">{(data ?? []).filter((a) => a.category === c).map((a) => (
            <div key={a.id} className={`rounded-lg border p-2.5 flex flex-col md:flex-row md:items-start gap-2 ${a.severity === "warning" ? "border-red-500/40 bg-red-500/5" : "border-sky-500/30 bg-sky-500/5"}`}>
              <div className="shrink-0"><StatusPill s={a.severity} /></div>
              <div className="flex-1 min-w-0"><div className="text-white text-[13px] font-medium">{tx(a.title)}</div><div className="text-term-muted text-[12px] break-words">{tx(a.detail)}</div></div>
              <div className="flex items-center gap-2 shrink-0 text-[11px]">
                {a.classification ? <ClassBadge c={a.classification} /> : null}
                <span className="text-term-muted font-mono">{dt(a.as_of)}</span>
                {a.source_url ? <a className="src" href={a.source_url} target="_blank" rel="noreferrer">來源 ↗</a> : null}
              </div>
            </div>))}</div>
        </Panel>))}
      <Hypothesis>警示門檻與風險分數一樣都是研究假設；觸發不代表會發生崩跌，也不是投資建議。</Hypothesis>
    </div>
  );
}
