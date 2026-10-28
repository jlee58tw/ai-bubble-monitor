/**
 * 繁體中文（台灣）介面字典：集中管理所有畫面文字的翻譯。
 * 只翻譯「標籤 / 說明文字」，絕不改動資料數值、公式或分類本身。
 * 找不到對照的後端字串會原樣顯示（多半是原始資料、廠商原文或技術代號）。
 */

/* ---------- 資料分類（classification） ---------- */
export const CLS_ZH: Record<string, string> = {
  reported: "已公布", guidance: "公司指引", estimated: "估計", derived: "推導", qualitative: "定性", disclosed: "公司揭露",
};
export const CLS_HELP: Record<string, string> = {
  reported: "發行公司、交易所或官方機構正式公布的數字（如 SEC 財報 XBRL、證交所、FRED、廠商價目頁）。",
  derived: "本系統依已公布數字計算而得（年增率、比率、市值＝股價×股數、回檔幅度、Q4＝全年−前三季）。",
  estimated: "媒體報導或非公司財報的估計值，未經查核。",
  guidance: "公司在財報新聞稿中給出的前瞻指引（逐字引用原文）。",
  qualitative: "定性或下限說法（例如「超過」某數字），不是精確數值。",
  disclosed: "公司在監管文件（如上市前 S-1）中揭露的數字，未經查核的季度數據。",
};

/* ---------- 狀態標籤 ---------- */
export const STATUS_ZH: Record<string, string> = {
  connected: "已連線", fresh: "最新", unavailable: "無資料", missing: "缺資料", placeholder: "尚未接入", stale: "過期",
  success: "成功", partial: "部分成功", failed: "失敗", running: "執行中", skipped: "略過", ok: "正常",
  insufficient: "資料不足", insufficient_data: "資料不足", current: "現行價", scheduled: "預定調價",
  documented_history: "官方歷史價", warning: "警示", info: "資訊", withheld: "暫不公布", computed: "已計算",
  small_sample: "樣本偏少", no_variation: "無變化", not_point_in_time: "無歷史時點資料", preceded: "有先行",
  no_preceding_signal: "無先行訊號", error: "錯誤", "n/a": "不適用",
};
export const st = (s: string | null | undefined) => (s == null ? "不適用" : STATUS_ZH[s] ?? (s.startsWith("rev v") ? `修訂版 ${s.slice(5)}` : s));

export const CONF_ZH: Record<string, string> = { high: "高", medium: "中", low: "低" };

/* ---------- 風險燈號 ---------- */
export type Level = { key: "low" | "mid" | "high" | "hot" | "na"; label: string; color: string; hex: string; plain: string };
export function riskLevel(score: number | null | undefined): Level {
  if (score == null) return { key: "na", label: "無資料", color: "text-term-muted", hex: "#8b949e", plain: "資料不足，無法給分（不代表沒有風險）。" };
  if (score < 40) return { key: "low", label: "偏低", color: "text-risk-low", hex: "#22c55e", plain: "指標距「過熱」門檻還有距離。" };
  if (score < 60) return { key: "mid", label: "中等", color: "text-risk-mid", hex: "#eab308", plain: "部分指標開始升溫，值得留意。" };
  if (score < 80) return { key: "high", label: "偏高", color: "text-risk-high", hex: "#f97316", plain: "多數指標接近研究假設的「過熱」區。" };
  return { key: "hot", label: "過熱", color: "text-risk-hot", hex: "#ef4444", plain: "指標已達研究假設的「過熱」門檻。" };
}

/* ---------- 六大風險維度 ---------- */
export const DIM_ZH: Record<string, { name: string; plain: string }> = {
  capex_cash: { name: "資本支出 vs 現金流", plain: "雲端巨頭砸錢蓋機房的速度，是否超過本業賺進來的現金。" },
  valuation: { name: "估值與市場壓力", plain: "AI 相關股票貴不貴、近期是否明顯回檔。" },
  monetization: { name: "AI 變現與定價力", plain: "AI 是否真的賺到錢、模型售價是否被迫下殺。" },
  supply_chain: { name: "算力供應鏈", plain: "輝達、台積電等供應商成長是否處於極端景氣。" },
  macro: { name: "總體與資金環境", plain: "利率與信用利差：資金是否便宜到令人鬆懈。" },
  technology: { name: "技術進展與 AI 代理可靠度", plain: "模型能力是否持續進步，足以支撐目前的投資。" },
};

/* ---------- 風險指標 ---------- */
export const IND_ZH: Record<string, { name: string; why: string }> = {
  hyperscaler_capex_to_ocf: { name: "雲端巨頭資本支出／營運現金流（最新一季平均，MSFT GOOGL AMZN META ORCL）", why: "資本支出吃掉大部分甚至全部營運現金流，代表要靠外部資金支應。" },
  hyperscaler_capex_minus_revenue_growth: { name: "資本支出年增率 − 營收年增率（同五家平均）", why: "投資成長長期遠快於營收，是典型的「過度建設」訊號。" },
  hyperscaler_fcf_margin: { name: "雲端巨頭自由現金流率（FCF／營收，最新一季平均）", why: "資本支出吸走現金流，會反映為偏薄甚至為負的自由現金流率。（FCF 年增率在前一年接近零或為負時沒有意義，因此不採用。）" },
  hyperscaler_capex_to_revenue: { name: "雲端巨頭資本支出／營收（平均）", why: "資本密集度遠高於軟體公司的歷史常態。" },
  ai_capex_disclosed: { name: "AI 專屬資本支出（公司揭露）", why: "沒有公司以機器可讀形式揭露「僅 AI」的資本支出。" },
  tw_ai_supply_chain_pe: { name: "台灣 AI 供應鏈本益比（2330、2382、2317 平均，證交所）", why: "硬體供應鏈的高本益比，已反映市場預期 AI 需求會持續。" },
  us_ai_forward_pe: { name: "美國 AI 龍頭預估本益比", why: "預估本益比需要付費授權的市場共識資料。" },
  ai_basket_drawdown: { name: "AI 股票距 52 週高點的回檔（可取得個股平均）", why: "廣泛而深的回檔，代表市場正在下修 AI 預期（屬壓力指標，不是估值水準）。" },
  ai_index_drawdown: { name: "指數距 52 週高點的回檔（那斯達克 100 與費城半導體平均，FRED）", why: "免金鑰的 AI 交易壓力指標（指數層級，不是估值指標）。" },
  ai_revenue_disclosed: { name: "公司揭露的 AI 營收 vs AI 資本支出", why: "AI 營收只零星以下限揭露，且沒有公司揭露 AI 資本支出，無法相比。" },
  ai_lab_compute_intensity: { name: "前沿 AI 實驗室算力與基礎設施費用／營收（Anthropic S-1，最新一季，公司揭露）", why: "推論／訓練算力吃掉前沿實驗室大部分營收，代表 AI 需求尚未能自給自足。單一公司、上市前 S-1 揭露（季度未經查核）；OpenAI 沒有可比揭露。屬研究假設，不是驗證過的門檻。" },
  model_price_deflation: { name: "前沿模型廠商牌價變動中位數（近 365 天）", why: "大幅且普遍的降價，代表商品化速度可能快過用量成長。" },
  nvda_datacenter_revenue_yoy: { name: "輝達資料中心營收年增率（最新一季，SEC XBRL）", why: "供應商極端高成長代表處於投資熱潮期，能否持續並不確定。" },
  gpu_spot_discount: { name: "Azure H100（ND96isr_H100_v5）Spot 價相對隨用隨付牌價的折扣（美東 eastus）", why: "Spot 折扣很深可能代表有閒置算力。注意：牌價很少調整（自 2023-12 未變）。" },
  tsmc_monthly_revenue: { name: "台積電（2330）月營收年增率（證交所 t187ap05_L）", why: "晶圓代工營收成長遠高於約 15% 的長期趨勢，代表處於熱潮期需求（與輝達資料中心同邏輯）。屬研究假設。" },
  us10y: { name: "美國 10 年期公債殖利率（FRED DGS10）", why: "折現率上升會壓縮長天期估值並提高融資成本。" },
  credit_spreads: { name: "穆迪 Baa 公司債 − 10 年期公債利差（FRED BAA10Y）", why: "信用利差極窄代表風險定價過於樂觀，常見於景氣末段（窄＝過熱）。代理指標：投資等級 Baa 利差；ICE 美銀高收益債利差因授權需事先核准而未採用。屬研究假設。" },
  metr_doubling_time: { name: "METR 任務時長倍增時間（2023 年起擬合，天）", why: "能力成長放緩，會削弱目前資本支出背後的論點。" },
  terminal_bench_top: { name: "Terminal-Bench 最高正確率（僅最新資料集版本）", why: "AI 代理在真實任務的成功率偏低，代表需要昂貴的人工覆核（見 ROI 模擬器）。" },
  composite_partial: { name: "時點綜合風險分數（部分覆蓋）", why: "" },
  score_gated: { name: "正式風險分數（需達覆蓋率門檻）", why: "" },
};
export const indName = (id: string, fallback: string) => IND_ZH[id]?.name ?? fallback;
export const indWhy = (id: string, fallback: string) => IND_ZH[id]?.why || tx(fallback);

/* ---------- 指標（metric）名稱與警語 ---------- */
export const METRIC_ZH: Record<string, string> = {
  ai_lab_compute_cost: "AI 實驗室算力與基礎設施費用（公司揭露，S-1）",
  ai_lab_operating_income: "AI 實驗室營業利益（損失）（公司揭露，S-1）",
  ai_lab_operating_income_media: "AI 實驗室營業利益（損失）（媒體報導）",
  ai_lab_revenue: "AI 實驗室季營收（公司揭露，S-1）",
  ai_lab_revenue_media: "AI 實驗室季營收（媒體報導）",
  ai_lab_run_rate_media: "AI 實驗室年化營收 run-rate（媒體報導）",
  ai_revenue_disclosed: "AI 營收／run-rate（公司揭露，下限）",
  azure_growth_yoy: "Azure 與其他雲端服務營收年增率（公司公布 %）",
  cloud_segment_operating_income: "雲端部門營業利益（MSFT 智慧雲、Google Cloud、AWS）",
  cloud_segment_operating_margin: "雲端部門營業利益率",
  cloud_segment_revenue: "雲端部門營收（MSFT 智慧雲、Google Cloud、AWS）",
  cloud_segment_revenue_yoy: "雲端部門營收年增率",
  nvda_datacenter_revenue: "輝達資料中心營收",
  ai_capex_disclosed: "AI 專屬資本支出（公司揭露）",
  aws_segment_capex: "AWS 部門長期資產增加數",
  capex_guidance: "資本支出指引（8-K 財報新聞稿逐字）",
  capex_to_ocf: "資本支出／營運現金流",
  capex_to_revenue: "資本支出／營收",
  capex_total: "公司總資本支出（現金）",
  capex_total_big4_cal: "四大雲端巨頭資本支出（日曆季合計）",
  capex_total_big4_cal_yoy: "四大雲端巨頭資本支出年增率",
  capex_yoy: "資本支出年增率",
  fcf: "自由現金流（營運現金流 − 資本支出）",
  fcf_yoy: "自由現金流年增率",
  ocf_yoy: "營運現金流年增率",
  operating_cash_flow: "營運現金流",
  revenue: "總營收",
  revenue_yoy: "營收年增率",
  baa_10y_spread: "穆迪 Baa 公司債殖利率 − 10 年期公債",
  us10y_yield: "美國 10 年期公債殖利率",
  us2y_yield: "美國 2 年期公債殖利率",
  us_10y2y_spread: "美債 10 年 − 2 年利差",
  tw_monthly_revenue: "月營收（上市公司申報）",
  tw_monthly_revenue_yoy: "月營收年增率（交易所公布）",
  tw_revenue_ytd_yoy: "累計營收年增率（交易所公布）",
  forward_pe: "預估本益比（市場共識 EPS）",
  market_cap: "市值（美股，推導）",
  tw_dividend_yield: "殖利率（證交所計算）",
  tw_drawdown_52w: "距 52 週高點回檔（證交所收盤）",
  tw_market_cap: "市值（新台幣）",
  tw_pb_ratio: "股價淨值比（證交所計算）",
  tw_pe_trailing: "本益比（證交所計算，過去四季）",
  tw_price_close: "收盤價（證交所）",
  tw_shares_outstanding: "已發行普通股（證交所公司資料）",
  us_drawdown_52w: "距 52 週高點回檔（美股，還原分割）",
  us_index_close: "美國股價指數收盤（那斯達克 100、那斯達克綜合、費城半導體）",
  us_index_drawdown_52w: "距 52 週高點回檔（美國指數）",
  us_price_close: "收盤價（美股原始價）",
  us_price_split_adj: "還原分割收盤價（美股，價格報酬）",
  us_rel_return_1y_vs_ndx: "近一年相對那斯達克 100 的價格報酬",
  us_rel_return_1y_vs_sox: "近一年相對費城半導體（SOX）的價格報酬",
  us_shares_outstanding: "流通在外普通股（SEC 封面頁）",
  us_split_factor: "股票分割比例（美股）",
};
export const metricName = (id: string | null | undefined, fallback?: string | null) => (id ? METRIC_ZH[id] ?? fallback ?? id : fallback ?? "");

export const METRIC_WARN_ZH: Record<string, string> = {
  ai_lab_operating_income_media: "媒體報導的估計值（知情人士／投資簡報），未經查核，不是公司申報的財報。",
  ai_lab_revenue_media: "媒體報導的估計值（知情人士／投資簡報），未經查核，不是公司申報的財報。",
  ai_lab_run_rate_media: "媒體報導的估計值（知情人士／投資簡報），未經查核，不是公司申報的財報。",
  ai_revenue_disclosed: "下限（「超過」）；公司自行定義、未經查核、單一公司。",
  cloud_segment_operating_income: "各公司自行定義的部門利益（分攤規則不同）；不是 AI 專屬。",
  cloud_segment_revenue: "雲端部門範圍比 AI 大：MSFT 智慧雲還包含伺服器產品、GitHub、Nuance 與企業服務；Google Cloud 含 Workspace；AWS 含所有雲端服務。",
  nvda_datacenter_revenue: "資料中心含網通與非 AI 運算；它是最接近、經查核的 AI 需求代理指標，不等於「AI 營收」。",
  ai_capex_disclosed: "無資料——絕不以總資本支出替代。",
  aws_segment_capex: "AWS 資本支出是最接近、經查核的雲端／AI 基礎設施拆分，但仍不是僅限 AI。",
  capex_total: "公司總資本支出，不是 AI 專屬。不含融資租賃新增（對 MSFT/ORCL/META 影響重大）。",
  capex_total_big4_cal: "公司總資本支出，不是 AI 專屬。ORCL 不納入（財年季度非日曆季）。",
  baa_10y_spread: "投資等級 Baa 利差，不是高收益債，也不是資料中心專屬。",
  tw_monthly_revenue: "公司總營收，不是僅 AI。3231 緯創與 6669 緯穎為 AI 伺服器代工廠（僅月營收）。",
  forward_pe: "無資料——市場共識預估需付費授權。",
  market_cap: "推導值，不是資料商市值。股數有落後（以封面頁日期為準），之後的買回／增發未反映。GOOGL/META 無資料。",
  tw_drawdown_52w: "未還原收盤價：除息造成的跌幅會略為高估回檔。",
  tw_market_cap: "使用 45 天內最接近的股數快照；股數歷史從開始擷取時起算。",
  us_index_close: "價格報酬指數水準。FRED NASDAQSOX 早期歷史偶有重複／過期值。",
  us_price_close: "需要 TIINGO_API_KEY（或 ALPHAVANTAGE_API_KEY）。原始收盤價，未還原分割／股利。TSM 為紐約證交所 ADR（1 ADR＝5 股）。",
  us_price_split_adj: "僅價格報酬（不含股利）。每次記錄到新分割時會修訂。",
  us_rel_return_1y_vs_ndx: "僅價格報酬（雙方皆不含股利）。需要股價金鑰（Tiingo／Alpha Vantage）。",
  us_rel_return_1y_vs_sox: "僅價格報酬（雙方皆不含股利）。需要股價金鑰（Tiingo／Alpha Vantage）。",
  us_shares_outstanding: "GOOGL／META 未涵蓋（多類股，只有分類別股數）。TSM 為年度快照。",
  us_split_factor: "只在分割日記錄；沒有紀錄代表 Tiingo 未回報分割（Alpha Vantage 免費版無分割資料）。",
};
export const metricWarn = (id: string | null | undefined, fallback: string | null | undefined) => (id && METRIC_WARN_ZH[id]) || (fallback ? tx(fallback) : null);

/* ---------- 實體名稱 ---------- */
export const ENTITY_ZH: Record<string, string> = {
  MSFT: "微軟 MSFT", GOOGL: "Alphabet GOOGL", AMZN: "亞馬遜 AMZN", META: "Meta", ORCL: "甲骨文 ORCL", NVDA: "輝達 NVDA",
  AMD: "超微 AMD", TSM: "台積電 ADR (TSM)", "2330": "台積電 2330", "2382": "廣達 2382", "2317": "鴻海 2317", "3231": "緯創 3231", "6669": "緯穎 6669",
  BIG4_CAL: "四大雲端巨頭", US: "美國", ANTHROPIC: "Anthropic", OPENAI: "OpenAI", NDX: "那斯達克 100", COMP: "那斯達克綜合", SOX: "費城半導體",
  QQQ: "QQQ (ETF)", SOXX: "SOXX (ETF)", SMH: "SMH (ETF)", TW_BASKET: "台股 AI 籃子", US_AI_BASKET: "美股 AI 籃子",
};
export const ent = (id: string | null | undefined) => (id ? ENTITY_ZH[id] ?? id : "");

/* ---------- 其他代號 ---------- */
export const PRICE_TYPE_ZH: Record<string, string> = { input: "輸入", output: "輸出", cached_input: "快取輸入" };
export const ALERT_CAT_ZH: Record<string, string> = { capex: "資本支出", valuation: "估值", pricing: "模型定價", risk: "風險分數", data_quality: "資料品質" };
export const EVENT_TYPE_ZH: Record<string, string> = { periodic_report: "定期財報", earnings_release_8k: "財報新聞稿 8-K" };
export const PRICE_KIND_ZH: Record<string, string> = { list_on_demand: "隨用隨付牌價", list_spot: "Spot 牌價" };
export const TIER_ZH = (t: string) => t.replace("standard", "標準").replace("(for prompts up to 100,000 tokens)", "（提示 ≤ 10 萬 tokens）")
  .replace("(for prompts over 100,000 tokens)", "（提示 > 10 萬 tokens）").replace("(short context)", "（短上下文）").replace("(paid)", "（付費）").replace("(routed)", "（轉接）");

/* ---------- 後端說明文字：完全比對 ---------- */
const PHRASES: Record<string, string> = {
  "Research prototype. Thresholds are research hypotheses, not validated predictions.": "研究原型。門檻皆為研究假設，不是經驗證的預測。",
  "No company discloses AI-only capex in machine-readable form (metric ai_capex_disclosed is UNAVAILABLE).": "沒有公司以機器可讀形式揭露「僅 AI」的資本支出（指標 ai_capex_disclosed 無資料）。",
  "Forward consensus estimates need a licensed data source (metric forward_pe is UNAVAILABLE).": "預估本益比需要付費授權的市場共識資料（指標 forward_pe 無資料）。",
  "Hyperscaler AI revenue is disclosed only irregularly and as lower bounds (e.g. AMZN 'exceeded $25B AWS AI run rate', 8-K 2026-07-30); no company discloses AI capex, so 'AI revenue vs AI capex' cannot be computed.":
    "雲端巨頭的 AI 營收只零星以「下限」方式揭露（例：AMZN 稱 AWS AI 年化營收「超過 250 億美元」，8-K 2026-07-30）；沒有公司揭露 AI 資本支出，因此無法計算「AI 營收 vs AI 資本支出」。",
  "FCF = operating cash flow - capex (derived from SEC XBRL).": "自由現金流＝營運現金流 − 資本支出（依 SEC XBRL 推導）。",
  "Derived from exchange closing prices.": "依交易所收盤價推導。",
  "Missing indicators are not treated as zero risk.": "缺少的指標不視為零風險。",
  "Indicator score = linear interpolation between `benign` (0) and `stretched` (100), clamped.": "指標分數＝在「溫和」（0 分）與「過熱」（100 分）兩門檻之間線性內插，超出範圍則截斷。",
  "Missing / unavailable / stale indicators are EXCLUDED from the point score and never treated as 0 risk:": "缺資料／無資料／過期的指標「不納入」點分數，也絕不視為 0 風險：",
  "coverage = sum of (dimension weight x indicator share) actually available.": "覆蓋率＝實際可取得指標的（維度權重 × 指標占比）加總。",
  "Below min_coverage no precise overall score is returned (score=None), only the range.": "覆蓋率低於最低門檻時，不給精確總分，只顯示可能範圍。",
  "Backtest of research-hypothesis thresholds on a very short window. No predictive validity is claimed.": "以極短期間回測研究假設門檻，不主張任何預測能力。",
  "Research prototype. Not investment advice and NOT evidence that any signal predicts drawdowns.": "研究原型。不是投資建議，也「不能」證明任何訊號可預測跌勢。",
  "TWSE outcomes cover only ~13 months (a handful of independent windows). US outcomes (Tiingo, split-adjusted, price return, 2015 onward) are longer, but the windows overlap heavily, the 8 stocks are highly correlated, and US mega-caps were selected with hindsight (survivorship / selection bias: today's AI winners).":
    "台股結果只涵蓋約 13 個月（少數獨立區間）。美股結果（Tiingo、還原分割、價格報酬、2015 年起）較長，但區間大量重疊、8 檔股票高度相關，且美國大型股是事後挑選（倖存者／選擇偏誤：今天的 AI 贏家）。",
  "Before ~2016 most indicators are missing (52-week drawdowns need a year of history; several SEC series start later), so early signal days are partial-coverage composites, not the live score.":
    "約 2016 年以前多數指標缺資料（52 週回檔需一年歷史；部分 SEC 序列較晚開始），因此早期訊號是部分覆蓋的綜合分數，不是即時分數。",
  "Price-based signals (ai_basket_drawdown, ai_index_drawdown, and the composite that includes them) are computed from the same/overlapping price series as the outcomes, so any association partly reflects volatility clustering, not bubble detection.":
    "以價格為基礎的訊號（ai_basket_drawdown、ai_index_drawdown 及包含它們的綜合分數）與結果使用相同／重疊的價格序列，因此任何關聯有一部分只是波動聚集，不是偵測到泡沫。",
  "Split-adjusted closes use split factors known today; this rescales whole pre-split histories by a constant, which leaves every return and drawdown unchanged (no information about future prices).":
    "還原分割收盤價使用今天已知的分割比例；這只是把分割前的整段歷史乘上常數，所有報酬與回檔都不變（不含未來價格資訊）。",
  "Forward windows overlap day to day; intervals use an overlap-adjusted effective sample size (n / H) and are approximate.": "前瞻區間逐日重疊；信賴區間使用重疊調整後的有效樣本數（n / H），僅為近似值。",
  "Thresholds are the same research hypotheses as the live risk engine; they were not fitted to this window, but nothing here is out-of-sample validation either.": "門檻與即時風險引擎相同，皆為研究假設；未針對此期間擬合，但這裡也不是樣本外驗證。",
  "Fundamental signals (SEC quarterly data) change only at filing dates; a signal that is ON for the whole window carries no timing information (its hit rate equals the base rate).": "基本面訊號（SEC 季資料）只在申報日變動；整段期間都亮燈的訊號不含任何時機資訊（命中率等於基準率）。",
  "Dataset-based indicators (model prices, GPU prices, benchmarks) have no stored history before they were first collected and are excluded (not_point_in_time); missing indicators widen the range and never count as zero risk.": "資料集型指標（模型價格、GPU 價格、基準測試）在首次蒐集前沒有歷史，因此排除（無歷史時點資料）；缺少的指標會放寬範圍，絕不算作零風險。",
  "signal ON on every evaluable day: hit rate = base rate, no timing information": "每個可評估日訊號都亮燈：命中率＝基準率，沒有時機資訊",
  "signal never ON in the evaluable window": "可評估期間內訊號從未亮燈",
  "TWSE STOCK_DAY": "證交所 STOCK_DAY", "equal-weight of available TWSE codes": "可取得台股代號等權重", "Tiingo EOD, split-adjusted (price return)": "Tiingo 日收盤，還原分割（價格報酬）",
  "equal-weight (rebased) of available US AI stocks, common dates": "可取得美股 AI 個股等權重（重設基期），共同交易日",
  "https://data.sec.gov/submissions/ (SEC EDGAR submissions API)": "https://data.sec.gov/submissions/（SEC EDGAR 申報 API）",
  "EDGAR reportDate = fiscal period end (10-Q/10-K/20-F) or event date (8-K)": "EDGAR reportDate＝財報期末（10-Q/10-K/20-F）或事件日（8-K）",
  "EDGAR filingDate = date the filing became public": "EDGAR filingDate＝文件公開日",
  "8-K containing Item 2.02 (Results of Operations and Financial Condition)": "含 Item 2.02（營運結果與財務狀況）的 8-K",
  "EDGAR 'recent' block only (latest ~1,000 filings of any type); older events not loaded": "僅載入 EDGAR「近期」區塊（各類最新約 1,000 份文件）；更早的事件未載入",
  "No EDGAR CIK. TWSE/MOPS filing calendars are not connected.": "沒有 EDGAR CIK；證交所／公開資訊觀測站的申報行事曆尚未接入。",
  "Azure list prices (pay-as-you-go and Spot), Linux, region eastus. Not negotiated, reserved or marketplace rental rates. usd_per_gpu_hour = instance price / GPU count.": "Azure 牌價（隨用隨付與 Spot）、Linux、美東 eastus 區。不是議價、預留或市集租賃價。每 GPU 小時價格＝執行個體價格 ÷ GPU 數。",
  "GPU marketplace rental price (H100/H200 $/GPU-hr)": "GPU 市集租賃價（H100/H200 每 GPU 小時美元）",
  "No marketplace/neocloud price source with terms that clearly permit automated collection was identified. Hyperscaler list prices (Azure) are shown instead; they are sticky list prices and do not reflect negotiated, reserved or secondary-market rental rates.": "找不到條款明確允許自動蒐集的市集／新雲端價格來源，因此改顯示雲端巨頭（Azure）牌價；牌價很少調整，不反映議價、預留或二手市場租賃價。",
  "Prices are USD per 1M tokens, list/standard tier as published by the vendor.": "價格為每 100 萬 tokens 的美元價，採廠商公布的牌價／標準方案。",
  "observed = first_seen_at/last_seen_at (UTC) when this app saw the price; effective_from/to only when the vendor documents it. History before the first observation is shown only where the vendor documents it (price_status=documented_history).": "「觀察時間」＝本系統首次／最後看到該價格的時間；生效起訖日只在廠商有文件記載時顯示。首次觀察前的歷史價只在廠商文件有記載時顯示（官方歷史價）。",
  "Rows no longer present in the latest successful snapshot of their vendor page are hidden (include_stale=true shows them with in_latest_snapshot=false).": "已不在廠商頁面最新快照中的價格列會隱藏。",
  "METR time horizon: task length (human-expert minutes) at which the model succeeds 50%/80% of the time. Date = model release date. Estimates above ~16 h are flagged as unreliable by METR.": "METR 任務時長：模型有 50%／80% 機率成功的任務長度（以人類專家所需分鐘計）。日期＝模型發布日。超過約 16 小時的估計值 METR 標註為不可靠。",
  "SWE-bench: % of GitHub issues resolved. Each split (Verified/Lite/Full test/Multimodal/Multilingual) is a different task set; results are only comparable within one split. Date = submission date.": "SWE-bench：解決 GitHub issue 的比例。每個子集（Verified／Lite／完整測試／多模態／多語言）任務不同，只能在同一子集內比較。日期＝提交日。",
  "Terminal-Bench: % of terminal tasks solved (agent harness + model). Only comparable within the same dataset version. CI = 95% half-width from the leaderboard.": "Terminal-Bench：完成終端機任務的比例（代理框架＋模型）。只能在同一資料集版本內比較。信賴區間＝排行榜提供的 95% 半寬。",
  "ALPHAVANTAGE_API_KEY not set (optional free key)": "未設定 ALPHAVANTAGE_API_KEY（選用的免費金鑰）",
  "Not covered: multi-class issuer, no single SEC share count": "未涵蓋：多類股發行公司，沒有單一 SEC 股數",
};

/* ---------- 後端說明文字：樣板（正規表示式） ---------- */
const PATTERNS: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^(\S+): capex growth ([+-]?[\d.]+%) vs revenue growth ([+-]?[\d.]+%) \((.+)\)$/, (m) => `${ent(m[1])}：資本支出年增 ${m[2]}，營收年增 ${m[3]}（${fp(m[4])}）`],
  [/^Capex YoY exceeds revenue YoY by (-?\d+) pp \(threshold (\d+)%\)\.$/, (m) => `資本支出年增率高於營收年增率 ${m[1]} 個百分點（門檻 ${m[2]}%）。`],
  [/^(\S+): negative free cash flow \$(-?[\d.,]+)B \((.+)\)$/, (m) => `${ent(m[1])}：自由現金流為負 ${usdYi(parseFloat(m[2].replace(/,/g, "")) * 1e9)}（${fp(m[3])}）`],
  [/^(\S+): (-?[\d.]+%) from 52-week high \(close (\S+)\)$/, (m) => `${ent(m[1])}：距 52 週高點 ${m[2]}（收盤日 ${m[3]}）`],
  [/^(\S+) (.+) (input|output|cached_input): scheduled \$([\d.]+)\/MTok from (\S+)(?: \(([+-]\d+%) vs current \$([\d.]+)\))?$/,
    (m) => `${m[1]} ${m[2]} ${PRICE_TYPE_ZH[m[3]]}：預定自 ${m[5]} 起調為每百萬 tokens $${m[4]}${m[6] ? `（較目前 $${m[7]} ${m[6]}）` : ""}`],
  [/^(\S+) (.+) (input|output|cached_input): \$([\d.]+) -> \$([\d.]+)\/MTok \(([+-]\d+%)\)$/, (m) => `${m[1]} ${m[2]} ${PRICE_TYPE_ZH[m[3]]}：每百萬 tokens $${m[4]} → $${m[5]}（${m[6]}）`],
  [/^Observed change between (\S+) and (\S+) \(tier: (.+)\)\.$/, (m) => `觀察到的變動介於 ${m[1]} 與 ${m[2]}（方案：${TIER_ZH(m[3])}）。`],
  [/^Vendor text: (.*)$/s, (m) => `廠商原文：${m[1]}`],
  [/^Risk score rose ([\d.]+) -> ([\d.]+)$/, (m) => `風險分數上升 ${m[1]} → ${m[2]}`],
  [/^Risk coverage (\d+)% below minimum (\d+)% - no point score$/, (m) => `風險覆蓋率 ${m[1]}% 低於最低門檻 ${m[2]}%，不給點分數`],
  [/^Source (\S+): last run (\S+)$/, (m) => `資料來源 ${m[1]}：最近一次執行 ${st(m[2])}`],
  [/^only ~([\d.]+) independent (\d+)-day windows$/, (m) => `僅約 ${m[1]} 個獨立的 ${m[2]} 日區間`],
  [/^(\d+) days with both a point-in-time signal and an observable (\d+)-day outcome \(need >= (\d+)\)$/, (m) => `同時具備時點訊號與可觀察 ${m[2]} 日結果的天數只有 ${m[1]} 天（至少需要 ${m[3]} 天）`],
  [/^observed price history is (\d+) days \(since (\S+)\); need (\d+)\. Undocumented past prices are never back-filled\.$/, (m) => `已觀察到的價格歷史只有 ${m[1]} 天（自 ${m[2]} 起），需要 ${m[3]} 天。沒有文件記載的過去價格絕不回補。`],
  [/^spot \$([\d.]+)\/h vs list \$([\d.]+)\/h \((\S+), Linux\)$/, (m) => `Spot 每小時 $${m[1]} vs 牌價每小時 $${m[2]}（${m[3]}，Linux）`],
  [/^METR-Horizon-v([\d.]+); 95% CI ([\d.]+)-([\d.]+) days$/, (m) => `METR-Horizon-v${m[1]}；95% 信賴區間 ${m[2]}–${m[3]} 天`],
  [/^(.+) vs (.+)$/, (m) => /^FY\d{4} Q\d [\d,]+$/.test(m[1]) ? `${m[1]} 對比 ${m[2]}` : m[0]],
];

/** 翻譯一段後端字串；找不到對照時原樣回傳（通常為原始資料或廠商原文）。 */
export function tx(s: string | null | undefined): string {
  if (s == null) return "";
  if (PHRASES[s]) return PHRASES[s];
  for (const [re, f] of PATTERNS) { const m = s.match(re); if (m) return f(m); }
  return s;
}

/* ---------- 數字與日期格式（台北習慣） ---------- */
const nf = (d: number) => new Intl.NumberFormat("zh-TW", { maximumFractionDigits: d, minimumFractionDigits: 0 });
export const num = (v: number | null | undefined, d = 2) => (v == null || Number.isNaN(v) ? "—" : nf(d).format(v));
/** 美元金額 → 「1,234.5 億美元」或「2.35 兆美元」 */
export function usdYi(v: number | null | undefined, d = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  const a = Math.abs(v), s = v < 0 ? "-" : "";
  if (a >= 1e12) return `${s}${nf(2).format(a / 1e12)} 兆美元`;
  if (a >= 1e8) return `${s}${nf(d).format(a / 1e8)} 億美元`;
  if (a >= 1e4) return `${s}${nf(1).format(a / 1e4)} 萬美元`;
  return `${s}${nf(2).format(a)} 美元`;
}
export function twdYi(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  const a = Math.abs(v), s = v < 0 ? "-" : "";
  if (a >= 1e12) return `${s}新台幣 ${nf(2).format(a / 1e12)} 兆元`;
  if (a >= 1e8) return `${s}新台幣 ${nf(1).format(a / 1e8)} 億元`;
  return `${s}新台幣 ${nf(0).format(a)} 元`;
}
export const pctZh = (v: number | null | undefined, d = 1, sign = false) => (v == null || Number.isNaN(v) ? "—" : `${sign && v > 0 ? "+" : ""}${(v * 100).toFixed(d)}%`);
/** 2026-10-28 → 2026/10/28 */
export const dt = (s: string | null | undefined) => (s ? s.slice(0, 10).replace(/-/g, "/") : "—");
/** FY2026 Q4 → FY2026 第4季 */
export const fp = (s: string | null | undefined) => (s ? s.replace(/^FY(\d{4}) Q(\d)$/, "FY$1 第$2季").replace(/^FY(\d{4})$/, "FY$1 全年") : "—");
export const UNIT_ZH: Record<string, string> = { USD: "美元", TWD: "新台幣", pct: "%", ratio: "倍", pct_points: "%", shares: "股", index: "點" };
/** 依單位格式化一個觀測值 */
export function fmtObs(v: number | null | undefined, unit: string): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (unit === "USD") return usdYi(v);
  if (unit === "TWD") return twdYi(v);
  if (unit === "pct") return pctZh(v);
  if (unit === "ratio") return `${num(v, 3)} 倍`;
  if (unit === "pct_points") return `${num(v, 2)}%`;
  if (unit === "shares") return `${num(v / 1e8, 2)} 億股`;
  if (unit === "index") return `${num(v, 2)} 點`;
  return `${num(v, 3)}${unit ? ` ${unit}` : ""}`;
}
