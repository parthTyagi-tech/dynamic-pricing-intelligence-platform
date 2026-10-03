import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  GitBranch,
  Globe2,
  LockKeyhole,
  Mail,
  Moon,
  Sparkles,
  Sun,
  UserRound,
  X,
  Zap,
} from "lucide-react";
import { FormEvent, useState, useEffect, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getCatalogProducts, isApiError, forgotPasswordRequest } from "../services/api";
import { useTheme } from "../context/ThemeContext";
import { Badge, Button, useToasts, ToastStack } from "../components/ui";

function getAuthErrorMessage(error: unknown) {
  if (isApiError(error)) {
    const payload = error.response?.data;
    if (typeof payload === "object" && payload !== null && "message" in payload) return String(payload.message);
    if (error.response?.status === 401) return "Invalid email or password.";
    if (error.response?.status === 404) return "No account was found for that email.";
    if (error.response?.status === 503) return "The pricing workspace is temporarily unavailable. Please try again shortly.";
  }
  return error instanceof Error ? error.message : "Unable to connect to the pricing workspace.";
}

export default function AuthPage({ defaultForgot = false }: { defaultForgot?: boolean }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, signup, loginWithGoogle } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const { toasts, push, dismiss } = useToasts();

  const [mode, setMode] = useState<"signin" | "signup">(location.pathname === "/signup" ? "signup" : "signin");
  const [showPassword, setShowPassword] = useState(false);
  const [forgotOpen, setForgotOpen] = useState(defaultForgot || location.pathname === "/forgot-password");
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotBusy, setForgotBusy] = useState(false);
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", organization: "Klypup Enterprise" });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const hiddenGoogleRef = useRef<HTMLDivElement>(null);

  const validate = () => {
    const next: Record<string, string> = {};
    if (mode === "signup" && form.name.trim().length < 2) next.name = "Enter your full name.";
    if (!/^\S+@\S+\.\S+$/.test(form.email)) next.email = "Use a valid work email.";
    if (form.password.length < 6) next.password = "Use at least 6 characters.";
    setErrors(next);
    return !Object.keys(next).length;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!validate()) return;
    setBusy(true);
    try {
      const authenticatedUser = mode === "signin" ? await login(form.email, form.password) : await signup(form);
      const products = await getCatalogProducts().catch(() => []);
      navigate(products.length ? "/dashboard" : "/onboarding", { replace: true });
      if (!products.length && authenticatedUser.onboarding_completed) {
        push("Your workspace has no catalog records yet. Complete onboarding to continue.", "info");
      }
    } catch (error) {
      push(getAuthErrorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (next: "signin" | "signup") => {
    setMode(next);
    setErrors({});
    navigate(next === "signin" ? "/login" : "/signup", { replace: true });
  };

  const handleForgotSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!forgotEmail || !/^\S+@\S+\.\S+$/.test(forgotEmail)) {
      push("Please enter a valid work email.", "error");
      return;
    }
    setForgotBusy(true);
    try {
      const res = await forgotPasswordRequest(forgotEmail);
      push(res.message || "If that email exists, a secure reset link is on its way.", "success");
      setForgotOpen(false);
      setForgotEmail("");
    } catch (err) {
      push(getAuthErrorMessage(err), "error");
    } finally {
      setForgotBusy(false);
    }
  };

  // Google credential callback
  const handleGoogleCredentialResponse = useCallback(
    async (response: any) => {
      const token = response?.credential || response?.access_token;
      if (!token) {
        push("Google sign-in returned no credential.", "error");
        return;
      }
      setGoogleBusy(true);
      try {
        const authenticatedUser = await loginWithGoogle({ credential: response?.credential, token: response?.access_token });
        push(`Welcome back, ${authenticatedUser.name}!`, "success");
        const products = await getCatalogProducts().catch(() => []);
        navigate(products.length ? "/dashboard" : "/onboarding", { replace: true });
      } catch (error) {
        push(getAuthErrorMessage(error), "error");
      } finally {
        setGoogleBusy(false);
      }
    },
    [loginWithGoogle, navigate, push]
  );

  // Initialize Google Identity Services (GIS)
  useEffect(() => {
    const clientId =
      (import.meta.env.VITE_GOOGLE_CLIENT_ID as string) ||
      "795228555040-equthg6jmnl92mro4ad16ovqo1ki95h2.apps.googleusercontent.com";

    const initGsi = () => {
      const g = (window as any).google;
      if (!g?.accounts?.id) return;
      try {
        g.accounts.id.initialize({
          client_id: clientId,
          callback: handleGoogleCredentialResponse,
          auto_select: false,
          cancel_on_tap_outside: true,
        });
      } catch (err) {
        console.warn("[GSI] Init notice:", err);
      }
    };

    if ((window as any).google?.accounts?.id) {
      initGsi();
    } else {
      const interval = setInterval(() => {
        if ((window as any).google?.accounts?.id) {
          clearInterval(interval);
          initGsi();
        }
      }, 150);
      return () => clearInterval(interval);
    }
  }, [handleGoogleCredentialResponse]);

  // Listener for OAuth redirect / hash fragment callbacks
  useEffect(() => {
    if (window.location.hash) {
      const hash = window.location.hash.substring(1);
      const params = new URLSearchParams(hash);
      const idToken = params.get("id_token");
      const accessToken = params.get("access_token");
      if (idToken || accessToken) {
        window.history.replaceState(null, "", window.location.pathname);
        setGoogleBusy(true);
        loginWithGoogle({ credential: idToken || undefined, token: accessToken || undefined })
          .then(async (user) => {
            push(`Welcome back, ${user.name}!`, "success");
            const products = await getCatalogProducts().catch(() => []);
            navigate(products.length ? "/dashboard" : "/onboarding", { replace: true });
          })
          .catch((err) => push(getAuthErrorMessage(err), "error"))
          .finally(() => setGoogleBusy(false));
      }
    }
  }, [loginWithGoogle, navigate, push]);

  // Trigger Google Sign-In
  const handleGoogleClick = () => {
    if (busy || googleBusy) return;
    setGoogleBusy(true);

    const clientId =
      (import.meta.env.VITE_GOOGLE_CLIENT_ID as string) ||
      "795228555040-equthg6jmnl92mro4ad16ovqo1ki95h2.apps.googleusercontent.com";

    const g = (window as any).google;

    // 1. If Google OAuth2 Token Client is available, launch the account chooser popup
    if (g?.accounts?.oauth2?.initTokenClient) {
      try {
        const client = g.accounts.oauth2.initTokenClient({
          client_id: clientId,
          scope: "openid email profile",
          callback: async (tokenResponse: any) => {
            if (tokenResponse?.error) {
              setGoogleBusy(false);
              if (tokenResponse.error !== "popup_closed_by_user") {
                push(`Google sign-in notice: ${tokenResponse.error}`, "info");
              }
              return;
            }
            if (tokenResponse?.access_token) {
              try {
                const authenticatedUser = await loginWithGoogle({ token: tokenResponse.access_token });
                push(`Welcome back, ${authenticatedUser.name}!`, "success");
                const products = await getCatalogProducts().catch(() => []);
                navigate(products.length ? "/dashboard" : "/onboarding", { replace: true });
              } catch (err) {
                push(getAuthErrorMessage(err), "error");
              } finally {
                setGoogleBusy(false);
              }
            }
          },
        });
        client.requestAccessToken({ prompt: "select_account" });
        return;
      } catch (err) {
        console.warn("initTokenClient failed, launching redirect fallback:", err);
      }
    }

    // 2. Direct OAuth 2.0 authorization redirect fallback
    const redirectUri = window.location.origin;
    const oauthUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${encodeURIComponent(
      clientId
    )}&redirect_uri=${encodeURIComponent(
      redirectUri
    )}&response_type=token%20id_token&scope=openid%20email%20profile&nonce=${Date.now()}&prompt=select_account`;
    window.location.href = oauthUrl;
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
            <strong>
              KLYPUP<span>AI</span>
            </strong>
            <small>PRICING INTELLIGENCE</small>
          </span>
        </div>
        <div className="auth-visual-copy">
          <Badge tone="indigo" dot>
            Decision intelligence, refined
          </Badge>
          <h1>
            Move with the market.
            <br />
            <em>Lead with the signal.</em>
          </h1>
          <p>
            Premium pricing intelligence for teams that want to turn every price point into a strategic advantage.
          </p>
        </div>
        <div className="auth-signal-grid">
          <div>
            <Zap size={16} />
            <span>1,284</span>
            <small>SKUs repriced</small>
          </div>
          <div>
            <Sparkles size={16} />
            <span>+7.8%</span>
            <small>margin lift</small>
          </div>
          <div>
            <Globe2 size={16} />
            <span>94.2%</span>
            <small>forecast confidence</small>
          </div>
        </div>
        <div className="auth-quote">
          “Klypup gives our operators the clarity to move quickly, without losing the story behind the decision.”
          <small>— Maya Chen, VP Growth at Northline</small>
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
            <strong>
              KLYPUP<span>AI</span>
            </strong>
          </div>

          <div className="auth-heading">
            <p className="eyebrow">Welcome to the workspace</p>
            <h2>{mode === "signin" ? "Good to see you again." : "Build your intelligence layer."}</h2>
            <p>
              {mode === "signin"
                ? "Sign in to continue managing your pricing system."
                : "Create your workspace and start making sharper pricing decisions."}
            </p>
          </div>

          <div className="auth-tabs">
            <button
              type="button"
              className={mode === "signin" ? "active" : ""}
              onClick={() => switchMode("signin")}
            >
              Sign in
            </button>
            <button
              type="button"
              className={mode === "signup" ? "active" : ""}
              onClick={() => switchMode("signup")}
            >
              Create account
            </button>
          </div>

          <form onSubmit={submit} className="auth-form">
            {mode === "signup" && (
              <label className="field">
                <span>Full name</span>
                <div className="field-input">
                  <UserRound size={16} />
                  <input
                    value={form.name}
                    onChange={(event) => setForm({ ...form, name: event.target.value })}
                    placeholder="Kiran Evans"
                  />
                </div>
                {errors.name && <small className="field-error">{errors.name}</small>}
              </label>
            )}

            <label className="field">
              <span>Work email</span>
              <div className="field-input">
                <Mail size={16} />
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm({ ...form, email: event.target.value })}
                  placeholder="you@company.com"
                />
              </div>
              {errors.email && <small className="field-error">{errors.email}</small>}
            </label>

            {mode === "signup" && (
              <label className="field">
                <span>Organization</span>
                <div className="field-input">
                  <Globe2 size={16} />
                  <input
                    value={form.organization}
                    onChange={(event) => setForm({ ...form, organization: event.target.value })}
                    placeholder="Company name"
                  />
                </div>
              </label>
            )}

            <label className="field">
              <span>Password</span>
              <div className="field-input">
                <LockKeyhole size={16} />
                <input
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                  onChange={(event) => setForm({ ...form, password: event.target.value })}
                  placeholder="••••••••"
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
              {errors.password && <small className="field-error">{errors.password}</small>}
            </label>

            {mode === "signin" && (
              <div className="form-options">
                <label className="remember">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(event) => setRemember(event.target.checked)}
                  />
                  <span>Remember me</span>
                </label>
                <button
                  type="button"
                  className="text-button forgot-password-btn"
                  onClick={() => setForgotOpen(true)}
                >
                  Forgot password?
                </button>
              </div>
            )}

            <Button type="submit" disabled={busy} className="auth-submit">
              {busy ? (
                "Connecting…"
              ) : mode === "signin" ? (
                <>
                  Enter command center <ArrowRight size={16} />
                </>
              ) : (
                <>
                  Create workspace <ArrowRight size={16} />
                </>
              )}
            </Button>
          </form>

          <div className="divider">
            <span>or continue with</span>
          </div>

          <div className="oauth-grid">
            <Button
              variant="secondary"
              onClick={handleGoogleClick}
              disabled={busy || googleBusy}
            >
              <span className="oauth-google">G</span>{" "}
              {googleBusy ? "Connecting…" : "Google"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => push("GitHub connection is ready for your workspace.", "info")}
            >
              <GitBranch size={16} /> GitHub
            </Button>
          </div>

          <p className="auth-legal">
            By continuing, you agree to Klypup’s{" "}
            <button type="button" className="text-button">
              Terms
            </button>{" "}
            and{" "}
            <button type="button" className="text-button">
              Privacy Policy
            </button>
            .
          </p>
        </div>
      </div>

      <AnimatePresence>
        {forgotOpen && (
          <div className="drawer-backdrop" onClick={() => setForgotOpen(false)}>
            <motion.aside
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              className="reset-drawer"
              onClick={(event) => event.stopPropagation()}
            >
              <button
                className="icon-button drawer-close"
                onClick={() => setForgotOpen(false)}
                aria-label="Close reset drawer"
              >
                <X size={18} />
              </button>
              <p className="eyebrow">Account recovery</p>
              <h2>Reset your password.</h2>
              <p>Enter your work email and we’ll send a secure reset link.</p>
              <form onSubmit={handleForgotSubmit}>
                <div className="field">
                  <span>Work email</span>
                  <div className="field-input">
                    <Mail size={16} />
                    <input
                      type="email"
                      required
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                      placeholder="you@company.com"
                    />
                  </div>
                </div>
                <Button type="submit" disabled={forgotBusy}>
                  {forgotBusy ? (
                    "Sending link…"
                  ) : (
                    <>
                      <Check size={16} /> Send reset link
                    </>
                  )}
                </Button>
              </form>
            </motion.aside>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
