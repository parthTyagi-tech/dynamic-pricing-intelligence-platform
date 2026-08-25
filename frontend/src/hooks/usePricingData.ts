import { useCallback, useEffect, useState } from "react";
import { getDashboardSnapshot } from "../services/api";
import { mockDashboard } from "../lib/mockData";
import type { DashboardSnapshot } from "../types/domain";

export function usePricingData() {
  const [data, setData] = useState<DashboardSnapshot>(mockDashboard);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const refresh = useCallback(async () => {
    setLoading(true);
    try { setData(await getDashboardSnapshot()); setError(false); } catch { setError(true); } finally { setLoading(false); }
  }, []);
  useEffect(() => { const first = window.setTimeout(() => void refresh(), 0); const interval = window.setInterval(() => void refresh(), 30000); return () => { window.clearTimeout(first); window.clearInterval(interval); }; }, [refresh]);
  return { data, loading, error, refresh };
}
