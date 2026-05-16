import { useState, useEffect, useCallback } from "react";
import apiClient from "../services/api";

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
  Zap,
  ArrowUpRight,
} from "lucide-react";

import { motion } from "framer-motion";

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

        apiClient.get("/dashboard/metrics"),
        apiClient.get("/dashboard/revenue"),
        apiClient.get("/dashboard/pricing-trends"),
        apiClient.get("/dashboard/demand"),
        apiClient.get("/dashboard/ai-performance"),
        apiClient.get("/dashboard/recommendations"),

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

      <div className="min-h-screen flex items-center justify-center">

        <div className="glass-card px-10 py-8 flex flex-col items-center gap-5">

          <div
            style={{
              width: 54,
              height: 54,
              borderRadius: "50%",
              border: "4px solid rgba(255,255,255,0.08)",
              borderTop: "4px solid #00A19B",
              animation: "spin 1s linear infinite",
            }}
          />

          <div className="text-center">

            <h2 className="text-xl font-bold text-white">
              Klypup AI
            </h2>

            <p className="text-slate-400 mt-1 text-sm">
              Loading dashboard analytics...
            </p>

          </div>

        </div>

      </div>
    );
  }

  return (

    <div className="space-y-8">

      <div
        className="relative overflow-hidden rounded-[28px] border border-white/10 p-8 lg:p-10"
        style={{
          background:
            "linear-gradient(135deg,rgba(12,16,32,0.92),rgba(15,23,42,0.92))",
          boxShadow:
            "0 24px 60px rgba(0,0,0,0.35)",
        }}
      >

        <div
          style={{
            position: "absolute",
            width: 260,
            height: 260,
            borderRadius: "50%",
            background: "rgba(0,161,155,0.16)",
            filter: "blur(100px)",
            top: -80,
            right: -40,
          }}
        />

        <div className="relative z-10">

          <div className="inline-flex items-center gap-2 bg-[#00A19B]/10 border border-[#00A19B]/20 text-[#7FF6EE] px-4 py-2 rounded-full text-sm mb-6">

            <Brain size={16} />

            Intelligent Pricing Analytics Active

          </div>

          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">

            <div>

              <h1 className="text-4xl lg:text-5xl font-bold text-white leading-tight">

                Welcome back,
                <span className="gradient-text">
                  {" "}
                  {user?.name || "User"}
                </span>

              </h1>

              <p className="text-slate-400 text-lg mt-4 max-w-2xl leading-8">

                Monitor live pricing intelligence, demand analytics,
                revenue performance and recommendation activity in real time.

              </p>

            </div>

            <div className="grid grid-cols-2 gap-4 min-w-[280px]">

              <MiniStat
                title="Active Models"
                value="12"
              />

              <MiniStat
                title="AI Signals"
                value="98%"
              />

              <MiniStat
                title="Live Products"
                value={metrics?.liveProducts || 0}
              />

              <MiniStat
                title="Recommendations"
                value={recommendations.length}
              />

            </div>

          </div>

        </div>

      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">

        <MetricCard
          icon={DollarSign}
          title="Revenue"
          value={`$${metrics?.totalRevenue || 0}`}
          accent="from-[#00A19B] to-[#14b8a6]"
        />

        <MetricCard
          icon={Crosshair}
          title="Pricing Accuracy"
          value={`${metrics?.pricingAccuracy || 0}%`}
          accent="from-[#6366f1] to-[#8b5cf6]"
        />

        <MetricCard
          icon={Activity}
          title="Market Volatility"
          value={`${metrics?.marketVolatility || 0}%`}
          accent="from-amber-500 to-orange-500"
        />

        <MetricCard
          icon={Brain}
          title="Recommendation Confidence"
          value={`${metrics?.aiConfidence || 0}%`}
          accent="from-emerald-500 to-teal-500"
        />

        <MetricCard
          icon={Eye}
          title="Competitor Changes"
          value={metrics?.competitorChanges || 0}
          accent="from-rose-500 to-pink-500"
        />

        <MetricCard
          icon={Percent}
          title="Conversion Rate"
          value={`${metrics?.conversionRate || 0}%`}
          accent="from-sky-500 to-cyan-500"
        />

      </div>

    </div>
  );
}

function MetricCard({
  icon: Icon,
  title,
  value,
  accent,
}) {

  return (

    <motion.div
      whileHover={{
        y: -4,
      }}
      className="glass-card p-6 relative overflow-hidden"
    >

      <div
        className={`absolute top-0 right-0 w-28 h-28 opacity-20 blur-3xl bg-gradient-to-br ${accent}`}
      />

      <div className="relative z-10">

        <div className="flex items-center justify-between mb-6">

          <div
            className={`w-14 h-14 rounded-2xl flex items-center justify-center bg-gradient-to-br ${accent}`}
          >

            <Icon
              className="text-white"
              size={28}
            />

          </div>

        </div>

        <div className="text-4xl font-bold text-white mb-2">
          {value}
        </div>

        <div className="text-slate-400 text-sm">
          {title}
        </div>

      </div>

    </motion.div>
  );
}

function MiniStat({
  title,
  value,
}) {

  return (

    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4 backdrop-blur-xl">

      <div className="text-slate-500 text-xs mb-2 uppercase tracking-wide">
        {title}
      </div>

      <div className="text-2xl font-bold text-white">
        {value}
      </div>

    </div>
  );
}