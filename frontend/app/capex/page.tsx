"use client";
import { ANIM, GRID, TICK, TT } from "@/lib/chart";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ClassBadge, ConfBadge, StatusPill } from "@/components/Badges";
import { ApiError, useApi } from "@/components/useApi";
import { API_BASE, apiGet, apiPost, type Observation } from "@/lib/api";
import { fmtValue } from "@/lib/format";
import { STATIC, staticCsv } from "@/lib/static";
import { PageIntro, Panel as P2 } from "@/components/Panel";
import { dt, ent, fp, metricName } from "@/lib/i18n";

const COMPANIES = ["MSFT", "GOOGL", "AMZN", "META", "ORCL"];
const COLORS: Record<string, string> = { MSFT: "#58a6ff", GOOGL: "#3fb950", AMZN: "#ffb000", META: "#d2a8ff", ORCL: "#f85149",
  capex_yoy: "#ffb000", revenue_yoy: "#58a6ff", ocf_yoy: "#3fb950", fcf_yoy: "#d2a8ff" };
const GROWTH = ["capex_yoy", "revenue_yoy", "ocf_yoy", "fcf_yoy"];
const ABS = ["capex_total", "revenue", "operating_cash_flow", "fcf"];

type RunStatus = { refresh_in_progress: boolean };

export default function CapexPage() {
  const [company, setCompany] = useState("MSFT");
  const [compare, setCompare] = useState<string[]>(COMPANIES);
  const [start, setStart] = useState("2021-01-01");
  const [end, setEnd] = useState("");
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null);
  const range = `&start=${start}${end ? `&end=${end}` : ""}`;
  const single = useApi<Observation[]>(`/api/observations?metric_id=${[...GROWTH, ...ABS, "capex_to_ocf", "capex_to_revenue"].join(",")}&entity_id=${company}${range}`);
  const multi = useApi<Observation[]>(compare.length ? `/api/observations?metric_id=capex_total&entity_id=${compare.join(",")}${range}` : null);

  const growth = useMemo(() => pivot(single.data, GROWTH, (o) => o.value * 100), [single.data]);
  const abs = useMemo(() => pivot(single.data, ABS, (o) => o.value / 1e9), [single.data]);
  const cross = useMemo(() => {
    const m = new Map<string, Record<string, number | string>>();
    (multi.data ?? []).forEach((o) => {
      const k = o.period_end; const row = m.get(k) ?? { period: k };
      row[o.entity_id] = o.value / 1e9; m.set(k, row);
    });
    return [...m.values()].sort((a, b) => String(a.period).localeCompare(String(b.period)));
  }, [multi.data]);

  async function refresh() {
    try {
      await apiPost("/api/refresh?provider=sec_edgar");
      setRefreshMsg("已開始更新…");
      const poll = setInterval(async () => {
        const s = await apiGet<RunStatus>("/api/health");
        if (!s.refresh_in_progress) {
          clearInterval(poll);
          const runs = await apiGet<{ provider: string; status: string; records_inserted: number; records_revised: number }[]>("/api/ingestion/runs?limit=2");
          setRefreshMsg(`完成：${runs.map((r) => `${r.provider}=${r.status}（新增 ${r.records_inserted} 筆、修訂 ${r.records_revised} 筆）`).join("、")}`);
          single.reload(); multi.reload();
        }
      }, 1500);
    } catch (e) { setRefreshMsg(String(e)); }
  }

  const csvHref = STATIC ? staticCsv(`capex_${company}.csv`) : `${API_BASE}/api/observations.csv?metric_id=${[...ABS, ...GROWTH, "capex_to_ocf", "capex_to_revenue"].join(",")}&entity_id=${company}${range}`;
  const table = (single.data ?? []).filter((o) => o.metric_id === "capex_total").slice().reverse();

  return (
    <div className="space-y-4">
      <PageIntro emoji="🏗️" title="雲端巨頭資本支出 (CapEx)"
        what={<>微軟、Google、亞馬遜、Meta、甲骨文五家公司每季花多少錢蓋資料中心與買設備，以及這筆錢跟營收、營運現金流 (OCF)、自由現金流 (FCF) 的成長速度比起來如何。資料全部來自 SEC EDGAR 財報。</>}
        how={<>左圖看<b>成長率</b>：橘色粗線（資本支出年增）若長期高於藍線（營收年增），代表投資跑得比收入快。右圖看<b>金額</b>（億美元）：紫線（自由現金流）往 0 以下掉，就是本業現金已不夠支應投資。下方長條圖比較各家規模。</>} />
      <div className="panel p-3 flex flex-wrap items-end gap-4">
        <label className="label">公司
          <select value={company} onChange={(e) => setCompany(e.target.value)} className="ml-2 bg-black border border-term-border text-white font-mono text-xs px-1 py-0.5">
            {COMPANIES.map((c) => <option key={c} value={c}>{ent(c)}</option>)}
          </select>
        </label>
        <label className="label">起 <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="ml-1 bg-black border border-term-border text-white text-xs px-1" /></label>
        <label className="label">迄 <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="ml-1 bg-black border border-term-border text-white text-xs px-1" /></label>
        <a className="btn" href={csvHref}>{STATIC ? "⬇ 下載 CSV（快照，完整歷史）" : "⬇ 下載 CSV"}</a>
        {STATIC ? null : <button className="btn" onClick={refresh}>⟳ 從 SEC EDGAR 更新</button>}
        {refreshMsg ? <span className="text-[11px] font-mono text-term-muted">{refreshMsg}</span> : null}
      </div>
      <div className="panel p-2.5 text-[12px] text-term-amber">
        ⚠ 數字是<b>公司總資本支出</b>（購置不動產、廠房及設備的現金支出，不含融資租賃），<b>不是 AI 專屬支出</b>。標示「推導」的季度，是用年初至今 (YTD) 現金流量表相減算出。
      </div>
      {single.error ? <ApiError error={single.error} /> : null}

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title={`${ent(company)} · 年增率 (%)：資本支出 vs 營收 vs 營運現金流 vs 自由現金流`} info="年增率 (YoY)＝與去年同一季相比的成長幅度。">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={growth}>
              <CartesianGrid stroke={GRID} strokeDasharray="2 4" />
              <XAxis dataKey="period" tick={TICK} tickFormatter={(v: string) => (/^\d{4}-/.test(v) ? dt(v) : fp(v))} />
              <YAxis tick={TICK} unit="%" />
              <Tooltip {...TT} formatter={(v: number) => `${v.toFixed(1)}%`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine y={0} stroke="var(--tick)" />
              {GROWTH.map((k) => <Line {...ANIM} key={k} dataKey={k} name={metricName(k)} stroke={COLORS[k]} dot={false} strokeWidth={k === "capex_yoy" ? 2.5 : 1.5} connectNulls={false} />)}
            </LineChart>
          </ResponsiveContainer>
          <p className="text-[10px] text-term-muted">線段中斷＝該期無數值（例如前期自由現金流為負時不計算年增率），不會補 0。</p>
        </Panel>
        <Panel title={`${ent(company)} · 每季金額（億美元）`} info="自由現金流 (FCF)＝營運現金流 − 資本支出。">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={abs}>
              <CartesianGrid stroke={GRID} strokeDasharray="2 4" />
              <XAxis dataKey="period" tick={TICK} tickFormatter={(v: string) => (/^\d{4}-/.test(v) ? dt(v) : fp(v))} />
              <YAxis tick={TICK} width={70} tickFormatter={(v: number) => `${(v * 10).toLocaleString("zh-TW", { maximumFractionDigits: 0 })} 億`} />
              <Tooltip {...TT} formatter={(v: number) => `${(v * 10).toLocaleString("zh-TW", { maximumFractionDigits: 1 })} 億美元`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine y={0} stroke="var(--tick)" />
              <Line {...ANIM} dataKey="capex_total" name={metricName("capex_total")} stroke="#ffb000" strokeWidth={2.5} dot={false} />
              <Line {...ANIM} dataKey="revenue" name={metricName("revenue")} stroke="#58a6ff" dot={false} />
              <Line {...ANIM} dataKey="operating_cash_flow" name={metricName("operating_cash_flow")} stroke="#3fb950" dot={false} />
              <Line {...ANIM} dataKey="fcf" name={metricName("fcf")} stroke="#d2a8ff" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel title="各公司每季資本支出比較（億美元，依財報季度結束日）">
        <div className="flex gap-2 mb-2">
          {COMPANIES.map((c) => (
            <label key={c} className="text-xs font-mono flex items-center gap-1">
              <input type="checkbox" checked={compare.includes(c)} onChange={() => setCompare((p) => p.includes(c) ? p.filter((x) => x !== c) : [...p, c])} />
              <span style={{ color: COLORS[c] }}>{ent(c)}</span>
            </label>
          ))}
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={cross}>
            <CartesianGrid stroke={GRID} strokeDasharray="2 4" />
            <XAxis dataKey="period" tick={TICK} tickFormatter={(v: string) => (/^\d{4}-/.test(v) ? dt(v) : fp(v))} />
            <YAxis tick={TICK} width={70} tickFormatter={(v: number) => `${(v * 10).toLocaleString("zh-TW", { maximumFractionDigits: 0 })} 億`} />
            <Tooltip {...TT} formatter={(v: number) => `${(v * 10).toLocaleString("zh-TW", { maximumFractionDigits: 1 })} 億美元`} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {compare.map((c) => <Bar {...ANIM} key={c} dataKey={c} name={ent(c)} radius={[3, 3, 0, 0]} fill={COLORS[c]} />)}
          </BarChart>
        </ResponsiveContainer>
        <p className="text-[10px] text-term-muted">甲骨文 (ORCL) 財年季度在 2／5／8／11 月結束，所以長條落在不同日期。</p>
      </Panel>

      <Panel title={`${ent(company)} · 資本支出明細與原始來源`}>
        <div className="overflow-x-auto">{single.data === null && !single.error ? <div className="text-term-muted font-mono text-xs p-2">載入中…</div> : null}
          <table className="w-full text-[11px] font-mono">
            <thead className="text-term-muted text-left">
              <tr className="whitespace-nowrap"><th>財報季度</th><th>期間</th><th className="text-right">資本支出</th><th>資料分類</th><th>可信度</th><th>申報（公布日）</th><th>版本</th><th>會計科目</th><th>來源</th></tr>
            </thead>
            <tbody>
              {table.map((o) => (
                <tr key={o.id} className="border-t border-term-border" title={o.methodology ?? ""}>
                  <td>{fp(o.fiscal_period)}</td><td>{dt(o.period_start)} → {dt(o.period_end)}</td>
                  <td className="text-right text-white">{fmtValue(o.value, o.unit)}</td>
                  <td><ClassBadge c={o.classification} /></td><td><ConfBadge c={o.confidence} /></td>
                  <td>{dt(o.publication_date)}</td><td>{o.version > 1 ? <StatusPill s={`rev v${o.version}`} /> : "v1"}</td>
                  <td className="text-term-muted">{o.source_ref?.replace("us-gaap:", "")}</td>
                  <td>{o.source_url ? <a className="src" href={o.source_url} target="_blank" rel="noreferrer">EDGAR ↗</a> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {single.data !== null && table.length === 0 ? <div className="text-term-down font-mono text-xs p-2">此條件下無資料（不以 0 顯示）。</div> : null}
        </div>
      </Panel>
    </div>
  );
}

function pivot(rows: Observation[] | null, metrics: string[], f: (o: Observation) => number) {
  const m = new Map<string, Record<string, number | string>>();
  (rows ?? []).filter((o) => metrics.includes(o.metric_id)).forEach((o) => {
    const k = o.period_end; const row = m.get(k) ?? { period: o.fiscal_period ?? k, _end: k };
    row[o.metric_id] = f(o); m.set(k, row);
  });
  return [...m.values()].sort((a, b) => String(a._end).localeCompare(String(b._end)));
}

function Panel({ title, children, info }: { title: string; children: React.ReactNode; info?: string }) {
  return <P2 title={title} info={info}>{children}</P2>;
}
