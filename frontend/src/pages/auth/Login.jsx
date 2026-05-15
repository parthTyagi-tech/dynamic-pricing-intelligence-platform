import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, Lock, Eye, EyeOff, AlertCircle, ArrowRight, Zap } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

/* ── Motion variants ─────────────────────────────────────────────────── */
const containerV = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0.09, delayChildren: 0.1 } },
};
const itemV = {
  hidden:  { opacity: 0, y: 22, filter: "blur(8px)" },
  visible: { opacity: 1, y: 0,  filter: "blur(0px)",
             transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } },
};

/* ── Field ───────────────────────────────────────────────────────────── */
function Field({ label, id, type, value, onChange, placeholder, Icon, error, right }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <label htmlFor={id} style={{
        fontSize: "0.68rem", fontWeight: 600, letterSpacing: "0.14em",
        textTransform: "uppercase", color: "var(--text-muted)",
        fontFamily: "var(--font-mono)",
      }}>
        {label}
      </label>

      <div style={{ position: "relative" }}>
        {/* left icon */}
        <span style={{
          position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)",
          color: error ? "var(--accent-danger)" : "var(--text-muted)",
          pointerEvents: "none", display: "flex",
        }}>
          <Icon size={15} />
        </span>

        <input
          id={id} type={type} value={value}
          onChange={onChange} placeholder={placeholder}
          autoComplete={type === "password" ? "current-password" : "email"}
          style={{
            width: "100%", boxSizing: "border-box",
            padding: "12px 40px 12px 42px",
            borderRadius: 12,
            background: "rgba(255,255,255,0.04)",
            border: `1px solid ${error ? "var(--accent-danger)" : "var(--border-subtle, rgba(255,255,255,0.1))"}`,
            color: "var(--text-primary)", fontSize: "0.875rem",
            fontFamily: "var(--font-body)", outline: "none",
            transition: "border-color 0.2s, box-shadow 0.2s",
          }}
          onFocus={(e) => {
            e.target.style.borderColor = error ? "var(--accent-danger)" : "var(--accent-primary)";
            e.target.style.boxShadow   = error
              ? "0 0 0 3px color-mix(in srgb, var(--accent-danger) 18%, transparent)"
              : "0 0 0 3px color-mix(in srgb, var(--accent-primary) 18%, transparent)";
          }}
          onBlur={(e) => {
            e.target.style.borderColor = error ? "var(--accent-danger)" : "var(--border-subtle, rgba(255,255,255,0.1))";
            e.target.style.boxShadow   = "none";
          }}
        />

        {right && (
          <span style={{
            position: "absolute", right: 14, top: "50%", transform: "translateY(-50%)",
          }}>
            {right}
          </span>
        )}
      </div>

      <AnimatePresence mode="wait">
        {error && (
          <motion.p
            key="err"
            initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
            style={{ display: "flex", alignItems: "center", gap: 5,
                     fontSize: "0.72rem", color: "var(--accent-danger)", margin: 0 }}>
            <AlertCircle size={11} /> {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Login Page ──────────────────────────────────────────────────────── */
export default function Login() {
  const { login }   = useAuth();
  const navigate    = useNavigate();
  const location    = useLocation();
  const from        = location.state?.from?.pathname || "/dashboard";

  const [form, setForm]         = useState({ email: "", password: "" });
  const [errors, setErrors]     = useState({});
  const [showPw, setShowPw]     = useState(false);
  const [loading, setLoading]   = useState(false);
  const [apiError, setApiError] = useState("");

  const set = (field) => (e) => {
    setForm((f) => ({ ...f, [field]: e.target.value }));
    setErrors((er) => ({ ...er, [field]: "" }));
    setApiError("");
  };

  const validate = () => {
    const e = {};
    if (!form.email)                            e.email    = "Email is required";
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email    = "Invalid email address";
    if (!form.password)                         e.password = "Password is required";
    else if (form.password.length < 6)          e.password = "At least 6 characters";
    return e;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setLoading(true); setApiError("");
    try {
      await login(form);
      navigate(from, { replace: true });
    } catch (err) {
      setApiError(
        err.response?.data?.message ||
        err.response?.data?.error   ||
        "Invalid credentials. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center",
      justifyContent: "center", padding: 16, position: "relative",
      overflow: "hidden", background: "var(--bg-primary, #080b14)",
    }}>
      {/* Ambient orbs */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}>
        <div style={{
          position: "absolute", top: -160, left: -160, width: 420, height: 420,
          borderRadius: "50%", opacity: 0.18,
          background: "radial-gradient(circle, var(--accent-primary, #6366f1), transparent 70%)",
          filter: "blur(40px)",
        }} />
        <div style={{
          position: "absolute", bottom: -100, right: -100, width: 360, height: 360,
          borderRadius: "50%", opacity: 0.12,
          background: "radial-gradient(circle, var(--accent-secondary, #8b5cf6), transparent 70%)",
          filter: "blur(40px)",
        }} />
        {/* subtle grid */}
        <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0.025 }}>
          <defs>
            <pattern id="lg" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M40 0L0 0 0 40" fill="none" stroke="white" strokeWidth="0.6" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#lg)" />
        </svg>
      </div>

      {/* Card */}
      <motion.div
        variants={containerV} initial="hidden" animate="visible"
        style={{ position: "relative", width: "100%", maxWidth: 440 }}
      >
        {/* glow border layer */}
        <div style={{
          position: "absolute", inset: -1, borderRadius: 20, pointerEvents: "none",
          background: "linear-gradient(135deg, color-mix(in srgb, var(--accent-primary, #6366f1) 28%, transparent), transparent 55%, color-mix(in srgb, var(--accent-secondary, #8b5cf6) 18%, transparent))",
        }} />

        <div style={{
          position: "relative", borderRadius: 20, padding: 36,
          display: "flex", flexDirection: "column", gap: 28,
          background: "rgba(12, 16, 32, 0.88)",
          backdropFilter: "blur(28px)",
          border: "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
          boxShadow: "0 32px 80px rgba(0,0,0,0.55), inset 0 0 0 1px rgba(255,255,255,0.04)",
        }}>

          {/* Brand */}
          <motion.div variants={itemV} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, textAlign: "center" }}>
            <div style={{
              width: 48, height: 48, borderRadius: 14,
              background: "linear-gradient(135deg, var(--accent-primary, #6366f1), var(--accent-secondary, #8b5cf6))",
              boxShadow: "0 8px 28px color-mix(in srgb, var(--accent-primary, #6366f1) 45%, transparent)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Zap size={22} color="white" />
            </div>
            <div>
              <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--font-display)" }}>
                Klypup
              </div>
              <div style={{ fontSize: "0.65rem", letterSpacing: "0.2em", textTransform: "uppercase",
                            color: "var(--text-muted)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
                AI Pricing Intelligence
              </div>
            </div>
          </motion.div>

          {/* Heading */}
          <motion.div variants={itemV}>
            <h1 style={{ margin: 0, fontSize: "1.6rem", fontWeight: 700,
                         color: "var(--text-primary)", fontFamily: "var(--font-display)" }}>
              Welcome back
            </h1>
            <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "var(--text-muted)" }}>
              Sign in to your workspace
            </p>
          </motion.div>

          {/* Form */}
          <motion.form variants={itemV} onSubmit={handleSubmit} noValidate
                       style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            <Field label="Email" id="email" type="email" value={form.email}
                   onChange={set("email")} placeholder="you@company.com"
                   Icon={Mail} error={errors.email} />

            <Field label="Password" id="password"
                   type={showPw ? "text" : "password"}
                   value={form.password} onChange={set("password")}
                   placeholder="••••••••" Icon={Lock} error={errors.password}
                   right={
                     <button type="button" onClick={() => setShowPw((s) => !s)}
                             style={{ background: "none", border: "none", cursor: "pointer",
                                      color: "var(--text-muted)", display: "flex", padding: 0 }}>
                       {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                     </button>
                   } />

            {/* API error */}
            <AnimatePresence mode="wait">
              {apiError && (
                <motion.div key="apierr"
                  initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "10px 14px", borderRadius: 10, fontSize: "0.82rem",
                    background: "color-mix(in srgb, var(--accent-danger, #ef4444) 10%, transparent)",
                    border: "1px solid color-mix(in srgb, var(--accent-danger, #ef4444) 28%, transparent)",
                    color: "var(--accent-danger, #ef4444)",
                  }}>
                  <AlertCircle size={14} style={{ flexShrink: 0 }} />
                  {apiError}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Submit button */}
            <motion.button
              type="submit" disabled={loading}
              whileHover={{ scale: loading ? 1 : 1.015 }}
              whileTap={{ scale: loading ? 1 : 0.975 }}
              style={{
                width: "100%", padding: "13px 0", borderRadius: 12, border: "none",
                background: loading
                  ? "rgba(99,102,241,0.45)"
                  : "linear-gradient(135deg, var(--accent-primary, #6366f1), var(--accent-secondary, #8b5cf6))",
                boxShadow: loading ? "none" : "0 8px 26px color-mix(in srgb, var(--accent-primary, #6366f1) 38%, transparent)",
                color: "white", fontSize: "0.875rem", fontWeight: 600,
                fontFamily: "var(--font-body)", cursor: loading ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                transition: "background 0.2s, box-shadow 0.2s",
              }}>
              {loading ? (
                <>
                  <span style={{
                    width: 16, height: 16, borderRadius: "50%",
                    border: "2px solid rgba(255,255,255,0.25)",
                    borderTopColor: "white",
                    animation: "spin 0.7s linear infinite",
                    display: "inline-block",
                  }} />
                  Signing in…
                </>
              ) : (
                <> Sign in <ArrowRight size={15} /> </>
              )}
            </motion.button>
          </motion.form>

          {/* Footer */}
          <motion.p variants={itemV}
                    style={{ margin: 0, textAlign: "center", fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Don't have an account?{" "}
            <Link to="/signup" style={{ color: "var(--accent-primary, #6366f1)", fontWeight: 600, textDecoration: "none" }}>
              Create one
            </Link>
          </motion.p>
        </div>
      </motion.div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        input::placeholder { color: var(--text-muted, #64748b); opacity: 0.6; }
      `}</style>
    </div>
  );
}