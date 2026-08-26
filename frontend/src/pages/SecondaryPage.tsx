import { motion } from "framer-motion";
import { ArrowRight, Bot, Check, ChevronRight, CircleAlert, Clock3, Database, Filter, Gauge, MailCheck, Package, Search, Sparkles, Target } from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { approveRecommendation, exportCatalog, getAgentObservability, getApprovalHistory, getRecommendationStatus, rejectRecommendation, startRecommendation, type AgentObservability } from "../services/api";
import { usePricingData } from "../hooks/usePricingData";
import type { ApprovalAuditEvent, Product, RecommendationJob } from "../types/domain";
import { cn, money } from "../lib/utils";
import { Badge, Button, EmptyState, GlassCard, IconMark, SectionTitle, useToasts, ToastStack } from "../components/ui";

type SecondaryKind = "catalog" | "approvals" | "agents";

export default function SecondaryPage({ kind }: { kind: SecondaryKind }) {
  const navigate = useNavigate();
  const { toasts, push, dismiss } = useToasts();
  const { data, loading: catalogLoading, error: catalogError, refresh: refreshCatalog } = usePricingData();
  const [query, setQuery] = useState("");
  const [approved, setApproved] = useState<string[]>([]);
  const [history, setHistory] = useState<ApprovalAuditEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [agentStats, setAgentStats] = useState<AgentObservability[]>([]);
  const [agentLoading, setAgentLoading] = useState(false);
  const [jobs, setJobs] = useState<Record<string, RecommendationJob>>({});
  const [startingProductId, setStartingProductId] = useState<string | null>(null);
  const title = kind === "catalog" ? "Catalog intelligence" : kind === "approvals" ? "Approval workspace" : "AI pricing agents";
  const subtitle = kind === "catalog" ? "Explore every item, signal, and price movement in one searchable layer." : kind === "approvals" ? "Make fast, explainable decisions on the recommendations that matter." : "Watch autonomous agents learn, reason, and execute pricing strategies.";
  const products = useMemo(() => data.products.filter((product) => `${product.name} ${product.sku} ${product.category}`.toLowerCase().includes(query.toLowerCase())), [data.products, query]);
  const pendingCount = data.products.filter((product) => product.status === "recommended").length;
  const avgConfidence = data.products.length ? data.products.reduce((sum, product) => sum + product.confidence, 0) / data.products.length : 0;
  const metrics = kind === "agents"
    ? [{ label: "Observed agents", value: String(agentStats.length), icon: Bot }, { label: "Logged calls", value: String(agentStats.reduce((sum, agent) => sum + agent.calls, 0)), icon: Sparkles }, { label: "Avg. confidence", value: `${avgConfidence.toFixed(1)}%`, icon: Gauge }]
    : kind === "approvals"
      ? [{ label: "Audit events", value: String(history.length), icon: Package }, { label: "Pending recommendations", value: String(pendingCount), icon: CircleAlert }, { label: "Approved actions", value: String(history.filter((event) => event.actionType === "approve" || event.actionType === "auto_execute").length), icon: Target }]
      : [{ label: "Items in view", value: String(products.length), icon: Package }, { label: "Need attention", value: String(pendingCount), icon: CircleAlert }, { label: "Catalog units", value: data.products.reduce((sum, product) => sum + product.inventory, 0).toLocaleString(), icon: Target }];

  useEffect(() => {
    if (kind === "approvals") {
      setHistoryLoading(true);
      void getApprovalHistory().then(setHistory).catch(() => push("Audit history is unavailable.", "error")).finally(() => setHistoryLoading(false));
    }
    if (kind === "agents") {
      setAgentLoading(true);
      void getAgentObservability().then(setAgentStats).catch(() => push("Agent observability is unavailable.", "error")).finally(() => setAgentLoading(false));
    }
  }, [kind, push]);

  useEffect(() => {
    const active = Object.entries(jobs).filter(([, job]) => job.status === "queued" || job.status === "running");
    if (!active.length) return undefined;
    const timer = window.setInterval(() => {
      void Promise.all(active.map(async ([productId, job]) => {
        try {
          const result = await getRecommendationStatus(job.recommendation_id);
          if (result.job) return [productId, result.job] as const;
        } catch {
          // Keep the last durable state visible while the next poll retries.
        }
        return [productId, job] as const;
      })).then((updates) => setJobs((current) => Object.fromEntries(updates.map(([productId, job]) => [productId, job || current[productId]]))));
    }, 2500);
    return () => window.clearInterval(timer);
  }, [jobs]);

  const refreshHistory = () => { setHistoryLoading(true); void getApprovalHistory().then(setHistory).catch(() => push("Audit history could not be refreshed.", "error")).finally(() => setHistoryLoading(false)); };
  const onExport = async () => { try { await exportCatalog("xlsx"); push("Updated catalog export downloaded.", "success"); } catch { push("Catalog export could not be generated.", "error"); } };
  const onRecommend = async (product: Product) => {
    setStartingProductId(product.id);
    try {
      const launch = await startRecommendation(product.id);
      setJobs((current) => ({ ...current, [product.id]: launch.job }));
      push(`${product.name}: scraper and pricing agents started.`, "success");
    } catch {
      push(`${product.name} could not be queued. Check that the durable worker is online.`, "error");
    } finally {
      setStartingProductId(null);
    }
  };
  const onApprove = async (product: Product) => {
    const recommendationId = jobs[product.id]?.recommendation_id || product.recommendationId;
    if (!recommendationId) { push("Run a recommendation before approving this catalog item.", "error"); return; }
    try { await approveRecommendation(recommendationId); setApproved((items) => [...items, product.id]); push(`${product.name} approved and synced.`, "success"); await refreshCatalog(); } catch { push(`${product.name} could not be approved.`, "error"); }
  };
  const onReject = async (product: Product) => {
    const recommendationId = jobs[product.id]?.recommendation_id || product.recommendationId;
    if (!recommendationId) return;
    const reason = window.prompt("Why are you rejecting this recommendation?", "Price evidence does not meet my business requirements.");
    if (!reason) return;
    try { await rejectRecommendation(recommendationId, reason); push(`${product.name} was rejected and audited.`, "info"); await refreshCatalog(); } catch { push(`${product.name} could not be rejected.`, "error"); }
  };

  return <div className="page-stack"><ToastStack toasts={toasts} dismiss={dismiss} /><header className="page-header compact-header"><div><p className="eyebrow">Workspace module</p><h1>{title}, <em>made legible.</em></h1><p className="page-lede">{subtitle}</p></div><Button onClick={() => void onExport()}>Export updated catalog <ArrowRight size={15} /></Button></header><section className="secondary-metrics">{metrics.map((metric) => <GlassCard key={metric.label}><metric.icon size={18} className="text-indigo" /><span><strong>{metric.value}</strong><small>{metric.label}</small></span></GlassCard>)}</section>{catalogError && kind === "catalog" && <EmptyState title="Catalog service unavailable" description="The catalog could not be loaded from the backend. Retry after checking the API connection." action={<Button onClick={() => void refreshCatalog()}>Retry catalog</Button>} />}{kind === "agents" ? <AgentConsole agents={agentStats} loading={agentLoading} onToast={push} /> : kind === "approvals" ? <ApprovalAuditPanel history={history} loading={historyLoading} onRefresh={refreshHistory} /> : <CatalogTable products={products} loading={catalogLoading} query={query} setQuery={setQuery} approved={approved} jobs={jobs} startingProductId={startingProductId} onRecommend={onRecommend} onApprove={onApprove} onReject={onReject} navigate={navigate} />}</div>;
}

function CatalogTable({ products, loading, query, setQuery, approved, jobs, startingProductId, onRecommend, onApprove, onReject, navigate }: { products: Product[]; loading: boolean; query: string; setQuery: (value: string) => void; approved: string[]; jobs: Record<string, RecommendationJob>; startingProductId: string | null; onRecommend: (product: Product) => Promise<void>; onApprove: (product: Product) => Promise<void>; onReject: (product: Product) => Promise<void>; navigate: ReturnType<typeof useNavigate> }) {
  return <GlassCard className="table-card"><div className="card-heading table-heading"><SectionTitle eyebrow="Live catalog" title="All catalog items" description="Search, inspect, and ask Klypup to research any offline-catalog product." /><div className="table-actions"><div className="search-field"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by product or SKU" /></div><Button variant="secondary" onClick={() => setQuery("")}><Filter size={14} /> Clear</Button></div></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Product</th><th>Current</th><th>AI target</th><th>Margin</th><th>Status</th><th>Action</th></tr></thead><tbody>{products.map((product) => { const job = jobs[product.id]; const ready = job?.status === "succeeded"; const hasRecommendation = Boolean(job?.recommendation_id || product.recommendationId); return <Fragment key={product.id}><tr><td><div className="product-cell"><IconMark initials={product.initials} color={product.image} /><span><strong>{product.name}</strong><small>{product.sku} · {product.category}</small></span></div></td><td className="mono">{money(product.currentPrice)}</td><td className="mono target-price">{money(product.targetPrice)}</td><td className="mono">{product.margin.toFixed(1)}%</td><td><Badge tone={job?.status === "failed" ? "rose" : ready || product.status === "recommended" ? "violet" : product.status === "approved" ? "emerald" : "amber"} dot>{approved.includes(product.id) ? "Approved" : job?.status || product.status}</Badge></td><td className="catalog-actions"><Button className="table-button" variant="secondary" disabled={startingProductId === product.id || job?.status === "queued" || job?.status === "running"} onClick={() => void onRecommend(product)}>{startingProductId === product.id ? "Queueing…" : job?.status === "queued" || job?.status === "running" ? "Researching…" : "Recommend"}</Button>{ready && hasRecommendation && <><Button className="table-button" variant={approved.includes(product.id) ? "secondary" : "primary"} disabled={approved.includes(product.id)} onClick={() => void onApprove(product)}>{approved.includes(product.id) ? <><Check size={13} /> Synced</> : "Approve"}</Button><Button className="table-button" variant="secondary" onClick={() => void onReject(product)}>Reject</Button></>}</td></tr>{job && <tr className="recommendation-detail-row"><td colSpan={6}><RecommendationJobPanel job={job} /></td></tr>}</Fragment>; })}</tbody></table>{loading && <EmptyState title="Loading live catalog" description="Reading products and recommendations from the database." />}{!loading && !products.length && <EmptyState title="No catalog records" description="Import a catalog or connect a verified store to begin pricing intelligence." />}</div><div className="table-footer"><span>Showing {products.length} live records</span><button className="text-button" onClick={() => navigate("/dashboard")}>Back to command center <ChevronRight size={14} /></button></div></GlassCard>;
}

function RecommendationJobPanel({ job }: { job: RecommendationJob }) {
  const latestByAgent = job.events.reduce<Record<string, RecommendationJob["events"][number]>>((all, event) => ({ ...all, [event.agent_name]: event }), {});
  return <div className="recommendation-job-panel"><div className="job-panel-heading"><div><p className="eyebrow">Orchestrator job</p><strong>{job.status === "succeeded" ? "Evidence collected — recommendation ready" : job.status === "failed" ? "Recommendation failed" : "Agents are working"}</strong><small>{job.current_agent || "orchestrator"} · {job.progress}% · {job.requested_platforms.join(" · ")}</small></div><div className="job-progress"><span style={{ width: `${job.progress}%` }} /></div></div>{job.error_message && <p className="job-error">{job.error_message}</p>}<div className="agent-event-strip">{["scraper", "market", "inventory", "orchestrator"].map((agent) => { const event = latestByAgent[agent]; return <div key={agent} className="agent-event-item"><Badge tone={event?.status === "succeeded" ? "emerald" : event?.status === "failed" ? "rose" : "violet"} dot>{agent}</Badge><span>{event?.message || "Waiting…"}</span></div>; })}</div>{job.offers.length > 0 && <div className="marketplace-deals"><p className="eyebrow">Live marketplace deals</p><div className="deal-grid">{job.offers.map((offer) => <a className="deal-card" key={offer.id} href={offer.product_url || undefined} target="_blank" rel="noreferrer"><div><strong>{offer.platform}</strong><Badge tone={offer.in_stock === false ? "rose" : "emerald"} dot>{offer.in_stock === false ? "Out of stock" : "Available"}</Badge></div><span>{offer.title || "Matched product offer"}</span><b>{offer.current_price ? money(offer.current_price) : "No price"}</b><small>{offer.source_type || "live evidence"} · {offer.match_confidence || "medium"} match</small></a>)}</div></div>}</div>;
}

function ApprovalAuditPanel({ history, loading, onRefresh }: { history: ApprovalAuditEvent[]; loading: boolean; onRefresh: () => void }) {
  return <GlassCard className="audit-history-card"><div className="card-heading"><SectionTitle eyebrow="Audit trail & history" title="Every price action, explained" description="A chronological record of decision, rationale, database sync, and notification delivery." /><Button variant="secondary" onClick={onRefresh} disabled={loading}>{loading ? "Refreshing…" : "Refresh history"}</Button></div>{history.length === 0 ? <EmptyState title={loading ? "Loading audit history" : "No action history yet"} description="Approved, rejected, and rolled-back price actions will appear here with their full rationale." /> : <div className="audit-timeline">{history.map((event) => <motion.div key={event.id} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="audit-event"><div className={cn("audit-marker", event.actionType === "approve" ? "success" : event.actionType === "reject" ? "danger" : "violet")}><Clock3 size={14} /></div><div className="audit-event-body"><div className="audit-event-top"><div><Badge tone={event.actionType === "approve" ? "emerald" : event.actionType === "reject" ? "rose" : "violet"} dot>{event.actionType === "approve" ? "APPROVED" : event.actionType === "reject" ? "REJECTED" : "ROLLED BACK"}</Badge><h3>{event.productName}</h3><span className="audit-sku">{event.sku} · {new Date(event.timestamp).toLocaleString()}</span></div><div className="audit-statuses"><span><MailCheck size={13} /> Email {event.emailSentStatus === "sent" ? "Sent ✓" : event.emailSentStatus}</span><span><Database size={13} /> DB Synced ✓</span></div></div><div className="audit-price-row"><span>₹{event.previousPrice.toLocaleString()} → <strong>₹{event.executedPrice.toLocaleString()}</strong></span><span>{event.userEmail}</span></div><details><summary>View LLM rationale</summary><p>{event.llmStatement}</p></details></div></motion.div>)}</div>}</GlassCard>;
}

function AgentConsole({ agents, loading, onToast }: { agents: AgentObservability[]; loading: boolean; onToast: (message: string, tone?: "success" | "error" | "info") => void }) {
  return <div className="agent-console-grid">{loading && <EmptyState title="Loading agent telemetry" description="Reading persisted model-call observability from the backend." />}{!loading && !agents.length && <EmptyState title="No agent telemetry yet" description="Agent metrics will appear after a real recommendation or scraper workflow has been processed." />}{agents.map((agent, index) => { const quality = agent.calls ? Math.min(100, Math.max(0, 100 - agent.avg_latency / 100)) : 0; return <motion.div key={agent.name} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .07 }}><GlassCard className={cn("agent-card", `agent-accent-${index % 2 ? "emerald" : "indigo"}`)}><div className="agent-card-top"><span className="agent-avatar"><Bot size={18} /></span><Badge tone={agent.calls ? "emerald" : "neutral"} dot>{agent.calls ? "Observed" : "Idle"}</Badge></div><h3>{agent.name}</h3><p>{agent.calls} persisted calls · {agent.avg_latency.toFixed(0)}ms average latency · ${agent.cost.toFixed(4)} cost</p><div className="agent-progress"><div><span>Observed quality</span><strong>{quality.toFixed(1)}%</strong></div><i><b style={{ width: `${quality}%` }} /></i></div><button className="text-button" onClick={() => onToast(`${agent.name} telemetry is sourced from persisted AI call logs.`, "info")}>Inspect telemetry <ArrowRight size={14} /></button></GlassCard></motion.div>; })}</div>;
}
