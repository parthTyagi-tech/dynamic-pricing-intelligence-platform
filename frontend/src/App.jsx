import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";

import {
  Suspense,
  lazy,
} from "react";

import {
  AuthProvider,
  useAuth,
} from "./context/AuthContext";

import ProtectedRoute from "./routes/ProtectedRoute";
import DashboardLayout from "./layouts/DashboardLayout";

/* =========================
   Lazy Loaded Pages
========================= */

const Login = lazy(() =>
  import("./pages/auth/Login")
);

const Signup = lazy(() =>
  import("./pages/auth/Signup")
);

const PremiumDashboardV2 = lazy(() =>
  import("./pages/KlypupDashboard")
);

const Products = lazy(() =>
  import("./pages/Products")
);

const Recommendations = lazy(() =>
  import("./pages/Recommendations")
);

const Approvals = lazy(() =>
  import("./pages/Approvals")
);

const AuditHistory = lazy(() =>
  import("./pages/AuditHistory")
);

const NotFound = lazy(() =>
  import("./pages/NotFound")
);

/* =========================
   Public Route Protection
========================= */

function PublicRoute({ children }) {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return (
      <Navigate
        to="/dashboard"
        replace
      />
    );
  }

  return children;
}

/* =========================
   Premium Global Loader
========================= */

function Loader() {
  return (
    <div
      className="
        min-h-screen
        flex
        items-center
        justify-center
        relative
        overflow-hidden
      "
      style={{
        background:
          "linear-gradient(135deg,#080b14 0%,#0f172a 45%,#0f766e 100%)",
      }}
    >
      {/* Background Glow */}
      <div
        style={{
          position: "absolute",
          width: 320,
          height: 320,
          borderRadius: "50%",
          background:
            "rgba(0,161,155,0.18)",
          filter: "blur(90px)",
          top: -80,
          right: -80,
        }}
      />

      <div
        style={{
          position: "absolute",
          width: 260,
          height: 260,
          borderRadius: "50%",
          background:
            "rgba(99,102,241,0.18)",
          filter: "blur(90px)",
          bottom: -60,
          left: -60,
        }}
      />

      {/* Loader Card */}
      <div
        className="
          relative
          z-10
          flex
          flex-col
          items-center
          gap-5
          px-10
          py-8
        "
        style={{
          borderRadius: 24,
          background:
            "rgba(12,16,32,0.82)",
          backdropFilter: "blur(14px)",
          border:
            "1px solid rgba(255,255,255,0.08)",
          boxShadow:
            "0 20px 60px rgba(0,0,0,0.45)",
        }}
      >
        {/* Animated Spinner */}
        <div
          style={{
            width: 54,
            height: 54,
            borderRadius: "50%",
            border:
              "4px solid rgba(255,255,255,0.08)",
            borderTop:
              "4px solid #00A19B",
            animation:
              "spin 1s linear infinite",
          }}
        />

        {/* Branding */}
        <div
          style={{
            textAlign: "center",
          }}
        >
          <h1
            style={{
              margin: 0,
              fontSize: "1.2rem",
              fontWeight: 700,
              color: "#ffffff",
            }}
          >
            Klypup AI
          </h1>

          <p
            style={{
              marginTop: 6,
              marginBottom: 0,
              fontSize: "0.82rem",
              color:
                "rgba(255,255,255,0.72)",
            }}
          >
            Loading workspace...
          </p>
        </div>
      </div>

      {/* Spinner Animation */}
      <style>
        {`
          @keyframes spin {
            to {
              transform: rotate(360deg);
            }
          }
        `}
      </style>
    </div>
  );
}

/* =========================
   Main App
========================= */

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<Loader />}>
          <Routes>

            {/* =====================
                Public Routes
            ====================== */}

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

            {/* =====================
                Protected Routes
            ====================== */}

            <Route
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route
                path="/dashboard"
                element={
                  <PremiumDashboardV2 />
                }
              />

              <Route
                path="/products"
                element={<Products />}
              />

              <Route
                path="/recommendations"
                element={
                  <Recommendations />
                }
              />

              <Route
                path="/approvals"
                element={<Approvals />}
              />

              <Route
                path="/audit-history"
                element={
                  <AuditHistory />
                }
              />
            </Route>

            {/* =====================
                Default Redirect
            ====================== */}

            <Route
              path="/"
              element={
                <Navigate
                  to="/dashboard"
                  replace
                />
              }
            />

            {/* =====================
                404 Page
            ====================== */}

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