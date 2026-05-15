import { motion } from 'framer-motion';
import { clsx } from 'clsx';

// ── Card ─────────────────────────────────────────────
export function Card({ children, className, hover = false, glow, onClick, animate = true }) {
  const Comp = animate ? motion.div : 'div';
  const props = animate ? {
    initial: { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.35, ease: 'easeOut' },
  } : {};

  return (
    <Comp
      {...props}
      onClick={onClick}
      className={clsx('glass p-5', hover && 'hover:border-accent-blue/20 transition-all cursor-pointer', glow && `glow-${glow}`, className)}
      style={{ transition: 'border-color 0.2s, box-shadow 0.2s' }}
    >
      {children}
    </Comp>
  );
}

// ── Stat Card ─────────────────────────────────────────
export function StatCard({ label, value, sub, icon: Icon, color = '#4facfe', trend, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: 'easeOut' }}
      className="glass p-5 relative overflow-hidden"
    >
      {/* bg accent */}
      <div className="absolute top-0 right-0 w-24 h-24 rounded-full opacity-5 -translate-y-6 translate-x-6"
        style={{ background: color, filter: 'blur(20px)' }} />
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)', letterSpacing: '0.1em' }}>{label}</p>
          <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{value}</p>
          {sub && <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{sub}</p>}
          {trend && (
            <p className="text-xs mt-1 font-medium" style={{ color: trend > 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
              {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}% vs last week
            </p>
          )}
        </div>
        {Icon && (
          <div className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
            <Icon size={18} style={{ color }} />
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ── Badge ─────────────────────────────────────────────
export function Badge({ children, variant = 'gray', dot = false }) {
  return (
    <span className={`badge badge-${variant}`}>
      {dot && <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: 'currentColor' }} />}
      {children}
    </span>
  );
}

// ── Confidence Bar ────────────────────────────────────
export function ConfidenceBar({ score, showLabel = true, height = 6 }) {
  const pct = Math.round((score ?? 0) * 100);
  const color = pct >= 85 ? 'var(--accent-green)' : pct >= 70 ? 'var(--accent-amber)' : 'var(--accent-red)';
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 rounded-full overflow-hidden" style={{ height, background: 'rgba(255,255,255,0.06)' }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
      {showLabel && <span className="text-xs font-mono font-semibold w-9 text-right" style={{ color }}>{pct}%</span>}
    </div>
  );
}

// ── Button ────────────────────────────────────────────
export function Button({ children, variant = 'primary', size = 'md', onClick, disabled, loading, className, type = 'button' }) {
  const sizes = { sm: 'px-3 py-1.5 text-xs', md: 'px-4 py-2 text-sm', lg: 'px-6 py-3 text-base' };
  const variants = {
    primary: 'text-white font-semibold',
    ghost: 'font-medium hover:bg-white/5',
    danger: 'font-semibold',
    outline: 'font-medium border',
  };

  const baseStyle = {
    primary: { background: 'var(--gradient-primary)', border: 'none' },
    ghost: { background: 'transparent', color: 'var(--text-secondary)', border: '1px solid transparent' },
    danger: { background: 'rgba(248,113,113,0.15)', color: 'var(--accent-red)', border: '1px solid rgba(248,113,113,0.3)' },
    outline: { background: 'transparent', color: 'var(--text-primary)', borderColor: 'var(--border)' },
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={clsx('rounded-lg flex items-center gap-2 transition-all duration-200', sizes[size], variants[variant], disabled && 'opacity-50 cursor-not-allowed', className)}
      style={baseStyle[variant]}
    >
      {loading && <span className="w-3.5 h-3.5 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'currentColor', borderTopColor: 'transparent' }} />}
      {children}
    </button>
  );
}

// ── Input ─────────────────────────────────────────────
export function Input({ label, error, className, icon: Icon, ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</label>}
      <div className="relative">
        {Icon && <Icon size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />}
        <input
          {...props}
          className={clsx('w-full rounded-lg text-sm outline-none transition-all', Icon ? 'pl-9 pr-3 py-2.5' : 'px-3 py-2.5', className)}
          style={{ background: 'var(--bg-glass)', border: `1px solid ${error ? 'var(--accent-red)' : 'var(--border)'}`, color: 'var(--text-primary)' }}
        />
      </div>
      {error && <p className="text-xs" style={{ color: 'var(--accent-red)' }}>{error}</p>}
    </div>
  );
}

// ── Textarea ──────────────────────────────────────────
export function Textarea({ label, error, className, ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</label>}
      <textarea
        {...props}
        rows={3}
        className={clsx('w-full rounded-lg text-sm outline-none resize-none transition-all px-3 py-2.5', className)}
        style={{ background: 'var(--bg-glass)', border: `1px solid ${error ? 'var(--accent-red)' : 'var(--border)'}`, color: 'var(--text-primary)' }}
      />
      {error && <p className="text-xs" style={{ color: 'var(--accent-red)' }}>{error}</p>}
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────
export function Skeleton({ className }) {
  return <div className={clsx('skeleton', className)} />;
}

// ── Empty State ───────────────────────────────────────
export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      {Icon && (
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)' }}>
          <Icon size={28} style={{ color: 'var(--text-muted)' }} />
        </div>
      )}
      <div className="text-center">
        <p className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>{title}</p>
        {description && <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{description}</p>}
      </div>
      {action}
    </div>
  );
}

// ── Divider ───────────────────────────────────────────
export function Divider() {
  return <div className="my-4" style={{ borderTop: '1px solid var(--border)' }} />;
}