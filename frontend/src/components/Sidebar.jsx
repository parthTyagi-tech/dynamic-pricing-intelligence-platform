import {
  LayoutDashboard,
  Package,
  Sparkles,
  CheckCircle,
  History,
  LogOut,
  Zap,
  MessageSquare,
  Cpu,
  TrendingUp,
  Globe,
  ShoppingCart,
  CreditCard,
} from "lucide-react";

import { NavLink } from "react-router-dom";

import { motion } from "framer-motion";

import { useAuth } from "../context/AuthContext";

const navItems = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    path: "/dashboard",
  },

  {
    label: "Products",
    icon: Package,
    path: "/products",
  },

  {
    label: "Recommendations",
    icon: Sparkles,
    path: "/recommendations",
  },

  {
    label: "Approvals",
    icon: CheckCircle,
    path: "/approvals",
  },

  {
    label: "Audit History",
    icon: History,
    path: "/audit-history",
  },

  {
    label: "AI Assistant",
    icon: MessageSquare,
    path: "/chat",
  },

  {
    label: "AI Observability",
    icon: Cpu,
    path: "/observability",
  },

  {
    label: "Pricing Backtester",
    icon: TrendingUp,
    path: "/backtesting",
  },

  {
    label: "Competitor Matcher",
    icon: Globe,
    path: "/competitor-matcher",
  },

  {
    label: "Integrations Hub",
    icon: ShoppingCart,
    path: "/integrations",
  },

  {
    label: "Plans & Billing",
    icon: CreditCard,
    path: "/billing",
  },
];

export default function Sidebar({
  collapsed = false,
}) {

  const { logout } = useAuth();

  return (

    <aside
      className={`
        h-screen
        flex
        flex-col
        relative
        overflow-hidden
        transition-all
        duration-300
        border-r
        border-white/10
        backdrop-blur-xl
        ${
          collapsed
            ? "w-16"
            : "w-64"
        }
      `}
      style={{
        background:
          "rgba(8,11,20,0.72)",

        boxShadow:
          "0 20px 60px rgba(0,0,0,0.35)",
      }}
    >

      {/* BACKGROUND GLOW */}

      <div
        style={{
          position: "absolute",
          width: 220,
          height: 220,
          borderRadius: "50%",
          background:
            "rgba(0,161,155,0.10)",

          filter: "blur(80px)",

          top: -60,
          right: -60,

          pointerEvents: "none",
        }}
      />

      {/* LOGO SECTION */}

      <div
        className="
          relative
          z-10
          px-4
          py-5
          border-b
          border-white/8
        "
      >

        <div
          className={`
            flex
            items-center
            ${
              collapsed
                ? "justify-center"
                : "gap-3"
            }
          `}
        >

          {/* LOGO */}

          <motion.div
            whileHover={{
              scale: 1.05,
            }}

            className="
              w-10
              h-10
              rounded-2xl
              flex
              items-center
              justify-center
              shadow-lg
            "

            style={{
              background:
                "linear-gradient(135deg,#00A19B,#6366f1)",
            }}
          >

            <Zap
              size={18}
              className="text-white"
            />

          </motion.div>

          {/* BRANDING */}

          {!collapsed && (

            <div>

              <h1
                className="
                  text-white
                  text-xl
                  font-bold
                  tracking-tight
                "
              >

                Klypup

              </h1>

              <p
                className="
                  text-xs
                  text-slate-400
                  mt-0.5
                "
              >

                AI Pricing Intelligence

              </p>

            </div>
          )}

        </div>

      </div>

      {/* NAVIGATION */}

      <nav
        className="
          flex-1
          px-3
          py-4
          space-y-1.5
          relative
          z-10
        "
      >

        {navItems.map((item) => {

          const Icon = item.icon;

          return (

            <NavLink
              key={item.path}

              to={item.path}

              className={({ isActive }) => `
                group
                relative
                flex
                items-center
                ${
                  collapsed
                    ? "justify-center"
                    : "gap-3"
                }
                px-3
                py-3
                rounded-2xl
                transition-all
                duration-200
                overflow-hidden

                ${
                  isActive

                    ? `
                      bg-gradient-to-r
                      from-[#00A19B]/20
                      to-[#6366f1]/20
                      text-white
                      border
                      border-white/10
                      shadow-lg
                    `

                    : `
                      text-slate-400
                      hover:bg-white/5
                      hover:text-white
                    `
                }
              `}
            >

              {/* ACTIVE GLOW */}

              <div
                className="
                  absolute
                  inset-0
                  opacity-0
                  group-hover:opacity-100
                  transition-opacity
                  duration-300
                "

                style={{
                  background:
                    "linear-gradient(135deg,rgba(0,161,155,0.06),rgba(99,102,241,0.06))",
                }}
              />

              {/* ICON */}

              <div className="relative z-10">

                <Icon size={18} />

              </div>

              {/* LABEL */}

              {!collapsed && (

                <span
                  className="
                    relative
                    z-10
                    text-sm
                    font-medium
                  "
                >

                  {item.label}

                </span>
              )}

            </NavLink>
          );
        })}

      </nav>

      {/* FOOTER */}

      <div
        className="
          p-3
          border-t
          border-white/8
          relative
          z-10
        "
      >

        <button
          onClick={logout}

          className={`
            w-full
            flex
            items-center
            ${
              collapsed
                ? "justify-center"
                : "justify-center gap-2"
            }
            px-4
            py-3
            rounded-2xl
            transition-all
            duration-200
            text-red-400
            hover:text-red-300
            hover:bg-red-500/10
            border
            border-transparent
            hover:border-red-500/20
          `}
        >

          <LogOut size={16} />

          {!collapsed && (
            <span
              className="
                text-sm
                font-medium
              "
            >

              Logout

            </span>
          )}

        </button>

      </div>

    </aside>
  );
}