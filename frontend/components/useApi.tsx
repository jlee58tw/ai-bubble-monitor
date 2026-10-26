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
    <div className="panel p-3 border-term-down text-term-down font-mono text-xs">
      API UNAVAILABLE — {error}. No data is displayed rather than showing stale or invented values.
    </div>
  );
}
