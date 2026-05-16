import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import {
  TrendingUp, TrendingDown, Zap, Brain, Target, Activity,
  ShoppingCart, AlertTriangle, ChevronRight, CheckCircle,
  BarChart2, Layers, Shield, Globe, RefreshCw, Search,
  Bell, Settings, ChevronLeft, X, Menu, Cpu, Eye,
  Database, Sparkles, ArrowUpRight, ArrowDownRight,
  Clock, DollarSign, Percent, LayoutDashboard, Package,
  Lightbulb, GitBranch, Radio, Crosshair, ChevronDown,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

// ─── Utility ────────────────────────────────────────────────────────────────
const fmt = (n, opts = {}) =>
  n == null ? "—" : new Intl.NumberFormat("en-US", opts).format(n);
const fmtUSD = (n) => fmt(n, { style: "currency", currency: "USD", minimumFractionDigits: 0 });
const fmtPct = (n) => (n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(1)}%`);

function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target == null) return;
    let start = null;
    const step = (ts) => {
      if (!start) start = ts;
      const p = Math.min((ts - start) / duration, 1);
      setValue(target * p);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [target, duration]);
  return value;
}

// ─── Skeleton ────────────────────────────────────────────────────────────────
const Skeleton = ({ w = "100%", h = 20, rounded = 6 }) => (
  <div
    className="klypup-skeleton"
    style={{ width: w, height: h, borderRadius: rounded }}
  />
);

// ─── Custom Tooltip ──────────────────────────────────────────────────────────
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="klypup-tooltip">
      <p className="klypup-tooltip-label">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="klypup-tooltip-row">
          <span>{p.name}:</span>
          <span>{typeof p.value === "number" ? fmtUSD(p.value) : p.value}</span>
        </p>
      ))}
    </div>
  );
};

// ─── Metric Card ─────────────────────────────────────────────────────────────
function MetricCard({ icon: Icon, label, value, prefix = "", suffix = "", trend, color, loading }) {
  const numeric = parseFloat(value) || 0;
  const counted = useCountUp(loading ? 0 : numeric);
  const isUp = trend > 0;

  return (
    <div className={`klypup-card klypup-metric-card klypup-metric-card--${color}`}>
      <div className="klypup-metric-header">
        <div className={`klypup-icon-wrap klypup-icon-wrap--${color}`}>
          <Icon size={18} />
        </div>
        {loading ? (
          <Skeleton w={60} h={14} />
        ) : (
          <span className={`klypup-trend ${isUp ? "klypup-trend--up" : "klypup-trend--down"}`}>
            {isUp ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
            {Math.abs(trend).toFixed(1)}%
          </span>
        )}
      </div>
      <div className="klypup-metric-value">
        {loading ? (
          <Skeleton w="70%" h={32} />
        ) : (
          <>
            {prefix}
            {counted.toLocaleString("en-US", { maximumFractionDigits: 1 })}
            {suffix}
          </>
        )}
      </div>
      <p className="klypup-metric-label">{label}</p>
    </div>
  );
}

// ─── Section Header ──────────────────────────────────────────────────────────
const SectionHeader = ({ icon: Icon, title, subtitle, accent = "cyan" }) => (
  <div className="klypup-section-header">
    <div className={`klypup-section-icon klypup-section-icon--${accent}`}>
      <Icon size={20} />
    </div>
    <div>
      <h2 className="klypup-section-title">{title}</h2>
      {subtitle && <p className="klypup-section-sub">{subtitle}</p>}
    </div>
  </div>
);

// ─── AI Step Card ─────────────────────────────────────────────────────────────
function AIStepCard({ step, icon: Icon, title, items, accent, delay }) {
  return (
    <div className={`klypup-ai-step klypup-ai-step--${accent}`} style={{ animationDelay: `${delay}ms` }}>
      <div className="klypup-ai-step-num">{step}</div>
      <div className={`klypup-ai-step-icon klypup-ai-step-icon--${accent}`}>
        <Icon size={22} />
      </div>
      <h3 className="klypup-ai-step-title">{title}</h3>
      <ul className="klypup-ai-step-list">
        {items.map((item, i) => (
          <li key={i} className="klypup-ai-step-item">
            <span className={`klypup-ai-step-dot klypup-ai-step-dot--${accent}`} />
            {item}
          </li>
        ))}
      </ul>
      {step < 4 && <div className={`klypup-ai-connector klypup-ai-connector--${accent}`} />}
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function KlypupDashboard() {
  const { user } = useAuth();

  // sidebar
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeNav, setActiveNav] = useState("dashboard");

  // clock
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // data states
  const [metrics, setMetrics] = useState(null);
  const [revenue, setRevenue] = useState([]);
  const [pricingTrends, setPricingTrends] = useState([]);
  const [demand, setDemand] = useState([]);
  const [aiPerf, setAiPerf] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [insights, setInsights] = useState(null);
  const [product, setProduct] = useState(null);
  const [productId, setProductId] = useState("1");
  const [priceSlider, setPriceSlider] = useState(null);

  // loading / error
  const [loading, setLoading] = useState({});
  const [errors, setErrors] = useState({});
  const [applyingId, setApplyingId] = useState(null);
  const [applySuccess, setApplySuccess] = useState(null);

  const setLoad = (key, v) => setLoading((p) => ({ ...p, [key]: v }));
  const setErr = (key, v) => setErrors((p) => ({ ...p, [key]: v }));

  const fetchAll = useCallback(async () => {
    const calls = [
      {
        key: "metrics",
        fn: () => axios.get("/api/metrics"),
        setter: (d) => setMetrics(d),
      },
      {
        key: "revenue",
        fn: () => axios.get("/api/revenue"),
        setter: (d) => setRevenue(d),
      },
      {
        key: "pricing",
        fn: () => axios.get("/api/pricing-trends"),
        setter: (d) => setPricingTrends(d),
      },
      {
        key: "demand",
        fn: () => axios.get("/api/demand"),
        setter: (d) => setDemand(d),
      },
      {
        key: "aiPerf",
        fn: () => axios.get("/api/ai-performance"),
        setter: (d) => setAiPerf(d),
      },
      {
        key: "recommendations",
        fn: () => axios.get("/api/recommendations"),
        setter: (d) => setRecommendations(d),
      },
      {
        key: "insights",
        fn: () => axios.get("/api/insights"),
        setter: (d) => setInsights(d),
      },
    ];
    await Promise.all(
      calls.map(async ({ key, fn, setter }) => {
        setLoad(key, true);
        setErr(key, null);
        try {
          const { data } = await fn();
          setter(data);
        } catch (e) {
          setErr(key, e?.response?.data?.message || e.message || "Failed to load");
        } finally {
          setLoad(key, false);
        }
      })
    );
  }, []);

  const fetchProduct = useCallback(async (id) => {
    setLoad("product", true);
    setErr("product", null);
    try {
      const { data } = await axios.get(`/api/product/${id}`);
      setProduct(data);
      setPriceSlider(data.suggestedPrice ?? data.currentPrice);
    } catch (e) {
      setErr("product", e?.response?.data?.message || e.message || "Failed to load product");
    } finally {
      setLoad("product", false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    fetchProduct(productId);
  }, [productId, fetchProduct]);

  const handleApplyPrice = async (recId, price) => {
    setApplyingId(recId);
    try {
      await axios.post("/api/apply-price", { id: recId, price });
      setApplySuccess(recId);
      setTimeout(() => setApplySuccess(null), 2500);
    } catch {
      // silently fail; in production show toast
    } finally {
      setApplyingId(null);
    }
  };

  // Nav items
  const navItems = [
    { id: "dashboard", icon: LayoutDashboard, label: "Dashboard" },
    { id: "pricing", icon: DollarSign, label: "Pricing Engine" },
    { id: "analytics", icon: BarChart2, label: "Analytics" },
    { id: "ai", icon: Brain, label: "AI Models" },
    { id: "products", icon: Package, label: "Products" },
    { id: "insights", icon: Lightbulb, label: "Insights" },
    { id: "settings", icon: Settings, label: "Settings" },
  ];

  const timeStr = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const dateStr = now.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });

  return (
    <>
      <style>{CSS}</style>

      <div className="klypup-root">
        {/* ── Sidebar ── */}
        <aside className={`klypup-sidebar ${sidebarOpen ? "klypup-sidebar--open" : "klypup-sidebar--closed"}`}>
          <div className="klypup-sidebar-logo">
            <div className="klypup-logo-mark">
              <Zap size={18} />
            </div>
            {sidebarOpen && <span className="klypup-logo-text">Klypup</span>}
          </div>

          <nav className="klypup-sidebar-nav">
            {navItems.map(({ id, icon: Icon, label }) => (
              <button
                key={id}
                className={`klypup-nav-item ${activeNav === id ? "klypup-nav-item--active" : ""}`}
                onClick={() => setActiveNav(id)}
              >
                <Icon size={17} />
                {sidebarOpen && <span>{label}</span>}
              </button>
            ))}
          </nav>

          <button className="klypup-sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          </button>
        </aside>

        {/* ── Main ── */}
        <div className="klypup-main">
          {/* ── Topbar ── */}
          <header className="klypup-topbar">
            <div className="klypup-topbar-left">
              <button className="klypup-icon-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
                <Menu size={18} />
              </button>
              <div className="klypup-search-wrap">
                <Search size={15} className="klypup-search-icon" />
                <input placeholder="Search products, metrics…" className="klypup-search" />
              </div>
            </div>
            <div className="klypup-topbar-right">
              <div className="klypup-live-badge">
                <span className="klypup-live-dot" />
                LIVE
              </div>
              <div className="klypup-clock">
                <Clock size={13} />
                <span>{timeStr}</span>
                <span className="klypup-clock-date">{dateStr}</span>
              </div>
              <button className="klypup-icon-btn klypup-notif">
                <Bell size={18} />
                <span className="klypup-notif-dot" />
              </button>
              <div className="klypup-avatar">
                {user?.name?.[0]?.toUpperCase() ?? "K"}
              </div>
            </div>
          </header>

          {/* ── Content ── */}
          <div className="klypup-content">

            {/* ── HERO ── */}
            <section className="klypup-hero">
              <div className="klypup-hero-glow klypup-hero-glow--1" />
              <div className="klypup-hero-glow klypup-hero-glow--2" />
              <div className="klypup-hero-left">
                <div className="klypup-ai-badge">
                  <Cpu size={12} />
                  AI ENGINE ACTIVE · v2.4.1
                </div>
                <h1 className="klypup-hero-heading">
                  Welcome back,{" "}
                  <span className="klypup-gradient-text">
                    {user?.name?.split(" ")[0] ?? "Founder"}
                  </span>
                </h1>
                <p className="klypup-hero-sub">
                  Your pricing intelligence is operating at peak efficiency. Markets
                  monitored, competitors tracked, revenue optimized.
                </p>
                <div className="klypup-hero-stats">
                  <div className="klypup-hero-stat">
                    <TrendingUp size={14} className="klypup-hero-stat-icon" />
                    {loading.metrics ? (
                      <Skeleton w={80} h={14} />
                    ) : (
                      <span>
                        Revenue{" "}
                        <strong className="klypup-green">
                          {fmtPct(metrics?.revenueGrowth)}
                        </strong>{" "}
                        this week
                      </span>
                    )}
                  </div>
                  <div className="klypup-hero-stat">
                    <Shield size={14} className="klypup-hero-stat-icon" />
                    {loading.metrics ? (
                      <Skeleton w={100} h={14} />
                    ) : (
                      <span>
                        AI Confidence{" "}
                        <strong className="klypup-cyan">
                          {metrics?.aiConfidence?.toFixed(1)}%
                        </strong>
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="klypup-hero-right">
                <div className="klypup-market-status">
                  <div className="klypup-market-status-header">
                    <Radio size={14} className="klypup-cyan-text" />
                    <span>Market Status</span>
                  </div>
                  {["NYSE", "NASDAQ", "Crypto"].map((m) => (
                    <div key={m} className="klypup-market-row">
                      <span>{m}</span>
                      <span className="klypup-live-dot" style={{ margin: "0 4px 0 auto" }} />
                      <span className="klypup-green" style={{ fontSize: 12 }}>OPEN</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* ── METRIC CARDS ── */}
            <section className="klypup-metrics-grid">
              <MetricCard
                icon={DollarSign}
                label="Total Revenue"
                value={metrics?.totalRevenue}
                prefix="$"
                trend={metrics?.revenueGrowth}
                color="cyan"
                loading={loading.metrics}
              />
              <MetricCard
                icon={Crosshair}
                label="Pricing Accuracy"
                value={metrics?.pricingAccuracy}
                suffix="%"
                trend={metrics?.pricingAccuracyTrend}
                color="violet"
                loading={loading.metrics}
              />
              <MetricCard
                icon={Activity}
                label="Market Volatility"
                value={metrics?.marketVolatility}
                suffix="%"
                trend={metrics?.volatilityTrend}
                color="amber"
                loading={loading.metrics}
              />
              <MetricCard
                icon={Brain}
                label="AI Confidence"
                value={metrics?.aiConfidence}
                suffix="%"
                trend={metrics?.aiConfidenceTrend}
                color="green"
                loading={loading.metrics}
              />
              <MetricCard
                icon={Eye}
                label="Competitor Changes"
                value={metrics?.competitorChanges}
                trend={metrics?.competitorTrend}
                color="rose"
                loading={loading.metrics}
              />
              <MetricCard
                icon={Percent}
                label="Conversion Rate"
                value={metrics?.conversionRate}
                suffix="%"
                trend={metrics?.conversionTrend}
                color="sky"
                loading={loading.metrics}
              />
            </section>

            {/* ── REVENUE + PRICING ── */}
            <div className="klypup-two-col">
              {/* Revenue */}
              <div className="klypup-card klypup-chart-card">
                <SectionHeader icon={TrendingUp} title="Revenue Analytics" subtitle="Actual vs AI Prediction" accent="cyan" />
                {errors.revenue && <p className="klypup-error">{errors.revenue}</p>}
                {loading.revenue ? (
                  <div className="klypup-chart-skeleton">
                    <Skeleton w="100%" h={220} rounded={8} />
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <AreaChart data={revenue} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="revActual" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.35} />
                          <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="revPred" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#a855f7" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                      <Tooltip content={<ChartTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
                      <Area type="monotone" dataKey="actual" name="Actual" stroke="#06b6d4" strokeWidth={2} fill="url(#revActual)" dot={false} />
                      <Area type="monotone" dataKey="predicted" name="AI Prediction" stroke="#a855f7" strokeWidth={2} fill="url(#revPred)" dot={false} strokeDasharray="5 3" />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Pricing Trends */}
              <div className="klypup-card klypup-chart-card">
                <SectionHeader icon={Zap} title="Live Pricing Engine" subtitle="AI vs Competitor vs Market" accent="violet" />
                {errors.pricing && <p className="klypup-error">{errors.pricing}</p>}
                {loading.pricing ? (
                  <div className="klypup-chart-skeleton">
                    <Skeleton w="100%" h={220} rounded={8} />
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={pricingTrends} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
                      <Tooltip content={<ChartTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
                      <Line type="monotone" dataKey="aiPrice" name="AI Price" stroke="#06b6d4" strokeWidth={2.5} dot={false} />
                      <Line type="monotone" dataKey="competitorPrice" name="Competitor" stroke="#f43f5e" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                      <Line type="monotone" dataKey="marketAverage" name="Market Avg" stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="2 4" />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* ── DEMAND + AI PERFORMANCE ── */}
            <div className="klypup-two-col">
              {/* Demand */}
              <div className="klypup-card klypup-chart-card">
                <SectionHeader icon={BarChart2} title="Demand Analytics" subtitle="Category demand intelligence" accent="amber" />
                {errors.demand && <p className="klypup-error">{errors.demand}</p>}
                {loading.demand ? (
                  <Skeleton w="100%" h={220} rounded={8} />
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={demand} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                      <XAxis type="number" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="category" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} width={90} />
                      <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                      <Bar dataKey="demand" name="Demand" fill="#f59e0b" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* AI Radar */}
              <div className="klypup-card klypup-chart-card">
                <SectionHeader icon={Brain} title="AI Model Performance" subtitle="Multi-dimensional scoring" accent="green" />
                {errors.aiPerf && <p className="klypup-error">{errors.aiPerf}</p>}
                {loading.aiPerf ? (
                  <Skeleton w="100%" h={220} rounded={8} />
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <RadarChart data={aiPerf} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
                      <PolarGrid stroke="rgba(255,255,255,0.08)" />
                      <PolarAngleAxis dataKey="metric" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "#475569", fontSize: 10 }} />
                      <Radar name="Score" dataKey="score" stroke="#22c55e" fill="#22c55e" fillOpacity={0.2} strokeWidth={2} />
                      <Tooltip content={<ChartTooltip />} />
                    </RadarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* ── RECOMMENDATIONS ── */}
            <section className="klypup-card">
              <SectionHeader icon={Sparkles} title="Real-Time Price Recommendations" subtitle="AI-generated pricing actions" accent="cyan" />
              {errors.recommendations && <p className="klypup-error">{errors.recommendations}</p>}
              {loading.recommendations ? (
                <div className="klypup-recs-grid">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="klypup-rec-card">
                      <Skeleton w="60%" h={16} />
                      <Skeleton w="40%" h={28} />
                      <Skeleton w="80%" h={12} />
                      <Skeleton w="100%" h={36} rounded={8} />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="klypup-recs-grid">
                  {recommendations.map((rec) => {
                    const diff = rec.suggestedPrice - rec.currentPrice;
                    const pct = ((diff / rec.currentPrice) * 100).toFixed(1);
                    const isApplying = applyingId === rec.id;
                    const isSuccess = applySuccess === rec.id;
                    return (
                      <div key={rec.id} className="klypup-rec-card">
                        <div className="klypup-rec-header">
                          <span className="klypup-rec-name">{rec.productName}</span>
                          <span
                            className={`klypup-conf-badge ${
                              rec.confidence >= 85
                                ? "klypup-conf-badge--high"
                                : rec.confidence >= 65
                                ? "klypup-conf-badge--mid"
                                : "klypup-conf-badge--low"
                            }`}
                          >
                            {rec.confidence}%
                          </span>
                        </div>
                        <div className="klypup-rec-prices">
                          <div className="klypup-rec-price-item">
                            <span className="klypup-rec-price-label">Current</span>
                            <span className="klypup-rec-price-val">{fmtUSD(rec.currentPrice)}</span>
                          </div>
                          <ChevronRight size={16} style={{ color: "#334155", flexShrink: 0 }} />
                          <div className="klypup-rec-price-item klypup-rec-price-item--ai">
                            <span className="klypup-rec-price-label">AI Suggests</span>
                            <span className="klypup-rec-price-val klypup-cyan-text">{fmtUSD(rec.suggestedPrice)}</span>
                          </div>
                          <span className={`klypup-price-diff ${diff >= 0 ? "klypup-green" : "klypup-rose"}`}>
                            {diff >= 0 ? "+" : ""}{pct}%
                          </span>
                        </div>
                        <p className="klypup-rec-reason">{rec.reason}</p>
                        <button
                          className={`klypup-apply-btn ${isSuccess ? "klypup-apply-btn--success" : ""}`}
                          onClick={() => handleApplyPrice(rec.id, rec.suggestedPrice)}
                          disabled={isApplying || isSuccess}
                        >
                          {isApplying ? (
                            <><RefreshCw size={13} className="klypup-spin" /> Applying…</>
                          ) : isSuccess ? (
                            <><CheckCircle size={13} /> Applied!</>
                          ) : (
                            <><Zap size={13} /> Apply Price</>
                          )}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* ── FEATURED PRODUCT ── */}
            <section className="klypup-card">
              <div className="klypup-product-header">
                <SectionHeader icon={Target} title="Featured Product Pricing" subtitle="Deep-dive price controls" accent="violet" />
                <div className="klypup-product-select">
                  <label className="klypup-product-label">Product ID</label>
                  <div className="klypup-product-input-wrap">
                    <input
                      className="klypup-product-input"
                      value={productId}
                      onChange={(e) => setProductId(e.target.value)}
                      placeholder="Enter product ID"
                    />
                    <button className="klypup-product-go" onClick={() => fetchProduct(productId)}>
                      <ChevronRight size={15} />
                    </button>
                  </div>
                </div>
              </div>

              {errors.product && <p className="klypup-error">{errors.product}</p>}
              {loading.product ? (
                <div className="klypup-product-grid">
                  {[...Array(8)].map((_, i) => <Skeleton key={i} w="100%" h={60} rounded={8} />)}
                </div>
              ) : product ? (
                <div className="klypup-product-panel">
                  <div className="klypup-product-grid">
                    {[
                      { label: "Current Price", value: fmtUSD(product.currentPrice), color: "default" },
                      { label: "AI Suggested", value: fmtUSD(product.suggestedPrice), color: "cyan" },
                      { label: "Competitor Avg", value: fmtUSD(product.competitorAverage), color: "rose" },
                      { label: "Demand Level", value: product.demandLevel, color: "amber" },
                      { label: "AI Confidence", value: `${product.aiConfidence}%`, color: "green" },
                      { label: "Revenue Uplift", value: fmtPct(product.revenueUplift), color: "green" },
                      { label: "Market Risk", value: product.marketRisk, color: "rose" },
                      { label: "Conversion Δ", value: fmtPct(product.conversionDelta), color: "cyan" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className={`klypup-product-stat klypup-product-stat--${color}`}>
                        <span className="klypup-product-stat-label">{label}</span>
                        <span className={`klypup-product-stat-value klypup-product-stat-value--${color}`}>
                          {value}
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="klypup-slider-section">
                    <div className="klypup-slider-header">
                      <span className="klypup-slider-label">Price Control</span>
                      <span className="klypup-slider-value">{fmtUSD(priceSlider)}</span>
                    </div>
                    <input
                      type="range"
                      className="klypup-slider"
                      min={product.currentPrice * 0.5}
                      max={product.currentPrice * 2}
                      step={0.01}
                      value={priceSlider ?? product.currentPrice}
                      onChange={(e) => setPriceSlider(parseFloat(e.target.value))}
                    />
                    <div className="klypup-slider-marks">
                      <span>-50%</span>
                      <span className="klypup-cyan-text">Suggested: {fmtUSD(product.suggestedPrice)}</span>
                      <span>+100%</span>
                    </div>
                    <button
                      className="klypup-apply-btn klypup-apply-btn--wide"
                      onClick={() => handleApplyPrice(product.id, priceSlider)}
                      disabled={!!applyingId}
                    >
                      <Zap size={15} />
                      Apply Custom Price: {fmtUSD(priceSlider)}
                    </button>
                  </div>
                </div>
              ) : null}
            </section>

            {/* ── INSIGHTS ── */}
            <section className="klypup-card">
              <SectionHeader icon={Lightbulb} title="Market Insights" subtitle="AI-curated intelligence feed" accent="amber" />
              {errors.insights && <p className="klypup-error">{errors.insights}</p>}
              {loading.insights ? (
                <div className="klypup-insights-grid">
                  {[...Array(5)].map((_, i) => <Skeleton key={i} w="100%" h={80} rounded={8} />)}
                </div>
              ) : insights ? (
                <div className="klypup-insights-grid">
                  {insights.trending?.map((item, i) => (
                    <div key={i} className="klypup-insight-card klypup-insight-card--cyan">
                      <TrendingUp size={14} className="klypup-cyan-text" />
                      <div>
                        <p className="klypup-insight-type">Trending</p>
                        <p className="klypup-insight-text">{item}</p>
                      </div>
                    </div>
                  ))}
                  {insights.alerts?.map((item, i) => (
                    <div key={i} className="klypup-insight-card klypup-insight-card--amber">
                      <AlertTriangle size={14} className="klypup-amber-text" />
                      <div>
                        <p className="klypup-insight-type">Alert</p>
                        <p className="klypup-insight-text">{item}</p>
                      </div>
                    </div>
                  ))}
                  {insights.competitor?.map((item, i) => (
                    <div key={i} className="klypup-insight-card klypup-insight-card--rose">
                      <Eye size={14} className="klypup-rose-text" />
                      <div>
                        <p className="klypup-insight-type">Competitor</p>
                        <p className="klypup-insight-text">{item}</p>
                      </div>
                    </div>
                  ))}
                  {insights.opportunities?.map((item, i) => (
                    <div key={i} className="klypup-insight-card klypup-insight-card--green">
                      <Sparkles size={14} className="klypup-green-text" />
                      <div>
                        <p className="klypup-insight-type">Opportunity</p>
                        <p className="klypup-insight-text">{item}</p>
                      </div>
                    </div>
                  ))}
                  {insights.bundles?.map((item, i) => (
                    <div key={i} className="klypup-insight-card klypup-insight-card--violet">
                      <Layers size={14} className="klypup-violet-text" />
                      <div>
                        <p className="klypup-insight-type">Bundle</p>
                        <p className="klypup-insight-text">{item}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </section>

            {/* ── HOW OUR AI WORKS ── */}
            <section className="klypup-ai-section">
              <div className="klypup-ai-glow" />
              <div className="klypup-ai-header">
                <div className="klypup-ai-badge klypup-ai-badge--large">
                  <Brain size={16} />
                  AI Architecture
                </div>
                <h2 className="klypup-ai-title">
                  How <span className="klypup-gradient-text">Klypup AI</span> Works
                </h2>
                <p className="klypup-ai-desc">
                  A proprietary stack of machine learning models, real-time data pipelines, and
                  reinforcement learning loops — engineered to maximize your revenue per decision.
                </p>
              </div>

              {/* Tech pills */}
              <div className="klypup-tech-pills">
                {[
                  "XGBoost", "LSTM Networks", "Gradient Boosting", "Reinforcement Learning",
                  "Time-Series ARIMA", "Elasticity Analysis", "Demand Forecasting",
                  "Competitor Intelligence", "Dynamic Pricing", "Predictive Analytics",
                ].map((t) => (
                  <span key={t} className="klypup-tech-pill">{t}</span>
                ))}
              </div>

              {/* Steps */}
              <div className="klypup-ai-steps">
                <AIStepCard
                  step={1} icon={Database} accent="cyan" delay={0}
                  title="Data Collection"
                  items={[
                    "Competitor pricing scraped in real-time",
                    "Historical sales & revenue data",
                    "Live market demand signals",
                    "Inventory & supply chain data",
                    "Seasonal trend patterns",
                    "User behavior & click-stream events",
                  ]}
                />
                <AIStepCard
                  step={2} icon={Cpu} accent="violet" delay={100}
                  title="AI Processing"
                  items={[
                    "XGBoost detects pricing elasticity",
                    "LSTM forecasts multi-step demand",
                    "Gradient Boosting ranks price points",
                    "Anomaly detection flags outliers",
                    "Temporal patterns extracted",
                  ]}
                />
                <AIStepCard
                  step={3} icon={GitBranch} accent="green" delay={200}
                  title="Prediction Engine"
                  items={[
                    "Optimal price computed per SKU",
                    "Revenue uplift estimated",
                    "Confidence score generated (0–100)",
                    "Risk-adjusted recommendations",
                    "Elasticity curve modeled",
                  ]}
                />
                <AIStepCard
                  step={4} icon={Zap} accent="amber" delay={300}
                  title="Recommendation Engine"
                  items={[
                    "Price pushed to dashboard instantly",
                    "One-click apply workflow",
                    "Outcome tracked & fed back",
                    "Model retrained on new data",
                    "Continuous reinforcement loop",
                  ]}
                />
              </div>

              {/* Model cards */}
              <div className="klypup-model-cards">
                {[
                  { name: "XGBoost", role: "Elasticity & Feature Importance", acc: 94, color: "cyan" },
                  { name: "LSTM", role: "Time-Series Demand Forecasting", acc: 91, color: "violet" },
                  { name: "Gradient Boost", role: "Price Rank & Revenue Opt.", acc: 96, color: "green" },
                  { name: "RL Agent", role: "Long-Horizon Strategy", acc: 88, color: "amber" },
                ].map((m) => (
                  <div key={m.name} className={`klypup-model-card klypup-model-card--${m.color}`}>
                    <div className={`klypup-model-icon klypup-model-icon--${m.color}`}>
                      <Brain size={18} />
                    </div>
                    <h4 className="klypup-model-name">{m.name}</h4>
                    <p className="klypup-model-role">{m.role}</p>
                    <div className="klypup-model-bar-wrap">
                      <div className="klypup-model-bar-track">
                        <div
                          className={`klypup-model-bar klypup-model-bar--${m.color}`}
                          style={{ width: `${m.acc}%` }}
                        />
                      </div>
                      <span className={`klypup-model-acc klypup-model-acc--${m.color}`}>{m.acc}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Footer */}
            <footer className="klypup-footer">
              <span>© {new Date().getFullYear()} Klypup · AI Pricing Intelligence</span>
              <span>Powered by proprietary ML infrastructure</span>
            </footer>
          </div>
        </div>
      </div>
    </>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────
const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #020408;
    --bg-1: #080e18;
    --bg-2: #0d1525;
    --border: rgba(255,255,255,0.06);
    --border-hover: rgba(255,255,255,0.12);
    --text: #e2e8f0;
    --text-muted: #64748b;
    --text-sub: #94a3b8;
    --cyan: #06b6d4;
    --cyan-dim: rgba(6,182,212,0.15);
    --violet: #a855f7;
    --violet-dim: rgba(168,85,247,0.15);
    --green: #22c55e;
    --green-dim: rgba(34,197,94,0.15);
    --amber: #f59e0b;
    --amber-dim: rgba(245,158,11,0.15);
    --rose: #f43f5e;
    --rose-dim: rgba(244,63,94,0.15);
    --sky: #38bdf8;
    --sky-dim: rgba(56,189,248,0.15);
    --sidebar-w: 220px;
    --sidebar-w-closed: 60px;
    --topbar-h: 56px;
    --radius: 12px;
    --font: 'Space Grotesk', sans-serif;
    --mono: 'JetBrains Mono', monospace;
  }

  body { background: var(--bg); color: var(--text); font-family: var(--font); }

  /* ─── Root ─── */
  .klypup-root { display: flex; min-height: 100vh; background: var(--bg); }

  /* ─── Sidebar ─── */
  .klypup-sidebar {
    position: fixed; top: 0; left: 0; height: 100vh; z-index: 100;
    background: var(--bg-1);
    border-right: 1px solid var(--border);
    display: flex; flex-direction: column;
    transition: width 0.25s cubic-bezier(0.4,0,0.2,1);
    overflow: hidden;
  }
  .klypup-sidebar--open { width: var(--sidebar-w); }
  .klypup-sidebar--closed { width: var(--sidebar-w-closed); }

  .klypup-sidebar-logo {
    display: flex; align-items: center; gap: 10px;
    padding: 16px 16px 12px;
    border-bottom: 1px solid var(--border);
    min-height: 56px;
  }
  .klypup-logo-mark {
    width: 30px; height: 30px; border-radius: 8px;
    background: linear-gradient(135deg, var(--cyan), var(--violet));
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; color: #fff;
    box-shadow: 0 0 16px rgba(6,182,212,0.4);
  }
  .klypup-logo-text { font-size: 16px; font-weight: 700; color: #fff; white-space: nowrap; }

  .klypup-sidebar-nav { flex: 1; padding: 12px 8px; display: flex; flex-direction: column; gap: 2px; overflow-y: auto; }

  .klypup-nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 10px; border-radius: 8px;
    background: none; border: none; cursor: pointer;
    color: var(--text-muted); font-family: var(--font); font-size: 13.5px; font-weight: 500;
    transition: all 0.15s; white-space: nowrap; width: 100%; text-align: left;
  }
  .klypup-nav-item:hover { background: rgba(255,255,255,0.04); color: var(--text); }
  .klypup-nav-item--active { background: var(--cyan-dim); color: var(--cyan); }

  .klypup-sidebar-toggle {
    margin: 8px; padding: 8px; border-radius: 8px;
    background: rgba(255,255,255,0.04); border: 1px solid var(--border);
    color: var(--text-muted); cursor: pointer; display: flex; align-items: center; justify-content: center;
    transition: all 0.15s;
  }
  .klypup-sidebar-toggle:hover { color: var(--text); border-color: var(--border-hover); }

  /* ─── Main ─── */
  .klypup-main {
    flex: 1;
    margin-left: var(--sidebar-w);
    transition: margin-left 0.25s cubic-bezier(0.4,0,0.2,1);
    display: flex; flex-direction: column; min-height: 100vh;
  }
  .klypup-sidebar--closed ~ .klypup-main { margin-left: var(--sidebar-w-closed); }

  /* ─── Topbar ─── */
  .klypup-topbar {
    position: sticky; top: 0; z-index: 90;
    height: var(--topbar-h);
    background: rgba(8,14,24,0.85);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 20px; gap: 16px;
  }
  .klypup-topbar-left { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
  .klypup-topbar-right { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }

  .klypup-icon-btn {
    width: 34px; height: 34px; border-radius: 8px;
    background: rgba(255,255,255,0.04); border: 1px solid var(--border);
    color: var(--text-muted); cursor: pointer; display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; flex-shrink: 0;
  }
  .klypup-icon-btn:hover { color: var(--text); border-color: var(--border-hover); background: rgba(255,255,255,0.07); }

  .klypup-search-wrap { position: relative; flex: 1; max-width: 340px; }
  .klypup-search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--text-muted); }
  .klypup-search {
    width: 100%; height: 34px; padding: 0 12px 0 32px;
    background: rgba(255,255,255,0.04); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text); font-family: var(--font); font-size: 13px;
    outline: none; transition: border-color 0.15s;
  }
  .klypup-search::placeholder { color: var(--text-muted); }
  .klypup-search:focus { border-color: var(--cyan); }

  .klypup-live-badge {
    display: flex; align-items: center; gap: 6px;
    padding: 4px 10px; border-radius: 20px;
    background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.25);
    color: var(--green); font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
    font-family: var(--mono);
  }
  .klypup-live-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--green); box-shadow: 0 0 6px var(--green);
    animation: klypup-pulse 1.5s infinite;
  }
  @keyframes klypup-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

  .klypup-clock { display: flex; align-items: center; gap: 6px; color: var(--text-sub); font-size: 13px; font-family: var(--mono); }
  .klypup-clock-date { color: var(--text-muted); font-size: 11px; }

  .klypup-notif { position: relative; }
  .klypup-notif-dot {
    position: absolute; top: 6px; right: 6px; width: 6px; height: 6px;
    border-radius: 50%; background: var(--rose); box-shadow: 0 0 6px var(--rose);
  }

  .klypup-avatar {
    width: 32px; height: 32px; border-radius: 50%;
    background: linear-gradient(135deg, var(--cyan), var(--violet));
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700; color: #fff; cursor: pointer;
    box-shadow: 0 0 12px rgba(6,182,212,0.3);
  }

  /* ─── Content ─── */
  .klypup-content { padding: 24px; display: flex; flex-direction: column; gap: 24px; max-width: 1600px; }

  /* ─── Hero ─── */
  .klypup-hero {
    position: relative; overflow: hidden;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 32px;
    display: flex; gap: 32px; align-items: center;
  }
  .klypup-hero-glow {
    position: absolute; border-radius: 50%; pointer-events: none; filter: blur(80px);
  }
  .klypup-hero-glow--1 { width: 400px; height: 300px; background: rgba(6,182,212,0.08); top: -60px; left: -80px; }
  .klypup-hero-glow--2 { width: 300px; height: 200px; background: rgba(168,85,247,0.07); bottom: -40px; right: -40px; }
  .klypup-hero-left { flex: 1; position: relative; z-index: 1; }
  .klypup-hero-right { position: relative; z-index: 1; }

  .klypup-ai-badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 20px;
    background: var(--cyan-dim); border: 1px solid rgba(6,182,212,0.3);
    color: var(--cyan); font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
    font-family: var(--mono); margin-bottom: 14px;
  }

  .klypup-hero-heading { font-size: clamp(22px, 3vw, 32px); font-weight: 700; color: #fff; margin-bottom: 8px; line-height: 1.2; }
  .klypup-gradient-text {
    background: linear-gradient(90deg, var(--cyan), var(--violet));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  }
  .klypup-hero-sub { color: var(--text-sub); font-size: 14px; line-height: 1.6; max-width: 480px; margin-bottom: 20px; }

  .klypup-hero-stats { display: flex; gap: 20px; flex-wrap: wrap; }
  .klypup-hero-stat { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-sub); }
  .klypup-hero-stat-icon { flex-shrink: 0; }
  .klypup-green { color: var(--green); font-weight: 600; }
  .klypup-cyan { color: var(--cyan); font-weight: 600; }

  .klypup-market-status {
    background: rgba(255,255,255,0.03); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px; min-width: 200px;
  }
  .klypup-market-status-header { display: flex; align-items: center; gap: 6px; color: var(--text-sub); font-size: 12px; margin-bottom: 12px; font-weight: 600; letter-spacing: 0.04em; }
  .klypup-market-row { display: flex; align-items: center; gap: 4px; font-size: 13px; color: var(--text-sub); padding: 4px 0; }

  /* ─── Card ─── */
  .klypup-card {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    transition: border-color 0.2s;
  }
  .klypup-card:hover { border-color: var(--border-hover); }

  /* ─── Metrics Grid ─── */
  .klypup-metrics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }

  .klypup-metric-card { cursor: default; position: relative; overflow: hidden; }
  .klypup-metric-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    opacity: 0; transition: opacity 0.2s;
  }
  .klypup-metric-card:hover::before { opacity: 1; }
  .klypup-metric-card--cyan::before { background: var(--cyan); }
  .klypup-metric-card--violet::before { background: var(--violet); }
  .klypup-metric-card--amber::before { background: var(--amber); }
  .klypup-metric-card--green::before { background: var(--green); }
  .klypup-metric-card--rose::before { background: var(--rose); }
  .klypup-metric-card--sky::before { background: var(--sky); }

  .klypup-metric-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }

  .klypup-icon-wrap {
    width: 32px; height: 32px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
  }
  .klypup-icon-wrap--cyan { background: var(--cyan-dim); color: var(--cyan); }
  .klypup-icon-wrap--violet { background: var(--violet-dim); color: var(--violet); }
  .klypup-icon-wrap--amber { background: var(--amber-dim); color: var(--amber); }
  .klypup-icon-wrap--green { background: var(--green-dim); color: var(--green); }
  .klypup-icon-wrap--rose { background: var(--rose-dim); color: var(--rose); }
  .klypup-icon-wrap--sky { background: var(--sky-dim); color: var(--sky); }

  .klypup-trend { display: flex; align-items: center; gap: 2px; font-size: 12px; font-weight: 600; font-family: var(--mono); }
  .klypup-trend--up { color: var(--green); }
  .klypup-trend--down { color: var(--rose); }

  .klypup-metric-value { font-size: 26px; font-weight: 700; color: #fff; line-height: 1; margin-bottom: 6px; font-family: var(--mono); }
  .klypup-metric-label { font-size: 12px; color: var(--text-muted); font-weight: 500; }

  /* ─── Two col ─── */
  .klypup-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  @media (max-width: 900px) { .klypup-two-col { grid-template-columns: 1fr; } }

  /* ─── Chart card ─── */
  .klypup-chart-card { display: flex; flex-direction: column; gap: 16px; }
  .klypup-chart-skeleton { opacity: 0.4; }

  /* ─── Section Header ─── */
  .klypup-section-header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
  .klypup-section-icon {
    width: 36px; height: 36px; border-radius: 9px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
  }
  .klypup-section-icon--cyan { background: var(--cyan-dim); color: var(--cyan); box-shadow: 0 0 16px rgba(6,182,212,0.2); }
  .klypup-section-icon--violet { background: var(--violet-dim); color: var(--violet); box-shadow: 0 0 16px rgba(168,85,247,0.2); }
  .klypup-section-icon--green { background: var(--green-dim); color: var(--green); box-shadow: 0 0 16px rgba(34,197,94,0.2); }
  .klypup-section-icon--amber { background: var(--amber-dim); color: var(--amber); box-shadow: 0 0 16px rgba(245,158,11,0.2); }
  .klypup-section-title { font-size: 16px; font-weight: 700; color: #fff; }
  .klypup-section-sub { font-size: 12px; color: var(--text-muted); margin-top: 1px; }

  /* ─── Skeleton ─── */
  .klypup-skeleton {
    background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
    background-size: 200% 100%;
    animation: klypup-shimmer 1.5s infinite;
  }
  @keyframes klypup-shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }

  /* ─── Tooltip ─── */
  .klypup-tooltip {
    background: var(--bg-2); border: 1px solid var(--border-hover);
    border-radius: 8px; padding: 10px 14px; font-size: 12px; font-family: var(--font);
  }
  .klypup-tooltip-label { color: var(--text-muted); margin-bottom: 6px; font-size: 11px; }
  .klypup-tooltip-row { display: flex; justify-content: space-between; gap: 16px; margin-top: 3px; }

  /* ─── Recommendations ─── */
  .klypup-recs-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; margin-top: 16px; }

  .klypup-rec-card {
    background: var(--bg-2); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px;
    display: flex; flex-direction: column; gap: 12px;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .klypup-rec-card:hover { border-color: var(--border-hover); box-shadow: 0 4px 24px rgba(0,0,0,0.3); }

  .klypup-rec-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .klypup-rec-name { font-size: 14px; font-weight: 600; color: #fff; }

  .klypup-conf-badge { padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 700; font-family: var(--mono); }
  .klypup-conf-badge--high { background: var(--green-dim); color: var(--green); border: 1px solid rgba(34,197,94,0.25); }
  .klypup-conf-badge--mid { background: var(--amber-dim); color: var(--amber); border: 1px solid rgba(245,158,11,0.25); }
  .klypup-conf-badge--low { background: var(--rose-dim); color: var(--rose); border: 1px solid rgba(244,63,94,0.25); }

  .klypup-rec-prices { display: flex; align-items: center; gap: 8px; }
  .klypup-rec-price-item { display: flex; flex-direction: column; gap: 2px; }
  .klypup-rec-price-item--ai { flex: 1; }
  .klypup-rec-price-label { font-size: 10px; color: var(--text-muted); font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
  .klypup-rec-price-val { font-size: 16px; font-weight: 700; color: var(--text); font-family: var(--mono); }
  .klypup-cyan-text { color: var(--cyan) !important; }
  .klypup-rose { color: var(--rose); }
  .klypup-rose-text { color: var(--rose); }
  .klypup-amber-text { color: var(--amber); }
  .klypup-green-text { color: var(--green); }
  .klypup-violet-text { color: var(--violet); }

  .klypup-price-diff { font-size: 12px; font-weight: 700; font-family: var(--mono); flex-shrink: 0; }

  .klypup-rec-reason { font-size: 12px; color: var(--text-sub); line-height: 1.5; flex: 1; }

  .klypup-apply-btn {
    display: flex; align-items: center; justify-content: center; gap: 6px;
    padding: 9px 16px; border-radius: 8px;
    background: var(--cyan-dim); border: 1px solid rgba(6,182,212,0.35);
    color: var(--cyan); font-family: var(--font); font-size: 13px; font-weight: 600;
    cursor: pointer; transition: all 0.2s;
  }
  .klypup-apply-btn:hover:not(:disabled) { background: rgba(6,182,212,0.25); box-shadow: 0 0 16px rgba(6,182,212,0.25); }
  .klypup-apply-btn:disabled { opacity: 0.6; cursor: not-allowed; }
  .klypup-apply-btn--success { background: var(--green-dim); border-color: rgba(34,197,94,0.35); color: var(--green); }
  .klypup-apply-btn--wide { width: 100%; margin-top: 12px; }
  .klypup-spin { animation: klypup-rotate 1s linear infinite; }
  @keyframes klypup-rotate { to { transform: rotate(360deg); } }

  /* ─── Product Panel ─── */
  .klypup-product-header { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
  .klypup-product-select { display: flex; flex-direction: column; gap: 4px; }
  .klypup-product-label { font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
  .klypup-product-input-wrap { display: flex; align-items: center; gap: 6px; }
  .klypup-product-input {
    padding: 7px 12px; background: var(--bg-2); border: 1px solid var(--border);
    border-radius: 7px; color: var(--text); font-family: var(--font); font-size: 13px; outline: none;
    width: 140px; transition: border-color 0.15s;
  }
  .klypup-product-input:focus { border-color: var(--cyan); }
  .klypup-product-go {
    width: 32px; height: 32px; border-radius: 7px;
    background: var(--cyan-dim); border: 1px solid rgba(6,182,212,0.3);
    color: var(--cyan); cursor: pointer; display: flex; align-items: center; justify-content: center;
    transition: all 0.15s;
  }
  .klypup-product-go:hover { background: rgba(6,182,212,0.25); }

  .klypup-product-panel { display: flex; flex-direction: column; gap: 20px; }
  .klypup-product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
  .klypup-product-stat {
    background: var(--bg-2); border: 1px solid var(--border);
    border-radius: 9px; padding: 14px;
    display: flex; flex-direction: column; gap: 6px;
    transition: border-color 0.15s;
  }
  .klypup-product-stat:hover { border-color: var(--border-hover); }
  .klypup-product-stat-label { font-size: 11px; color: var(--text-muted); font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
  .klypup-product-stat-value { font-size: 20px; font-weight: 700; font-family: var(--mono); color: var(--text); }
  .klypup-product-stat-value--cyan { color: var(--cyan); }
  .klypup-product-stat-value--rose { color: var(--rose); }
  .klypup-product-stat-value--amber { color: var(--amber); }
  .klypup-product-stat-value--green { color: var(--green); }
  .klypup-product-stat-value--default { color: #fff; }

  .klypup-slider-section { background: var(--bg-2); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
  .klypup-slider-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .klypup-slider-label { font-size: 13px; font-weight: 600; color: var(--text-sub); }
  .klypup-slider-value { font-size: 20px; font-weight: 700; font-family: var(--mono); color: var(--cyan); }
  .klypup-slider {
    width: 100%; height: 4px; border-radius: 2px; outline: none;
    background: linear-gradient(90deg, var(--cyan) calc((var(--val, 50)) * 1%), rgba(255,255,255,0.1) 0);
    -webkit-appearance: none; appearance: none; cursor: pointer; margin-bottom: 8px;
    accent-color: var(--cyan);
  }
  .klypup-slider-marks { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); }

  /* ─── Insights ─── */
  .klypup-insights-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-top: 16px; }
  .klypup-insight-card {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 14px; border-radius: 9px; border: 1px solid var(--border);
    background: var(--bg-2); transition: all 0.2s;
  }
  .klypup-insight-card:hover { border-color: var(--border-hover); }
  .klypup-insight-card--cyan { border-color: rgba(6,182,212,0.15); }
  .klypup-insight-card--amber { border-color: rgba(245,158,11,0.15); }
  .klypup-insight-card--rose { border-color: rgba(244,63,94,0.15); }
  .klypup-insight-card--green { border-color: rgba(34,197,94,0.15); }
  .klypup-insight-card--violet { border-color: rgba(168,85,247,0.15); }
  .klypup-insight-type { font-size: 10px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
  .klypup-insight-text { font-size: 13px; color: var(--text-sub); line-height: 1.45; }

  /* ─── Error ─── */
  .klypup-error {
    background: var(--rose-dim); border: 1px solid rgba(244,63,94,0.25);
    border-radius: 8px; padding: 10px 14px; font-size: 13px; color: var(--rose); margin-bottom: 8px;
  }

  /* ─── AI Section ─── */
  .klypup-ai-section {
    position: relative; overflow: hidden;
    background: var(--bg-1); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 40px;
  }
  .klypup-ai-glow {
    position: absolute; width: 600px; height: 400px; border-radius: 50%;
    background: radial-gradient(ellipse, rgba(168,85,247,0.06) 0%, transparent 70%);
    top: -100px; right: -100px; pointer-events: none;
  }

  .klypup-ai-header { text-align: center; margin-bottom: 32px; position: relative; z-index: 1; }
  .klypup-ai-badge--large { font-size: 12px; margin-bottom: 16px; justify-content: center; }
  .klypup-ai-title { font-size: clamp(24px, 4vw, 38px); font-weight: 800; color: #fff; margin-bottom: 12px; }
  .klypup-ai-desc { font-size: 15px; color: var(--text-sub); max-width: 600px; margin: 0 auto; line-height: 1.65; }

  .klypup-tech-pills { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 36px; }
  .klypup-tech-pill {
    padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;
    background: rgba(255,255,255,0.04); border: 1px solid var(--border);
    color: var(--text-sub); font-family: var(--mono);
    transition: all 0.15s;
  }
  .klypup-tech-pill:hover { border-color: var(--cyan); color: var(--cyan); background: var(--cyan-dim); }

  .klypup-ai-steps { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; margin-bottom: 36px; position: relative; z-index: 1; }

  .klypup-ai-step {
    background: var(--bg-2); border: 1px solid var(--border);
    border-radius: 12px; padding: 22px; position: relative;
    display: flex; flex-direction: column; gap: 12px;
    transition: all 0.3s;
    animation: klypup-fadein 0.5s ease both;
  }
  .klypup-ai-step:hover { border-color: var(--border-hover); transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
  .klypup-ai-step--cyan:hover { border-color: rgba(6,182,212,0.3); box-shadow: 0 8px 32px rgba(6,182,212,0.08); }
  .klypup-ai-step--violet:hover { border-color: rgba(168,85,247,0.3); box-shadow: 0 8px 32px rgba(168,85,247,0.08); }
  .klypup-ai-step--green:hover { border-color: rgba(34,197,94,0.3); box-shadow: 0 8px 32px rgba(34,197,94,0.08); }
  .klypup-ai-step--amber:hover { border-color: rgba(245,158,11,0.3); box-shadow: 0 8px 32px rgba(245,158,11,0.08); }

  @keyframes klypup-fadein { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

  .klypup-ai-step-num {
    position: absolute; top: -10px; left: 18px;
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; padding: 2px 8px;
    font-size: 11px; font-weight: 700; color: var(--text-muted); font-family: var(--mono);
  }
  .klypup-ai-step-icon {
    width: 40px; height: 40px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
  }
  .klypup-ai-step-icon--cyan { background: var(--cyan-dim); color: var(--cyan); box-shadow: 0 0 20px rgba(6,182,212,0.2); }
  .klypup-ai-step-icon--violet { background: var(--violet-dim); color: var(--violet); box-shadow: 0 0 20px rgba(168,85,247,0.2); }
  .klypup-ai-step-icon--green { background: var(--green-dim); color: var(--green); box-shadow: 0 0 20px rgba(34,197,94,0.2); }
  .klypup-ai-step-icon--amber { background: var(--amber-dim); color: var(--amber); box-shadow: 0 0 20px rgba(245,158,11,0.2); }

  .klypup-ai-step-title { font-size: 15px; font-weight: 700; color: #fff; }

  .klypup-ai-step-list { list-style: none; display: flex; flex-direction: column; gap: 6px; }
  .klypup-ai-step-item { display: flex; align-items: flex-start; gap: 8px; font-size: 12.5px; color: var(--text-sub); line-height: 1.45; }
  .klypup-ai-step-dot {
    width: 5px; height: 5px; border-radius: 50%; margin-top: 5px; flex-shrink: 0;
  }
  .klypup-ai-step-dot--cyan { background: var(--cyan); }
  .klypup-ai-step-dot--violet { background: var(--violet); }
  .klypup-ai-step-dot--green { background: var(--green); }
  .klypup-ai-step-dot--amber { background: var(--amber); }

  /* ─── Model Cards ─── */
  .klypup-model-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; position: relative; z-index: 1; }

  .klypup-model-card {
    background: var(--bg-2); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px;
    display: flex; flex-direction: column; gap: 10px;
    transition: all 0.2s;
  }
  .klypup-model-card:hover { transform: translateY(-2px); }
  .klypup-model-card--cyan:hover { border-color: rgba(6,182,212,0.3); box-shadow: 0 0 24px rgba(6,182,212,0.1); }
  .klypup-model-card--violet:hover { border-color: rgba(168,85,247,0.3); box-shadow: 0 0 24px rgba(168,85,247,0.1); }
  .klypup-model-card--green:hover { border-color: rgba(34,197,94,0.3); box-shadow: 0 0 24px rgba(34,197,94,0.1); }
  .klypup-model-card--amber:hover { border-color: rgba(245,158,11,0.3); box-shadow: 0 0 24px rgba(245,158,11,0.1); }

  .klypup-model-icon { width: 36px; height: 36px; border-radius: 9px; display: flex; align-items: center; justify-content: center; }
  .klypup-model-icon--cyan { background: var(--cyan-dim); color: var(--cyan); }
  .klypup-model-icon--violet { background: var(--violet-dim); color: var(--violet); }
  .klypup-model-icon--green { background: var(--green-dim); color: var(--green); }
  .klypup-model-icon--amber { background: var(--amber-dim); color: var(--amber); }

  .klypup-model-name { font-size: 15px; font-weight: 700; color: #fff; }
  .klypup-model-role { font-size: 12px; color: var(--text-muted); line-height: 1.4; }

  .klypup-model-bar-wrap { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
  .klypup-model-bar-track { flex: 1; height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; }
  .klypup-model-bar { height: 100%; border-radius: 2px; transition: width 1s ease; }
  .klypup-model-bar--cyan { background: var(--cyan); box-shadow: 0 0 8px rgba(6,182,212,0.5); }
  .klypup-model-bar--violet { background: var(--violet); box-shadow: 0 0 8px rgba(168,85,247,0.5); }
  .klypup-model-bar--green { background: var(--green); box-shadow: 0 0 8px rgba(34,197,94,0.5); }
  .klypup-model-bar--amber { background: var(--amber); box-shadow: 0 0 8px rgba(245,158,11,0.5); }
  .klypup-model-acc { font-size: 12px; font-weight: 700; font-family: var(--mono); flex-shrink: 0; }
  .klypup-model-acc--cyan { color: var(--cyan); }
  .klypup-model-acc--violet { color: var(--violet); }
  .klypup-model-acc--green { color: var(--green); }
  .klypup-model-acc--amber { color: var(--amber); }

  /* ─── Footer ─── */
  .klypup-footer {
    padding: 20px 0; border-top: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
    font-size: 12px; color: var(--text-muted);
  }

  /* ─── Scrollbar ─── */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.15); }

  /* ─── Responsive ─── */
  @media (max-width: 768px) {
    .klypup-content { padding: 16px; gap: 16px; }
    .klypup-hero { flex-direction: column; padding: 20px; }
    .klypup-hero-right { width: 100%; }
    .klypup-market-status { min-width: unset; }
    .klypup-ai-section { padding: 24px 16px; }
    .klypup-sidebar--open { width: var(--sidebar-w-closed); }
    .klypup-main { margin-left: var(--sidebar-w-closed) !important; }
    .klypup-logo-text, .klypup-nav-item span { display: none; }
  }
`;