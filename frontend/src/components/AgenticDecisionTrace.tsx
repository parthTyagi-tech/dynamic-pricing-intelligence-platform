import React, { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ExternalLink,
  Info,
  Layers,
  ShieldCheck,
  XCircle,
  Zap,
} from "lucide-react";
import { Badge, Button, GlassCard } from "./ui";
import { money } from "../lib/utils";
import type { AgenticTaskState } from "../services/api";

interface Props {
  task: AgenticTaskState;
  onApprove?: () => void;
  onReject?: (reason: string) => void;
  isApproving?: boolean;
}

const cleanRationale = (text: string) => {
  if (!text) return "";
  return text
    .replace(/\(ID:\s*[a-f0-9-]{36}\)/gi, "")
    .replace(/\(Gap\s*#\d+([^\)]*)\)/gi, "")
    .replace(/\(SEC-\d+\)/gi, "")
    .replace(/\(Problem\s*\d+\)/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
};

export const AgenticDecisionTrace: React.FC<Props> = ({
  task,
  onApprove,
  onReject,
  isApproving = false,
}) => {
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const recommendation = task.recommendation;
  const decisionTraces = task.decision_traces || [];
  const events = task.events || [];

  return (
    <GlassCard className="agentic-decision-trace" glow>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-white/10 pb-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-indigo-500/10 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400">
            <Bot size={22} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-white">Autonomous Agent Decision Trace</h3>
              <Badge
                tone={
                  task.status === "succeeded" || task.status === "approved"
                    ? "emerald"
                    : task.status === "running"
                    ? "violet"
                    : task.status === "rejected"
                    ? "rose"
                    : "neutral"
                }
                dot
              >
                {task.status.toUpperCase()}
              </Badge>
            </div>
            <p className="text-xs text-slate-500 dark:text-zinc-400">
              Session: <code className="text-slate-700 dark:text-zinc-300 font-mono">#{task.task_id.slice(0, 8)}</code> · Scoped to verified category marketplaces
            </p>
          </div>
        </div>

        {recommendation && (
          <div className="text-right">
            <span className="text-xs text-slate-500 dark:text-zinc-400">Recommended Price</span>
            <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
              {money(recommendation.recommended_price)}
            </div>
          </div>
        )}
      </div>

      {/* Financial Guardrails Active Bar */}
      {recommendation && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-4">
          <div className="p-2.5 rounded-md bg-slate-100/80 dark:bg-zinc-900/60 border border-slate-200 dark:border-white/5 flex items-center gap-2">
            <ShieldCheck size={16} className={recommendation.margin_floor_applied ? "text-amber-500 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400"} />
            <div>
              <div className="text-xs font-medium text-slate-900 dark:text-white">Margin Floor Guardrail</div>
              <div className="text-[11px] text-slate-600 dark:text-zinc-400">
                {recommendation.margin_floor_applied ? "Clamped to protect unit margin" : "Safely above cost floor"}
              </div>
            </div>
          </div>

          <div className="p-2.5 rounded-md bg-slate-100/80 dark:bg-zinc-900/60 border border-slate-200 dark:border-white/5 flex items-center gap-2">
            <AlertTriangle
              size={16}
              className={recommendation.sanity_bound_flagged ? "text-rose-500 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}
            />
            <div>
              <div className="text-xs font-medium text-slate-900 dark:text-white">Price Sanity Guardrail</div>
              <div className="text-[11px] text-slate-600 dark:text-zinc-400">
                {recommendation.sanity_bound_flagged ? "Flagged: >50% deviation (Requires audit)" : "Within safe deviation limits"}
              </div>
            </div>
          </div>

          <div className="p-2.5 rounded-md bg-slate-100/80 dark:bg-zinc-900/60 border border-slate-200 dark:border-white/5 flex items-center gap-2">
            <Zap size={16} className="text-indigo-600 dark:text-indigo-400" />
            <div>
              <div className="text-xs font-medium text-slate-900 dark:text-white">Data Confidence</div>
              <div className="text-[11px] uppercase font-semibold text-indigo-600 dark:text-indigo-300">
                {recommendation.confidence} CONFIDENCE
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Autonomous Decision Traces (Explainability) */}
      <div className="mb-4">
        <h4 className="text-xs font-semibold text-slate-700 dark:text-zinc-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <Layers size={14} className="text-indigo-600 dark:text-indigo-400" />
          Autonomous Reasoning Steps ({decisionTraces.length})
        </h4>

        <div className="space-y-2">
          {decisionTraces.map((trace, idx) => (
            <div
              key={idx}
              className="p-3 rounded-lg bg-slate-50 dark:bg-zinc-900/80 border border-slate-200 dark:border-white/5 text-xs transition-all hover:border-slate-300 dark:hover:border-white/10"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-indigo-600 dark:text-indigo-300 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 dark:bg-indigo-400" />
                  {trace.agent} · {cleanRationale(trace.decision_point)}
                </span>
                <span className="text-[10px] text-slate-500 dark:text-zinc-500">
                  {new Date(trace.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-slate-700 dark:text-zinc-300 mb-1 leading-relaxed">{cleanRationale(trace.rationale)}</p>
              <div className="text-[11px] text-emerald-700 dark:text-emerald-400/90 font-mono bg-slate-200/70 dark:bg-black/40 px-2 py-1 rounded inline-block">
                ↳ Action: {cleanRationale(trace.action_taken)}
              </div>
            </div>
          ))}

          {decisionTraces.length === 0 && (
            <p className="text-xs text-slate-500 dark:text-zinc-500 italic p-3">Supervisor is actively planning execution...</p>
          )}
        </div>
      </div>

      {/* Verified Platform Evidence */}
      {recommendation?.platform_prices_snapshot && (
        <div className="mb-5">
          <h4 className="text-xs font-semibold text-slate-700 dark:text-zinc-300 uppercase tracking-wider mb-2">
            Verified Marketplace Evidence
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {Object.entries(recommendation.platform_prices_snapshot).map(([platform, item]: [string, any]) => {
              const isFallback = item.data_source === "estimated_fallback" || item.unverified_match;
              const isCached = item.data_source === "cached_recent" || item.data_source === "verified_cache";
              const isLive = item.data_source === "live_scrape";
              const matchPct = Math.round((item.match_score || 0.85) * 100);

              return (
                <div
                  key={platform}
                  className={`p-3.5 rounded-xl border flex items-center justify-between transition-all ${
                    isFallback
                      ? "bg-amber-50 dark:bg-amber-950/20 border-amber-300 dark:border-amber-500/30 text-amber-900 dark:text-amber-200"
                      : isCached
                      ? "bg-blue-50 dark:bg-blue-950/20 border-blue-300 dark:border-blue-500/30 text-blue-900 dark:text-zinc-200"
                      : "bg-white dark:bg-zinc-900/70 border-slate-200 dark:border-white/5 text-slate-900 dark:text-white shadow-sm"
                  }`}
                >
                  <div className="space-y-1 text-left">
                    <div className="font-semibold text-sm flex items-center gap-2 flex-wrap">
                      <span className="text-slate-900 dark:text-white font-bold">{platform}</span>
                      {item.verified && !isFallback && (
                        <CheckCircle2 size={13} className="text-emerald-500 dark:text-emerald-400" />
                      )}
                      {isLive && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-500/30 font-mono font-medium">
                          LIVE{item.latency_ms ? ` · ${Math.round(item.latency_ms)}ms` : ""}
                        </span>
                      )}
                      {isFallback && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-500/20 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-500/30 font-medium">
                          {item.reason === "circuit_open" ? "Circuit Open" : "Estimated — unverified"}
                        </span>
                      )}
                      {isCached && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-500/20 text-blue-800 dark:text-blue-300 border border-blue-300 dark:border-blue-500/30 font-medium">
                          Cached
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-600 dark:text-zinc-300 font-medium">
                      {isFallback
                        ? (item.reason || "Excluded from consensus pricing")
                        : `Jaccard Match: ${matchPct}%`}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`font-bold text-base ${isFallback ? "text-amber-600 dark:text-amber-400/80 line-through" : "text-slate-900 dark:text-white"}`}>
                      {money(item.price || 0)}
                    </div>
                    {item.product_url && !isFallback ? (
                      <a
                        href={item.product_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 inline-flex items-center gap-1 font-medium underline underline-offset-2"
                      >
                        Inspect on {platform} <ExternalLink size={10} />
                      </a>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Human-in-the-Loop Actions */}
      {task.status === "succeeded" && onApprove && (
        <div className="pt-3 border-t border-slate-200 dark:border-white/10 flex items-center justify-between gap-3">
          {!rejecting ? (
            <>
              <Button
                variant="secondary"
                onClick={() => setRejecting(true)}
                disabled={isApproving}
                className="text-xs text-rose-600 dark:text-rose-400 hover:text-rose-500 dark:hover:text-rose-300"
              >
                <XCircle size={14} /> Reject with feedback
              </Button>
              <Button
                onClick={onApprove}
                disabled={isApproving}
                className="text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white"
              >
                <CheckCircle2 size={14} /> {isApproving ? "Committing..." : "Approve and Sync Price"}
              </Button>
            </>
          ) : (
            <div className="w-full flex items-center gap-2">
              <input
                type="text"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Reason for rejecting this recommendation..."
                className="flex-1 text-xs px-3 py-1.5 rounded bg-slate-100 dark:bg-black/50 border border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500"
              />
              <Button
                variant="secondary"
                onClick={() => setRejecting(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                onClick={() => {
                  if (onReject) onReject(rejectReason);
                  setRejecting(false);
                }}
                className="text-xs bg-rose-600 hover:bg-rose-500 text-white"
              >
                Submit Rejection
              </Button>
            </div>
          )}
        </div>
      )}
    </GlassCard>
  );
};
