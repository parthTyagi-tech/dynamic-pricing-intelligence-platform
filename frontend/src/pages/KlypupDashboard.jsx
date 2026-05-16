import { useState, useEffect } from "react";
import {
  LayoutDashboard, BarChart3, TrendingUp, Globe, Target,
  FileText, Settings, Search, ChevronRight, ChevronLeft,
  Zap, Activity, DollarSign, Shield, ArrowUpRight, ArrowDownRight,
  Brain, Database, RefreshCw, Layers, Sparkles,
  Flame, ShoppingCart, Package, SlidersHorizontal, AlertTriangle
} from "lucide-react";
import {
  LineChart as ReLineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis
} from "recharts";

/* ── animated counter ── */
function useCounter(target, duration = 1800) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    let current = 0;
    const step = target / (duration / 16);
    const timer = setInterval(() => {
      current += step;
      if (current >= target) { setVal(target); clearInterval(timer); }
      else setVal(Math.floor(current));
    }, 16);
    return () => clearInterval(timer);
  }, [target, duration]);
  return val;
}

/* ── sparkline ── */
const spark = () => Array.from({ length: 8 }, () => 30 + Math.random() * 60);

function MiniSpark({ data, color = "#818cf8" }) {
  const max = Math.max(...data), min = Math.min(...data);
  const w = 80, h = 28;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / (max - min || 1)) * h;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ── chart data ── */
const revenueData = [
  { t: "Jan", rev: 42000, pred: 44000 }, { t: "Feb", rev: 51000, pred: 50000 },
  { t: "Mar", rev: 47000, pred: 49000 }, { t: "Apr", rev: 63000, pred: 61000 },
  { t: "May", rev: 71000, pred: 72000 }, { t: "Jun", rev: 68000, pred: 70000 },
  { t: "Jul", rev: 82000, pred: 80000 }, { t: "Aug", rev: 91000, pred: 89000 },
  { t: "Sep", rev: 87000, pred: 90000 }, { t: "Oct", rev: 104000, pred: 102000 },
  { t: "Nov", rev: 112000, pred: 110000 }, { t: "Dec", rev: 128000, pred: 125000 },
];
const pricingData = [
  { t: "00:00", ai: 249, comp: 262, market: 255 },
  { t: "04:00", ai: 241, comp: 258, market: 250 },
  { t: "08:00", ai: 268, comp: 255, market: 260 },
  { t: "12:00", ai: 285, comp: 270, market: 278 },
  { t: "16:00", ai: 279, comp: 268, market: 274 },
  { t: "20:00", ai: 295, comp: 280, market: 288 },
  { t: "23:59", ai: 310, comp: 290, market: 302 },
];
const demandData = [
  { cat: "Electronics", score: 88 }, { cat: "Fashion", score: 72 },
  { cat: "Home & Garden", score: 65 }, { cat: "Sports", score: 81 },
  { cat: "Books", score: 44 }, { cat: "Beauty", score: 77 },
];
const radarData = [
  { subject: "Accuracy", A: 92 }, { subject: "Speed", A: 87 },
  { subject: "Coverage", A: 79 }, { subject: "Reliability", A: 95 },
  { subject: "Adaptability", A: 83 }, { subject: "Insights", A: 91 },
];

/* ── nav items ── */
const navItems = [
  { icon: LayoutDashboard, label: "Dashboard" },
  { icon: BarChart3, label: "Analytics" },
  { icon: Brain, label: "AI Engine" },
  { icon: SlidersHorizontal, label: "Dynamic Pricing" },
  { icon: Globe, label: "Market Insights" },
  { icon: Target, label: "Competitor Tracking" },
  { icon: FileText, label: "Reports" },
  { icon: Settings, label: "Settings" },
];

const workflowSteps = [
  { icon: Database, label: "Market Data", desc: "Real-time ingestion from 500+ sources", color: "#818cf8" },
  { icon: Brain, label: "AI Processing", desc: "ML models analyze patterns & signals", color: "#a78bfa" },
  { icon: Activity, label: "Prediction Engine", desc: "Demand forecasting & price elasticity", color: "#c084fc" },
  { icon: Zap, label: "Pricing Output", desc: "Optimal price delivered in <50ms", color: "#e879f9" },
];

const aiCards = [
  { icon: Brain, title: "Machine Learning", desc: "Gradient Boosting + Neural Networks trained on 10M+ pricing events", tag: "Core AI", color: "#818cf8" },
  { icon: TrendingUp, title: "Predictive Analytics", desc: "Time-series forecasting with 94.2% demand accuracy", tag: "Forecasting", color: "#34d399" },
  { icon: Globe, title: "Market Intelligence", desc: "Real-time crawl of 2,400+ competitor storefronts", tag: "Intelligence", color: "#60a5fa" },
  { icon: Activity, title: "Real-time Engine", desc: "Sub-50ms pricing decisions at 1M+ RPM capacity", tag: "Performance", color: "#f472b6" },
  { icon: RefreshCw, title: "Demand Forecasting", desc: "LSTM + seasonal decomposition for 30-day outlook", tag: "Forecasting", color: "#fb923c" },
  { icon: Layers, title: "Competitive AI", desc: "Automated gap analysis and undercutting alerts", tag: "Competition", color: "#a3e635" },
];

const insightCards = [
  { icon: Flame, label: "High Demand", title: "4K Monitors", change: "+34%", up: true, detail: "Surge in remote work adoption" },
  { icon: AlertTriangle, label: "Low Inventory", title: "RTX 4090 GPU", change: "-67%", up: false, detail: "Stock critically low — 12 units" },
  { icon: TrendingUp, label: "Trending", title: "Smart Home Devices", change: "+21%", up: true, detail: "Category up 3 weeks straight" },
  { icon: Target, label: "Competitor Move", title: "Apple AirPods", change: "-8%", up: false, detail: "Amazon dropped price 2h ago" },
  { icon: Sparkles, label: "Opportunity", title: "Gaming Chairs", change: "+15%", up: true, detail: "Underpriced vs. demand signal" },
  { icon: Package, label: "Bundle Alert", title: "Laptop + Mouse", change: "+28%", up: true, detail: "Bundle conversion rate spiking" },
];

const howItWorksSteps = [
  { step: "01", title: "Data Ingestion", icon: Database, desc: "We continuously pull pricing signals from competitor sites, market feeds, historical sales, seasonal patterns, and consumer behavior datasets — processing over 2 million data points per hour." },
  { step: "02", title: "Pattern Recognition", icon: Brain, desc: "Our ML pipeline identifies non-obvious pricing patterns: demand elasticity curves, time-of-day effects, competitor response latency, and category-level price sensitivity." },
  { step: "03", title: "Price Prediction", icon: TrendingUp, desc: "A stacked ensemble of XGBoost, LightGBM, and LSTM neural networks outputs confidence-weighted price recommendations per product SKU, updated every 15 minutes." },
  { step: "04", title: "Recommendation Output", icon: Zap, desc: "Optimal prices are pushed via API to your storefront or ERP system. Every recommendation includes rationale, confidence score, and projected revenue impact." },
];

/* ── Metric Card ── */
function MetricCard({ icon: Icon, label, value, unit = "", change, up, color, sparkData }) {
  const num = useCounter(typeof value === "number" ? value : 0);
  const display = typeof value === "number" ? `${num}${unit}` : value;
  return (
    <div
      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 16, padding: 20, transition: "all 0.3s", cursor: "default", position: "relative", overflow: "hidden" }}
      onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.06)"; e.currentTarget.style.borderColor = color + "55"; e.currentTarget.style.boxShadow = `0 0 24px ${color}22`; }}
      onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.03)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)"; e.currentTarget.style.boxShadow = "none"; }}
    >
      <div style={{ position: "absolute", top: -20, right: -20, width: 80, height: 80, borderRadius: "50%", background: color + "15", filter: "blur(20px)" }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div style={{ background: color + "22", borderRadius: 10, padding: 8, display: "flex" }}>
          <Icon size={16} style={{ color }} />
        </div>
        {sparkData && <MiniSpark data={sparkData} color={color} />}
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color: "#fff", marginBottom: 4, letterSpacing: -0.5 }}>{display}</div>
      <div style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", marginBottom: 8 }}>{label}</div>
      {change && (
        <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11 }}>
          {up ? <ArrowUpRight size={12} style={{ color: "#34d399" }} /> : <ArrowDownRight size={12} style={{ color: "#f87171" }} />}
          <span style={{ color: up ? "#34d399" : "#f87171" }}>{change}</span>
          <span style={{ color: "rgba(255,255,255,0.35)" }}>vs last month</span>
        </div>
      )}
    </div>
  );
}

/* ── Sidebar ── */
function Sidebar({ collapsed, setCollapsed, activePage, setActivePage }) {
  return (
    <aside style={{
      width: collapsed ? 68 : 220,
      minHeight: "100vh",
      background: "rgba(8,8,20,0.95)",
      borderRight: "1px solid rgba(255,255,255,0.06)",
      display: "flex", flexDirection: "column",
      padding: "20px 0",
      transition: "width 0.3s cubic-bezier(0.4,0,0.2,1)",
      flexShrink: 0, position: "relative", zIndex: 10,
    }}>
      {/* Logo */}
      <div style={{ padding: collapsed ? "0 14px 20px" : "0 20px 28px", display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0, background: "linear-gradient(135deg,#818cf8,#c084fc)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 16px #818cf855" }}>
          <Zap size={18} color="#fff" />
        </div>
        {!collapsed && (
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#fff", lineHeight: 1.1 }}>Klypup</div>
            <div style={{ fontSize: 10, color: "#818cf8", fontWeight: 500 }}>AI Pricing</div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "0 8px", display: "flex", flexDirection: "column", gap: 2 }}>
        {navItems.map(({ icon: Icon, label }) => {
          const active = activePage === label;
          return (
            <button key={label} onClick={() => setActivePage(label)} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: collapsed ? "10px 14px" : "10px 12px",
              borderRadius: 10, border: "none", cursor: "pointer",
              background: active ? "rgba(129,140,248,0.15)" : "transparent",
              color: active ? "#a5b4fc" : "rgba(255,255,255,0.45)",
              fontSize: 13, fontWeight: active ? 600 : 400,
              transition: "all 0.2s", textAlign: "left", width: "100%",
              borderLeft: active ? "2px solid #818cf8" : "2px solid transparent",
            }}
              onMouseEnter={e => { if (!active) { e.currentTarget.style.color = "rgba(255,255,255,0.8)"; e.currentTarget.style.background = "rgba(255,255,255,0.05)"; } }}
              onMouseLeave={e => { if (!active) { e.currentTarget.style.color = "rgba(255,255,255,0.45)"; e.currentTarget.style.background = "transparent"; } }}
            >
              <Icon size={16} />
              {!collapsed && <span>{label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Collapse button only — no user profile */}
      <div style={{ padding: "0 8px" }}>
        <button onClick={() => setCollapsed(!collapsed)} style={{
          display: "flex", alignItems: "center", justifyContent: collapsed ? "center" : "flex-end",
          padding: "8px 12px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)",
          background: "transparent", color: "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 12,
          transition: "all 0.2s", gap: 6, width: "100%",
        }}
          onMouseEnter={e => (e.currentTarget.style.color = "#fff")}
          onMouseLeave={e => (e.currentTarget.style.color = "rgba(255,255,255,0.4)")}
        >
          {collapsed ? <ChevronRight size={14} /> : <><ChevronLeft size={14} /><span>Collapse</span></>}
        </button>
      </div>
    </aside>
  );
}

/* ── Navbar — search bar only ── */
function Navbar() {
  return (
    <header style={{
      height: 60, background: "rgba(8,8,20,0.8)",
      backdropFilter: "blur(20px)",
      borderBottom: "1px solid rgba(255,255,255,0.06)",
      display: "flex", alignItems: "center", gap: 16,
      padding: "0 24px", position: "sticky", top: 0, zIndex: 20,
    }}>
      {/* Gradient top line */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 1, background: "linear-gradient(90deg,transparent,#818cf8,#c084fc,transparent)" }} />
      {/* Search only */}
      <div style={{ maxWidth: 340, width: "100%", position: "relative" }}>
        <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "rgba(255,255,255,0.3)" }} />
        <input style={{
          width: "100%", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 10, padding: "7px 12px 7px 34px", color: "#fff",
          fontSize: 13, outline: "none", fontFamily: "inherit",
        }} placeholder="Search products, competitors..." />
      </div>
    </header>
  );
}

/* ── Section Heading ── */
function SectionHeading({ label, title, desc }) {
  return (
    <div style={{ marginBottom: 32 }}>
      <div style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "rgba(129,140,248,0.1)", border: "1px solid rgba(129,140,248,0.2)", borderRadius: 20, padding: "4px 12px", marginBottom: 12 }}>
        <Sparkles size={11} style={{ color: "#818cf8" }} />
        <span style={{ fontSize: 11, color: "#a5b4fc", fontWeight: 600, letterSpacing: 0.5 }}>{label}</span>
      </div>
      <h2 style={{ fontSize: 24, fontWeight: 700, color: "#fff", margin: "0 0 8px", letterSpacing: -0.5 }}>{title}</h2>
      {desc && <p style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", margin: 0 }}>{desc}</p>}
    </div>
  );
}

/* ── Custom Tooltip ── */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "rgba(10,10,28,0.95)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: "10px 14px" }}>
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.5)", marginBottom: 6 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize: 12, color: p.color, marginBottom: 2 }}>
          {p.name}: <strong>{typeof p.value === "number" && p.value > 999 ? `$${(p.value / 1000).toFixed(0)}k` : p.value}</strong>
        </div>
      ))}
    </div>
  );
}

/* ── Pricing Panel ── */
function PricingPanel() {
  const [aiPrice, setAiPrice] = useState(285);
  const [demand] = useState(72);
  return (
    <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 16, padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", marginBottom: 4 }}>Product</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#fff" }}>Sony WH-1000XM5</div>
        </div>
        <div style={{ background: "rgba(52,211,153,0.1)", border: "1px solid rgba(52,211,153,0.2)", borderRadius: 8, padding: "4px 10px", fontSize: 11, color: "#34d399" }}>✓ Optimized</div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 20 }}>
        {[
          { label: "Current Price", value: "$279", color: "rgba(255,255,255,0.7)" },
          { label: "AI Suggested", value: `$${aiPrice}`, color: "#818cf8" },
          { label: "Comp. Average", value: "$294", color: "#fb923c" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: "rgba(0,0,0,0.3)", borderRadius: 10, padding: 12, textAlign: "center" }}>
            <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginBottom: 6 }}>{label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: "rgba(255,255,255,0.5)" }}>AI Price: <span style={{ color: "#818cf8" }}>${aiPrice}</span></span>
          <span style={{ fontSize: 12, color: "rgba(255,255,255,0.5)" }}>Range $220–$380</span>
        </div>
        <input type="range" min={220} max={380} step={1} value={aiPrice} onChange={e => setAiPrice(Number(e.target.value))} style={{ width: "100%", accentColor: "#818cf8" }} />
      </div>
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: "rgba(255,255,255,0.5)" }}>Demand Level: <span style={{ color: "#34d399" }}>{demand}%</span></span>
          <span style={{ fontSize: 11, color: demand > 70 ? "#34d399" : "#fb923c" }}>{demand > 70 ? "High" : "Medium"} Demand</span>
        </div>
        <div style={{ height: 6, background: "rgba(255,255,255,0.08)", borderRadius: 3, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${demand}%`, background: "#34d399", borderRadius: 3 }} />
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 20 }}>
        {[
          { label: "AI Confidence", value: "94.2%", icon: Brain, color: "#818cf8" },
          { label: "Market Risk", value: "Low", icon: Shield, color: "#34d399" },
          { label: "Potential Uplift", value: "+$6.2K", icon: DollarSign, color: "#f472b6" },
          { label: "Conversion Δ", value: "+3.1%", icon: TrendingUp, color: "#60a5fa" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} style={{ background: "rgba(0,0,0,0.25)", borderRadius: 10, padding: "10px 12px", display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ background: color + "22", borderRadius: 7, padding: 6 }}><Icon size={13} style={{ color }} /></div>
            <div>
              <div style={{ fontSize: 10, color: "rgba(255,255,255,0.4)" }}>{label}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>{value}</div>
            </div>
          </div>
        ))}
      </div>
      <button style={{ width: "100%", background: "linear-gradient(135deg,#6366f1,#a855f7)", border: "none", borderRadius: 10, padding: 11, color: "#fff", fontWeight: 600, fontSize: 13, cursor: "pointer", boxShadow: "0 0 20px #818cf840" }}
        onMouseEnter={e => e.currentTarget.style.boxShadow = "0 0 30px #818cf870"}
        onMouseLeave={e => e.currentTarget.style.boxShadow = "0 0 20px #818cf840"}
      >Apply AI Price Recommendation</button>
    </div>
  );
}

/* ── Main App ── */
export default function KlypupDashboard() {
  const [collapsed, setCollapsed] = useState(false);
  const [activePage, setActivePage] = useState("Dashboard");

  const metrics = [
    { icon: DollarSign, label: "Total Revenue", value: 128000, unit: "", change: "+23.4%", up: true, color: "#818cf8", sparkData: spark() },
    { icon: Brain, label: "Pricing Accuracy", value: 94, unit: "%", change: "+2.1%", up: true, color: "#34d399", sparkData: spark() },
    { icon: Activity, label: "Market Volatility", value: 38, unit: "%", change: "-4.7%", up: false, color: "#fb923c", sparkData: spark() },
    { icon: Zap, label: "AI Confidence", value: 92, unit: "%", change: "+1.8%", up: true, color: "#a855f7", sparkData: spark() },
    { icon: Target, label: "Competitor Changes", value: 47, unit: "", change: "+12", up: false, color: "#f472b6", sparkData: spark() },
    { icon: ShoppingCart, label: "Conversion Rate", value: 7, unit: "%", change: "+0.9%", up: true, color: "#60a5fa", sparkData: spark() },
  ];

  return (
    <div style={{ minHeight: "100vh", background: "#060612", display: "flex", fontFamily: "'Inter', system-ui, sans-serif", color: "#fff", position: "relative", overflow: "hidden" }}>
      {/* bg orbs */}
      <div style={{ position: "fixed", top: -200, left: -200, width: 600, height: 600, borderRadius: "50%", background: "radial-gradient(circle,rgba(99,102,241,0.12) 0%,transparent 70%)", pointerEvents: "none", zIndex: 0 }} />
      <div style={{ position: "fixed", bottom: -200, right: -100, width: 500, height: 500, borderRadius: "50%", background: "radial-gradient(circle,rgba(168,85,247,0.10) 0%,transparent 70%)", pointerEvents: "none", zIndex: 0 }} />
      <div style={{ position: "fixed", top: "40%", right: "10%", width: 300, height: 300, borderRadius: "50%", background: "radial-gradient(circle,rgba(244,114,182,0.07) 0%,transparent 70%)", pointerEvents: "none", zIndex: 0 }} />

      {/* Sidebar */}
      <div style={{ position: "relative", zIndex: 5, display: "flex", flexShrink: 0 }}>
        <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} activePage={activePage} setActivePage={setActivePage} />
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, overflowX: "hidden" }}>
        <Navbar />

        <main style={{ flex: 1, padding: "28px 28px 60px", display: "flex", flexDirection: "column", gap: 48 }}>

          {/* ── Hero ── */}
          <section>
            <div style={{ marginBottom: 28 }}>
              <div style={{ fontSize: 13, color: "rgba(255,255,255,0.45)", marginBottom: 6 }}>
                Saturday, 16 May 2026 · Live market session active
              </div>
              <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0, letterSpacing: -0.8, color: "#fff" }}>
                Welcome back
              </h1>
              <p style={{ fontSize: 13, color: "rgba(255,255,255,0.45)", margin: "6px 0 0" }}>
                AI engine is running · 312 products optimized · Revenue up 23.4% this month
              </p>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 14 }}>
              {metrics.map(m => <MetricCard key={m.label} {...m} />)}
            </div>
          </section>

          {/* ── AI Engine ── */}
          <section>
            <SectionHeading label="AI ARCHITECTURE" title="What Powers Klypup?" desc="A multi-model AI system trained on billions of pricing signals, running 24/7 to maximize your revenue." />
            <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 32, flexWrap: "wrap" }}>
              {workflowSteps.map((step, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", flex: 1, minWidth: 140 }}>
                  <div style={{ flex: 1, background: "rgba(255,255,255,0.03)", border: `1px solid ${step.color}33`, borderRadius: 14, padding: "16px 14px", textAlign: "center", position: "relative", overflow: "hidden", transition: "all 0.3s" }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = step.color + "88"; e.currentTarget.style.boxShadow = `0 0 20px ${step.color}22`; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = step.color + "33"; e.currentTarget.style.boxShadow = "none"; }}
                  >
                    <div style={{ background: step.color + "22", borderRadius: 10, width: 40, height: 40, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 10px" }}>
                      <step.icon size={18} style={{ color: step.color }} />
                    </div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "#fff", marginBottom: 4 }}>{step.label}</div>
                    <div style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", lineHeight: 1.4 }}>{step.desc}</div>
                  </div>
                  {i < workflowSteps.length - 1 && <div style={{ padding: "0 6px", color: "#818cf8", flexShrink: 0 }}><ChevronRight size={18} /></div>}
                </div>
              ))}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 14 }}>
              {aiCards.map(card => (
                <div key={card.title} style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 14, padding: "18px 20px", transition: "all 0.3s", cursor: "default" }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = card.color + "44"; e.currentTarget.style.background = "rgba(255,255,255,0.05)"; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)"; e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                    <div style={{ background: card.color + "22", borderRadius: 9, padding: 8 }}><card.icon size={16} style={{ color: card.color }} /></div>
                    <span style={{ fontSize: 10, background: card.color + "18", color: card.color, padding: "3px 8px", borderRadius: 6, fontWeight: 600 }}>{card.tag}</span>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#fff", marginBottom: 6 }}>{card.title}</div>
                  <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", lineHeight: 1.5 }}>{card.desc}</div>
                </div>
              ))}
            </div>
          </section>

          {/* ── Live Analytics ── */}
          <section>
            <SectionHeading label="LIVE ANALYTICS" title="Market & Revenue Intelligence" desc="Real-time charts updated every 60 seconds from live market feeds." />
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, marginBottom: 16 }}>
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 16, padding: 24 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "#fff" }}>Revenue vs AI Prediction</div>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>12-month overview · USD</div>
                  </div>
                  <div style={{ display: "flex", gap: 12, fontSize: 11, color: "rgba(255,255,255,0.5)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 5 }}><div style={{ width: 8, height: 2, background: "#818cf8", borderRadius: 1 }} />Actual</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 5 }}><div style={{ width: 8, height: 2, background: "#c084fc", borderRadius: 1, opacity: 0.6 }} />Predicted</div>
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={revenueData}>
                    <defs>
                      <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#818cf8" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#818cf8" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="predGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#c084fc" stopOpacity={0.15} />
                        <stop offset="95%" stopColor="#c084fc" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="t" tick={{ fontSize: 10, fill: "rgba(255,255,255,0.35)" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "rgba(255,255,255,0.35)" }} axisLine={false} tickLine={false} tickFormatter={v => `$${v / 1000}k`} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="rev" name="Actual" stroke="#818cf8" strokeWidth={2} fill="url(#revGrad)" dot={false} />
                    <Area type="monotone" dataKey="pred" name="Predicted" stroke="#c084fc" strokeWidth={1.5} fill="url(#predGrad)" strokeDasharray="4 3" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 16, padding: 24 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#fff", marginBottom: 4 }}>AI Model Performance</div>
                <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginBottom: 16 }}>6-axis accuracy radar</div>
                <ResponsiveContainer width="100%" height={200}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="rgba(255,255,255,0.07)" />
                    <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10, fill: "rgba(255,255,255,0.45)" }} />
                    <Radar name="AI" dataKey="A" stroke="#818cf8" fill="#818cf8" fillOpacity={0.15} strokeWidth={2} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 16, padding: 24 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#fff", marginBottom: 4 }}>Live Pricing Trends</div>
                <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginBottom: 16 }}>AI vs Competitor vs Market</div>
                <ResponsiveContainer width="100%" height={180}>
                  <ReLineChart data={pricingData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="t" tick={{ fontSize: 10, fill: "rgba(255,255,255,0.35)" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "rgba(255,255,255,0.35)" }} axisLine={false} tickLine={false} domain={[220, 320]} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line type="monotone" dataKey="ai" name="AI Price" stroke="#818cf8" strokeWidth={2.5} dot={false} />
                    <Line type="monotone" dataKey="comp" name="Competitor" stroke="#fb923c" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
                    <Line type="monotone" dataKey="market" name="Market Avg" stroke="#34d399" strokeWidth={1.5} strokeDasharray="2 2" dot={false} />
                  </ReLineChart>
                </ResponsiveContainer>
              </div>
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 16, padding: 24 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#fff", marginBottom: 4 }}>Demand by Category</div>
                <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginBottom: 16 }}>Score out of 100</div>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={demandData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: "rgba(255,255,255,0.35)" }} axisLine={false} tickLine={false} />
                    <YAxis dataKey="cat" type="category" tick={{ fontSize: 10, fill: "rgba(255,255,255,0.45)" }} axisLine={false} tickLine={false} width={80} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="score" name="Demand" fill="#818cf8" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>

          {/* ── Dynamic Pricing ── */}
          <section>
            <SectionHeading label="PRICING INTELLIGENCE" title="Dynamic Pricing Control Panel" desc="AI-powered recommendations with real-time market signals and confidence scoring." />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <PricingPanel />
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {[
                  { name: "MacBook Pro M4", current: "$2,499", suggested: "$2,399", conf: 91, action: "decrease", reason: "Competitor dropped $150" },
                  { name: "Samsung 85\" TV", current: "$1,299", suggested: "$1,349", conf: 87, action: "increase", reason: "Demand surge +28%" },
                  { name: "Dyson V15", current: "$649", suggested: "$649", conf: 96, action: "hold", reason: "Optimal price point" },
                  { name: "iPad Air M2", current: "$749", suggested: "$729", conf: 82, action: "decrease", reason: "Market softening" },
                  { name: "Bose QC45", current: "$279", suggested: "$299", conf: 89, action: "increase", reason: "Low inventory signal" },
                ].map(({ name, current, suggested, conf, action, reason }) => (
                  <div key={name} style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 12, padding: "14px 16px", display: "flex", alignItems: "center", gap: 12, transition: "all 0.2s" }}
                    onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.05)"}
                    onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,0.03)"}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", marginBottom: 2 }}>{name}</div>
                      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>{reason}</div>
                    </div>
                    <div style={{ textAlign: "center", minWidth: 70 }}>
                      <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)" }}>Current</div>
                      <div style={{ fontSize: 13, color: "rgba(255,255,255,0.7)" }}>{current}</div>
                    </div>
                    <div style={{ color: "rgba(255,255,255,0.2)" }}>→</div>
                    <div style={{ textAlign: "center", minWidth: 70 }}>
                      <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)" }}>AI Price</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: action === "increase" ? "#34d399" : action === "decrease" ? "#f87171" : "#818cf8" }}>{suggested}</div>
                    </div>
                    <div style={{ textAlign: "center", minWidth: 50 }}>
                      <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)" }}>Conf.</div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "#a5b4fc" }}>{conf}%</div>
                    </div>
                    <button style={{ background: "rgba(129,140,248,0.15)", border: "1px solid rgba(129,140,248,0.25)", borderRadius: 7, padding: "5px 10px", fontSize: 11, color: "#a5b4fc", cursor: "pointer", whiteSpace: "nowrap" }}
                      onMouseEnter={e => e.currentTarget.style.background = "rgba(129,140,248,0.25)"}
                      onMouseLeave={e => e.currentTarget.style.background = "rgba(129,140,248,0.15)"}
                    >Apply</button>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* ── Market Insights ── */}
          <section>
            <SectionHeading label="MARKET INSIGHTS" title="Live Market Intelligence" desc="AI-curated signals from your product catalog, competitors, and market conditions." />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 14 }}>
              {insightCards.map(card => (
                <div key={card.title} style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 14, padding: 18, transition: "all 0.3s", cursor: "default" }}
                  onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.borderColor = (card.up ? "#34d399" : "#f87171") + "44"; }}
                  onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.03)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)"; }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <span style={{ fontSize: 10, background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.5)", padding: "3px 8px", borderRadius: 5 }}>{card.label}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: card.up ? "#34d399" : "#f87171", display: "flex", alignItems: "center", gap: 2 }}>
                      {card.up ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{card.change}
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                    <div style={{ background: (card.up ? "#34d399" : "#f87171") + "18", borderRadius: 8, padding: 8 }}>
                      <card.icon size={15} style={{ color: card.up ? "#34d399" : "#f87171" }} />
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "#fff" }}>{card.title}</div>
                  </div>
                  <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", lineHeight: 1.4 }}>{card.detail}</div>
                </div>
              ))}
            </div>
          </section>

          {/* ── How AI Works ── */}
          <section>
            <SectionHeading label="AI TRANSPARENCY" title="How Our AI Works" desc="A step-by-step look inside the Klypup pricing intelligence pipeline." />
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {howItWorksSteps.map((s, i) => (
                <div key={i} style={{ display: "flex", gap: 20, padding: "20px 24px", background: "rgba(255,255,255,0.02)", borderRadius: 14, border: "1px solid rgba(255,255,255,0.06)", transition: "all 0.3s", cursor: "default" }}
                  onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.borderColor = "#818cf844"; }}
                  onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.02)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)"; }}
                >
                  <div style={{ fontSize: 36, fontWeight: 800, color: "rgba(129,140,248,0.2)", lineHeight: 1, flexShrink: 0 }}>{s.step}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                      <div style={{ background: "rgba(129,140,248,0.15)", borderRadius: 8, padding: 7 }}><s.icon size={15} style={{ color: "#818cf8" }} /></div>
                      <div style={{ fontSize: 15, fontWeight: 600, color: "#fff" }}>{s.title}</div>
                    </div>
                    <p style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", margin: 0, lineHeight: 1.6 }}>{s.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Footer */}
          <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.25)" }}>© 2026 Klypup AI Pricing Intelligence · All rights reserved</div>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#34d399" }} />
              <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>All systems operational</span>
            </div>
          </div>
        </main>
      </div>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }
        *{box-sizing:border-box}
        input[type=range]{height:4px;cursor:pointer}
        ::-webkit-scrollbar{width:4px;height:4px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:2px}
      `}</style>
    </div>
  );
}
