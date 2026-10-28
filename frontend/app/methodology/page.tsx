"use client";
import Link from "next/link";
import { Hypothesis, Loading, PageIntro, Panel } from "@/components/Panel";
import { DIM_ZH, ent, indName, indWhy, tx } from "@/lib/i18n";
import { ApiError, useApi } from "@/components/useApi";

type Cfg = { version: number; min_coverage: number; dimensions: { id: string; name: string; weight: number }[];
  indicators: { id: string; dimension: string; name: string; calc: string; args?: Record<string, unknown>; max_age_days?: number; thresholds?: { benign: number; stretched: number }; rationale: string; status?: string; reason?: string }[];
  alerts: Record<string, unknown> };
type Resp = { config_hash: string; config: Cfg; rules: string[] };

const CALC_ZH: Record<string, string> = {
  obs_latest: "最新觀測值", obs_ratio_latest: "最新比率（A ÷ B）", obs_yoy_latest: "最新年增率", obs_mean_latest: "多家公司最新值平均",
  obs_spread_latest: "最新差值（A − B）", model_price_change: "模型價格變動", gpu_spot_discount: "GPU Spot 價折扣", metr_doubling: "METR 能力倍增時間",
  bench_top: "基準測試最高分", unavailable: "無資料（未接入）",
};
const pctS = (v: unknown) => `${Math.round(Number(v) * 100)}%`;
const ALERT_RULE: Record<string, (v: unknown) => string> = {
  capex_vs_revenue_gap: (v) => `資本支出年增率高於營收年增率超過 ${pctS(v)} 時警示`,
  negative_fcf: (v) => (v ? "自由現金流轉負時警示" : "不檢查自由現金流"),
  risk_rise_points: (v) => `綜合風險分數較前次上升 ≥ ${v} 分時警示`,
  price_cut_pct: (v) => `模型價格調降 ≥ ${pctS(Math.abs(Number(v)))} 時警示`,
  price_change_lookback_days: (v) => `價格變動回看 ${v} 天`,
  scheduled_change_horizon_days: (v) => `預告調價：未來 ${v} 天內`,
  drawdown: (v) => `股價從 52 週高點下跌 ≥ ${pctS(Math.abs(Number(v)))} 時警示`,
  companies: (v) => `監測公司：${(v as string[]).map((x) => ent(x)).join("、")}`,
};

export default function Methodology() {
  const { data, error } = useApi<Resp>("/api/methodology");
  const c = data?.config;
  return (
    <div className="space-y-4">
      <PageIntro emoji="📐" title="方法論"
        what={<>這個儀表板怎麼算分：六大面向、每個指標的計算方式、門檻與權重，以及資料分類與回測規則。</>}
        how={<>每個指標會依「溫和（0 分）」到「過熱（100 分）」兩個門檻換算成 0–100 分，再依面向權重加總。缺資料的指標<b>不算 0 分</b>，而是讓分數範圍變寬並降低覆蓋率。</>} />
      <Hypothesis>以下每個門檻都是建置者選定的<b>研究假設</b>，不是經過驗證的泡沫或崩盤預測指標。權重與門檻存放在 backend/app/registry/risk.yaml；修改後設定雜湊會改變，不同雜湊的快照不互相比較。</Hypothesis>
      {error ? <ApiError error={error} /> : null}
      <Loading show={!data && !error} />
      {data ? (<>
        <Panel title={`計分規則 · 設定 ${data.config_hash} · 第 ${c?.version} 版`}>
          <ul className="list-disc pl-5 text-[13px] space-y-1">{data.rules.map((r) => <li key={r} title={r}>{tx(r)}</li>)}</ul>
        </Panel>
        <Panel title="資料分類">
          <ul className="list-disc pl-5 text-[13px] space-y-1">
            <li><b className="text-term-up">已公布 (reported)</b>：發行公司、交易所或官方機構申報／公布的原始數值（SEC XBRL、證交所、FRED、廠商價格頁）。</li>
            <li><b className="text-purple-400">推導 (derived)</b>：本系統由已公布數值計算而得（年增率、比率、市值＝股價 × 股數、跌幅、Q4＝全年 − Q1～Q3），每筆觀測都附公式。</li>
            <li><b className="text-term-amber">估計 (estimated)</b>：預測／市場共識。目前一筆都沒有匯入（共識預估需授權）。</li>
            <li><b className="text-term-down">無資料／尚未接入 (unavailable / placeholder)</b>：沒有符合使用條款的來源。明確標示，絕不補值，也絕不算作 0 風險。</li>
          </ul>
        </Panel>
        {c?.dimensions.map((d) => (
          <Panel key={d.id} title={`${DIM_ZH[d.id]?.name ?? d.name} · 權重 ${d.weight}%`} info={DIM_ZH[d.id]?.plain}>
            <div className="overflow-x-auto"><table className="w-full text-[12px]">
              <thead className="text-term-muted text-left whitespace-nowrap"><tr><th>指標</th><th>計算方式</th><th className="text-right">溫和（0 分）</th><th className="text-right">過熱（100 分）</th><th className="text-right">資料最長有效（天）</th><th>假設／理由</th></tr></thead>
              <tbody>{c.indicators.filter((i) => i.dimension === d.id).map((i) => (
                <tr key={i.id} className="border-t border-term-border align-top">
                  <td className="text-white min-w-[160px]">{indName(i.id, i.name)}<div className="text-term-muted text-[10px] font-mono">{i.id}</div></td>
                  <td className="text-term-muted">{CALC_ZH[i.calc] ?? i.calc}</td>
                  <td className="text-right font-mono">{i.thresholds?.benign ?? "—"}</td><td className="text-right font-mono">{i.thresholds?.stretched ?? "—"}</td>
                  <td className="text-right font-mono">{i.max_age_days ?? "—"}</td>
                  <td className="max-w-[520px]" title={`原文：${i.rationale}`}>{indWhy(i.id, i.rationale)}</td>
                </tr>))}</tbody>
            </table></div>
          </Panel>))}
        <Panel title="警示規則（僅在網頁內顯示，每次請求時由已儲存的真實資料計算）">
          <ul className="list-disc pl-5 text-[13px] space-y-1">{Object.entries(c?.alerts ?? {}).map(([k, v]) => <li key={k}>{ALERT_RULE[k] ? ALERT_RULE[k](v) : `${k}：${JSON.stringify(v)}`}</li>)}</ul>
        </Panel>
        <Panel title="可靠度 ROI 模擬器公式">
          <p className="text-[13px]">請見 <Link className="src" href="/roi">ROI 模擬器</Link>（由 <code>/api/roi</code> 計算）。規格定義：有效任務成本＝AI 推論成本＋工具成本＋人工審查成本＋預期重工成本＋預期失敗損失；有效 ROI＝（人工基準成本 − 有效任務成本）÷ 人工基準成本。</p>
          <p className="text-[13px] text-term-amber mt-1">建模假設（僅限預期項目）：預期重工成本＝(1 − p) × 可重工比例 × 重工成本；預期失敗損失＝(1 − p) × (1 − 可重工比例) × 失敗補救成本；人工審查成本＝審查分鐘 ÷ 60 × 時薪。所有輸入都是使用者的情境數值。</p>
        </Panel>
        <Panel title="歷史回測（時點重建）：請見回測頁">
          <ul className="text-[13px] list-disc ml-4 space-y-1">
            <li>不偷看未來：在每個過去日期 d，讀取觀測資料表的指標只用 publication_date ≤ d 的資料重算，並採用 d 當天的版本（之後的修正與重編在公布前都看不到）。推導資料的公布日取其輸入中最晚的公布日。</li>
            <li>資料集型指標（模型價格、GPU 牌價、METR／基準測試）在首次蒐集前沒有歷史：標記為「無歷史時點資料」並排除。缺少的指標會放寬 0–100 範圍，絕不算作零風險。</li>
            <li>過去的覆蓋率都低於最低門檻，所以每個過去日期都不公布正式風險分數。回測改報告明確標示的「部分覆蓋綜合分數」與個別指標訊號。</li>
            <li>訊號亮燈＝綜合分數 ≥ 60 或單一指標分數 ≥ 70（與即時引擎相同的研究門檻，沒有事後擬合）。未知的日子會排除，絕不當作「未亮燈」。</li>
            <li>結果定義：未來 H＝20 個交易日內最低收盤價跌幅 ≤ −10%。台股（2330／2382／2317 與等權籃子，約 13 個月）與美股（Tiingo 分割調整後收盤價，2015 年起）。報告內容：亮燈／未亮燈時的命中率與基準率、以有效樣本 n＝n/H 調整重疊視窗的近似 Wilson 95% 信賴區間，以及從亮燈起點到每次 ≥10% 修正的領先天數（左設限以「≥」表示）。</li>
            <li>狀態標籤：資料不足（天數太少或訊號從未亮燈）、無變化（一直亮燈，沒有時機資訊）、樣本偏少（已計算但獨立視窗很少）。這裡沒有任何結果能證明預測有效性。</li>
          </ul>
        </Panel>
        <Panel title="申報事件、公司指引、觀察清單">
          <p className="text-[13px]">事件來自 SEC EDGAR 申報資料（10-Q／10-K／20-F 與 8-K Item 2.02）：觀測日＝報告期末／事件日，公布日＝申報日。只載入 EDGAR 的「recent」區塊，所以會標示每家公司最早的儲存日期。公司指引只收錄附來源網址與原文引述的數字，絕不推測。觀察清單存放在資料庫，只顯示已儲存的觀測值。</p>
        </Panel>
      </>) : null}
    </div>
  );
}
