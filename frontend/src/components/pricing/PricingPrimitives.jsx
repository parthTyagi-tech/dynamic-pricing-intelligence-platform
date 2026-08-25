import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Check, ChevronRight, CircleAlert, Info, Sparkles } from "lucide-react";

export function Panel({ children, className = "", glow = false, ...props }) {
  return (
    <motion.section
      whileHover={{ y: -1 }}
      transition={{ duration: 0.18 }}
      className={`obsidian-panel ${glow ? "obsidian-panel-glow" : ""} ${className}`}
      {...props}
    >
      {children}
    </motion.section>
  );
}

export function Eyebrow({ children, tone = "cyan" }) {
  return <span className={`eyebrow eyebrow-${tone}`}>{children}</span>;
}

export function SectionHeader({ eyebrow, title, description, action }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
        <h2 className="section-title">{title}</h2>
        {description && <p className="section-description">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatusBadge({ children, tone = "neutral", dot = true }) {
  return (
    <span className={`status-badge status-${tone}`}>
      {dot && <span className="status-dot" />}
      {children}
    </span>
  );
}

export function IconButton({ children, label, className = "", ...props }) {
  return (
    <button type="button" aria-label={label} className={`icon-button ${className}`} {...props}>
      {children}
    </button>
  );
}

export function PrimaryButton({ children, icon: Icon = ChevronRight, className = "", ...props }) {
  return (
    <button type="button" className={`primary-button ${className}`} {...props}>
      {children}
      <Icon size={15} strokeWidth={2.5} />
    </button>
  );
}

export function GhostButton({ children, icon: Icon, className = "", ...props }) {
  return (
    <button type="button" className={`ghost-button ${className}`} {...props}>
      {Icon && <Icon size={14} />}
      {children}
    </button>
  );
}

export function MetricCard({ label, value, detail, trend, icon: Icon, tone = "cyan", progress }) {
  const positive = trend >= 0;
  return (
    <Panel className="metric-card" glow={tone === "cyan"}>
      <div className="metric-card-top">
        <div className={`metric-icon metric-icon-${tone}`}><Icon size={17} /></div>
        <span className="metric-label">{label}</span>
        {trend !== undefined && (
          <span className={`metric-trend ${positive ? "trend-positive" : "trend-negative"}`}>
            {positive ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
            {Math.abs(trend).toFixed(1)}%
          </span>
        )}
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
      {progress !== undefined && (
        <div className="metric-progress"><span style={{ width: `${Math.min(100, progress)}%` }} /></div>
      )}
    </Panel>
  );
}

export function ProgressRing({ value, label, tone = "cyan" }) {
  const radius = 35;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(100, value) / 100) * circumference;
  return (
    <div className="ring-wrap">
      <svg viewBox="0 0 84 84" className={`progress-ring progress-ring-${tone}`} role="img" aria-label={`${label}: ${value}%`}>
        <circle className="ring-track" cx="42" cy="42" r={radius} />
        <circle className="ring-value" cx="42" cy="42" r={radius} strokeDasharray={circumference} strokeDashoffset={offset} />
      </svg>
      <div className="ring-copy"><strong>{value}%</strong><span>{label}</span></div>
    </div>
  );
}

export function EmptyState({ icon: Icon = Sparkles, title, description, action }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon size={22} /></div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function SeverityIcon({ severity }) {
  if (severity === "CRITICAL") return <CircleAlert size={15} />;
  if (severity === "WARNING") return <CircleAlert size={15} />;
  return <Info size={15} />;
}

export function Toggle({ checked, onChange, label }) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={checked}
      className={`toggle ${checked ? "toggle-on" : ""}`}
      onClick={() => onChange(!checked)}
    >
      <span />
    </button>
  );
}

export function ApprovalAction({ approved, loading, onClick }) {
  return (
    <button type="button" className={`approval-button ${approved ? "is-approved" : ""}`} disabled={loading || approved} onClick={onClick}>
      {approved ? <Check size={13} /> : loading ? <span className="mini-spinner" /> : <Check size={13} />}
      {approved ? "Approved" : "Approve"}
    </button>
  );
}
