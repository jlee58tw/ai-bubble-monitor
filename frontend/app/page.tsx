"use client";
import Link from "next/link";
import DimBars, { type Dim } from "@/components/DimBars";
import Gauge from "@/components/Gauge";
import KpiCard from "@/components/KpiCard";
import MetricCard from "@/components/MetricCard";
import { Hypothesis, Info, Loading, PageIntro, Panel, tsTaipei } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import type { Card } from "@/lib/api";
import { DIM_ZH, IND_ZH, dt, fp, num, pctZh, riskLevel, tx, usdYi } from "@/lib/i18n";

type Ind = { id: string; status: string; value: number | null; score: number | null; as_of: string | null; detail: string | null };
type Risk = { coverage: number; min_coverage: number; score: number | null; score_low: number | null; score_high: number | null; precise_score_withheld: boolean;
  computed_for: string; label: string; config_hash: string; dimensions: (Dim & { indicators: Ind[] })[] };
type Alert = { id: string; severity: string; category: string; title: string };

const SECTIONS: { title: string; metrics: string[]; note?: string }[] = [
  { title: "四大雲端巨頭資本支出（日曆季）", metrics: ["capex_total_big4_cal", "capex_total_big4_cal_yoy"], note: "MSFT＋GOOGL＋AMZN＋META 公司總資本支出，不是 AI 專屬；ORCL 財年季度非日曆季，不納入。" },
  { title: "公司總資本支出 (CapEx)（最新一季）", metrics: ["capex_total"] },
  { title: "資本支出年增率", metrics: ["capex_yoy"] },
  { title: "資本支出／營運現金流", metrics: ["capex_to_ocf"], note: "大於 1.0 倍＝該季資本支出超過本業賺進的現金。" },
  { title: "資本支出／營收", metrics: ["capex_to_revenue"] },
  { title: "自由現金流 (FCF)（營運現金流 − 資本支出）", metrics: ["fcf"] },
  { title: "營收", metrics: ["revenue"] },
  { title: "總體", metrics: ["us10y_yield"] },
  { title: "其他／尚無資料（明確列出缺口）", metrics: ["nvda_datacenter_revenue", "ai_capex_disclosed", "market_cap"] },
];

export default function Overview() {
  const ov = useApi<{ generated_at: string; cards: Card[] }>("/api/overview");
  const rk = useApi<Risk>("/api/risk");
  const al = useApi<Alert[]>("/api/alerts");
  const r = rk.data;
  const ind = (id: string) => r?.dimensions.flatMap((d) => d.indicators).find((i) => i.id === id);
  const ok = (i?: Ind) => (i && i.status === "ok" && i.value != null ? i : undefined);
  const big4 = ov.data?.cards.find((c) => c.metric_id === "capex_total_big4_cal")?.current;
  const big4y = ov.data?.cards.find((c) => c.metric_id === "capex_total_big4_cal_yoy")?.current;
  const ocf = ok(ind("hyperscaler_capex_to_ocf")), gap = ok(ind("hyperscaler_capex_minus_revenue_growth")), fcfm = ok(ind("hyperscaler_fcf_margin"));
  const nv = ok(ind("nvda_datacenter_revenue_yoy")), tsmc = ok(ind("tsmc_monthly_revenue")), lab = ok(ind("ai_lab_compute_intensity"));
  const lv = riskLevel(r?.score);
  const warn = al.data?.filter((a) => a.severity === "warning").length ?? 0;
  const err = ov.error || rk.error;
  return (
    <div className="space-y-6">
      <PageIntro emoji="🏠" title="總覽：AI 變現撐得起資本支出嗎？"
        what={<>用一個 0–100 的<b>研究型風險分數</b>，加上六大面向與關鍵數字，快速看出「AI 投資熱潮」目前偏冷還是偏熱。所有數字都來自公開資料（SEC、證交所、FRED、廠商價目頁）。</>}
        how={<>先看左邊<b>儀表</b>：指針越往右（橘、紅）代表越多指標接近研究假設的「過熱」門檻；再看<b>覆蓋率</b>，覆蓋率越低，分數越不可靠。右邊彩色長條告訴你是哪個面向在升溫，斜線條紋＝無資料（不是 0 分）。</>} />
      {err ? <ApiError error={err} /> : null}<Loading show={rk.loading || ov.loading} />

      {r ? (
        <div className="grid gap-4 lg:grid-cols-5">
          <Panel title="AI 泡沫風險分數" className="lg:col-span-2" info="六大面向、19 個指標依權重加總的研究型分數。門檻是作者設定的研究假設，不是經驗證的預測模型。">
            <Gauge score={r.precise_score_withheld ? null : r.score} low={r.score_low} high={r.score_high} coverage={r.coverage} minCoverage={r.min_coverage} />
            <div className="mt-3 rounded-lg p-3 text-[13px]" style={{ background: `${lv.hex}14`, border: `1px solid ${lv.hex}55` }}>
              <b>一句話解讀：</b>{r.score != null && !r.precise_score_withheld
                ? <>目前分數 {r.score.toFixed(1)}（{lv.label}），{lv.plain}資料覆蓋率 {(r.coverage * 100).toFixed(1)}%，有 {(100 - r.coverage * 100).toFixed(1)}% 的權重缺資料，因此真實分數可能落在 {r.score_low?.toFixed(1)}–{r.score_high?.toFixed(1)} 之間。</>
                : <>覆蓋率不足，暫不公布點分數，只顯示可能範圍。</>}
            </div>
            <div className="mt-2 text-[11px] text-term-muted">計算基準日 {dt(r.computed_for)} · 設定版本 {r.config_hash} · {tx(r.label)}</div>
          </Panel>
          <Panel title="六大面向" className="lg:col-span-3" info="每個面向的分數是其可用指標的平均；斜線條紋代表該面向可用指標太少而不給分。">
            <DimBars dims={r.dimensions} />
            <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-term-muted">
              {[["#22c55e", "偏低 0–39"], ["#eab308", "中等 40–59"], ["#f97316", "偏高 60–79"], ["#ef4444", "過熱 80–100"]].map(([c, t]) =>
                <span key={t} className="inline-flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full" style={{ background: c }} />{t}</span>)}
              <Link href="/risk" className="src ml-auto">看每個指標的細節 →</Link>
            </div>
          </Panel>
        </div>) : null}

      <section>
        <h2 className="text-base font-semibold mb-2">🔑 關鍵數字（白話版）</h2>
        <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard title="四大雲端巨頭季資本支出" value={big4 ? usdYi(big4.value, 0) : null} asOf={big4 ? fp(big4.fiscal_period) : null} href="/capex"
            plain={big4y ? `比去年同期 ${big4y.value >= 0 ? "多" : "少"} ${pctZh(Math.abs(big4y.value))}。這是公司總資本支出，不等於 AI 支出。` : "年增率無資料。"}
            info="MSFT＋GOOGL＋AMZN＋META 同一日曆季的資本支出 (CapEx) 加總，資料來自 SEC 財報。" />
          <KpiCard title="資本支出 ÷ 營運現金流" value={ocf ? `${num(ocf.value!, 2)} 倍` : null} score={ocf?.score ?? null} asOf={dt(ocf?.as_of)} href="/capex"
            plain={ocf ? `五大雲端業者平均每賺 1 元營運現金，就花 ${num(ocf.value!, 2)} 元蓋機房與買設備。` : "無資料。"} info={IND_ZH.hyperscaler_capex_to_ocf.why} />
          <KpiCard title="資本支出年增 − 營收年增" value={gap ? `${num(gap.value! * 100, 0)} 個百分點` : null} score={gap?.score ?? null} asOf={dt(gap?.as_of)} href="/capex"
            plain={gap ? `投資成長速度平均比營收成長快 ${num(gap.value! * 100, 0)} 個百分點。` : "無資料。"} info={IND_ZH.hyperscaler_capex_minus_revenue_growth.why} />
          <KpiCard title="雲端巨頭自由現金流率" value={fcfm ? pctZh(fcfm.value) : null} score={fcfm?.score ?? null} asOf={dt(fcfm?.as_of)} href="/capex"
            plain={fcfm ? (fcfm.value! < 0 ? "平均自由現金流已轉負：蓋完機房後，本業現金不夠用。" : `每 100 元營收平均剩 ${num(fcfm.value! * 100, 1)} 元自由現金。`) : "無資料。"} info={IND_ZH.hyperscaler_fcf_margin.why} />
          <KpiCard title="輝達資料中心營收年增率" value={nv ? pctZh(nv.value, 1, true) : null} score={nv?.score ?? null} asOf={dt(nv?.as_of)} href="/supply-chain"
            plain={nv ? `AI 晶片龍頭的資料中心營收比去年同期成長 ${pctZh(nv.value)}，供應端仍在熱潮期。` : "無資料。"} info={IND_ZH.nvda_datacenter_revenue_yoy.why} />
          <KpiCard title="台積電月營收年增率" value={tsmc ? pctZh(tsmc.value, 1, true) : null} score={tsmc?.score ?? null} asOf={dt(tsmc?.as_of)} href="/supply-chain"
            plain={tsmc ? `台積電單月營收比去年同月成長 ${pctZh(tsmc.value)}，遠高於約 15% 的長期趨勢。` : "無資料。"} info={IND_ZH.tsmc_monthly_revenue.why} />
          <KpiCard title="AI 實驗室算力成本 ÷ 營收" value={lab ? pctZh(lab.value, 0) : null} score={lab?.score ?? null} asOf={dt(lab?.as_of)} href="/ai-monetization"
            plain={lab ? `Anthropic 每 100 元營收約有 ${num(lab.value! * 100, 0)} 元花在算力與基礎設施（公司揭露，S-1）。` : "無資料。"} info={IND_ZH.ai_lab_compute_intensity.why} />
          <KpiCard title="目前警示" value={al.data ? `${al.data.length} 則` : null} href="/alerts"
            plain={al.data ? `其中 ${warn} 則為警示等級，其餘為資訊。警示只是規則觸發，不是預測。` : "無資料。"} info="依固定規則（如資本支出年增遠高於營收年增、自由現金流為負、股價回檔超過 20%）即時計算。" />
        </div>
      </section>

      <Hypothesis>研究原型：分數與燈號只反映「目前公開數據相對於研究假設門檻的位置」，<b>不是</b>泡沫破裂或股價的預測，也<b>不是</b>投資建議。缺資料一律不計入、不當成零風險。</Hypothesis>

      {ov.data ? <>
        <div className="flex items-end justify-between flex-wrap gap-2">
          <h2 className="text-base font-semibold">📊 各公司最新財報數字 <Info text="每張卡片：最新一期數值、與前一期比較、資料分類（已公布／推導…）與 SEC 原始來源連結。" /></h2>
          <span className="text-[11px] text-term-muted">資料產生時間 {tsTaipei(ov.data.generated_at)}</span>
        </div>
        {SECTIONS.map((s) => {
          const cards = ov.data!.cards.filter((c) => s.metrics.includes(c.metric_id));
          return (
            <section key={s.title}>
              <div className="flex gap-3 items-baseline mb-1.5 flex-wrap">
                <h3 className="text-[13px] font-semibold text-term-amber">{s.title}</h3>
                {s.note ? <span className="text-[11px] text-term-muted">{s.note}</span> : null}
              </div>
              <div className="grid gap-2 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                {cards.map((c) => <MetricCard key={c.metric_id + c.entity_id} c={c} />)}
              </div>
            </section>
          );
        })}</> : null}
      <div className="text-[11px] text-term-muted">面向說明：{Object.values(DIM_ZH).map((d) => d.name).join("、")}。</div>
    </div>
  );
}
