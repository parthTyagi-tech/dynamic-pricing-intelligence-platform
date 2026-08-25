import { Component, type ErrorInfo, type ReactNode } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { AppShell } from "./components/AppShell";
import { Button, GlassCard, ToastStack, useToasts } from "./components/ui";
import AuthPage from "./pages/AuthPage";
import CompetitorsPage from "./pages/CompetitorsPage";
import DashboardPage from "./pages/DashboardPage";
import PricingPage from "./pages/PricingPage";
import SecondaryPage from "./pages/SecondaryPage";
import SettingsPage from "./pages/SettingsPage";
import ScraperHubPage from "./pages/ScraperHubPage";

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error("Klypup UI error", error, info); }
  render() { if (this.state.hasError) return <div className="fatal-state"><GlassCard><p className="eyebrow">Recovery mode</p><h1>Something interrupted the workspace.</h1><p>Refresh the view to reconnect your pricing intelligence.</p><Button onClick={() => window.location.reload()}>Reload workspace</Button></GlassCard></div>; return this.props.children; }
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="page-loading"><div className="loading-orb" /><p>Restoring secure workspace…</p></div>;
  return user ? <>{children}</> : <Navigate to="/login" replace state={{ from: location.pathname }} />;
}

function ProtectedLayout({ onToast }: { onToast: (message: string) => void }) {
  return <ProtectedRoute><AppShell onToast={onToast}><Outlet /></AppShell></ProtectedRoute>;
}

function AppRoutes() {
  const { push, toasts, dismiss } = useToasts();
  return <><Routes><Route path="/login" element={<AuthPage />} /><Route path="/signup" element={<AuthPage />} /><Route element={<ProtectedLayout onToast={(message) => push(message)} />}><Route index element={<Navigate to="/dashboard" replace />} /><Route path="/dashboard" element={<DashboardPage />} /><Route path="/catalog" element={<SecondaryPage kind="catalog" />} /><Route path="/approvals" element={<SecondaryPage kind="approvals" />} /><Route path="/agents" element={<SecondaryPage kind="agents" />} /><Route path="/pricing" element={<PricingPage />} /><Route path="/competitors" element={<CompetitorsPage />} /><Route path="/scrapers" element={<ScraperHubPage />} /><Route path="/settings" element={<SettingsPage />} /><Route path="*" element={<Navigate to="/dashboard" replace />} /></Route></Routes><ToastStack toasts={toasts} dismiss={dismiss} /></>;
}

export default function App() { return <ErrorBoundary><AuthProvider><BrowserRouter><AppRoutes /></BrowserRouter></AuthProvider></ErrorBoundary>; }
