"use client";
import { ANIM, GRID, TICK, TT } from "@/lib/chart";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ClassBadge, StatusPill } from "@/components/Badges";
import KpiCard from "@/components/KpiCard";
import { Hypothesis, Loading, PageIntro, Panel, SourceStatus } from "@/components/Panel";
import { ApiError, useApi } from "@/components/useApi";
import type { Observation } from "@/lib/api";
import { IND_ZH, PRICE_KIND_ZH, dt, fp, num, pctZh, tx } from "@/lib/i18n";

type Gpu = { rows: { id: number; sku: string; gpu_model: string; gpu_count: number; price_kind: string; region: string; usd_per_hour: number; usd_per_gpu_hour: number; effective_from: string | null; last_seen_at: string; source_url: string }[];
  placeholders: { id: string; name: string; status: string; limitation: string }[]; notes: string[]; sources: Record<string, { last_status: string; last_success_at: string | null; message: string | null }> };
type Ind = { id: string; status: string; value: number | null; score: number | null; as_of: string | null; detail: string | null };
type Risk = { dimensions: { indicators: Ind[] }[] };

export default function SupplyChain() {
  const dc = useApi<Observation[]>("/api/observations?metric_id=nvda_datacenter_revenue&entity_id=NVDA");
  const gpu = useApi<Gpu>("/api/gpu-prices");
  const risk = useApi<Risk>("/api/risk");
  const ind = (id: string) => risk.data?.dimensions.flatMap((d) => d.indicators).find((i) => i.id === id && i.status === "ok" && i.value != null);
  const nv = ind("nvda_datacenter_revenue_yoy"), ts = ind("tsmc_monthly_revenue"), sp = ind("gpu_spot_discount");
  const data = (dc.data ?? []).map((o) => ({ q: fp(o.fiscal_period), v: o.value / 1e8, c: o.classification }));
  return (
    <div className="space-y-5">
      <PageIntro emoji="🔌" title="算力供應鏈與 GPU 價格"
        what={<>AI 熱潮的「賣鏟子的人」：輝達 (NVIDIA) 資料中心營收、台積電月營收成長，以及 Azure 雲端 GPU 的牌價與 Spot（閒置折扣）價。</>}
        how={<>供應商營收<b>成長越極端</b>，代表處在投資高峰期，但能否持續不確定；GPU <b>Spot 折扣越深</b>，可能代表有閒置算力。長條圖中紫色＝由年報推導的第 4 季，藍色＝季報直接公布。</>} />
      <div className="grid gap-3 grid-cols-1 md:grid-cols-3">
        <KpiCard title="輝達資料中心營收年增" value={nv ? pctZh(nv.value, 1, true) : null} score={nv?.score ?? null} asOf={dt(nv?.as_of)} info={IND_ZH.nvda_datacenter_revenue_yoy.why}
          plain={nv ? `最新一季資料中心營收比去年同季多 ${pctZh(nv.value)}，處於投資高峰期。` : "無資料。"} />
        <KpiCard title="台積電月營收年增" value={ts ? pctZh(ts.value, 1, true) : null} score={ts?.score ?? null} asOf={dt(ts?.as_of)} info={IND_ZH.tsmc_monthly_revenue.why}
          plain={ts ? `證交所公布的最新月營收，比去年同月多 ${pctZh(ts.value)}；長期趨勢約 15%。` : "無資料。"} />
        <KpiCard title="H100 Spot 折扣" value={sp ? pctZh(sp.value, 1) : null} score={sp?.score ?? null} asOf={dt(sp?.as_of)} info={IND_ZH.gpu_spot_discount.why}
          plain={sp ? `Azure H100 的 Spot 價比隨用隨付牌價便宜 ${pctZh(sp.value)}，可能反映閒置算力（牌價自 2023 年底未變，僅供參考）。` : "無資料。"} />
      </div>
      {dc.error ? <ApiError error={dc.error} /> : null}
      <Panel title="輝達資料中心部門營收（億美元）— SEC 10-Q／10-K XBRL（維度事實 nvda:DataCenterMember）" info="輝達把營收拆成資料中心、遊戲等部門；資料中心部門幾乎就是 AI 加速器的銷售。">
        <Loading show={!dc.data && !dc.error} />
        <ResponsiveContainer width="100%" height={280}><BarChart data={data}>
          <CartesianGrid stroke={GRID} strokeDasharray="2 4" /><XAxis dataKey="q" tick={TICK} /><YAxis tick={TICK} width={70} tickFormatter={(v: number) => `${v.toLocaleString("zh-TW")} 億`} />
          <Tooltip {...TT} formatter={(x: number) => [`${x.toLocaleString("zh-TW", { maximumFractionDigits: 1 })} 億美元`, "資料中心營收"]} />
          <Bar {...ANIM} dataKey="v" name="資料中心營收" radius={[4, 4, 0, 0]}>{data.map((d, i) => <Cell key={i} fill={d.c === "derived" ? "#a78bfa" : "#60aaff"} />)}</Bar></BarChart></ResponsiveContainer>
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono mt-2"><thead className="text-term-muted text-left whitespace-nowrap"><tr><th>財報季度</th><th>期間</th><th className="text-right">營收</th><th>資料分類</th><th>申報日</th><th>來源</th></tr></thead>
          <tbody>{(dc.data ?? []).slice().reverse().map((o) => (
            <tr key={o.id} className="border-t border-term-border"><td>{fp(o.fiscal_period)}</td><td>{dt(o.period_start)} → {dt(o.period_end)}</td>
              <td className="text-right text-white">{num(o.value / 1e8, 1)} 億美元</td><td><ClassBadge c={o.classification} /></td><td>{dt(o.publication_date)}</td>
              <td>{o.source_url ? <a className="src" href={o.source_url} target="_blank" rel="noreferrer">EDGAR ↗</a> : "—"}</td></tr>))}</tbody></table></div>
        <p className="text-[11px] text-term-muted">第 4 季為<b>推導</b>值＝全年（10-K）減第 1–3 季；其他季度為公布的 3 個月數字。</p>
      </Panel>
      <Panel title="雲端 GPU 價格 — Azure 零售價格 API（牌價、Linux、美東 eastus）" info="每 GPU 小時價格＝整台虛擬機每小時價格 ÷ GPU 數量。這是公開牌價，不是議價、預留或二手租賃價。">
        {gpu.error ? <ApiError error={gpu.error} /> : null}
        <SourceStatus sources={gpu.data?.sources} />
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono mt-2"><thead className="text-term-muted text-left whitespace-nowrap"><tr><th>GPU</th><th>VM 規格</th><th>價格類型</th><th className="text-right">美元／小時（整台）</th><th className="text-right">美元／GPU 小時</th><th>價格生效日</th><th>來源</th></tr></thead>
          <tbody>{(gpu.data?.rows ?? []).map((r) => (
            <tr key={r.id} className="border-t border-term-border"><td className="text-white">{r.gpu_count}× {r.gpu_model}</td><td>{r.sku}</td><td>{PRICE_KIND_ZH[r.price_kind] ?? r.price_kind}</td>
              <td className="text-right">{r.usd_per_hour.toFixed(3)}</td><td className="text-right text-white">{r.usd_per_gpu_hour.toFixed(3)}</td><td>{dt(r.effective_from)}</td>
              <td><a className="src" href={r.source_url} target="_blank" rel="noreferrer">Azure ↗</a></td></tr>))}</tbody></table></div>
        {(gpu.data?.notes ?? []).map((n) => <p key={n} className="text-[11px] text-term-muted">{tx(n)}</p>)}
        {(gpu.data?.placeholders ?? []).map((p) => (
          <div key={p.id} className="mt-2 rounded-lg border border-dashed border-term-border p-2 text-[12px]"><StatusPill s={p.status} /> {tx(p.name)}<div className="text-term-muted mt-1">{tx(p.limitation)}</div></div>))}
      </Panel>
      <Hypothesis>台積電月營收已接入（證交所 t187ap05_L），用於上方卡片與風險分數。供應鏈數字火熱只代表需求強勁，不代表必然過熱；缺資料不等於沒有風險。</Hypothesis>
    </div>
  );
}
