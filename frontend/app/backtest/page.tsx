"use client";
import { ANIM, GRID, TICK, TT } from "@/lib/chart";
import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Hypothesis, Loading, PageIntro, Panel } from "@/components/Panel";
import { ent, indName, st, tx } from "@/lib/i18n";
import { ApiError, useApi } from "@/components/useApi";
import { API_BASE } from "@/lib/api";
import { STATIC, staticCsv } from "@/lib/static";

type Eval = { status: string; reason?: string; n_signal_known_days: number; n_independent_windows: number; n_on?: number; n_off?: number;
  hits_on?: number; hits_off?: number; hit_rate_on?: number | null; hit_rate_off?: number | null; base_rate?: number;
  ci95_on_overlap_adjusted?: [number, number] | null; lift_vs_base?: number | null };
type Lead = { peak_date: string; trigger_date: string; max_drawdown: number; status: string; signal_on_since?: string;
  lead_days_to_trigger?: number; lead_days_to_peak?: number; left_censored?: boolean; peak_at_history_start: boolean };
type Sig = { id: string; name: string; threshold: number; status: string; reason?: string; days_known: number; share_on: number | null;
  per_series: Record<string, Eval>; lead_times: Record<string, Lead[]> };
type Bt = { computed_for: string; config_hash: string; label: string; caveats: string[]; params: Record<string, number>;
  window: { start: string | null; end: string | null; trading_days: number };
  series_status: Record<string, { status: string; days?: number; reason?: string; source?: string }>;
  excluded_indicators: { id: string; status: string }[];
  episodes: Record<string, { peak_date: string; trigger_date: string; trough_date: string; max_drawdown: number; recovered_date: string | null; peak_at_history_start: boolean }[]>;
  signals: Sig[];
  daily: { date: string; coverage: number; composite_partial: number | null; close: Record<string, number | null> }[];
  history_monthly: { date: string; coverage: number; composite_partial: number | null; score_low: number; score_high: number }[] };

const pct = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
const dts = (s: string | null | undefined) => (s ? s.slice(0, 10).replace(/-/g, "/") : "—");
const STAT: Record<string, string> = { small_sample: "text-term-amber", no_variation: "text-term-muted", insufficient_data: "text-term-down", computed: "text-white" };

export default function Backtest() {
  const [p, setP] = useState({ horizon: 20, drawdown: 0.1, composite_threshold: 60, indicator_threshold: 70 });
  const q = new URLSearchParams(Object.entries(p).map(([k, v]) => [k, String(v)])).toString();
  const { data: r, error, loading } = useApi<Bt>(`/api/backtest?${q}`);
  const [selRaw, setSel] = useState<string | null>(null);
  const sel = selRaw ?? (r && r.episodes["US_AI_BASKET"] ? "US_AI_BASKET" : "TW_BASKET");
  const daily = (r?.daily ?? []).map((d) => ({ date: d.date, composite: d.composite_partial, price: d.close[sel] ?? null }));
  const hist = (r?.history_monthly ?? []).map((h) => ({ ...h, band: [h.score_low, h.score_high], cov: h.coverage * 100 }));
  const series = r ? Object.keys(r.episodes) : [];
  return (
    <div className="space-y-4">
      <PageIntro emoji="🔬" title="歷史訊號回測（時點重建）"
        what={<>把風險指標「倒帶」回過去每一天，只用當天已經公布的資料重算，再看訊號亮起後，股價是否在接下來一段期間大跌。目的是檢驗門檻設定，<b>不是證明能預測</b>。</>}
        how={<>看「命中率（訊號亮）」和「基準率」的差距：差不多就代表訊號沒有額外資訊。樣本偏少、信賴區間很寬時，任何結論都不可靠。</>} />
      <div className="panel p-3 border-term-down text-[12px] space-y-1">
        <div className="text-term-down font-semibold">⚠️ 這不是預測有效性的證據。{tx(r?.label)}</div>
        <ul className="list-disc ml-4 text-term-muted">{(r?.caveats ?? []).map((c) => <li key={c}>{tx(c)}</li>)}</ul>
      </div>
      {error ? <ApiError error={error} /> : null}<Loading show={loading} />
      <div className="panel p-3">
        <div className="flex flex-wrap gap-4 text-xs items-end">
          {([["horizon", "往後觀察期（交易日）", 1], ["drawdown", "跌幅達多少算命中（0–1）", 0.01],
            ["composite_threshold", "綜合分數 ≥ 多少算亮燈", 1], ["indicator_threshold", "單一指標 ≥ 多少算亮燈", 1]] as const).map(([k, l, st]) => (
            <label key={k} className="flex flex-col gap-1"><span className="text-term-muted">{l}</span>
              <input type="number" step={st} value={p[k]} onChange={(e) => { const v = parseFloat(e.target.value); if (!Number.isNaN(v)) setP({ ...p, [k]: v }); }}
                className="w-28 bg-black border border-term-border text-white px-1 py-0.5 text-right font-mono" /></label>))}
          <a className="btn" href={STATIC ? staticCsv("backtest_default.csv") : `${API_BASE}/api/backtest.csv?${q}`}>下載 CSV（每日）</a>
          <span className="text-term-muted">期間 {dts(r?.window.start)} → {dts(r?.window.end)} · {r?.window.trading_days ?? 0} 個交易日 · 設定雜湊 <span className="font-mono">{r?.config_hash}</span></span>
        </div>
        {STATIC ? <div className="text-[11px] text-term-muted mt-1">靜態快照版只提供預設參數的結果；調整參數需連線到 API。</div> : null}
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="結果序列（用來檢驗的股價）">
          <div className="overflow-x-auto max-h-[320px]"><table className="w-full text-[11px] font-mono"><tbody>{r && Object.entries(r.series_status).map(([k, v]) => (
            <tr key={k} className="border-t border-term-border"><td>{ent(k)}</td><td className={v.status === "ok" ? "text-term-up" : "text-term-down"}>{v.status === "ok" ? "正常" : st(v.status)}</td>
              <td className="text-term-muted">{v.days != null ? `${v.days.toLocaleString("zh-TW")} 天 · ` : ""}{tx(v.source ?? v.reason)}</td></tr>))}</tbody></table></div>
          <div className="text-[11px] text-term-muted mt-2">未納入時點重建的指標（範圍放寬，絕不算作 0 分）：{" "}
            {r?.excluded_indicators.map((x) => `${indName(x.id, x.id)}（${st(x.status)}）`).join("、")}</div>
        </Panel>
        <Panel title={`時點綜合分數（部分覆蓋）vs ${ent(sel)} 收盤價`} info="橘線是只用當時已公布資料重算的綜合分數（左軸 0–100）；藍線是股價（右軸）。這不是正式公布的風險分數。">
          <div className="flex flex-wrap gap-1 mb-1">{series.map((s) => <button key={s} className={`btn ${s === sel ? "!bg-term-amber !text-black" : ""}`} onClick={() => setSel(s)}>{ent(s)}</button>)}</div>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={daily}><CartesianGrid stroke={GRID} strokeDasharray="3 3" /><XAxis dataKey="date" tick={TICK} minTickGap={40} tickFormatter={dts} />
              <YAxis yAxisId="s" domain={[0, 100]} tick={TICK} /><YAxis yAxisId="p" orientation="right" tick={TICK} domain={["auto", "auto"]} />
              <Tooltip {...TT} labelFormatter={dts} />
              <Line {...ANIM} yAxisId="s" dataKey="composite" stroke="#f59e0b" strokeWidth={2} dot={false} name="綜合分數（部分覆蓋）" connectNulls={false} />
              <Line {...ANIM} yAxisId="p" dataKey="price" stroke="#60aaff" strokeWidth={1.5} dot={false} name={`${ent(sel)} 收盤價`} />
            </ComposedChart>
          </ResponsiveContainer>
        </Panel>
      </div>
      <Panel title="訊號評估：命中＝訊號亮燈，且收盤價在 H 個交易日內下跌 ≥ X%" info="命中率（亮）要明顯高於基準率才有意義；95% 信賴區間已針對重疊視窗調整，樣本越少區間越寬。">
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted whitespace-nowrap"><tr><th className="text-left">訊號</th><th>序列</th><th>狀態</th><th>可評估天數</th><th>約略獨立視窗</th>
            <th>亮燈天數</th><th>命中率（亮）</th><th>95% 信賴區間</th><th>命中率（未亮）</th><th>基準率</th><th className="text-left">說明</th></tr></thead>
          <tbody>{r?.signals.map((s) => s.status !== "computed" ? (
            <tr key={s.id} className="border-t border-term-border"><td>{indName(s.id, s.name)} <span className="text-term-muted">≥{s.threshold}</span></td><td>全部</td>
              <td className="text-term-down">資料不足</td><td colSpan={8} className="text-term-muted">{tx(s.reason)}</td></tr>
          ) : Object.entries(s.per_series).map(([k, e], i) => (
            <tr key={s.id + k} className="border-t border-term-border text-center">
              <td className="text-left min-w-[180px]">{i === 0 ? <><span title={s.name}>{indName(s.id, s.name)}</span> <span className="text-term-muted">≥{s.threshold} · 亮燈 {pct(s.share_on, 0)}</span></> : ""}</td>
              <td className="whitespace-nowrap">{ent(k)}</td><td className={STAT[e.status]}>{st(e.status)}</td><td>{e.n_signal_known_days}</td><td>{e.n_independent_windows}</td>
              <td>{e.n_on ?? "—"}</td><td>{pct(e.hit_rate_on)}</td><td>{e.ci95_on_overlap_adjusted ? `${pct(e.ci95_on_overlap_adjusted[0], 0)}–${pct(e.ci95_on_overlap_adjusted[1], 0)}` : "—"}</td>
              <td>{pct(e.hit_rate_off)}</td><td>{pct(e.base_rate)}</td><td className="text-left text-term-muted">{tx(e.reason)}</td></tr>)))}</tbody></table></div>
      </Panel>
      <Panel title={`修正事件：${ent(sel)}（從歷史高點下跌 ≥ X%，限可用歷史）與訊號領先天數 · 在上方選擇序列`}>
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted"><tr><th className="text-left">序列</th><th>高點</th><th>確認日（≤ −X%）</th><th>最大跌幅</th>
            {r?.signals.filter((s) => s.status === "computed").map((s) => <th key={s.id} title={s.name} className="max-w-[90px] break-words font-sans">{indName(s.id, s.id)}</th>)}</tr></thead>
          <tbody>{series.filter((k) => k === sel).flatMap((k) => (r?.episodes[k] ?? []).map((ep, j) => (
            <tr key={k + j} className="border-t border-term-border text-center"><td className="text-left whitespace-nowrap">{ent(k)}</td>
              <td>{dts(ep.peak_date)}{ep.peak_at_history_start ? " *" : ""}</td><td>{dts(ep.trigger_date)}</td><td className="text-term-down">{pct(ep.max_drawdown)}</td>
              {r?.signals.filter((s) => s.status === "computed").map((s) => { const l = s.lead_times[k]?.[j];
                return <td key={s.id} className={l?.status === "preceded" ? "text-white" : "text-term-muted"}>
                  {!l ? "—" : l.status === "preceded" ? `${l.left_censored ? "≥" : ""}${l.lead_days_to_trigger} 天` : l.status === "no_preceding_signal" ? "無訊號" : "資料不足"}</td>; })}
            </tr>)))}</tbody></table></div>
        <div className="text-[11px] text-term-muted mt-2">領先天數＝訊號連續亮燈的起點到確認日的日曆天數。「≥」＝第一個可評估日訊號就已亮燈（左設限）。
          如果訊號在大部分期間都亮著，幾乎每次修正都會「被它領先」——這是結構使然，請先對照亮燈比例與基準率再解讀。* 高點落在已儲存歷史的第一天。</div>
      </Panel>
      <Panel title="長期時點綜合分數（月底，自 2010 年起）：僅供脈絡參考；結果檢驗從有股價資料開始（美股 2015、台股約 13 個月）"
        info="橘色區帶＝把缺少的指標分別當作 0 分與 100 分時的範圍；灰色虛線＝當時的資料覆蓋率（%）。">
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={hist}><CartesianGrid stroke={GRID} strokeDasharray="3 3" /><XAxis dataKey="date" tick={TICK} minTickGap={40} tickFormatter={dts} />
            <YAxis domain={[0, 100]} tick={TICK} /><Tooltip {...TT} labelFormatter={dts} />
            <Area {...ANIM} dataKey="band" stroke="none" fill="#f59e0b" fillOpacity={0.15} name="範圍（缺值＝0…100）" />
            <Line {...ANIM} dataKey="composite_partial" stroke="#f59e0b" strokeWidth={2} dot={false} name="綜合分數（部分覆蓋）" />
            <Line {...ANIM} dataKey="cov" stroke="#94a3b8" strokeDasharray="3 3" dot={false} name="覆蓋率 %" />
          </ComposedChart>
        </ResponsiveContainer>
      </Panel>
      <Hypothesis>方法：對每個日期 d，所有讀取觀測資料表的指標都只用 publication_date ≤ d 的資料重算，並採用 d 當天的版本（之後的修正看不到）。
        正式風險分數需要覆蓋率 ≥ 最低門檻，過去每個日期都未達標而暫不公布，因此「綜合分數（部分覆蓋）」只用當時可得的時點指標，<b>不是</b>正式公布的風險分數。
        結果使用實際的台股收盤價，以及（若有儲存）經分割調整的美股收盤價（Tiingo，只算價格報酬、不含股利）；美股名單是事後挑選的。
        視窗彼此重疊，所以獨立樣本遠少於天數。完整說明見「方法論」頁。</Hypothesis>
    </div>
  );
}
