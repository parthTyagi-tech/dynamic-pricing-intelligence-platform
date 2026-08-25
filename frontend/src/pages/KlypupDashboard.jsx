import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  BarChart3,
  Bell,
  BrainCircuit,
  Check,
  ChevronDown,
  ChevronRight,
  CircleDollarSign,
  CircleGauge,
  Clock3,
  Database,
  Download,
  Filter,
  Gauge,
  LineChart as LineChartIcon,
  Maximize2,
  MoreHorizontal,
  PackageCheck,
  Play,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingDown,
  X,
  Zap,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { motion, AnimatePresence } from "framer-motion";

import apiClient from "../services/api";
import { useAuth } from "../context/AuthContext";
import { createDashboardSnapshot, normalizeApiSnapshot } from "../lib/mockPricingData";
import {
  ApprovalAction,
  EmptyState,
  Eyebrow,
  GhostButton,
  IconButton,
  MetricCard,
  Panel,
  PrimaryButton,
  SectionHeader,
  SeverityIcon,
  StatusBadge,
  Toggle,
} from "../components/pricing/PricingPrimitives";

const currency = (value) => `$${Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const preciseCurrency = (value) => `$${Number(value || 0).toFixed(2)}`;
const pct = (value) => `${Number(value || 0).toFixed(1)}%`;

const chartTooltip = {
  contentStyle: {
    background: "#101827",
    border: "1px solid rgba(0,240,255,0.22)",
    borderRadius: 12,
    color: "#e5eef8",
    fontSize: 12,
  },
  labelStyle: { color: "#94a3b8", marginBottom: 4 },
};

function TickerStrip({ metrics }) {
  return (
    <div className="ticker-strip" aria-label="Live pricing ticker">
      <div className="ticker-label"><span className="live-pulse" /> Live signal feed</div>
      <div className="ticker-item"><span>Repriced SKUs</span><strong>{metrics.activeSkus.toLocaleString()}</strong><em className="ticker-up">+4.2%</em></div>
      <div className="ticker-item"><span>Revenue lift</span><strong>{pct(metrics.revenueLift)}</strong><em className="ticker-up">+1.8%</em></div>
      <div className="ticker-item"><span>Avg. margin gain</span><strong>{pct(metrics.marginGain)}</strong><em className="ticker-up">+0.6%</em></div>
      <div className="ticker-item"><span>Market shifts today</span><strong>{metrics.competitorChanges}</strong><em className="ticker-down">3 critical</em></div>
      <div className="ticker-sync"><RefreshCw size={12} /> synced 12s ago</div>
    </div>
  );
}

function DashboardHeader({ user, autopilot, setAutopilot, onOpenActivity }) {
  return (
    <header className="dashboard-header">
      <div>
        <div className="header-breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>Executive Dashboard</strong></div>
        <div className="flex items-center gap-3 mt-2">
          <h1 className="dashboard-title">Executive Command Center</h1>
          <StatusBadge tone="live">Operational</StatusBadge>
        </div>
        <p className="dashboard-subtitle">Pricing intelligence across your catalog, competitors, and demand signals.</p>
      </div>
      <div className="header-actions">
        <div className="header-date"><Clock3 size={14} /><span>Mon, Aug 25, 2026</span></div>
        <div className="autopilot-control">
          <span className="autopilot-dot" />
          <span>Auto-Pilot</span>
          <Toggle checked={autopilot} onChange={setAutopilot} label="Toggle auto-pilot mode" />
        </div>
        <IconButton label="Open activity center" onClick={onOpenActivity}><Bell size={16} /></IconButton>
        <div className="avatar" title={user?.name || "Pricing Analyst"}>{(user?.name || "PA").slice(0, 2).toUpperCase()}</div>
      </div>
    </header>
  );
}

function HeroPulse({ metrics }) {
  return (
    <Panel className="hero-pulse-card" glow>
      <div className="hero-pulse-grid" />
      <div className="relative z-10 flex items-start justify-between gap-6">
        <div>
          <Eyebrow tone="violet">AI PRICING OPERATIONS</Eyebrow>
          <h2 className="hero-title">Your catalog is <span>outperforming</span> the market.</h2>
          <p className="hero-copy">The pricing engine has protected <strong>{pct(metrics.marginGain)}</strong> in average margin while creating a projected <strong>{currency(metrics.projectedRevenue)}</strong> revenue opportunity.</p>
          <div className="flex flex-wrap gap-3 mt-5">
            <PrimaryButton icon={Sparkles}>Review AI recommendations</PrimaryButton>
            <GhostButton icon={BarChart3}>Open analytics</GhostButton>
          </div>
        </div>
        <div className="hero-signal" aria-hidden="true">
          <div className="signal-orbit signal-orbit-one" />
          <div className="signal-orbit signal-orbit-two" />
          <div className="signal-core"><BrainCircuit size={25} /></div>
        </div>
      </div>
      <div className="hero-footer">
        <div><span>Decision engine</span><strong><span className="live-pulse" /> Processing 1.2k signals/min</strong></div>
        <div><span>Model confidence</span><strong className="font-mono">98.4%</strong></div>
        <div><span>Guardrail status</span><strong className="text-emerald-300"><ShieldCheck size={14} /> All systems clear</strong></div>
      </div>
    </Panel>
  );
}

function RecommendationQueue({ recommendations, approvedIds, actioningId, onApprove, onReject, onDetails }) {
  return (
    <Panel className="queue-panel">
      <div className="panel-heading">
        <div><Eyebrow>AI RECOMMENDATION QUEUE</Eyebrow><h2>Decisions waiting for you</h2></div>
        <div className="flex items-center gap-2"><StatusBadge tone="violet">{recommendations.length} pending</StatusBadge><IconButton label="Queue options"><MoreHorizontal size={17} /></IconButton></div>
      </div>
      <div className="queue-table-wrap">
        <table className="data-table queue-table">
          <thead><tr><th>Product / SKU</th><th>Recommendation</th><th>Confidence</th><th>Impact</th><th /></tr></thead>
          <tbody>
            {recommendations.length === 0 ? <tr><td colSpan="5"><EmptyState icon={Check} title="Queue cleared" description="There are no pending price changes requiring review." /></td></tr> : recommendations.map((item, index) => {
              const delta = item.suggestedPrice - item.currentPrice;
              const approved = approvedIds.includes(item.sku);
              return (
                <motion.tr key={item.sku} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }}>
                  <td><button type="button" className="product-cell text-left" onClick={() => onDetails(item)}><span className="product-avatar">{item.productName.slice(0, 2).toUpperCase()}</span><span><strong>{item.productName}</strong><small>{item.sku} · {item.category}</small></span></button></td>
                  <td><button type="button" className="recommendation-copy text-left" onClick={() => onDetails(item)}><span className={delta >= 0 ? "text-emerald-300" : "text-cyan-300"}>{delta >= 0 ? "Increase" : "Lower"} price by {Math.abs((delta / item.currentPrice) * 100).toFixed(1)}%</span><small>{item.rationale}</small></button></td>
                  <td><div className="confidence-cell"><div className="confidence-bar"><span style={{ width: `${item.confidence}%` }} /></div><strong>{item.confidence}%</strong></div></td>
                  <td><span className="impact-value">+{item.volumeLift}% volume</span><small className="block text-slate-500">+{item.marginDelta}% margin</small></td>
                  <td><div className="row-actions"><ApprovalAction approved={approved} loading={actioningId === item.sku} onClick={() => onApprove(item)} /><button type="button" className="reject-button" onClick={() => onReject(item)} disabled={approved}>Dismiss</button></div></td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="panel-footer"><span><Zap size={13} /> Decision engine auto-scores every recommendation</span><button type="button" className="footer-link" onClick={() => window.location.assign("/recommendations")}>View full queue <ChevronRight size={13} /></button></div>
    </Panel>
  );
}

function CompetitorMatrix({ competitors, selectedProduct, onProductChange, products }) {
  return (
    <Panel className="competitor-panel">
      <div className="panel-heading">
        <div><Eyebrow>MARKET INTELLIGENCE</Eyebrow><h2>Competitor price monitoring</h2><p>Live spread for the selected SKU across marketplace signals.</p></div>
        <div className="select-wrap"><select value={selectedProduct.sku} onChange={(event) => onProductChange(event.target.value)} aria-label="Select product"><option value={selectedProduct.sku}>{selectedProduct.sku}</option>{products.filter((item) => item.sku !== selectedProduct.sku).map((item) => <option value={item.sku} key={item.sku}>{item.sku}</option>)}</select><ChevronDown size={14} /></div>
      </div>
      <div className="competitor-content">
        <div className="spread-grid">
          {competitors.map((item) => {
            const isStore = item.name === "Your store";
            const alert = item.delta < -2;
            return <div key={item.name} className={`spread-card ${alert ? "spread-alert" : ""}`}><div className="flex items-center justify-between gap-2"><span className="marketplace-logo">{item.name.slice(0, 2)}</span><span className={`stock-dot ${item.inStock ? "in-stock" : "out-stock"}`} title={item.inStock ? "In stock" : "Out of stock"} /></div><span className="spread-name">{item.name}</span><strong className={isStore ? "text-white" : alert ? "text-rose-300" : "text-slate-200"}>{preciseCurrency(item.price)}</strong><small className={item.delta >= 0 ? "text-emerald-300" : "text-rose-300"}>{isStore ? "Baseline" : `${item.delta >= 0 ? "+" : ""}${preciseCurrency(item.delta)} vs you`}</small><span className="spread-seen">{item.lastSeen}</span></div>;
          })}
        </div>
        <div className="alert-callout"><div className="alert-icon"><TrendingDown size={17} /></div><div><strong>Target undercut alert</strong><p>Target is {preciseCurrency(Math.abs(competitors.find((item) => item.name === "Target")?.delta || 0))} above your price. Opportunity to hold position and capture margin.</p></div><ChevronRight size={15} /></div>
      </div>
    </Panel>
  );
}

function QuadrantMap({ recommendations }) {
  const points = recommendations.map((item, index) => ({ x: item.currentPrice + index * 5, y: item.volumeLift * 4 + item.marginDelta * 8, z: 1, name: item.sku }));
  return (
    <Panel className="quadrant-panel">
      <div className="panel-heading"><div><Eyebrow>PORTFOLIO POSITIONING</Eyebrow><h2>Price / velocity quadrant</h2></div><IconButton label="Expand quadrant"><Maximize2 size={15} /></IconButton></div>
      <div className="quadrant-chart">
        <div className="quadrant-label q1">Premium velocity</div><div className="quadrant-label q2">Growth zone</div><div className="quadrant-label q3">Review pricing</div><div className="quadrant-label q4">Low velocity</div>
        <ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ top: 16, right: 16, bottom: 8, left: -14 }}><CartesianGrid stroke="rgba(148,163,184,.12)" strokeDasharray="3 3" /><XAxis type="number" dataKey="x" name="price" stroke="#64748b" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} /><YAxis type="number" dataKey="y" name="velocity" stroke="#64748b" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip {...chartTooltip} cursor={{ strokeDasharray: "4 4" }} /><Scatter data={points} fill="#00f0ff" /></ScatterChart></ResponsiveContainer>
      </div>
      <div className="quadrant-legend"><span><i className="legend-dot dot-cyan" /> Your catalog</span><span><i className="legend-dot dot-violet" /> Market median</span><span>↑ sales velocity</span></div>
    </Panel>
  );
}

function ElasticitySimulator({ product, price, setPrice, data }) {
  const simulatedData = useMemo(() => data.map((point) => {
    const elasticity = Math.max(0.4, 1.9 - (price - 100) / 110);
    const units = Math.max(30, Math.round(point.units * (1 + (price - point.price) * elasticity * -0.004)));
    return { ...point, units, projected: Math.round(price * units * 0.22) };
  }), [data, price]);
  const currentUnits = simulatedData[Math.min(simulatedData.length - 1, Math.max(0, Math.round((price - 100) / 8)))]?.units || 180;
  const projectedProfit = Math.round(price * currentUnits * 0.22);

  return (
    <Panel className="simulator-panel" glow>
      <div className="panel-heading"><div><Eyebrow>DEMAND LAB</Eyebrow><h2>Price elasticity simulator</h2><p>Drag the price and see projected volume and profit respond in real time.</p></div><div className="select-wrap compact-select"><select value={product.sku} readOnly aria-label="Selected simulator product"><option>{product.sku} · {product.productName}</option></select><ChevronDown size={14} /></div></div>
      <div className="simulator-layout">
        <div className="simulator-controls">
          <div className="simulator-price"><span>Simulated price</span><strong>{preciseCurrency(price)}</strong><em className={price <= product.currentPrice ? "text-cyan-300" : "text-emerald-300"}>{price <= product.currentPrice ? "Capture demand" : "Capture margin"}</em></div>
          <input className="price-range" type="range" min="10" max="200" step="0.5" value={price} onChange={(event) => setPrice(Number(event.target.value))} aria-label="Simulated product price" />
          <div className="range-labels"><span>$10</span><span>Recommended {preciseCurrency(product.suggestedPrice)}</span><span>$200</span></div>
          <div className="simulator-stats"><div><span>Projected units</span><strong>{currentUnits.toLocaleString()}</strong><small><ArrowUpRight size={12} /> 14.8%</small></div><div><span>Projected net profit</span><strong>{currency(projectedProfit)}</strong><small><ArrowUpRight size={12} /> 8.4%</small></div></div>
          <div className="simulator-note"><Gauge size={14} /><span>Sweet spot detected at <strong>{preciseCurrency(product.suggestedPrice)}</strong></span></div>
        </div>
        <div className="simulator-chart"><div className="chart-legend"><span><i className="legend-line line-cyan" /> Unit sales</span><span><i className="legend-line line-violet" /> Net profit</span></div><ResponsiveContainer width="100%" height="100%"><LineChart data={simulatedData} margin={{ top: 20, right: 12, bottom: 4, left: -12 }}><CartesianGrid stroke="rgba(148,163,184,.1)" vertical={false} /><XAxis dataKey="price" stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${value}`} tickLine={false} axisLine={false} /><YAxis yAxisId="left" stroke="#64748b" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} /><YAxis yAxisId="right" orientation="right" stroke="#64748b" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip {...chartTooltip} formatter={(value, name) => [name === "units" ? `${value} units` : currency(value), name === "units" ? "Unit sales" : "Net profit"]} /><Line yAxisId="left" type="monotone" dataKey="units" stroke="#00f0ff" strokeWidth={2.5} dot={false} /><Line yAxisId="right" type="monotone" dataKey="projected" stroke="#a78bfa" strokeWidth={2.5} dot={false} /></LineChart></ResponsiveContainer></div>
      </div>
    </Panel>
  );
}

function RuleBuilder({ rules, onToggle, onAdd }) {
  return (
    <Panel className="rules-panel">
      <div className="panel-heading"><div><Eyebrow>GOVERNANCE</Eyebrow><h2>Pricing rule builder</h2><p>Guardrails keep autonomous actions inside your operating policy.</p></div><IconButton label="Rule settings"><Settings2 size={15} /></IconButton></div>
      <div className="rule-list">{rules.map((rule) => <div className={`rule-row ${rule.enabled ? "rule-enabled" : ""}`} key={rule.id}><div className="rule-switch"><Toggle checked={rule.enabled} onChange={() => onToggle(rule.id)} label={`Toggle ${rule.name}`} /></div><div className="rule-copy"><strong>{rule.name}</strong><span><b>IF</b> {rule.condition}</span><span><b>THEN</b> {rule.action} <em>ELSE</em> {rule.outcome}</span></div><ChevronRight size={14} className="text-slate-600" /></div>)}</div>
      <button type="button" className="add-rule-button" onClick={onAdd}><span>+</span> Add pricing rule <span className="shortcut">⌘ K</span></button>
    </Panel>
  );
}

function PriceHistory({ history }) {
  const [range, setRange] = useState("24H");
  return <Panel className="history-panel"><div className="panel-heading"><div><Eyebrow>PRODUCT ANALYTICS</Eyebrow><h2>Price history & stock availability</h2><p>Your price against the market with inventory context.</p></div><div className="history-actions"><div className="range-tabs">{["24H", "7D", "30D", "90D", "YTD"].map((item) => <button type="button" className={range === item ? "active" : ""} onClick={() => setRange(item)} key={item}>{item}</button>)}</div><IconButton label="Download history"><Download size={15} /></IconButton></div></div><div className="history-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={history} margin={{ top: 20, right: 12, bottom: 4, left: -12 }}><CartesianGrid stroke="rgba(148,163,184,.1)" vertical={false} /><XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} /><YAxis stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={(value) => `$${value}`} tickLine={false} axisLine={false} /><Tooltip {...chartTooltip} formatter={(value, name) => [preciseCurrency(value), name === "yourPrice" ? "Your price" : name === "amazon" ? "Amazon" : "Walmart"]} /><Line type="monotone" dataKey="yourPrice" stroke="#00f0ff" strokeWidth={2.5} dot={false} name="yourPrice" /><Line type="monotone" dataKey="amazon" stroke="#a78bfa" strokeWidth={1.8} dot={false} name="amazon" /><Line type="monotone" dataKey="walmart" stroke="#64748b" strokeWidth={1.8} dot={false} name="walmart" /></LineChart></ResponsiveContainer></div><div className="history-legend"><span><i className="legend-line line-cyan" /> Your price</span><span><i className="legend-line line-violet" /> Amazon</span><span><i className="legend-line line-slate" /> Walmart</span><span className="stock-marker"><PackageCheck size={13} /> stock availability overlay active</span></div></Panel>;
}

function ActivityDrawer({ open, onClose, activity }) {
  const [filter, setFilter] = useState("ALL");
  const filtered = filter === "ALL" ? activity : activity.filter((item) => item.type === filter);
  return <AnimatePresence>{open && <><motion.div className="drawer-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} /><motion.aside className="activity-drawer" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 28, stiffness: 280 }}><div className="drawer-header"><div><Eyebrow>LIVE ACTIVITY</Eyebrow><h2>Alert center</h2><p>Monitoring price changes, stockouts, and model triggers.</p></div><IconButton label="Close activity center" onClick={onClose}><X size={17} /></IconButton></div><div className="drawer-filters">{["ALL", "CRITICAL", "WARNING", "INFO"].map((item) => <button type="button" className={filter === item ? "active" : ""} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div><div className="drawer-feed">{filtered.map((item) => <div className={`activity-item activity-${item.type.toLowerCase()}`} key={item.id}><div className="activity-icon"><SeverityIcon severity={item.type} /></div><div><div className="flex items-center justify-between gap-2"><strong>{item.title}</strong><small>{item.time}</small></div><p>{item.message}</p></div></div>)}</div><div className="drawer-footer"><span><span className="live-pulse" /> Feed updates every 5 seconds</span><button type="button" className="footer-link">Mark all read</button></div></motion.aside></> }</AnimatePresence>;
}

// Shared helper retained for the existing recommendation and approval pages.
// eslint-disable-next-line react-refresh/only-export-components
export const getProcessedCompetitors = (competitorList = [], productInput = {}) => {
  const currentPrice = Number(productInput?.current_price || productInput?.currentPrice || 0);
  return competitorList
    .filter(Boolean)
    .map((competitor, index) => {
      const price = Number(competitor.competitor_price || competitor.price || 0);
      return {
        id: competitor.id || `${competitor.competitor_name || "competitor"}-${index}`,
        competitor_name: competitor.competitor_name || competitor.name || "Marketplace",
        competitor_price: price,
        in_stock: competitor.in_stock !== false,
        price_gap_pct: currentPrice ? Number((((price - currentPrice) / currentPrice) * 100).toFixed(2)) : 0,
        url: competitor.url || "#",
      };
    });
};

export default function KlypupDashboard() {
  const { user } = useAuth();
  const [snapshot, setSnapshot] = useState(() => createDashboardSnapshot(0));
  const [loading, setLoading] = useState(true);
  const [autopilot, setAutopilot] = useState(true);
  const [activityOpen, setActivityOpen] = useState(false);
  const [approvedIds, setApprovedIds] = useState([]);
  const [actioningId, setActioningId] = useState(null);
  const [selectedSku, setSelectedSku] = useState(snapshot.recommendations[0].sku);
  const [simulatedPrice, setSimulatedPrice] = useState(snapshot.recommendations[0].suggestedPrice);
  const [rules, setRules] = useState(snapshot.rules);
  const [toast, setToast] = useState("");
  const [details, setDetails] = useState(null);

  const selectedProduct = snapshot.recommendations.find((item) => item.sku === selectedSku) || snapshot.recommendations[0];

  const fetchDashboard = useCallback(async () => {
    try {
      const endpoints = ["/dashboard/metrics", "/dashboard/recommendations"];
      const results = await Promise.allSettled(endpoints.map((endpoint) => apiClient.get(endpoint)));
      const responses = { metrics: results[0].status === "fulfilled" ? results[0].value.data : {}, recommendations: results[1].status === "fulfilled" ? (results[1].value.data?.recommendations || results[1].value.data) : [] };
      const hasApiData = results.some((item) => item.status === "fulfilled");
      if (hasApiData) setSnapshot((current) => ({ ...current, ...normalizeApiSnapshot(responses) }));
    } catch (error) {
      console.info("Using local pricing intelligence snapshot", error?.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialFetch = window.setTimeout(fetchDashboard, 0);
    let tick = 0;
    const interval = window.setInterval(() => {
      tick += 1;
      setSnapshot((current) => ({ ...current, ...createDashboardSnapshot(tick) }));
      fetchDashboard();
    }, 5000);
    return () => {
      window.clearTimeout(initialFetch);
      window.clearInterval(interval);
    };
  }, [fetchDashboard]);

  useEffect(() => {
    if (!toast) return undefined;
    const timeout = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const handleApprove = async (item) => {
    setActioningId(item.sku);
    setApprovedIds((current) => [...current, item.sku]);
    setToast(`${item.sku} price change approved`);
    try {
      if (item.id) await apiClient.post(`/approvals/approve/${item.id}`);
    } catch (error) {
      console.info("Approval queued locally while backend is unavailable", error?.message);
    } finally {
      window.setTimeout(() => setActioningId(null), 450);
    }
  };

  const handleReject = (item) => {
    setSnapshot((current) => ({ ...current, recommendations: current.recommendations.filter((entry) => entry.sku !== item.sku) }));
    setToast(`${item.sku} recommendation dismissed`);
  };

  const handleRuleToggle = (id) => setRules((current) => current.map((rule) => rule.id === id ? { ...rule, enabled: !rule.enabled } : rule));
  const handleAddRule = () => setToast("Rule builder is ready for a new policy");

  if (loading) {
    return <div className="dashboard-loading"><div className="loading-orbit"><div className="loading-core"><Sparkles size={22} /></div></div><span>Calibrating your pricing workspace</span><small>Connecting to live market signals…</small></div>;
  }

  return (
    <div className="pricing-dashboard">
      <DashboardHeader user={user} autopilot={autopilot} setAutopilot={setAutopilot} onOpenActivity={() => setActivityOpen(true)} />
      <TickerStrip metrics={snapshot.metrics} />
      <div className="dashboard-grid dashboard-grid-top"><HeroPulse metrics={snapshot.metrics} /><Panel className="executive-kpis"><div className="panel-heading compact"><div><Eyebrow>EXECUTIVE SIGNALS</Eyebrow><h2>Performance at a glance</h2></div><StatusBadge tone="live">Live</StatusBadge></div><div className="kpi-stack"><MetricCard icon={CircleGauge} label="Avg. price elasticity" value={snapshot.metrics.elasticity.toFixed(2)} detail="Demand sensitivity index" trend={6.2} tone="cyan" progress={72} /><MetricCard icon={Target} label="Repricing win rate" value={`${snapshot.metrics.winRate}%`} detail="Last 30-day decisions" trend={2.4} tone="violet" progress={snapshot.metrics.winRate} /><MetricCard icon={CircleDollarSign} label="Revenue multiplier" value={`${snapshot.metrics.revenueMultiplier.toFixed(2)}×`} detail="AI projection vs baseline" trend={4.8} tone="emerald" progress={86} /><MetricCard icon={Database} label="Active catalog SKUs" value={snapshot.metrics.activeSkus.toLocaleString()} detail="Across 5 categories" trend={1.9} tone="slate" /></div></Panel></div>
      <div className="dashboard-grid dashboard-grid-queue"><RecommendationQueue recommendations={snapshot.recommendations.filter((item) => !approvedIds.includes(item.sku))} approvedIds={approvedIds} actioningId={actioningId} onApprove={handleApprove} onReject={handleReject} onDetails={setDetails} /><Panel className="revenue-panel"><div className="panel-heading"><div><Eyebrow>REVENUE OPPORTUNITY</Eyebrow><h2>AI lift trajectory</h2></div><select className="inline-select" defaultValue="30D" aria-label="Revenue period"><option>7D</option><option>30D</option><option>90D</option></select></div><div className="revenue-hero"><strong>{currency(snapshot.metrics.projectedRevenue)}</strong><span><ArrowUpRight size={14} /> projected revenue</span></div><div className="mini-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={snapshot.history}><Line type="monotone" dataKey="yourPrice" stroke="#00f0ff" strokeWidth={2.4} dot={false} /><Line type="monotone" dataKey="amazon" stroke="#7c3aed" strokeWidth={1.6} dot={false} /></LineChart></ResponsiveContainer></div><div className="revenue-bottom"><div><span>Baseline</span><strong>$155.8k</strong></div><div><span>AI projection</span><strong className="text-cyan-300">{currency(snapshot.metrics.projectedRevenue)}</strong></div><div><span>Net lift</span><strong className="text-emerald-300">+{pct(snapshot.metrics.revenueLift)}</strong></div></div></Panel></div>
      <div className="section-block"><SectionHeader eyebrow="COMPETITIVE INTELLIGENCE" title="See where your catalog wins" description="Track price spread, undercut risk, and portfolio positioning from one market view." action={<GhostButton icon={Filter}>Filter catalog</GhostButton>} /><div className="dashboard-grid dashboard-grid-competitors"><CompetitorMatrix competitors={snapshot.competitors} selectedProduct={selectedProduct} onProductChange={setSelectedSku} products={snapshot.recommendations} /><QuadrantMap recommendations={snapshot.recommendations} /></div></div>
      <div className="section-block"><SectionHeader eyebrow="AI PRICE ELASTICITY & DEMAND" title="Model the next price before you push it" description="Experiment with demand curves in a safe sandbox, then promote the winning strategy into your rule engine." action={<StatusBadge tone="violet"><Play size={12} /> Simulation mode</StatusBadge>} /><div className="dashboard-grid dashboard-grid-simulator"><ElasticitySimulator product={selectedProduct} price={simulatedPrice} setPrice={setSimulatedPrice} data={snapshot.elasticity} /><RuleBuilder rules={rules} onToggle={handleRuleToggle} onAdd={handleAddRule} /></div></div>
      <div className="section-block"><SectionHeader eyebrow="DEEP-DIVE ANALYTICS" title="Price history that explains the outcome" description="Compare your historical pricing with competitor moves and inventory health." action={<GhostButton icon={LineChartIcon}>Export report</GhostButton>} /><PriceHistory history={snapshot.history} /></div>
      <div className="bottom-status"><div><span className="status-dot" /> All systems operational</div><span>Last model refresh 2m ago</span><span>Data latency 180ms</span><span>Workspace: {user?.organization || "Klypup Enterprise"}</span></div>
      <ActivityDrawer open={activityOpen} onClose={() => setActivityOpen(false)} activity={snapshot.activity} />
      <AnimatePresence>{details && <motion.div className="detail-modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setDetails(null)}><motion.div className="detail-modal" initial={{ opacity: 0, y: 16, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10 }} onClick={(event) => event.stopPropagation()}><div className="flex items-start justify-between gap-4"><div><Eyebrow>RECOMMENDATION DETAIL</Eyebrow><h2>{details.productName}</h2><p>{details.sku} · {details.category}</p></div><IconButton label="Close recommendation detail" onClick={() => setDetails(null)}><X size={16} /></IconButton></div><div className="detail-price-grid"><div><span>Current</span><strong>{preciseCurrency(details.currentPrice)}</strong></div><div><span>AI suggested</span><strong className="text-cyan-300">{preciseCurrency(details.suggestedPrice)}</strong></div><div><span>Confidence</span><strong className="text-violet-300">{details.confidence}%</strong></div></div><div className="detail-explanation"><Sparkles size={16} /><p>{details.rationale}</p></div><PrimaryButton icon={Check} onClick={() => { handleApprove(details); setDetails(null); }}>Approve price change</PrimaryButton></motion.div></motion.div>}</AnimatePresence>
      {toast && <motion.div className="toast-message" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }}><Check size={15} /> {toast}</motion.div>}
    </div>
  );
}
