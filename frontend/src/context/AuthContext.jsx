import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { apiClient } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]         = useState(null);
  const [token, setToken]       = useState(() => localStorage.getItem("klypup_token"));
  const [loading, setLoading]   = useState(true);

  /* ── Restore session on mount ─────────────────────────────────── */
  useEffect(() => {
    const restore = async () => {
      const stored = localStorage.getItem("klypup_token");
      if (!stored) { setLoading(false); return; }
      try {
        const { data } = await apiClient.get("/auth/profile");
        setUser(data.user ?? data);
        setToken(stored);
      } catch {
        _clear();
      } finally {
        setLoading(false);
      }
    };
    restore();
  }, []);

  const _persist = (tok, userData) => {
    localStorage.setItem("klypup_token", tok);
    setToken(tok);
    setUser(userData);
  };

  const _clear = () => {
    localStorage.removeItem("klypup_token");
    setToken(null);
    setUser(null);
  };

  /* ── Auth actions ─────────────────────────────────────────────── */
  const login = useCallback(async ({ email, password }) => {
    const { data } = await apiClient.post("/auth/login", { email, password });
    _persist(data.token ?? data.access_token, data.user ?? data);
    return data;
  }, []);

  const signup = useCallback(async ({ name, email, password, organization_name }) => {
    const { data } = await apiClient.post("/auth/register", {
      name, email, password, organization_name,
    });
    _persist(data.token ?? data.access_token, data.user ?? data);
    return data;
  }, []);

  const logout = useCallback(() => { _clear(); }, []);

  /* ── Listen for 401 events emitted by axios interceptor ──────── */
  useEffect(() => {
    const handler = () => _clear();
    window.addEventListener("klypup:unauthorized", handler);
    return () => window.removeEventListener("klypup:unauthorized", handler);
  }, []);

  const isAuthenticated = Boolean(token && user);
  const isAdmin         = isAuthenticated && (user?.role === "admin" || user?.is_admin === true);

  return (
    <AuthContext.Provider
      value={{ user, token, loading, isAuthenticated, isAdmin, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}