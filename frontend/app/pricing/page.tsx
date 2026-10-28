"use client";
import { useMemo, useState } from "react";
import { StatusPill } from "@/components/Badges";
import { Hypothesis, Loading, PageIntro, Panel, SourceStatus, tsTaipei } from "@/components/Panel";
import { PRICE_TYPE_ZH, TIER_ZH, dt, tx } from "@/lib/i18n";
import { ApiError, useApi } from "@/components/useApi";

type Row = { id: number; vendor: string; model_id: string; model_label: string; tier: string; price_type: string; usd_per_mtok: number;
  price_status: string; effective_from: string | null; effective_to: string | null; first_seen_at: string; last_seen_at: string;
  source_url: string; raw_text: string | null; note: string | null; open_weight: boolean };
type Resp = { rows: Row[]; notes: string[]; sources: Record<string, { last_status: string; last_success_at: string | null; message: string | null }> };
const VENDORS = ["openai", "anthropic", "google", "openrouter"];
const TYPES = ["input", "output", "cached_input"];
const VNAME: Record<string, string> = { openai: "OpenAI", anthropic: "Anthropic", google: "Google", openrouter: "OpenRouter" };

export default function Pricing() {
  const [vendor, setVendor] = useState("anthropic");
  const [q, setQ] = useState("");
  const { data, error } = useApi<Resp>(`/api/model-prices?vendor=${vendor}`);
  const grouped = useMemo(() => {
    const m = new Map<string, { label: string; tier: string; status: string; ef: string | null; et: string | null; first: string; url: string; raw: string[]; note: string | null; p: Record<string, number> }>();
    (data?.rows ?? []).filter((r) => !q || r.model_id.toLowerCase().includes(q.toLowerCase()) || r.model_label.toLowerCase().includes(q.toLowerCase())).forEach((r) => {
      const k = `${r.model_id}|${r.tier}|${r.price_status}|${r.effective_from}`;
      const g = m.get(k) ?? { label: r.model_label, tier: r.tier, status: r.price_status, ef: r.effective_from, et: r.effective_to, first: r.first_seen_at, url: r.source_url, raw: [], note: r.note, p: {} };
      g.p[r.price_type] = r.usd_per_mtok; if (r.price_status !== "current" && r.raw_text) g.raw.push(r.raw_text);
      m.set(k, g);
    });
    return [...m.entries()];
  }, [data, q]);
  return (
    <div className="space-y-4">
      <PageIntro emoji="🏷️" title="AI 模型 API 定價"
        what={<>OpenAI、Anthropic、Google 與開放權重模型（經 OpenRouter）的官方 API 牌價：每 100 萬個 token 要多少美元。價格是 AI 公司「怎麼賺錢」最直接的訊號。</>}
        how={<>同等級模型<b>降價越快</b>，代表價格競爭激烈、變現壓力大。狀態「預定調價」＝廠商頁面寫明的未來價格；「官方歷史價」＝廠商文件自己列出的舊價。滑鼠移到列上可看廠商原文。</>} />
      <div className="panel p-3 flex flex-wrap items-center gap-2">
        <span className="label">廠商</span>
        {VENDORS.map((v) => <button key={v} className={`btn ${v === vendor ? "text-term-amber border-term-amber" : ""}`} onClick={() => setVendor(v)}>{VNAME[v]}{v === "openrouter" ? "（開放權重）" : ""}</button>)}
        <input placeholder="篩選模型…" value={q} onChange={(e) => setQ(e.target.value)} className="bg-black border border-term-border text-white text-xs px-1 py-0.5 font-mono" />
      </div>
      {error ? <ApiError error={error} /> : null}
      <SourceStatus sources={data?.sources} />
      <Panel title={`${VNAME[vendor]} · 每 100 萬 tokens 美元價（牌價／標準方案，依官方公布）`} info="token 是模型處理文字的單位，約等於 0.75 個英文字或 1 個中文字左右。輸入＝你送給模型的文字，輸出＝模型回覆的文字。">
        <Loading show={!data && !error} />
        <div className="overflow-x-auto"><table className="w-full text-[11px] font-mono">
          <thead className="text-term-muted text-left whitespace-nowrap"><tr><th>模型（原名）</th><th>方案</th><th>狀態</th>{TYPES.map((t) => <th key={t} className="text-right">{PRICE_TYPE_ZH[t]}</th>)}<th>生效期間</th><th>首次觀測（台北）</th><th>來源</th></tr></thead>
          <tbody>{grouped.map(([k, g]) => (
            <tr key={k} className="border-t border-term-border align-top" title={g.raw.length ? `廠商原文：${g.raw.join(" | ")}` : tx(g.note) || ""}>
              <td className="text-white">{g.label}</td><td className="text-term-muted">{TIER_ZH(g.tier)}</td><td><StatusPill s={g.status} /></td>
              {TYPES.map((t) => <td key={t} className="text-right">{g.p[t] !== undefined ? `$${g.p[t]}` : "—"}</td>)}
              <td className="text-term-muted">{g.ef || g.et ? `${g.ef ? dt(g.ef) : "…"} → ${g.et ? dt(g.et) : "…"}` : "—"}</td>
              <td className="text-term-muted">{tsTaipei(g.first)}</td>
              <td><a className="src" href={g.url} target="_blank" rel="noreferrer">↗</a></td>
            </tr>))}</tbody>
        </table></div>
        {data && grouped.length === 0 ? <div className="text-term-down font-mono text-xs p-2">無資料（來源未抓取或被阻擋）。</div> : null}
      </Panel>
      <div className="text-[11px] text-term-muted space-y-1">
        {(data?.notes ?? []).map((n) => <p key={n}>{tx(n)}</p>)}
        <p>預定調價＝廠商頁面寫明的未來價格；官方歷史價＝廠商自家文件列出的過去價格（滑鼠移到該列可看引用原文）。除此之外不顯示其他歷史價——本站只知道從第一次觀測起的價格。OpenRouter 列為有 Hugging Face id 的模型（開放權重）；OpenRouter 會轉送到第三方主機，顯示的是 OpenRouter 的標價。</p>
      </div>
      <Hypothesis>牌價下跌不等於 AI 公司虧損，也可能是成本下降；這裡只呈現公開價格，不做預測。</Hypothesis>
    </div>
  );
}
