import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, Eye, EyeOff, LockKeyhole, Moon, ShieldCheck, Sparkles, Sun, AlertTriangle } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { Badge, Button, useToasts, ToastStack } from "../components/ui";
import { resetPasswordRequest, isApiError } from "../services/api";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";

  const { isDark, toggleTheme } = useTheme();
  const { toasts, push, dismiss } = useToasts();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    if (!token) {
      setErrorMsg("Missing or invalid password reset token. Please request a new link.");
      return;
    }

    if (password.length < 6) {
      setErrorMsg("Password must be at least 6 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setErrorMsg("Passwords do not match. Please verify both fields.");
      return;
    }

    setBusy(true);
    try {
      const res = await resetPasswordRequest(token, password);
      setSuccess(true);
      push(res.message || "Password reset successfully! Redirecting to sign in...", "success");
      setTimeout(() => {
        navigate("/login", { replace: true });
      }, 2000);
    } catch (err) {
      let msg = "Failed to reset password. The link may have expired.";
      if (isApiError(err)) {
        const payload = err.response?.data as { message?: string } | undefined;
        if (payload?.message) {
          msg = String(payload.message);
        }
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setErrorMsg(msg);
      push(msg, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`auth-page ${isDark ? "theme-dark" : "theme-light"}`}>
      <ToastStack toasts={toasts} dismiss={dismiss} />

      <div className="auth-visual">
        <div className="auth-orb auth-orb-one" />
        <div className="auth-orb auth-orb-two" />
        <div className="auth-grid" />
        <div className="auth-brand">
          <span className="brand-glyph">
            <Sparkles size={18} />
          </span>
          <span>
            <strong>KLYPUP<span>AI</span></strong>
            <small>PRICING INTELLIGENCE</small>
          </span>
        </div>
        <div className="auth-visual-copy">
          <Badge tone="indigo" dot>
            Cryptographic Access Recovery
          </Badge>
          <h1>
            Restore control.<br />
            <em>Protect the perimeter.</em>
          </h1>
          <p>
            Secure, tokenized credentials recovery powered by HMAC URLSafe time-limited signatures.
          </p>
        </div>
        <div className="auth-signal-grid">
          <div>
            <ShieldCheck size={16} />
            <span>256-bit</span>
            <small>HMAC Token</small>
          </div>
          <div>
            <LockKeyhole size={16} />
            <span>60 min</span>
            <small>Token Validity</small>
          </div>
          <div>
            <Sparkles size={16} />
            <span>Bcrypt</span>
            <small>Salted Storage</small>
          </div>
        </div>
        <div className="auth-quote">
          “Every credential rotation is recorded into the immutable audit ledger to ensure complete organizational governance.”
          <small>— Klypup Security Architecture</small>
        </div>
      </div>

      <div className="auth-form-side">
        <button
          type="button"
          className="auth-theme-toggle button button-secondary"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {isDark ? <Sun size={15} /> : <Moon size={15} />}
          <span>{isDark ? "Light" : "Dark"}</span>
        </button>

        <div className="auth-form-wrap">
          <div className="mobile-auth-brand">
            <span className="brand-glyph">
              <Sparkles size={18} />
            </span>
            <strong>KLYPUP<span>AI</span></strong>
          </div>

          <div className="auth-heading">
            <p className="eyebrow">Credential Management</p>
            <h2>Create a new password.</h2>
            <p>Enter your new secure password to restore workspace access.</p>
          </div>

          {!token ? (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <div style={{ display: "inline-flex", padding: 12, borderRadius: "50%", background: "rgba(239, 68, 68, 0.1)", color: "#ef4444", marginBottom: 16 }}>
                <AlertTriangle size={32} />
              </div>
              <h3 style={{ fontSize: 18, marginBottom: 8, color: "var(--text-primary, var(--text))" }}>Missing Reset Token</h3>
              <p style={{ color: "var(--text-secondary, #94a3b8)", fontSize: 14, marginBottom: 24, lineHeight: 1.5 }}>
                No secure recovery token was detected in the URL. Please check the email link or request a new one.
              </p>
              <Link to="/login">
                <Button variant="secondary">
                  Back to Sign In <ArrowRight size={16} />
                </Button>
              </Link>
            </div>
          ) : success ? (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <div style={{ display: "inline-flex", padding: 12, borderRadius: "50%", background: "rgba(16, 185, 129, 0.1)", color: "#10b981", marginBottom: 16 }}>
                <CheckCircle2 size={32} />
              </div>
              <h3 style={{ fontSize: 18, marginBottom: 8, color: "var(--text-primary, var(--text))" }}>Password Updated</h3>
              <p style={{ color: "var(--text-secondary, #94a3b8)", fontSize: 14, marginBottom: 24, lineHeight: 1.5 }}>
                Your new password has been committed to the secure ledger. Redirecting you to the sign-in page...
              </p>
              <Button onClick={() => navigate("/login", { replace: true })}>
                Sign In Now <ArrowRight size={16} />
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="auth-form">
              {errorMsg && (
                <div style={{ padding: "12px 16px", borderRadius: 8, background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#fca5a5", fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
                  <AlertTriangle size={16} />
                  <span>{errorMsg}</span>
                </div>
              )}

              <label className="field">
                <span>New Password</span>
                <div className="field-input">
                  <LockKeyhole size={16} />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 6 characters"
                    required
                    minLength={6}
                  />
                  <button
                    type="button"
                    className="field-icon-action"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </label>

              <label className="field">
                <span>Confirm New Password</span>
                <div className="field-input">
                  <LockKeyhole size={16} />
                  <input
                    type={showConfirm ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat new password"
                    required
                    minLength={6}
                  />
                  <button
                    type="button"
                    className="field-icon-action"
                    onClick={() => setShowConfirm(!showConfirm)}
                    aria-label={showConfirm ? "Hide password" : "Show password"}
                  >
                    {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </label>

              <Button type="submit" disabled={busy} className="auth-submit">
                {busy ? "Updating Credentials…" : (
                  <>
                    Save New Password & Sign In <ArrowRight size={16} />
                  </>
                )}
              </Button>

              <div style={{ textAlign: "center", marginTop: 16 }}>
                <Link to="/login" className="text-button" style={{ fontSize: 13 }}>
                  Remembered your password? Sign in
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
