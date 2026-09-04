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
      <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400">
            <Bot size={22} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-white">Autonomous Agent Decision Trace</h3>
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
            <p className="text-xs text-zinc-400">
              Task ID: <code className="text-zinc-300">{task.task_id.slice(0, 8)}</code> · Scoped to verified category platforms
            </p>
          </div>
        </div>

        {recommendation && (
          <div className="text-right">
            <span className="text-xs text-zinc-400">Recommended Price</span>
            <div className="text-xl font-bold text-emerald-400">
              {money(recommendation.recommended_price)}
            </div>
          </div>
        )}
      </div>

      {/* Financial Guardrails Active Bar */}
      {recommendation && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-4">
          <div className="p-2.5 rounded-md bg-zinc-900/60 border border-white/5 flex items-center gap-2">
            <ShieldCheck size={16} className={recommendation.margin_floor_applied ? "text-amber-400" : "text-emerald-400"} />
            <div>
              <div className="text-xs font-medium text-white">Margin Floor Guardrail</div>
              <div className="text-[11px] text-zinc-400">
                {recommendation.margin_floor_applied ? "Clamped to protect unit margin" : "Safely above cost floor"}
              </div>
            </div>
          </div>

          <div className="p-2.5 rounded-md bg-zinc-900/60 border border-white/5 flex items-center gap-2">
            <AlertTriangle
              size={16}
              className={recommendation.sanity_bound_flagged ? "text-rose-400" : "text-emerald-400"}
            />
            <div>
              <div className="text-xs font-medium text-white">Price Sanity Bound (SEC-10)</div>
              <div className="text-[11px] text-zinc-400">
                {recommendation.sanity_bound_flagged ? "Flagged: >50% deviation (Requires audit)" : "Within safe deviation limits"}
              </div>
            </div>
          </div>

          <div className="p-2.5 rounded-md bg-zinc-900/60 border border-white/5 flex items-center gap-2">
            <Zap size={16} className="text-indigo-400" />
            <div>
              <div className="text-xs font-medium text-white">Data Confidence</div>
              <div className="text-[11px] text-zinc-400 uppercase font-semibold text-indigo-300">
                {recommendation.confidence} CONFIDENCE
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Autonomous Decision Traces (Explainability) */}
      <div className="mb-4">
        <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <Layers size={14} className="text-indigo-400" />
          Autonomous Reasoning Steps ({decisionTraces.length})
        </h4>

        <div className="space-y-2">
          {decisionTraces.map((trace, idx) => (
            <div
              key={idx}
              className="p-3 rounded-lg bg-zinc-900/80 border border-white/5 text-xs transition-all hover:border-white/10"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-indigo-300 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                  {trace.agent} · {trace.decision_point}
                </span>
                <span className="text-[10px] text-zinc-500">
                  {new Date(trace.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-zinc-300 mb-1 leading-relaxed">{trace.rationale}</p>
              <div className="text-[11px] text-emerald-400/90 font-mono bg-black/40 px-2 py-1 rounded inline-block">
                ↳ Action: {trace.action_taken}
              </div>
            </div>
          ))}

          {decisionTraces.length === 0 && (
            <p className="text-xs text-zinc-500 italic p-3">Supervisor is actively planning execution...</p>
          )}
        </div>
      </div>

      {/* Verified Platform Evidence */}
      {recommendation?.platform_prices_snapshot && (
        <div className="mb-5">
          <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-2">
            Verified Marketplace Evidence
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {Object.entries(recommendation.platform_prices_snapshot).map(([platform, item]: [string, any]) => (
              <div
                key={platform}
                className="p-3 rounded-lg bg-zinc-900/70 border border-white/5 flex items-center justify-between"
              >
                <div>
                  <div className="font-semibold text-sm text-white flex items-center gap-1.5">
                    {platform}
                    {item.verified && (
                      <CheckCircle2 size={13} className="text-emerald-400" />
                    )}
                  </div>
                  <div className="text-[11px] text-zinc-400">
                    Match Confidence: {Math.round((item.match_score || 0.9) * 100)}%
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-sm text-zinc-200">
                    {money(item.price || 0)}
                  </div>
                  {item.product_url && (
                    <a
                      href={item.product_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-0.5"
                    >
                      Inspect source <ExternalLink size={10} />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Human-in-the-Loop Actions */}
      {task.status === "succeeded" && onApprove && (
        <div className="pt-3 border-t border-white/10 flex items-center justify-between gap-3">
          {!rejecting ? (
            <>
              <Button
                variant="secondary"
                onClick={() => setRejecting(true)}
                disabled={isApproving}
                className="text-xs text-rose-400 hover:text-rose-300"
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
                className="flex-1 text-xs px-3 py-1.5 rounded bg-black/50 border border-white/10 text-white focus:outline-none focus:border-indigo-500"
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
