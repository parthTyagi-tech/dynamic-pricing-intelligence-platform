import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LineChart, Play, RefreshCw, BarChart2, DollarSign, TrendingUp, HelpCircle, Layers, CheckCircle } from "lucide-react";
import apiClient from "../services/api";

export default function Backtesting() {
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [elasticity, setElasticity] = useState(1.5);
  const [days, setDays] = useState(30);
  
  const [loading, setLoading] = useState(false);
  const [simResults, setSimResults] = useState(null);
  const [currentDayProgress, setCurrentDayProgress] = useState(0);

  // Load products list
  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const response = await apiClient.get("/products");
        setProducts(response.data.products || []);
        if (response.data.products && response.data.products.length > 0) {
          setSelectedProductId(response.data.products[0].id);
        }
      } catch (error) {
        console.error("Error loading products for backtesting:", error);
      }
    };
    fetchProducts();
  }, []);

  const handleRunBacktest = async () => {
    if (!selectedProductId) return;
    setLoading(true);
    setSimResults(null);
    setCurrentDayProgress(0);

    // Simulate progress increments for UI premium effect
    const interval = setInterval(() => {
      setCurrentDayProgress(prev => {
        if (prev >= days) {
          clearInterval(interval);
          return days;
        }
        return prev + 1;
      });
    }, 40);

    try {
      const response = await apiClient.post("/simulation/run", {
        product_id: selectedProductId,
        elasticity,
        days
      });
      
      // Delay slightly to finish progress animation smoothly
      setTimeout(() => {
        setSimResults(response.data);
        setLoading(false);
      }, 300);
    } catch (error) {
      console.error("Error running backtest:", error);
      clearInterval(interval);
      setLoading(false);
    }
  };

  // Svg line chart renderer for dual lines (Baseline vs AI optimized revenue)
  const getSvgPathPoints = (data, valueKey, width = 700, height = 200) => {
    if (!data || data.length < 2) return "";
    const values = data.map(d => d[valueKey]);
    
    // Find min and max across BOTH actual and ai revenues to draw relative to same scale!
    const allRevenues = [
      ...data.map(d => d.actual_revenue),
      ...data.map(d => d.ai_revenue)
    ];
    const minVal = Math.min(...allRevenues);
    const maxVal = Math.max(...allRevenues);
    const valRange = maxVal - minVal || 1.0;

    return data.map((d, index) => {
      const x = (index / (data.length - 1)) * (width - 40) + 20;
      const y = height - ((d[valueKey] - minVal) / valRange) * (height - 40) - 20;
      return `${x},${y}`;
    }).join(" ");
  };

  return (
    <div className="space-y-6">
      {/* HEADER SECTION */}
      <div className="flex justify-between items-center bg-white/5 border border-white/8 rounded-3xl p-6 relative overflow-hidden"
           style={{ background: "rgba(10, 15, 30, 0.7)", backdropFilter: "blur(20px)" }}>
        <div className="absolute top-0 right-0 w-24 h-24 opacity-15 blur-2xl bg-teal-500" />
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center bg-teal-600/30 text-teal-400 border border-teal-500/20">
            <LineChart size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-wide">Pricing Backtester Simulation</h1>
            <p className="text-xs text-slate-400 mt-1">Simulate historical AI pricing decisions and evaluate customer demand elasticity impacts.</p>
          </div>
        </div>
      </div>

      {/* PARAMETERS CONFIG CARD */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 bg-white/5 border border-white/8 rounded-3xl p-6 flex flex-col justify-between"
             style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
          <div className="space-y-5">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Layers size={16} className="text-indigo-400" />
              Configure Simulation Parameters
            </h3>

            {/* Product dropdown */}
            <div className="space-y-1.5">
              <label className="text-xs text-slate-400 font-semibold">Select Target Product</label>
              <select
                value={selectedProductId}
                onChange={(e) => setSelectedProductId(e.target.value)}
                className="w-full bg-white/5 border border-white/10 text-white text-xs rounded-xl p-3 outline-none focus:border-indigo-500/50"
              >
                {products.map(p => (
                  <option key={p.id} value={p.id} className="bg-slate-900 text-white">
                    {p.name} ({p.sku}) - ${p.current_price}
                  </option>
                ))}
              </select>
            </div>

            {/* Elasticity coefficient slider */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <label className="text-slate-400 font-semibold">Price Elasticity Coefficient</label>
                <span className="text-teal-300 font-bold">{elasticity.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="3.5"
                step="0.1"
                value={elasticity}
                onChange={(e) => setElasticity(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-white/15 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
              <p className="text-[10px] text-slate-500">How sensitive consumers are to price changes (higher means more drop in volume as price rises).</p>
            </div>

            {/* Duration slider */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <label className="text-slate-400 font-semibold">Simulation Period (Days)</label>
                <span className="text-indigo-300 font-bold">{days} days</span>
              </div>
              <input
                type="range"
                min="7"
                max="90"
                step="1"
                value={days}
                onChange={(e) => setDays(parseInt(e.target.value))}
                className="w-full h-1.5 bg-white/15 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
            </div>
          </div>

          <button
            onClick={handleRunBacktest}
            disabled={loading || !selectedProductId}
            className="w-full mt-6 flex items-center justify-center gap-2 py-3 bg-gradient-to-r from-teal-500 to-indigo-600 hover:from-teal-400 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-teal-500/10 cursor-pointer disabled:opacity-50 select-none"
          >
            <Play size={14} fill="white" />
            Run AI Backtest Simulation
          </button>
        </div>

        {/* LOADING & PREVIEW OVERLAY */}
        <div className="lg:col-span-2 bg-white/5 border border-white/8 rounded-3xl p-6 min-h-[320px] flex items-center justify-center relative overflow-hidden"
             style={{ background: "rgba(10, 15, 30, 0.2)" }}>
          
          <AnimatePresence mode="wait">
            {loading && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-4 text-center z-10"
              >
                <div className="w-16 h-16 rounded-full border-4 border-teal-500/20 border-t-teal-400 animate-spin" />
                <div className="space-y-1.5">
                  <h4 className="text-sm font-bold text-white tracking-wide">Dynamic Pricing Simulation Running...</h4>
                  <p className="text-xs text-teal-300 font-mono">Simulating day {currentDayProgress} of {days}...</p>
                </div>
              </motion.div>
            )}

            {!loading && !simResults && (
              <motion.div
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-3 text-center"
              >
                <TrendingUp size={48} className="text-slate-600" />
                <h4 className="text-sm font-semibold text-slate-400">Ready to simulate. Select a product and click run.</h4>
                <p className="text-xs text-slate-500 max-w-sm">The simulator aggregates competitor price swings, audits target margin bounds, and plots optimized price lift logs.</p>
              </motion.div>
            )}

            {!loading && simResults && (
              <motion.div
                key="results"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="w-full space-y-6"
              >
                {/* LIFT METRICS ROW */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  {[
                    { label: "Baseline Revenue", val: `$${simResults.summary.total_actual_revenue.toLocaleString()}`, color: "text-slate-400" },
                    { label: "AI-Optimized Revenue", val: `$${simResults.summary.total_ai_revenue.toLocaleString()}`, color: "text-teal-400" },
                    { label: "Revenue Lift Margin", val: `+${simResults.summary.revenue_lift_pct}%`, color: "text-emerald-400", highlight: true },
                    { label: "Net Profit Growth", val: `+${simResults.summary.profit_lift_pct}%`, color: "text-teal-400", highlight: true }
                  ].map((card, idx) => (
                    <div key={idx} className={`p-4 rounded-2xl border ${
                      card.highlight ? "border-emerald-500/20 bg-emerald-500/5" : "border-white/5 bg-white/5"
                    }`}>
                      <span className="text-[10px] text-slate-500 font-semibold">{card.label}</span>
                      <h4 className={`text-base font-bold mt-2 ${card.color}`}>{card.val}</h4>
                    </div>
                  ))}
                </div>

                {/* GRAPH COMPARISON */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <h5 className="font-bold text-white">Daily Revenue Comparison ($ USD)</h5>
                    <div className="flex items-center gap-4">
                      <span className="flex items-center gap-1.5 text-slate-500"><span className="w-2.5 h-1 bg-slate-500 rounded" /> Baseline Price</span>
                      <span className="flex items-center gap-1.5 text-teal-400"><span className="w-2.5 h-1 bg-teal-400 rounded" /> Klypup Dynamic</span>
                    </div>
                  </div>
                  <div className="w-full">
                    <svg className="w-full h-44 overflow-visible" viewBox="0 0 700 200">
                      {/* Actual Revenue Line */}
                      <polyline
                        fill="none"
                        stroke="#64748b"
                        strokeWidth="1.8"
                        strokeDasharray="4,4"
                        points={getSvgPathPoints(simResults.timeline, "actual_revenue")}
                      />
                      {/* AI Revenue Line */}
                      <polyline
                        fill="none"
                        stroke="#2dd4bf"
                        strokeWidth="2.5"
                        points={getSvgPathPoints(simResults.timeline, "ai_revenue")}
                      />
                    </svg>
                    <div className="flex justify-between text-[10px] text-slate-600 px-3">
                      <span>Day 1</span>
                      <span>Timeline Curve (Days 1 to {days})</span>
                      <span>Day {days}</span>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* TIMELINE DETAILED DATA TABLE */}
      {simResults && (
        <div className="bg-white/5 border border-white/8 rounded-3xl p-6"
             style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
          <h3 className="text-sm font-bold text-white mb-4">Simulation Daily Step Audit Trail</h3>
          <div className="overflow-y-auto max-h-[300px] scrollbar-thin">
            <table className="min-w-full divide-y divide-white/10 text-xs">
              <thead className="bg-white/5 sticky top-0">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Day</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Baseline Price</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Competitor price</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">AI dynamic Price</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Baseline Revenue</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">AI dynamic Revenue</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Revenue Lift</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {simResults.timeline.map((point, idx) => {
                  const lift = point.ai_revenue - point.actual_revenue;
                  return (
                    <tr key={idx} className="hover:bg-white/5 transition-colors">
                      <td className="px-4 py-2.5 text-slate-400">Day {point.day}</td>
                      <td className="px-4 py-2.5 text-slate-300 font-mono">${point.actual_price} ({point.actual_quantity} sold)</td>
                      <td className="px-4 py-2.5 text-slate-400 font-mono">${point.competitor_price}</td>
                      <td className="px-4 py-2.5 text-teal-300 font-semibold font-mono">${point.ai_price} ({point.ai_quantity} sold)</td>
                      <td className="px-4 py-2.5 text-slate-400 font-mono">${point.actual_revenue}</td>
                      <td className="px-4 py-2.5 text-teal-400 font-mono">${point.ai_revenue}</td>
                      <td className={`px-4 py-2.5 font-bold font-mono ${lift >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                        {lift >= 0 ? "+" : ""}${lift.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
