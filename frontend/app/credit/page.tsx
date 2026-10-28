"use client";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { Hypothesis, Loading, PageIntro, Panel } from "@/components/Panel";
import { ANIM, TT } from "@/lib/chart";
import { dt } from "@/lib/i18n";
import { ApiError, useApi } from "@/components/useApi";
import type { Observation } from "@/lib/api";

const SERIES = [
  { m: "us10y_yield", label: "美國 10 年期公債殖利率 (DGS10)", fred: "DGS10", c: "#60aaff", plain: "長期借錢成本的基準；越高，AI 資料中心的融資與估值壓力越大。" },
  { m: "us2y_yield", label: "美國 2 年期公債殖利率 (DGS2)", fred: "DGS2", c: "#a78bfa", plain: "反映市場對聯準會短期利率的預期。" },
  { m: "us_10y2y_spread", label: "10 年 − 2 年利差 (T10Y2Y)", fred: "T10Y2Y", c: "#22d3ee", plain: "殖利率曲線斜率；負值（倒掛）常被視為景氣轉弱訊號。" },
  { m: "baa_10y_spread", label: "穆迪 Baa 公司債 − 10 年公債利差 (BAA10Y)", fred: "BAA10Y", c: "#f59e0b", plain: "企業借錢要比政府多付多少；越低＝資金越便宜、市場越樂觀。" },
];

export default function Credit() {
  const start = new Date(Date.now() - 400 * 864e5).toISOString().slice(0, 10);
  const { data, error, loading } = useApi<Observation[]>(`/api/observations?metric_id=${SERIES.map((s) => s.m).join(",")}&start=${start}`);
  return (
    <div className="space-y-4">
      <PageIntro emoji="🏦" title="信用與利率（資金環境）"
        what={<>AI 基礎建設很燒錢，資金成本很關鍵。這頁追蹤美國公債殖利率與公司債利差（資料來源：聖路易聯準銀行 FRED，已公布數字）。</>}
        how={<>每張卡片：大字是最新值（%），小圖是近 13 個月走勢。<b>利率越高</b>＝借錢越貴；<b>信用利差越窄</b>＝資金越便宜，代表市場樂觀，但不代表安全。</>} />
      {error ? <ApiError error={error} /> : null}<Loading show={loading} />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{SERIES.map((s) => {
        const rows = (data ?? []).filter((o) => o.metric_id === s.m).sort((a, b) => a.period_end.localeCompare(b.period_end));
        const last = rows[rows.length - 1]; const yr = rows.filter((o) => o.period_end >= start);
        const lo = Math.min(...yr.map((o) => o.value)), hi = Math.max(...yr.map((o) => o.value));
        return (
          <Panel key={s.m} title={s.label} info={s.plain}>
            {last ? <div className="font-mono"><div className="text-3xl font-extrabold" style={{ color: s.c }}>{last.value.toFixed(2)}<span className="text-sm text-term-muted"> %</span></div>
              <div className="h-16 -mx-1 my-1"><ResponsiveContainer width="100%" height="100%"><AreaChart data={yr.map((o) => ({ d: dt(o.period_end), v: o.value }))}>
                <defs><linearGradient id={`g_${s.m}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={s.c} stopOpacity={0.5} /><stop offset="100%" stopColor={s.c} stopOpacity={0} /></linearGradient></defs>
                <YAxis hide domain={["auto", "auto"]} /><Tooltip {...TT} formatter={(v: number) => [`${v.toFixed(2)}%`, "數值"]} labelFormatter={(l: string) => l} />
                <Area {...ANIM} type="monotone" dataKey="v" stroke={s.c} strokeWidth={2} fill={`url(#g_${s.m})`} /></AreaChart></ResponsiveContainer></div>
              <div className="text-[12px] text-term-fg">{s.plain}</div>
              <div className="text-[11px] text-term-muted mt-1">資料日期 {dt(last.period_end)} · 近約 13 個月區間 {lo.toFixed(2)}–{hi.toFixed(2)}</div>
              <div className="text-[10px] mt-1"><a className="underline text-term-info" href={`https://fred.stlouisfed.org/series/${s.fred}`} target="_blank" rel="noreferrer">FRED {s.fred}</a> · 已公布</div></div>
              : <div className="text-xs text-term-down">無資料（不以 0 顯示）</div>}
          </Panel>);
      })}</div>
      <Hypothesis>Baa 利差低於約 1.5 個百分點在歷史上屬於偏窄（風險指標「信用利差」因此視為完全過熱）。利差窄代表 AI 建設的資金很便宜，<b>不代表安全</b>。</Hypothesis>
      <Panel title="無資料的項目">
        <ul className="list-disc pl-5 text-xs text-term-down space-y-1">
          <li>ICE 美銀高收益債／投資級債選擇權調整利差 (OAS)——授權條款要求事先取得 ICE 同意才能再散布，因此不儲存。</li>
          <li>雲端巨頭逐筆發債與融資租賃負債——沒有接入免費、機器可讀的來源。</li>
          <li>私募信貸／資料中心資產擔保證券 (ABS) 發行量——沒有免費的官方來源。</li>
        </ul>
        <div className="text-[11px] text-term-amber mt-2">這裡沒有資料，不能解讀成沒有風險。</div>
      </Panel>
    </div>
  );
}
