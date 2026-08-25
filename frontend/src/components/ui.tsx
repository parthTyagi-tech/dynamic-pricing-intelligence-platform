import { AnimatePresence, motion } from "framer-motion";
import { Check, CircleAlert, Info, Loader2, X } from "lucide-react";
import { useCallback, useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "../lib/utils";

export function GlassCard({ children, className, glow = false }: { children: ReactNode; className?: string; glow?: boolean }) {
  return <motion.section whileHover={{ y: -2 }} transition={{ duration: 0.18 }} className={cn("glass-card", glow && "glass-card-glow", className)}>{children}</motion.section>;
}

export function Button({ children, className, variant = "primary", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  return <button className={cn("button", `button-${variant}`, className)} {...props}>{children}</button>;
}

export function Badge({ children, tone = "neutral", dot = false }: { children: ReactNode; tone?: "neutral" | "indigo" | "emerald" | "rose" | "violet" | "amber"; dot?: boolean }) {
  return <span className={cn("badge", `badge-${tone}`)}>{dot && <span className="badge-dot" />}{children}</span>;
}

export function SectionTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="section-title-row"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h2>{title}</h2>{description && <p className="section-description">{description}</p>}</div>{action}</div>;
}

export function Skeleton({ className = "" }: { className?: string }) { return <div className={cn("skeleton", className)} aria-hidden="true" />; }

export function LoadingPanel() { return <div className="loading-panel"><Loader2 className="spin" size={24} /><span>Syncing workspace intelligence…</span></div>; }

export type Toast = { id: number; tone: "success" | "error" | "info"; message: string };
export function ToastStack({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: number) => void }) {
  return <div className="toast-stack"><AnimatePresence>{toasts.map((toast) => <motion.div key={toast.id} initial={{ opacity: 0, x: 20, scale: .96 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: 20 }} className={cn("toast", `toast-${toast.tone}`)}>{toast.tone === "success" ? <Check size={16} /> : toast.tone === "error" ? <CircleAlert size={16} /> : <Info size={16} />}<span>{toast.message}</span><button type="button" className="toast-close" onClick={() => dismiss(toast.id)} aria-label="Dismiss notification"><X size={14} /></button></motion.div>)}</AnimatePresence></div>;
}

export function useToasts() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((message: string, tone: Toast["tone"] = "success") => { const id = Date.now(); setToasts((items) => [...items, { id, tone, message }]); window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 4200); }, []);
  const dismiss = useCallback((id: number) => setToasts((items) => items.filter((item) => item.id !== id)), []);
  return { toasts, push, dismiss };
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) { return <div className="empty-state"><div className="empty-icon"><Info size={18} /></div><h3>{title}</h3><p>{description}</p>{action}</div>; }

export function ErrorState({ retry }: { retry: () => void }) { return <div className="error-state"><CircleAlert size={20} /><div><strong>We couldn’t refresh this view.</strong><span>Fallback intelligence is still available.</span></div><Button variant="secondary" onClick={retry}>Try again</Button></div>; }

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) { return <button type="button" role="switch" aria-checked={checked} aria-label={label} className={cn("toggle", checked && "toggle-on")} onClick={onChange}><span /></button>; }

export function IconMark({ initials, color }: { initials: string; color?: string }) { return <span className="icon-mark" style={{ background: color }}>{initials}</span>; }
