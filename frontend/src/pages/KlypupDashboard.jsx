import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  BarChart3,
  Globe,
  Target,
  FileText,
  Settings,
  Search,
  ChevronRight,
  ChevronLeft,
  Zap,
  Activity,
  DollarSign,
  Brain,
  ShoppingCart,
  SlidersHorizontal,
} from "lucide-react";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const revenueData = [
  { t: "Jan", rev: 42000 },
  { t: "Feb", rev: 51000 },
  { t: "Mar", rev: 47000 },
  { t: "Apr", rev: 63000 },
  { t: "May", rev: 71000 },
  { t: "Jun", rev: 68000 },
];

const navItems = [
  {
    icon: LayoutDashboard,
    label: "Dashboard",
  },
  {
    icon: BarChart3,
    label: "Analytics",
  },
  {
    icon: Brain,
    label: "AI Engine",
  },
  {
    icon: SlidersHorizontal,
    label: "Dynamic Pricing",
  },
  {
    icon: Globe,
    label: "Market Insights",
  },
  {
    icon: Target,
    label: "Competitor Tracking",
  },
  {
    icon: FileText,
    label: "Reports",
  },
  {
    icon: Settings,
    label: "Settings",
  },
];

function useCounter(target, duration = 1500) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let start = 0;

    const increment =
      target / (duration / 16);

    const timer = setInterval(() => {
      start += increment;

      if (start >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 16);

    return () => clearInterval(timer);
  }, [target, duration]);

  return count;
}

function MetricCard({
  icon: Icon,
  label,
  value,
  unit = "",
  change,
  color,
}) {
  const animatedValue =
    useCounter(value);

  return (
    <div
      style={{
        background:
          "rgba(255,255,255,0.03)",
        border:
          "1px solid rgba(255,255,255,0.08)",
        borderRadius: 18,
        padding: 22,
      }}
    >
      <div
        style={{
          width: 42,
          height: 42,
          borderRadius: 12,
          background: `${color}22`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 14,
        }}
      >
        <Icon
          size={18}
          style={{ color }}
        />
      </div>

      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          color: "#fff",
        }}
      >
        {animatedValue}
        {unit}
      </div>

      <div
        style={{
          color:
            "rgba(255,255,255,0.5)",
          marginTop: 6,
          fontSize: 13,
        }}
      >
        {label}
      </div>

      <div
        style={{
          marginTop: 10,
          color: "#34d399",
          fontSize: 12,
        }}
      >
        {change}
      </div>
    </div>
  );
}

function Sidebar({
  collapsed,
  setCollapsed,
  activePage,
  setActivePage,
}) {
  return (
    <aside
      style={{
        width: collapsed ? 70 : 220,
        minHeight: "100vh",
        background:
          "rgba(8,8,20,0.95)",
        borderRight:
          "1px solid rgba(255,255,255,0.06)",
        padding: "20px 10px",
        transition: "0.3s",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 30,
          paddingLeft: 10,
        }}
      >
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: 12,
            background:
              "linear-gradient(135deg,#6366f1,#a855f7)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Zap size={18} color="#fff" />
        </div>

        {!collapsed && (
          <div>
            <div
              style={{
                color: "#fff",
                fontWeight: 700,
              }}
            >
              Klypup
            </div>

            <div
              style={{
                fontSize: 11,
                color: "#818cf8",
              }}
            >
              AI Pricing
            </div>
          </div>
        )}
      </div>

      <nav
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        {navItems.map(
          ({ icon: Icon, label }) => {
            const active =
              activePage === label;

            return (
              <button
                key={label}
                onClick={() =>
                  setActivePage(label)
                }
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  border: "none",
                  cursor: "pointer",
                  borderRadius: 12,
                  padding: "12px",
                  background: active
                    ? "rgba(129,140,248,0.15)"
                    : "transparent",
                  color: active
                    ? "#a5b4fc"
                    : "rgba(255,255,255,0.5)",
                  textAlign: "left",
                }}
              >
                <Icon size={18} />

                {!collapsed && (
                  <span>{label}</span>
                )}
              </button>
            );
          }
        )}
      </nav>

      <button
        onClick={() =>
          setCollapsed(!collapsed)
        }
        style={{
          marginTop: 30,
          width: "100%",
          border: "none",
          cursor: "pointer",
          borderRadius: 10,
          padding: "10px",
          background:
            "rgba(255,255,255,0.04)",
          color: "#fff",
        }}
      >
        {collapsed ? (
          <ChevronRight size={16} />
        ) : (
          <ChevronLeft size={16} />
        )}
      </button>
    </aside>
  );
}

function Navbar() {
  return (
    <header
      style={{
        height: 60,
        background:
          "rgba(8,8,20,0.8)",
        backdropFilter: "blur(20px)",
        borderBottom:
          "1px solid rgba(255,255,255,0.06)",
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 340,
          position: "relative",
        }}
      >
        <Search
          size={14}
          style={{
            position: "absolute",
            left: 12,
            top: "50%",
            transform:
              "translateY(-50%)",
            color:
              "rgba(255,255,255,0.3)",
          }}
        />

        <input
          placeholder="Search products, competitors..."
          style={{
            width: "100%",
            background:
              "rgba(255,255,255,0.05)",
            border:
              "1px solid rgba(255,255,255,0.08)",
            borderRadius: 10,
            padding:
              "10px 14px 10px 36px",
            color: "#fff",
            outline: "none",
            fontSize: 13,
          }}
        />
      </div>
    </header>
  );
}

export default function KlypupDashboard() {
  const user = JSON.parse(
    localStorage.getItem("user")
  );

  const [collapsed, setCollapsed] =
    useState(false);

  const [activePage, setActivePage] =
    useState("Dashboard");

  const metrics = [
    {
      icon: DollarSign,
      label: "Total Revenue",
      value: 128000,
      change: "+23.4%",
      color: "#818cf8",
    },

    {
      icon: Brain,
      label: "Pricing Accuracy",
      value: 94,
      unit: "%",
      change: "+2.1%",
      color: "#34d399",
    },

    {
      icon: Activity,
      label: "AI Confidence",
      value: 92,
      unit: "%",
      change: "+1.8%",
      color: "#a855f7",
    },

    {
      icon: ShoppingCart,
      label: "Conversion Rate",
      value: 7,
      unit: "%",
      change: "+0.9%",
      color: "#60a5fa",
    },
  ];

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#060612",
        display: "flex",
        color: "#fff",
        fontFamily:
          "'Inter', system-ui, sans-serif",
      }}
    >
      <Sidebar
        collapsed={collapsed}
        setCollapsed={setCollapsed}
        activePage={activePage}
        setActivePage={setActivePage}
      />

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <Navbar />

        <main
          style={{
            padding: 28,
          }}
        >
          <section
            style={{
              marginBottom: 30,
            }}
          >
            <div
              style={{
                fontSize: 13,
                color:
                  "rgba(255,255,255,0.45)",
                marginBottom: 8,
              }}
            >
              Saturday, 16 May 2026 · Live market
              session active
            </div>

            <h1
              style={{
                fontSize: 38,
                fontWeight: 700,
                margin: 0,
                color: "#fff",
              }}
            >
              Welcome back,{" "}
              <span
                style={{
                  background:
                    "linear-gradient(90deg,#818cf8,#c084fc)",
                  WebkitBackgroundClip:
                    "text",
                  WebkitTextFillColor:
                    "transparent",
                }}
              >
                {user?.name || "User"}
              </span>
            </h1>

            <p
              style={{
                marginTop: 10,
                color:
                  "rgba(255,255,255,0.45)",
                fontSize: 14,
              }}
            >
              AI engine is running · 312
              products optimized · Revenue up
              23.4% this month
            </p>
          </section>

          <section
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fit,minmax(220px,1fr))",
              gap: 16,
              marginBottom: 40,
            }}
          >
            {metrics.map((metric) => (
              <MetricCard
                key={metric.label}
                {...metric}
              />
            ))}
          </section>

          <section
            style={{
              background:
                "rgba(255,255,255,0.03)",
              border:
                "1px solid rgba(255,255,255,0.08)",
              borderRadius: 18,
              padding: 24,
            }}
          >
            <h2
              style={{
                marginTop: 0,
                fontSize: 24,
              }}
            >
              Revenue Analytics
            </h2>

            <ResponsiveContainer
              width="100%"
              height={300}
            >
              <AreaChart data={revenueData}>
                <defs>
                  <linearGradient
                    id="colorRevenue"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="5%"
                      stopColor="#818cf8"
                      stopOpacity={0.4}
                    />

                    <stop
                      offset="95%"
                      stopColor="#818cf8"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>

                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.05)"
                />

                <XAxis
                  dataKey="t"
                  stroke="rgba(255,255,255,0.4)"
                />

                <YAxis
                  stroke="rgba(255,255,255,0.4)"
                />

                <Tooltip />

                <Area
                  type="monotone"
                  dataKey="rev"
                  stroke="#818cf8"
                  fillOpacity={1}
                  fill="url(#colorRevenue)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </section>
        </main>
      </div>
    </div>
  );
}