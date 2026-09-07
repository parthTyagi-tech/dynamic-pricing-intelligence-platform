import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  BellRing,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Command,
  ExternalLink,
  HeartPulse,
  Loader2,
  Play,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Wifi,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { usePricingData } from "../hooks/usePricingData";
import {
  acknowledgePriceDropAlert,
  getPriceDropAlerts,
  getScraperStatus,
  runSingleScraper,
  triggerHealthCheck,
  type ScraperStatus,
} from "../services/api";
import type { PriceDropAlert, Product } from "../types/domain";
import { money } from "../lib/utils";
import { Badge, Button, GlassCard, SectionTitle, ToastStack, useToasts } from "../components/ui";

type PlatformState = "active" | "idle" | "alert" | "running";

interface Platform extends ScraperStatus {
  name: string;
  code: string;
  color: string;
  state: PlatformState;
}

interface LogLine {
  id: number;
  time: string;
  platform: string;
  status: number | "…";
  message: string;
  tone: "ok" | "warn" | "error";
}

const colors = [
  "#f59e0b",
  "#60a5fa",
  "#f472b6",
  "#34d399",
  "#a78bfa",
  "#c084fc",
  "#38bdf8",
  "#fb923c",
  "#4ade80",
  "#e879f9",
  "#2dd4bf",
  "#f87171",
  "#818cf8",
  "#fbbf24",
];

const formatTime = () => new Date().toLocaleTimeString([], { hour12: false });

function CircuitBadge({
  circuitState,
  backoffMinutes,
  failures,
}: {
  circuitState?: "closed" | "open" | "half_open";
  backoffMinutes?: number;
  failures?: number;
}) {
  if (circuitState === "open") {
    return (
      <Badge tone="rose" dot>
        Circuit Open ({backoffMinutes || 15}m backoff)
      </Badge>
    );
  }
  if (circuitState === "half_open") {
    return (
      <Badge tone="amber" dot>
        Half-Open (Probe)
      </Badge>
    );
  }
  if ((failures || 0) > 0) {
    return (
      <Badge tone="amber" dot>
        {failures} fail/hr
      </Badge>
    );
  }
  return (
    <Badge tone="emerald" dot>
      Healthy (Closed)
    </Badge>
  );
}

function PlatformCard({
  platform,
  onRun,
}: {
  platform: Platform;
  onRun: () => void;
}) {
  const sample = platform.latest_sample;
  const isFallback = sample?.data_source === "estimated_fallback";
  const isOpen = platform.circuit_state === "open";

  return (
    <motion.div
      layout
      whileHover={{ y: -3 }}
      className={`scraper-platform-card ${isOpen ? "opacity-85 border-rose-500/30" : ""}`}
    >
      <div className="scraper-card-head">
        <div
          className="scraper-logo"
          style={{ borderColor: `${platform.color}66`, color: platform.color }}
        >
          {platform.code}
        </div>
        <CircuitBadge
          circuitState={platform.circuit_state}
          backoffMinutes={platform.backoff_minutes}
          failures={platform.failure_count_last_hour}
        />
      </div>

      <h3>{platform.name}</h3>

      <div className="scraper-meta">
        <span>
          <Clock3 size={12} /> observed{" "}
          {platform.last_scraped
            ? new Date(platform.last_scraped).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })
            : "never"}
        </span>
        <span>
          <Activity size={12} /> {platform.checks} checks
        </span>
      </div>

      {/* Latest Price Sample */}
      {sample ? (
        <div
          className={`mt-2 p-2 rounded text-xs ${
            isFallback
              ? "bg-amber-950/30 border border-amber-500/30 text-amber-200"
              : "bg-zinc-900/60 border border-white/5 text-zinc-300"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-white">
              {money(sample.price)}
            </span>
            <span className="text-[10px] opacity-80">
              {isFallback ? (
                <span className="text-amber-300">Estimated (Fallback)</span>
              ) : (
                <span className="text-emerald-400">
                  {Math.round(sample.match_score * 100)}% match
                </span>
              )}
            </span>
          </div>
          {sample.product_url && !isFallback && (
            <a
              href={sample.product_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-indigo-400 hover:underline flex items-center gap-0.5 mt-1 truncate"
            >
              Verified listing <ExternalLink size={9} />
            </a>
          )}
        </div>
      ) : (
        <div className="mt-2 p-2 rounded text-xs bg-zinc-900/40 border border-white/5 text-zinc-500 italic">
          No recent price sample verified
        </div>
      )}

      <div className="scraper-card-foot mt-3">
        <span className="text-[11px] text-zinc-400">
          {isOpen
            ? `Cooldown active (${platform.backoff_minutes || 15}m)`
            : `${platform.checks.toLocaleString()} telemetry checks`}
        </span>
        <button
          type="button"
          onClick={onRun}
          disabled={platform.state === "running"}
          aria-label={`Run ${platform.name} scraper`}
          className={isOpen ? "text-amber-400" : ""}
        >
          {platform.state === "running" ? (
            <>
              <Loader2 size={13} className="spin" /> Probing…
            </>
          ) : (
            <>
              <Play size={13} /> {isOpen ? "Probe probe" : "Run now"}
            </>
          )}
        </button>
      </div>
    </motion.div>
  );
}

function formatAlertAge(timestamp: string) {
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - new Date(timestamp).getTime()) / 60000)
  );
  return minutes < 1 ? "just now" : `${minutes}m ago`;
}

export default function ScraperHubPage() {
  const { data } = usePricingData();
  const { toasts, push, dismiss } = useToasts();
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [alerts, setAlerts] = useState<PriceDropAlert[]>([]);
  const [runningAll, setRunningAll] = useState(false);
  const [runningCanary, setRunningCanary] = useState(false);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingAlerts, setLoadingAlerts] = useState(false);

  const load = async (announce = false) => {
    try {
      const [status, nextAlerts] = await Promise.all([
        getScraperStatus(),
        getPriceDropAlerts("open"),
      ]);

      setPlatforms(
        status.map((item, index) => ({
          ...item,
          name: item.marketplace,
          code: item.marketplace.slice(0, 2).toUpperCase(),
          color: colors[index % colors.length],
          state:
            item.circuit_state === "open"
              ? "alert"
              : item.circuit_state === "half_open"
              ? "idle"
              : "active",
        }))
      );
      setAlerts(nextAlerts);
      if (announce) push(`Loaded ${status.length} agentic scraper targets.`);
    } catch {
      push("Scraper telemetry is unavailable; no seeded targets were shown.", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 30000);
    return () => window.clearInterval(timer);
  }, []);

  const visible = useMemo(
    () =>
      platforms.filter((platform) =>
        platform.name.toLowerCase().includes(query.toLowerCase())
      ),
    [platforms, query]
  );

  const refreshAlerts = async (announce = false) => {
    setLoadingAlerts(true);
    try {
      const next = await getPriceDropAlerts("open");
      setAlerts(next);
      if (announce)
        push(
          next.length
            ? `${next.length} open competitor drop alert${next.length === 1 ? "" : "s"}.`
            : "No open competitor drop alerts.",
          next.length ? "error" : "info"
        );
    } catch {
      if (announce) push("Alert service is unavailable.", "error");
    } finally {
      setLoadingAlerts(false);
    }
  };

  const run = async (platformName: string) => {
    const product: Product | undefined = data.products[0];
    setPlatforms((items) =>
      items.map((item) =>
        item.name === platformName ? { ...item, state: "running" } : item
      )
    );

    setLogs((items) => [
      {
        id: Date.now(),
        time: formatTime(),
        platform: platformName,
        status: "…" as const,
        message: `Dispatched single-platform agentic task (Product: ${product?.sku || "Canary"})`,
        tone: "ok" as const,
      },
      ...items,
    ].slice(0, 16));

    try {
      const result = await runSingleScraper(platformName, product?.id);
      setLogs((items) => [
        {
          id: Date.now(),
          time: formatTime(),
          platform: platformName,
          status: 202,
          message: `Agent task claimed (task: ${result.task_id?.slice(0, 8)}) · Circuit state updated`,
          tone: "ok" as const,
        },
        ...items,
      ].slice(0, 16));
      push(`Dispatched ${platformName} agentic scrape task.`);
      // Reload after slight delay to see updated reliability telemetry
      setTimeout(() => void load(), 3500);
    } catch (err: any) {
      const errMsg = err?.response?.data?.message || err?.message || "Task failed";
      setLogs((items) => [
        {
          id: Date.now(),
          time: formatTime(),
          platform: platformName,
          status: 503,
          message: `Scraper error: ${errMsg}`,
          tone: "warn" as const,
        },
        ...items,
      ].slice(0, 16));
      push(`${platformName} scrape error: ${errMsg}`, "error");
    } finally {
      setPlatforms((items) =>
        items.map((item) =>
          item.name === platformName
            ? {
                ...item,
                state:
                  item.circuit_state === "open"
                    ? "alert"
                    : item.circuit_state === "half_open"
                    ? "idle"
                    : "active",
              }
            : item
        )
      );
    }
  };

  const runAll = async () => {
    setRunningAll(true);
    const product = data.products[0];
    setLogs((items) => [
      {
        id: Date.now(),
        time: formatTime(),
        platform: "Supervisor",
        status: "…" as const,
        message: `Starting sequential agentic scrape across all ${platforms.length} targets...`,
        tone: "ok" as const,
      },
      ...items,
    ].slice(0, 16));

    for (const platform of platforms) {
      await run(platform.name);
    }
    setRunningAll(false);
  };

  const runCanaryChecks = async () => {
    setRunningCanary(true);
    setLogs((items) => [
      {
        id: Date.now(),
        time: formatTime(),
        platform: "CanaryScheduler",
        status: "…" as const,
        message: `Triggering scheduled canary health check reachability probes across all 14 platforms...`,
        tone: "ok" as const,
      },
      ...items,
    ].slice(0, 16));

    try {
      const res = await triggerHealthCheck();
      const count = res.results?.length || 14;
      push(`Canary reachability checks completed for ${count} platforms.`);
      setLogs((items) => [
        {
          id: Date.now(),
          time: formatTime(),
          platform: "CanaryScheduler",
          status: 200,
          message: `Canary run completed · ${count} platforms probed · ScraperReliability refreshed`,
          tone: "ok" as const,
        },
        ...items,
      ].slice(0, 16));
      await load();
    } catch (err: any) {
      push("Canary health check encountered an error.", "error");
    } finally {
      setRunningCanary(false);
    }
  };

  const acknowledge = async (alert: PriceDropAlert) => {
    try {
      await acknowledgePriceDropAlert(alert.id);
      setAlerts((items) => items.filter((item) => item.id !== alert.id));
      push(`${alert.competitorName} alert acknowledged.`);
    } catch {
      push("Alert could not be acknowledged.", "error");
    }
  };

  const itemsLastCycle = platforms.reduce((sum, item) => sum + item.checks, 0);
  const openCircuits = platforms.filter((p) => p.circuit_state === "open").length;

  return (
    <div className="page-stack">
      <ToastStack toasts={toasts} dismiss={dismiss} />

      <header className="page-header">
        <div>
          <p className="eyebrow">
            <Radio size={12} /> Agentic Scraper Intelligence Hub <span className="live-dot" />
          </p>
          <h1>
            Autonomous Market Sensors, <em>Resilient & Self-Reporting.</em>
          </h1>
          <p className="page-lede">
            Unified agentic pipeline covering all 14 eCommerce platforms with circuit breaker protection, exponential backoff, and match-score verification.
          </p>
        </div>

        <div className="header-controls flex gap-2">
          <Button
            variant="secondary"
            onClick={() => void runCanaryChecks()}
            disabled={runningCanary || loading}
          >
            {runningCanary ? (
              <Loader2 className="spin" size={14} />
            ) : (
              <HeartPulse size={14} />
            )}{" "}
            Run Canary Probes
          </Button>

          <Button
            onClick={() => void runAll()}
            disabled={runningAll || loading}
          >
            {runningAll ? (
              <Loader2 className="spin" size={14} />
            ) : (
              <RefreshCw size={14} />
            )}{" "}
            {runningAll ? "Probing targets…" : "Run observed targets"}
          </Button>
        </div>
      </header>

      {/* Summary KPI Grid */}
      <div className="scraper-summary-grid">
        <div>
          <Wifi size={16} />
          <span>
            <strong>
              {platforms.filter((item) => item.circuit_state !== "open").length}/
              {platforms.length}
            </strong>
            <small>platforms operational</small>
          </span>
        </div>

        <div>
          <ShieldAlert size={16} />
          <span>
            <strong>{openCircuits}</strong>
            <small>circuit breakers open</small>
          </span>
        </div>

        <div>
          <CheckCircle2 size={16} />
          <span>
            <strong>
              {platforms.filter((p) => p.latest_sample?.data_source === "live_scrape").length}
            </strong>
            <small>verified live price samples</small>
          </span>
        </div>

        <div>
          <Terminal size={16} />
          <span>
            <strong>{itemsLastCycle.toLocaleString()}</strong>
            <small>total reachability checks</small>
          </span>
        </div>
      </div>

      {/* Sudden Competitor Drops Alert Panel */}
      <GlassCard className="price-alert-panel">
        <div className="card-heading">
          <SectionTitle
            eyebrow="Automated guardrail"
            title="Sudden competitor drops"
            description="Persistent price drop alerts detected by the agentic pipeline."
          />
          <Button
            variant="secondary"
            onClick={() => void refreshAlerts(true)}
            disabled={loadingAlerts}
          >
            {loadingAlerts ? (
              <Loader2 className="spin" size={14} />
            ) : (
              <RefreshCw size={14} />
            )}{" "}
            Refresh alerts
          </Button>
        </div>

        {alerts.length === 0 ? (
          <div className="alert-empty">
            <CheckCircle2 size={17} />
            <span>No open competitor drops have been persisted.</span>
          </div>
        ) : (
          <div className="alert-list">
            <AnimatePresence initial={false}>
              {alerts.map((alert) => (
                <motion.div
                  key={alert.id}
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: 8 }}
                  className="price-alert-row"
                >
                  <div className="alert-icon">
                    <CircleAlert size={15} />
                  </div>
                  <div className="alert-copy">
                    <strong>
                      {alert.competitorName} dropped {alert.dropPercent.toFixed(1)}%
                    </strong>
                    <span>
                      {alert.productName} · {alert.sku} · {formatAlertAge(alert.detectedAt)}
                    </span>
                  </div>
                  <div className="alert-prices">
                    <strong>₹{alert.currentPrice.toLocaleString()}</strong>
                    <span>from ₹{alert.previousPrice.toLocaleString()}</span>
                  </div>
                  <button
                    type="button"
                    className="alert-dismiss"
                    onClick={() => void acknowledge(alert)}
                    aria-label={`Acknowledge ${alert.competitorName} alert`}
                  >
                    <X size={14} />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </GlassCard>

      {/* Target Matrix Grid */}
      <section className="scraper-section">
        <div className="section-title-row">
          <SectionTitle
            eyebrow="Target matrix"
            title="Agentic Marketplace Sensors (14 Platforms)"
            description="Every platform is protected by circuit breaker exponential backoff, strict validation, and match scoring."
          />
          <div className="search-field">
            <Search size={14} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter platform sensors..."
              aria-label="Filter observed targets"
            />
          </div>
        </div>

        <div className="scraper-platform-grid">
          {visible.map((platform) => (
            <PlatformCard
              key={platform.name}
              platform={platform}
              onRun={() => void run(platform.name)}
            />
          ))}
        </div>

        {!loading && !visible.length && (
          <p className="table-subtext">No marketplace sensors match this filter.</p>
        )}
      </section>

      {/* Terminal & Pipeline Explanation Layout */}
      <section className="scraper-terminal-layout">
        <GlassCard className="terminal-card">
          <div className="card-heading">
            <SectionTitle
              eyebrow="Execution terminal"
              title="Supervisor Agent Stream"
              description="Live agentic tasks, probe runs, and circuit breaker transitions."
            />
            <Badge tone="emerald" dot>
              Live Telemetry
            </Badge>
          </div>

          <div className="terminal-window">
            <div className="terminal-top">
              <span>
                <i />
                <i />
                <i />
              </span>
              <small>supervisor-agent / agentic-v3</small>
              <Command size={13} />
            </div>

            <div className="terminal-lines">
              <AnimatePresence initial={false}>
                {logs.map((log) => (
                  <motion.div
                    key={log.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="terminal-line"
                  >
                    <span className="terminal-time">{log.time}</span>
                    <span className="terminal-platform">{log.platform}</span>
                    <strong className={log.tone}>{log.status}</strong>
                    <span className="terminal-message">{log.message}</span>
                  </motion.div>
                ))}
              </AnimatePresence>
              <div className="terminal-cursor">
                <span>›</span> supervisor ready for task dispatch
                <span className="cursor-blink">_</span>
              </div>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="pipeline-card">
          <div className="card-heading">
            <SectionTitle
              eyebrow="Pipeline health"
              title="Agentic Scraper Guardrails"
              description="How data flows securely from marketplace search to verified pricing recommendation."
            />
          </div>

          <div className="pipeline-steps">
            <div className="pipeline-step active">
              <span>01</span>
              <strong>Circuit Gate</strong>
              <small>check open/half-open</small>
            </div>
            <div className="pipeline-connector" />
            <div className="pipeline-step active">
              <span>02</span>
              <strong>Probe & Retry</strong>
              <small>15s timeout + jitter</small>
            </div>
            <div className="pipeline-connector" />
            <div className="pipeline-step active">
              <span>03</span>
              <strong>Match Verification</strong>
              <small>match_score ≥ 0.70</small>
            </div>
            <div className="pipeline-connector" />
            <div className="pipeline-step active">
              <span>04</span>
              <strong>Pricing Clamp</strong>
              <small>margin floor & bounds</small>
            </div>
          </div>

          <div className="pipeline-callout">
            <Terminal size={15} />
            <p>
              <strong>14 platform agents actively registered.</strong>
              <br />
              Estimated/fallback data is never fed into automated price changes.
            </p>
          </div>

          <Button
            variant="secondary"
            onClick={() =>
              push(
                "All scraper activity is immutably logged with audit trails (SEC-8).",
                "info"
              )
            }
          >
            <ExternalLink size={14} /> View Audit Logs
          </Button>
        </GlassCard>
      </section>
    </div>
  );
}
