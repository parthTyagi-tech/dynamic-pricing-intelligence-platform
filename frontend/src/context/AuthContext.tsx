import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getProfile, loginRequest, signupRequest } from "../services/api";
import type { User } from "../types/domain";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (payload: { name: string; email: string; password: string; organization: string }) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("klypup_token");
    if (!token) { setLoading(false); return; }
    if (token === "demo-token") {
      localStorage.removeItem("klypup_token");
      setLoading(false);
      return;
    }
    void getProfile().then(setUser).catch(() => localStorage.removeItem("klypup_token")).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const clear = () => { localStorage.removeItem("klypup_token"); setUser(null); };
    window.addEventListener("klypup:unauthorized", clear);
    return () => window.removeEventListener("klypup:unauthorized", clear);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const result = await loginRequest(email, password);
    if (!result.token) throw new Error("The server did not return a sign-in token.");
    localStorage.setItem("klypup_token", result.token);
    setUser(result.user);
    return result.user;
  }, []);

  const signup = useCallback(async (payload: { name: string; email: string; password: string; organization: string }) => {
    const result = await signupRequest(payload);
    if (!result.token) throw new Error("The server did not return an account token.");
    localStorage.setItem("klypup_token", result.token);
    setUser(result.user);
    return result.user;
  }, []);

  const logout = useCallback(() => { localStorage.removeItem("klypup_token"); setUser(null); }, []);
  const value = useMemo(() => ({ user, loading, isAuthenticated: Boolean(user), login, signup, logout }), [user, loading, login, signup, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
