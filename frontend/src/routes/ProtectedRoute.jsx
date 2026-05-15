import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * ProtectedRoute
 * Props:
 *   adminOnly  {boolean}  – restrict to admins only
 *   fallback   {JSX}      – custom loading UI
 */
export default function ProtectedRoute({ children, adminOnly = false, fallback }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();
  const location = useLocation();

  if (loading) return fallback ?? <AuthLoadingScreen />;

  if (!isAuthenticated)
    return <Navigate to="/login" state={{ from: location }} replace />;

  if (adminOnly && !isAdmin)
    return <Navigate to="/dashboard" replace />;

  return children;
}

/* ── Full-screen spinner shown while restoring session ───────────────── */
function AuthLoadingScreen() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "1rem",
        background: "var(--bg-primary, #080b14)",
      }}
    >
      <div style={{ position: "relative", width: 48, height: 48 }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            border: "2px solid rgba(255,255,255,0.08)",
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            border: "2px solid transparent",
            borderTopColor: "var(--accent-primary, #6366f1)",
            animation: "spin 0.8s linear infinite",
          }}
        />
      </div>
      <p
        style={{
          fontSize: "0.7rem",
          letterSpacing: "0.2em",
          textTransform: "uppercase",
          color: "var(--text-muted, #64748b)",
          fontFamily: "var(--font-mono, monospace)",
        }}
      >
        Authenticating
      </p>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}