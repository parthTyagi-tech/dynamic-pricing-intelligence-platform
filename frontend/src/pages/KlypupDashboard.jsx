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
  Database,
  RefreshCw,
  Layers,
  Globe,
  ChevronRight,
} from "lucide-react";

import { motion } from "framer-motion";

import { useAuth } from "../context/AuthContext";

/* ── Static data for new sections ── */
const workflowSteps = [
  { icon: Database, label: "Market Data", desc: "Real-time ingestion from 500+ sources", color: "#2dd4bf" },
  { icon: Brain, label: "AI Processing", desc: "ML models analyze patterns & signals", color: "#38bdf8" },
  { icon: Activity, label: "Prediction Engine", desc: "Demand forecasting & price elasticity", color: "#818cf8" },
  { icon: Zap, label: "Pricing Output", desc: "Optimal price delivered in <50ms", color: "#34d399" },
];

const aiCards = [
  { icon: Brain, title: "Machine Learning", desc: "Gradient Boosting + Neural Networks trained on 10M+ pricing events", tag: "Core AI", accent: "from-[#00A19B] to-[#14b8a6]", color: "#2dd4bf" },
  { icon: TrendingUp, title: "Predictive Analytics", desc: "Time-series forecasting with 94.2% demand accuracy", tag: "Forecasting", accent: "from-emerald-500 to-teal-500", color: "#34d399" },
  { icon: Globe, title: "Market Intelligence", desc: "Real-time crawl of 2,400+ competitor storefronts", tag: "Intelligence", accent: "from-sky-500 to-cyan-500", color: "#38bdf8" },
  { icon: Activity, title: "Real-time Engine", desc: "Sub-50ms pricing decisions at 1M+ RPM capacity", tag: "Performance", accent: "from-[#6366f1] to-[#8b5cf6]", color: "#818cf8" },
  { icon: RefreshCw, title: "Demand Forecasting", desc: "LSTM + seasonal decomposition for 30-day outlook", tag: "Forecasting", accent: "from-rose-500 to-pink-500", color: "#f472b6" },
  { icon: Layers, title: "Competitive AI", desc: "Automated gap analysis and undercutting alerts", tag: "Competition", accent: "from-amber-500 to-orange-500", color: "#fb923c" },
];

const howItWorksSteps = [
  { step: "01", title: "Data Ingestion", icon: Database, desc: "We continuously pull pricing signals from competitor sites, market feeds, historical sales, seasonal patterns, and consumer behavior datasets — processing over 2 million data points per hour." },
  { step: "02", title: "Pattern Recognition", icon: Brain, desc: "Our ML pipeline identifies non-obvious pricing patterns: demand elasticity curves, time-of-day effects, competitor response latency, and category-level price sensitivity." },
  { step: "03", title: "Price Prediction", icon: TrendingUp, desc: "A stacked ensemble of XGBoost, LightGBM, and LSTM neural networks outputs confidence-weighted price recommendations per product SKU, updated every 15 minutes." },
  { step: "04", title: "Recommendation Output", icon: Zap, desc: "Optimal prices are pushed via API to your storefront or ERP system. Every recommendation includes rationale, confidence score, and projected revenue impact." },
];

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

      {/* ── Hero Banner ── */}
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

      {/* ── Metric Cards ── */}
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

      {/* ── What Powers Klypup ── */}
      <div className="space-y-6">

        <SectionHeading
          label="AI ARCHITECTURE"
          title="What Powers Klypup?"
          desc="A multi-model AI system trained on billions of pricing signals, running 24/7 to maximize your revenue."
        />

        {/* Workflow pipeline */}
        <div className="flex items-stretch gap-0 flex-wrap">
          {workflowSteps.map((step, i) => (
            <div key={i} className="flex items-center flex-1 min-w-[140px]">
              <motion.div
                whileHover={{ y: -3 }}
                className="flex-1 glass-card p-4 text-center"
                style={{ borderColor: step.color + "33" }}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-3"
                  style={{ background: step.color + "18" }}
                >
                  <step.icon size={18} style={{ color: step.color }} />
                </div>
                <div className="text-sm font-semibold text-white mb-1">{step.label}</div>
                <div className="text-xs text-slate-400 leading-relaxed">{step.desc}</div>
              </motion.div>
              {i < workflowSteps.length - 1 && (
                <ChevronRight size={18} className="text-slate-600 flex-shrink-0 mx-1" />
              )}
            </div>
          ))}
        </div>

        {/* AI capability cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {aiCards.map((card) => (
            <motion.div
              key={card.title}
              whileHover={{ y: -4 }}
              className="glass-card p-5 relative overflow-hidden"
            >
              <div
                className={`absolute top-0 right-0 w-24 h-24 opacity-15 blur-3xl bg-gradient-to-br ${card.accent}`}
              />
              <div className="relative z-10">
                <div className="flex items-start justify-between mb-4">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center"
                    style={{ background: card.color + "18" }}
                  >
                    <card.icon size={18} style={{ color: card.color }} />
                  </div>
                  <span
                    className="text-xs font-semibold px-2 py-1 rounded-md"
                    style={{ background: card.color + "15", color: card.color }}
                  >
                    {card.tag}
                  </span>
                </div>
                <div className="text-sm font-semibold text-white mb-2">{card.title}</div>
                <div className="text-xs text-slate-400 leading-relaxed">{card.desc}</div>
              </div>
            </motion.div>
          ))}
        </div>

      </div>

      {/* ── How Our AI Works ── */}
      <div className="space-y-5">

        <SectionHeading
          label="AI TRANSPARENCY"
          title="How Our AI Works"
          desc="A step-by-step look inside the Klypup pricing intelligence pipeline."
        />

        <div className="flex flex-col gap-3">
          {howItWorksSteps.map((s, i) => (
            <motion.div
              key={i}
              whileHover={{ x: 4 }}
              className="glass-card p-5 flex gap-5"
            >
              <div
                className="text-4xl font-extrabold flex-shrink-0 leading-none select-none"
                style={{ color: "rgba(0,161,155,0.2)" }}
              >
                {s.step}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ background: "rgba(0,161,155,0.12)" }}
                  >
                    <s.icon size={15} style={{ color: "#2dd4bf" }} />
                  </div>
                  <div className="text-sm font-semibold text-white">{s.title}</div>
                </div>
                <p className="text-sm text-slate-400 leading-relaxed">{s.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>

      </div>

    </div>
  );
}

/* ── Sub-components ── */

function SectionHeading({ label, title, desc }) {
  return (
    <div>
      <div className="inline-flex items-center gap-2 bg-[#00A19B]/10 border border-[#00A19B]/20 text-[#7FF6EE] px-3 py-1.5 rounded-full text-xs font-semibold mb-3 tracking-wide">
        <Sparkles size={11} />
        {label}
      </div>
      <h2 className="text-2xl font-bold text-white mb-1">{title}</h2>
      {desc && <p className="text-slate-400 text-sm">{desc}</p>}
    </div>
  );
}

function MetricCard({ icon: Icon, title, value, accent }) {

  return (

    <motion.div
      whileHover={{ y: -4 }}
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

            <Icon className="text-white" size={28} />

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

function MiniStat({ title, value }) {

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
