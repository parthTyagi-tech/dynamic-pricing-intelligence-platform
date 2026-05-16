import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Suspense, lazy } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";

import ProtectedRoute from "./routes/ProtectedRoute";
import DashboardLayout from "./layouts/DashboardLayout";

const Login = lazy(() => import("./pages/auth/Login"));
const Signup = lazy(() => import("./pages/auth/Signup"));

const KlypupDashboard = lazy(() =>
  import("./pages/KlypupDashboard")
);

const Products = lazy(() => import("./pages/Products"));
const Recommendations = lazy(() => import("./pages/Recommendations"));
const Approvals = lazy(() => import("./pages/Approvals"));
const AuditHistory = lazy(() => import("./pages/AuditHistory"));
const NotFound = lazy(() => import("./pages/NotFound"));

function PublicRoute({ children }) {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}

function Loader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#080b14] text-white">
      Loading...
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<Loader />}>
          <Routes>

            {/* Public Routes */}
            <Route
              path="/login"
              element={
                <PublicRoute>
                  <Login />
                </PublicRoute>
              }
            />

            <Route
              path="/signup"
              element={
                <PublicRoute>
                  <Signup />
                </PublicRoute>
              }
            />

            {/* Protected Routes */}
            <Route
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route
                path="/dashboard"
                element={<KlypupDashboard />}
              />

              <Route
                path="/products"
                element={<Products />}
              />

              <Route
                path="/recommendations"
                element={<Recommendations />}
              />

              <Route
                path="/approvals"
                element={<Approvals />}
              />

              <Route
                path="/audit-history"
                element={<AuditHistory />}
              />
            </Route>

            {/* Default Redirect */}
            <Route
              path="/"
              element={<Navigate to="/dashboard" replace />}
            />

            {/* 404 */}
            <Route
              path="*"
              element={<NotFound />}
            />

          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}