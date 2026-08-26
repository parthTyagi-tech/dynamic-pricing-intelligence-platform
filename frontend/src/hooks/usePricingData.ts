import { useCallback, useEffect, useState } from "react";
import { getDashboardSnapshot } from "../services/api";
import type { DashboardSnapshot } from "../types/domain";

export function usePricingData() {
  const emptySnapshot: DashboardSnapshot = { kpis: [], chart: [], products: [], activity: [], systemHealth: "offline", updatedAt: "" };
  const [data, setData] = useState<DashboardSnapshot>(emptySnapshot);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const refresh = useCallback(async () => {
    setLoading(true);
    try { setData(await getDashboardSnapshot()); setError(false); } catch { setError(true); } finally { setLoading(false); }
  }, []);
  useEffect(() => { const first = window.setTimeout(() => void refresh(), 0); const interval = window.setInterval(() => void refresh(), 30000); return () => { window.clearTimeout(first); window.clearInterval(interval); }; }, [refresh]);
  return { data, loading, error, refresh };
}
