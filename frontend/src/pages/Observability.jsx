import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Cpu, DollarSign, RefreshCw, BarChart2, Activity, Zap, ShieldAlert, Award } from "lucide-react";
import apiClient from "../services/api";

export default function Observability() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStats = async () => {
    try {
      const response = await apiClient.get("/observability/stats");
      setStats(response.data);
    } catch (error) {
      console.error("Error fetching observability stats:", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchStats();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="w-10 h-10 border-4 border-t-indigo-500 border-white/10 rounded-full animate-spin" />
      </div>
    );
  }

  const metrics = stats?.metrics || {
    total_cost: 0.0,
    total_tokens: 0,
    avg_latency: 0.0,
    total_calls: 0,
    success_rate: 100.0
  };

  const agents = stats?.agents || [];
  const models = stats?.models || [];
  const logs = stats?.recent_logs || [];
  const timeline = stats?.cost_timeline || [];

  // SVG Line Chart coordinates calculation for Cumulative Cost & Latency
  const getSvgCoordinates = (data, valueKey, width = 600, height = 150) => {
    if (!data || data.length < 2) return "";
    const values = data.map(d => d[valueKey]);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const valRange = maxVal - minVal || 1.0;

    return data.map((d, index) => {
      const x = (index / (data.length - 1)) * (width - 40) + 20;
      const y = height - ((d[valueKey] - minVal) / valRange) * (height - 30) - 15;
      return `${x},${y}`;
    }).join(" ");
  };

  return (
    <div className="space-y-6">
      {/* HEADER SECTION */}
      <div className="flex justify-between items-center bg-white/5 border border-white/8 rounded-3xl p-6 relative overflow-hidden"
           style={{ background: "rgba(10, 15, 30, 0.7)", backdropFilter: "blur(20px)" }}>
        <div className="absolute top-0 right-0 w-24 h-24 opacity-15 blur-2xl bg-indigo-500" />
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center bg-indigo-600/30 text-indigo-400 border border-indigo-500/20">
            <Cpu size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-wide">LLM Agents Observability</h1>
            <p className="text-xs text-slate-400 mt-1">Audit token consumption, cost metrics, and execution latencies in real time.</p>
          </div>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 text-xs font-semibold bg-white/5 hover:bg-white/10 text-white rounded-xl border border-white/10 hover:border-white/15 transition-all cursor-pointer disabled:opacity-50"
        >
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
          Refresh Stats
        </button>
      </div>

      {/* METRICS ROW */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          { label: "Total LLM Cost", val: `₹${metrics.total_cost.toFixed(4)}`, icon: DollarSign, color: "text-emerald-400" },
          { label: "Total Tokens", val: metrics.total_tokens.toLocaleString(), icon: BarChart2, color: "text-blue-400" },
          { label: "Avg Latency", val: `${metrics.avg_latency} ms`, icon: Zap, color: "text-amber-400" },
          { label: "Total Calls", val: metrics.total_calls, icon: Activity, color: "text-purple-400" },
          { label: "Success Rate", val: `${metrics.success_rate}%`, icon: Award, color: "text-teal-400" }
        ].map((card, idx) => (
          <div key={idx} className="bg-white/5 border border-white/8 rounded-2xl p-5 flex flex-col justify-between"
               style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-400 font-medium">{card.label}</span>
              <card.icon className={`${card.color} opacity-80`} size={16} />
            </div>
            <div className="text-lg font-bold text-white mt-4">{card.val}</div>
          </div>
        ))}
      </div>

      {/* CHARTS ROW */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cumulative cost chart */}
        <div className="bg-white/5 border border-white/8 rounded-3xl p-6"
             style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
          <h3 className="text-sm font-bold text-white mb-4">Cumulative API Spend (₹ INR)</h3>
          {timeline.length > 1 ? (
            <div className="w-full">
              <svg className="w-full h-40 overflow-visible" viewBox="0 0 600 150">
                <defs>
                  <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.2"/>
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.0"/>
                  </linearGradient>
                </defs>
                {/* Area under curve */}
                <path
                  d={`M 20,135 L ${getSvgCoordinates(timeline, "cumulative_cost")} L ${600 - 20},135 Z`}
                  fill="url(#costGrad)"
                />
                {/* Curve line */}
                <polyline
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="2.5"
                  points={getSvgCoordinates(timeline, "cumulative_cost")}
                />
              </svg>
              <div className="flex justify-between text-[10px] text-slate-500 mt-2 px-3">
                <span>{timeline[0]?.timestamp}</span>
                <span>Timeline (chronological order)</span>
                <span>{timeline[timeline.length - 1]?.timestamp}</span>
              </div>
            </div>
          ) : (
            <div className="h-40 flex items-center justify-center text-xs text-slate-500">Not enough data to render timeline chart.</div>
          )}
        </div>

        {/* Latency curve chart */}
        <div className="bg-white/5 border border-white/8 rounded-3xl p-6"
             style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
          <h3 className="text-sm font-bold text-white mb-4">Agent Execution Latency (ms)</h3>
          {timeline.length > 1 ? (
            <div className="w-full">
              <svg className="w-full h-40 overflow-visible" viewBox="0 0 600 150">
                <defs>
                  <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.2"/>
                    <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.0"/>
                  </linearGradient>
                </defs>
                <path
                  d={`M 20,135 L ${getSvgCoordinates(timeline, "latency")} L ${600 - 20},135 Z`}
                  fill="url(#latGrad)"
                />
                <polyline
                  fill="none"
                  stroke="#f59e0b"
                  strokeWidth="2.5"
                  points={getSvgCoordinates(timeline, "latency")}
                />
              </svg>
              <div className="flex justify-between text-[10px] text-slate-500 mt-2 px-3">
                <span>{timeline[0]?.timestamp}</span>
                <span>Timeline (chronological order)</span>
                <span>{timeline[timeline.length - 1]?.timestamp}</span>
              </div>
            </div>
          ) : (
            <div className="h-40 flex items-center justify-center text-xs text-slate-500">Not enough data to render timeline chart.</div>
          )}
        </div>
      </div>

      {/* TABLES ROW */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agent breakdown */}
        <div className="lg:col-span-2 bg-white/5 border border-white/8 rounded-3xl p-6"
             style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
          <h3 className="text-sm font-bold text-white mb-4">Agent Consensus Breakdown</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10 text-xs">
              <thead className="bg-white/5">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Agent Name</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Total Calls</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Avg Latency</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Est Cost (INR)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {agents.map((ag, idx) => (
                  <tr key={idx} className="hover:bg-white/5 transition-colors">
                    <td className="px-4 py-3 text-white font-medium">{ag.name}</td>
                    <td className="px-4 py-3 text-slate-400">{ag.calls}</td>
                    <td className="px-4 py-3 text-slate-400">{ag.avg_latency} ms</td>
                    <td className="px-4 py-3 text-teal-400 font-mono">₹{ag.cost.toFixed(5)}</td>
                  </tr>
                ))}
                {agents.length === 0 && (
                  <tr>
                    <td colSpan="4" className="px-4 py-6 text-center text-slate-500">No agent activities logged.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Model distribution */}
        <div className="bg-white/5 border border-white/8 rounded-3xl p-6"
             style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
          <h3 className="text-sm font-bold text-white mb-4">Model Distribution</h3>
          <div className="space-y-4">
            {models.map((mod, idx) => {
              const totalCalls = metrics.total_calls || 1;
              const pct = (mod.calls / totalCalls) * 100;
              return (
                <div key={idx} className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold text-white">
                    <span className="truncate">{mod.name}</span>
                    <span>{pct.toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-white/10 h-2.5 rounded-full overflow-hidden">
                    <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="text-[10px] text-slate-500">{mod.calls} logs</div>
                </div>
              );
            })}
            {models.length === 0 && (
              <div className="text-xs text-slate-500 text-center py-6">No model allocations recorded.</div>
            )}
          </div>
        </div>
      </div>

      {/* DETAILED LOGS HISTORY */}
      <div className="bg-white/5 border border-white/8 rounded-3xl p-6"
           style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
        <h3 className="text-sm font-bold text-white mb-4">Audit Call History Logs</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-white/10 text-xs">
            <thead className="bg-white/5">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-slate-300">Timestamp</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-300">Agent</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-300">Model</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-300">Tokens</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-300">Latency</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-300">Cost</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-300">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {logs.map((log, idx) => (
                <tr key={idx} className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">{new Date(log.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3 text-white font-medium">{log.agent_name}</td>
                  <td className="px-4 py-3 text-slate-400 font-mono">{log.model_name}</td>
                  <td className="px-4 py-3 text-slate-400">{log.total_tokens.toLocaleString()}</td>
                  <td className="px-4 py-3 text-slate-400">{log.latency_ms} ms</td>
                  <td className="px-4 py-3 text-teal-400 font-mono">₹{log.cost.toFixed(5)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                      log.status === "success" 
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" 
                        : "bg-red-500/10 text-red-400 border-red-500/20"
                    }`}>
                      {log.status.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr>
                  <td colSpan="7" className="px-4 py-6 text-center text-slate-500">No logs found in db history.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
