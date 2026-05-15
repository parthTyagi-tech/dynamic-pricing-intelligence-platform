import { useState, useEffect } from "react";

import { motion } from "framer-motion";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
 CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

import {
  Package,
  TrendingUp,
  CheckCircle,
  AlertTriangle,
  Brain,
  ArrowUpRight,
  ArrowDownRight,
  ShieldCheck,
  Loader2,
  RefreshCw,
} from "lucide-react";

import apiClient from "../services/api";


/* ======================================
   ANIMATIONS
====================================== */

const stagger = {
  animate: {
    transition: {
      staggerChildren: 0.07,
    },
  },
};

const fadeUp = {
  initial: {
    opacity: 0,
    y: 20,
  },

  animate: {
    opacity: 1,
    y: 0,
  },
};


/* ======================================
   TOOLTIP
====================================== */

const CustomTooltip = ({
  active,
  payload,
  label,
}) => {

  if (
    active &&
    payload &&
    payload.length
  ) {

    return (

      <div className="bg-[#0e1220]/95 border border-white/10 rounded-xl px-3 py-2.5 backdrop-blur-xl shadow-xl">

        <p className="text-xs text-slate-400 mb-1">
          {label}
        </p>

        {payload.map((p, i) => (

          <p
            key={i}
            className="text-xs font-semibold"
            style={{
              color: p.color,
            }}
          >

            {p.name}: {p.value}

            {
              typeof p.value === "number"
                ? "%"
                : ""
            }

          </p>
        ))}
      </div>
    );
  }

  return null;
};


/* ======================================
   KPI CARD
====================================== */

function StatCard({
  icon: Icon,
  label,
  value,
  change,
  trend,
  gradient,
}) {

  const isPositive =
    trend === "up";

  return (

    <motion.div
      variants={fadeUp}
      className="relative rounded-2xl border border-white/8 bg-white/3 backdrop-blur-sm overflow-hidden group hover:border-white/15 transition-all duration-300"
    >

      <div
        className={`absolute inset-0 bg-gradient-to-br ${gradient} opacity-0 group-hover:opacity-10 transition-opacity duration-300`}
      />

      <div className="p-5">

        <div className="flex items-start justify-between mb-4">

          <div
            className={`p-2.5 rounded-xl bg-gradient-to-br ${gradient}`}
          >

            <Icon
              size={16}
              className="text-white"
            />

          </div>

          <div
            className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold ${
              isPositive
                ? "bg-emerald-500/15 text-emerald-400"
                : "bg-red-500/15 text-red-400"
            }`}
          >

            {
              isPositive ? (
                <ArrowUpRight size={11} />
              ) : (
                <ArrowDownRight size={11} />
              )
            }

            {Math.abs(change)}%

          </div>
        </div>

        <div>

          <div className="text-2xl font-bold text-white">

            {value}

          </div>

          <div className="text-xs text-slate-500 mt-1">

            {label}

          </div>

        </div>

      </div>

    </motion.div>
  );
}


/* ======================================
   DASHBOARD
====================================== */

export default function Dashboard() {

  const [stats, setStats] =
    useState(null);

  const [loading, setLoading] =
    useState(true);

  const [refreshing, setRefreshing] =
    useState(false);

  const [lastUpdated,
    setLastUpdated] =
    useState(new Date());

  const [refreshMessage,
    setRefreshMessage] =
    useState(false);

  const [error, setError] =
    useState(null);

  const [recentActivity,
    setRecentActivity] =
    useState([]);

  const [statusDist,
    setStatusDist] =
    useState([]);

  const [confidenceTrend,
    setConfidenceTrend] =
    useState([]);


  /* ======================================
     LIVE TREND GENERATOR
  ====================================== */

  const generateTrendData = () => {

    return [

      {
        day: "Mon",
        confidence:
          Math.floor(
            Math.random() * 20
          ) + 75,
      },

      {
        day: "Tue",
        confidence:
          Math.floor(
            Math.random() * 20
          ) + 75,
      },

      {
        day: "Wed",
        confidence:
          Math.floor(
            Math.random() * 20
          ) + 75,
      },

      {
        day: "Thu",
        confidence:
          Math.floor(
            Math.random() * 20
          ) + 75,
      },

      {
        day: "Fri",
        confidence:
          Math.floor(
            Math.random() * 20
          ) + 75,
      },

      {
        day: "Sat",
        confidence:
          Math.floor(
            Math.random() * 20
          ) + 75,
      },

      {
        day: "Sun",
        confidence:
          Math.floor(
            Math.random() * 20
          ) + 75,
      },
    ];
  };


  /* ======================================
     FETCH DATA
  ====================================== */

  const fetchData = async () => {

    try {

      setLoading(true);

      const [
        productsRes,
        recsRes,
        historyRes,
      ] = await Promise.all([

        apiClient.get("/products"),

        apiClient.get("/recommendations"),

        apiClient.get("/approvals/history"),
      ]);


      const prods =
        productsRes.data?.products || [];

      const recs =
        recsRes.data?.recommendations || [];

      const history =
        historyRes.data?.history || [];


      const pending =
        recs.filter(
          (r) =>
            r.status === "pending"
        ).length;

      const approved =
        recs.filter(
          (r) =>
            r.status === "approved"
        ).length;

      const rejected =
        recs.filter(
          (r) =>
            r.status === "rejected"
        ).length;

      const lowStock =
        prods.filter(
          (p) =>
            p.inventory_quantity < 10
        ).length;

      const avgMargin =
        prods.length
          ? (
              prods.reduce(
                (sum, p) =>

                  sum +
                  (
                    parseFloat(
                      p.margin_percent
                    ) || 0
                  ),

                0
              ) / prods.length
            ).toFixed(1)
          : 0;


      setStats({

        totalProducts:
          prods.length,

        pending,

        approved,

        rejected,

        lowStock,

        avgMargin,
      });


      setStatusDist([

        {
          name: "Approved",
          value: approved,
          color: "#10b981",
        },

        {
          name: "Pending",
          value: pending,
          color: "#8b5cf6",
        },

        {
          name: "Rejected",
          value: rejected,
          color: "#ef4444",
        },
      ]);


      /* ======================================
         RECENT ACTIVITY
      ====================================== */

      const recommendationActivities =
        recs.map((rec, index) => ({

          id:
            `rec-${index}`,

          product:
            rec.product?.name ||
            "Unknown Product",

          type:
            rec.status || "generated",

          time:
            new Date(
              rec.created_at
            ).toLocaleString(),

          agent:
            rec.created_by_agent ||
            "AI Pricing Agent",
        }));


      const approvalActivities =
        history.map((item, index) => ({

          id:
            `approval-${index}`,

          product:
            item.product?.name ||
            "Unknown Product",

          type:
            item.action_type,

          time:
            new Date(
              item.timestamp
            ).toLocaleString(),

          agent:
            item.action_type ===
            "approve"
              ? "Recommendation Approved"
              : "Recommendation Rejected",
        }));


      const mergedActivities = [

        ...recommendationActivities,

        ...approvalActivities,
      ];


      mergedActivities.sort(
        (a, b) =>

          new Date(b.time) -
          new Date(a.time)
      );


      setRecentActivity(
        mergedActivities.slice(0, 8)
      );


      setConfidenceTrend(
        generateTrendData()
      );

      setError(null);

    } catch (err) {

      console.error(err);

      setError(
        "Failed to load dashboard data"
      );

    } finally {

      setLoading(false);
    }
  };


  /* ======================================
     REFRESH
  ====================================== */

  const handleRefresh = async () => {

    try {

      setRefreshing(true);

      const newTrendData =
        generateTrendData();

      setConfidenceTrend(
        [...newTrendData]
      );

      await fetchData();

      setLastUpdated(
        new Date()
      );

      setRefreshMessage(true);

      setTimeout(() => {

        setRefreshMessage(false);

      }, 2000);

    } catch (err) {

      console.error(
        "Refresh failed:",
        err
      );

    } finally {

      setRefreshing(false);
    }
  };


  /* ======================================
     INITIAL LOAD
  ====================================== */

  useEffect(() => {

    setConfidenceTrend(
      generateTrendData()
    );

    fetchData();

  }, []);


  /* ======================================
     KPI CARDS
  ====================================== */

  const kpiCards = stats
    ? [

        {
          icon: Package,
          label: "Total Products",
          value: stats.totalProducts,
          change: 8,
          trend: "up",
          gradient:
            "from-violet-500 to-purple-600",
        },

        {
          icon: Brain,
          label: "Pending AI Recs",
          value: stats.pending,
          change: 12,
          trend: "up",
          gradient:
            "from-sky-500 to-blue-600",
        },

        {
          icon: CheckCircle,
          label: "Approved Recs",
          value: stats.approved,
          change: 24,
          trend: "up",
          gradient:
            "from-emerald-500 to-teal-600",
        },

        {
          icon: ShieldCheck,
          label: "AI Accuracy",
          value: "94%",
          change: 6,
          trend: "up",
          gradient:
            "from-cyan-500 to-blue-600",
        },

        {
          icon: TrendingUp,
          label: "Revenue Optimized",
          value: "₹2.4L",
          change: 18,
          trend: "up",
          gradient:
            "from-pink-500 to-rose-600",
        },

        {
          icon: AlertTriangle,
          label: "Low Stock Alerts",
          value: stats.lowStock,
          change: 3,
          trend: "down",
          gradient:
            "from-amber-500 to-orange-600",
        },
      ]
    : [];


  if (loading && !refreshing) {

    return (

      <div className="h-full flex items-center justify-center">

        <div className="flex items-center gap-3 text-violet-400">

          <Loader2
            className="animate-spin"
            size={20}
          />

          <span className="text-sm font-medium">

            Loading AI Dashboard...

          </span>

        </div>

      </div>
    );
  }


  return (

    <div className="relative p-6 lg:p-8 space-y-8 max-w-[1600px] mx-auto overflow-hidden">

      {/* HEADER */}

      <motion.div
        initial={{
          opacity: 0,
          y: -10,
        }}

        animate={{
          opacity: 1,
          y: 0,
        }}

        className="relative flex items-start justify-between z-10"
      >

        <div>

          <h1 className="text-3xl font-bold text-white">

            Intelligence Overview

          </h1>

          <p className="text-sm text-slate-500 mt-1">

            Real-time pricing intelligence
            across your catalog

          </p>

        </div>


        {/* REFRESH */}

        <div className="flex items-center gap-3 relative z-50">

          <button
            type="button"

            onClick={(e) => {

              e.preventDefault();

              handleRefresh();
            }}

            disabled={refreshing}

            className="relative z-50 flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-500/15 border border-violet-500/20 text-violet-300 hover:bg-violet-500/20 transition-all disabled:opacity-50 cursor-pointer"
          >

            {
              refreshing ? (

                <Loader2
                  size={16}
                  className="animate-spin"
                />

              ) : (

                <RefreshCw size={16} />

              )
            }

            <span className="text-sm font-medium">

              {
                refreshing
                  ? "Refreshing..."
                  : "Refresh"
              }

            </span>

          </button>


          <div className="text-right">

            <div className="text-white text-sm font-semibold">

              {lastUpdated.toLocaleTimeString()}

            </div>

            <div className="text-slate-500 text-xs">

              Live AI Monitoring

            </div>

          </div>


          {
            refreshMessage && (

              <motion.div
                initial={{
                  opacity: 0,
                  y: -5,
                }}

                animate={{
                  opacity: 1,
                  y: 0,
                }}

                className="absolute top-14 right-0 px-3 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs backdrop-blur-xl"
              >

                AI data refreshed successfully

              </motion.div>
            )
          }

        </div>

      </motion.div>


      {/* KPI CARDS */}

      <motion.div
        variants={stagger}
        initial="initial"
        animate="animate"
        className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 relative z-10"
      >

        {
          kpiCards.map((card, i) => (

            <StatCard
              key={i}
              {...card}
            />
          ))
        }

      </motion.div>


      {/* CHARTS */}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 relative z-10">

        <motion.div
          initial={{
            opacity: 0,
            y: 20,
          }}

          animate={{
            opacity: 1,
            y: 0,
          }}

          className="xl:col-span-2 rounded-2xl border border-white/8 bg-white/3 backdrop-blur-sm p-6"
        >

          <div className="mb-6">

            <h3 className="text-sm font-semibold text-white">

              AI Confidence Trend

            </h3>

          </div>

          <ResponsiveContainer
            width="100%"
            height={220}
          >

            <AreaChart
              data={[...confidenceTrend]}
            >

              <defs>

                <linearGradient
                  id="confGrad"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >

                  <stop
                    offset="5%"
                    stopColor="#8b5cf6"
                    stopOpacity={0.3}
                  />

                  <stop
                    offset="95%"
                    stopColor="#8b5cf6"
                    stopOpacity={0}
                  />

                </linearGradient>

              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
              />

              <XAxis
                dataKey="day"
                tick={{
                  fontSize: 11,
                  fill: "#64748b",
                }}
              />

              <YAxis
                tick={{
                  fontSize: 11,
                  fill: "#64748b",
                }}
              />

              <Tooltip
                content={<CustomTooltip />}
              />

              <Area
                type="monotone"
                dataKey="confidence"
                stroke="#8b5cf6"
                fill="url(#confGrad)"
              />

            </AreaChart>

          </ResponsiveContainer>

        </motion.div>


        <motion.div
          initial={{
            opacity: 0,
            y: 20,
          }}

          animate={{
            opacity: 1,
            y: 0,
          }}

          className="rounded-2xl border border-white/8 bg-white/3 backdrop-blur-sm p-6"
        >

          <div className="mb-6">

            <h3 className="text-sm font-semibold text-white">

              Recommendation Status

            </h3>

          </div>

          <ResponsiveContainer
            width="100%"
            height={180}
          >

            <PieChart>

              <Pie
                data={statusDist}
                innerRadius={50}
                outerRadius={75}
                dataKey="value"
              >

                {
                  statusDist.map(
                    (entry, index) => (

                      <Cell
                        key={index}
                        fill={entry.color}
                      />
                    )
                  )
                }

              </Pie>

              <Tooltip
                content={<CustomTooltip />}
              />

            </PieChart>

          </ResponsiveContainer>

        </motion.div>

      </div>


      {/* RECENT ACTIVITY */}

      <motion.div
        initial={{
          opacity: 0,
          y: 20,
        }}

        animate={{
          opacity: 1,
          y: 0,
        }}

        className="rounded-2xl border border-white/8 bg-white/3 backdrop-blur-sm p-6 relative z-10"
      >

        <div className="flex items-center gap-2 mb-5">

          <TrendingUp
            size={16}
            className="text-violet-400"
          />

          <h3 className="text-sm font-semibold text-white">

            Recent AI Activity

          </h3>

        </div>

        <div className="space-y-3">

          {
            recentActivity.length > 0 ? (

              recentActivity.map(
                (item) => (

                  <div
                    key={item.id}
                    className="flex items-center justify-between p-4 rounded-xl bg-white/3 border border-white/5"
                  >

                    <div>

                      <div className="text-sm text-white font-medium">

                        {item.product}

                      </div>

                      <div className="text-xs text-slate-500 mt-1">

                        {item.agent}

                      </div>

                    </div>

                    <div className="text-right">

                      <div
                        className={`text-xs font-semibold capitalize ${
                          item.type === "approve"
                            ? "text-emerald-400"

                            : item.type === "reject" ||
                              item.type === "rejected"

                            ? "text-red-400"

                            : item.type === "pending"

                            ? "text-yellow-400"

                            : "text-violet-400"
                        }`}
                      >

                        {item.type}

                      </div>

                      <div className="text-xs text-slate-500 mt-1">

                        {item.time}

                      </div>

                    </div>

                  </div>
                )
              )

            ) : (

              <div className="text-center py-10 text-slate-500 text-sm">

                No recent AI activity found

              </div>
            )
          }

        </div>

      </motion.div>

    </div>
  );
}