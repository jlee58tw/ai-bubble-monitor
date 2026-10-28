"use client";
import { useCallback, useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(() => {
    if (!path) return;
    setLoading(true);
    apiGet<T>(path).then((d) => { setData(d); setError(null); })
      .catch((e) => setError(String(e))).finally(() => setLoading(false));
  }, [path]);
  useEffect(() => { load(); }, [load]);
  return { data, error, loading, reload: load };
}

export function ApiError({ error }: { error: string }) {
  return (
    <div className="panel p-3 !border-red-500/50 text-term-down text-xs">
      ⛔ 資料介面無法使用（API 無資料）— {error}。寧可不顯示，也不會顯示過期或捏造的數值。
    </div>
  );
}
