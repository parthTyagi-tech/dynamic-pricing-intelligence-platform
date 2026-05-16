import { useState, useEffect, useCallback } from "react";
import { apiClient } from "../services/api";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

import {
  TrendingUp,
  Activity,
  Brain,
  DollarSign,
  Percent,
  Eye,
  Crosshair,
  BarChart2,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";

export default function KlypupDashboard() {
  const { user } = useAuth();

  const [metrics, setMetrics] = useState({});
  const [revenue, setRevenue] = useState([]);
  const [pricingTrends, setPricingTrends] = useState([]);
  const [demand, setDemand] = useState([]);
  const [aiPerf, setAiPerf] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);

      const [
        metricsRes,
        revenueRes,
        pricingRes,
        demandRes,
        aiPerfRes,
        recommendationsRes,
      ] = await Promise.all([
        apiClient.get("/metrics"),
        apiClient.get("/revenue"),
        apiClient.get("/pricing-trends"),
        apiClient.get("/demand"),
        apiClient.get("/ai-performance"),
        apiClient.get("/recommendations"),
      ]);

      setMetrics(metricsRes.data || {});
      setRevenue(revenueRes.data || []);
      setPricingTrends(pricingRes.data || []);
      setDemand(demandRes.data || []);
      setAiPerf(aiPerfRes.data || []);
      setRecommendations(recommendationsRes.data || []);
    } catch (error) {
      console.error("Dashboard Error:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center">
        Loading Dashboard...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050816] text-white p-6">

      {/* HERO */}
      <div className="mb-10">
        <div className="inline-flex items-center gap-2 bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 px-4 py-2 rounded-full text-sm mb-5">
          <Brain size={16} />
          AI Pricing Intelligence Active
        </div>

        <h1 className="text-5xl font-bold mb-4">
          Welcome back
        </h1>

        <p className="text-slate-400 text-lg">
          Real-time AI powered dynamic pricing analytics dashboard.
        </p>

        <div className="mt-4 text-cyan-400">
          Logged in as: {user?.name || "User"}
        </div>
      </div>

      {/* METRICS */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 mb-10">

        <MetricCard
          icon={DollarSign}
          title="Revenue"
          value={`$${metrics?.totalRevenue || 0}`}
          color="cyan"
        />

        <MetricCard
          icon={Crosshair}
          title="Pricing Accuracy"
          value={`${metrics?.pricingAccuracy || 0}%`}
          color="violet"
        />

        <MetricCard
          icon={Activity}
          title="Market Volatility"
          value={`${metrics?.marketVolatility || 0}%`}
          color="amber"
        />

        <MetricCard
          icon={Brain}
          title="AI Confidence"
          value={`${metrics?.aiConfidence || 0}%`}
          color="green"
        />

        <MetricCard
          icon={Eye}
          title="Competitor Changes"
          value={metrics?.competitorChanges || 0}
          color="rose"
        />

        <MetricCard
          icon={Percent}
          title="Conversion Rate"
          value={`${metrics?.conversionRate || 0}%`}
          color="sky"
        />
      </div>

      {/* CHARTS */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-10">

        {/* Revenue */}
        <div className="bg-[#0b1020] border border-white/10 rounded-2xl p-5">
          <div className="flex items-center gap-3 mb-6">
            <TrendingUp className="text-cyan-400" />
            <h2 className="text-xl font-semibold">
              Revenue Analytics
            </h2>
          </div>

          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={revenue}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip />
              <Legend />

              <Area
                type="monotone"
                dataKey="actual"
                stroke="#06b6d4"
                fill="#06b6d4"
                fillOpacity={0.2}
              />

              <Area
                type="monotone"
                dataKey="predicted"
                stroke="#a855f7"
                fill="#a855f7"
                fillOpacity={0.15}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Pricing */}
        <div className="bg-[#0b1020] border border-white/10 rounded-2xl p-5">
          <div className="flex items-center gap-3 mb-6">
            <Zap className="text-violet-400" />
            <h2 className="text-xl font-semibold">
              Live Pricing Engine
            </h2>
          </div>

          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={pricingTrends}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip />
              <Legend />

              <Line
                type="monotone"
                dataKey="aiPrice"
                stroke="#06b6d4"
                strokeWidth={3}
              />

              <Line
                type="monotone"
                dataKey="competitorPrice"
                stroke="#f43f5e"
              />

              <Line
                type="monotone"
                dataKey="marketAverage"
                stroke="#f59e0b"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* DEMAND + AI */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-10">

        {/* Demand */}
        <div className="bg-[#0b1020] border border-white/10 rounded-2xl p-5">
          <div className="flex items-center gap-3 mb-6">
            <BarChart2 className="text-amber-400" />
            <h2 className="text-xl font-semibold">
              Demand Analytics
            </h2>
          </div>

          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={demand}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="category" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip />

              <Bar
                dataKey="demand"
                fill="#f59e0b"
                radius={[6, 6, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* AI Performance */}
        <div className="bg-[#0b1020] border border-white/10 rounded-2xl p-5">
          <div className="flex items-center gap-3 mb-6">
            <Brain className="text-green-400" />
            <h2 className="text-xl font-semibold">
              AI Performance
            </h2>
          </div>

          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={aiPerf}>
              <PolarGrid />
              <PolarAngleAxis dataKey="metric" />
              <PolarRadiusAxis />
              <Radar
                dataKey="score"
                stroke="#22c55e"
                fill="#22c55e"
                fillOpacity={0.4}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* RECOMMENDATIONS */}
      <div className="bg-[#0b1020] border border-white/10 rounded-2xl p-6 mb-10">

        <div className="flex items-center gap-3 mb-8">
          <Sparkles className="text-cyan-400" />
          <h2 className="text-2xl font-semibold">
            AI Recommendations
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">

          {recommendations.map((item) => (
            <div
              key={item.id}
              className="bg-[#111827] border border-white/10 rounded-xl p-5"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold">
                  {item.productName}
                </h3>

                <div className="text-cyan-400 text-sm">
                  {item.confidence}%
                </div>
              </div>

              <div className="space-y-2 text-sm text-slate-300">
                <div>
                  Current: ${item.currentPrice}
                </div>

                <div className="text-cyan-400">
                  Suggested: ${item.suggestedPrice}
                </div>

                <div className="text-slate-400">
                  {item.reason}
                </div>
              </div>

              <button
                className="mt-5 w-full bg-cyan-500 hover:bg-cyan-400 transition-all text-black font-semibold py-2 rounded-lg"
              >
                Apply Price
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* AI SECTION */}
      <div className="bg-[#0b1020] border border-white/10 rounded-2xl p-8">

        <div className="flex items-center gap-3 mb-6">
          <Brain className="text-cyan-400" />
          <h2 className="text-3xl font-bold">
            How Klypup AI Works
          </h2>
        </div>

        <p className="text-slate-400 mb-8 max-w-4xl leading-8">
          Klypup AI uses Machine Learning, Dynamic Pricing Algorithms,
          Demand Forecasting, Time-Series Prediction, XGBoost,
          LSTM Neural Networks, Predictive Analytics and Competitor
          Intelligence to optimize product pricing in real-time.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">

          <AIBox
            step="01"
            title="Data Collection"
            desc="Collects competitor pricing, demand, inventory, user behavior and seasonal trends."
          />

          <AIBox
            step="02"
            title="AI Processing"
            desc="AI models analyze elasticity, market changes and pricing patterns."
          />

          <AIBox
            step="03"
            title="Prediction Engine"
            desc="Predicts optimal price and estimates revenue uplift with confidence score."
          />

          <AIBox
            step="04"
            title="Recommendation Engine"
            desc="Generates real-time pricing recommendations and actionable insights."
          />
        </div>
      </div>
    </div>
  );
}

function MetricCard({ icon: Icon, title, value, color }) {
  return (
    <div className="bg-[#0b1020] border border-white/10 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-5">
        <div
          className={`w-12 h-12 rounded-xl flex items-center justify-center bg-${color}-500/10`}
        >
          <Icon className={`text-${color}-400`} />
        </div>
      </div>

      <div className="text-3xl font-bold mb-2">
        {value}
      </div>

      <div className="text-slate-400">
        {title}
      </div>
    </div>
  );
}

function AIBox({ step, title, desc }) {
  return (
    <div className="bg-[#111827] border border-white/10 rounded-2xl p-5">
      <div className="text-cyan-400 font-bold text-sm mb-3">
        STEP {step}
      </div>

      <h3 className="text-xl font-semibold mb-3">
        {title}
      </h3>

      <p className="text-slate-400 leading-7 text-sm">
        {desc}
      </p>
    </div>
  );
}