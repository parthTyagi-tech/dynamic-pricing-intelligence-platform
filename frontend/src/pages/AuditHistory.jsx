import { useEffect, useState } from "react";

import {
  History,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  IndianRupee,
  ShieldCheck,
  Activity,
  Sparkles,
  User,
} from "lucide-react";

import { motion } from "framer-motion";

import apiClient from "../services/api";

export default function AuditHistory() {

  const [history, setHistory] = useState([]);

  const [loading, setLoading] = useState(true);

  const fetchHistory = async () => {

    try {

      const response = await apiClient.get(
        "/approvals/history"
      );

      setHistory(
        response.data.history || []
      );

    } catch (error) {

      console.error(error);

    } finally {

      setLoading(false);
    }
  };

  useEffect(() => {

    fetchHistory();

  }, []);

  const getActionIcon = (action) => {

    if (
      action?.toLowerCase() === "approve"
    ) {

      return (
        <CheckCircle
          className="text-green-400"
          size={20}
        />
      );
    }

    return (
      <XCircle
        className="text-red-400"
        size={20}
      />
    );
  };

  const getActionColor = (action) => {

    if (
      action?.toLowerCase() === "approve"
    ) {

      return `
        bg-green-500/10
        text-green-400
        border
        border-green-500/20
      `;
    }

    return `
      bg-red-500/10
      text-red-400
      border
      border-red-500/20
    `;
  };

  return (

    <div className="space-y-8">

      {/* HERO */}

      <div
        className="
          relative
          overflow-hidden
          rounded-[28px]
          border
          border-white/10
          p-8
          lg:p-10
        "
        style={{
          background:
            "linear-gradient(135deg,rgba(12,16,32,0.92),rgba(15,23,42,0.92))",

          boxShadow:
            "0 24px 60px rgba(0,0,0,0.35)",
        }}
      >

        <div
          style={{
            position: "absolute",
            width: 240,
            height: 240,
            borderRadius: "50%",

            background:
              "rgba(99,102,241,0.12)",

            filter: "blur(100px)",

            top: -60,
            right: -60,
          }}
        />

        <div className="relative z-10">

          <div
            className="
              inline-flex
              items-center
              gap-2
              bg-[#6366f1]/10
              border
              border-[#6366f1]/20
              text-[#c7d2fe]
              px-4
              py-2
              rounded-full
              text-sm
              mb-6
            "
          >

            <ShieldCheck size={16} />

            Enterprise Audit Tracking

          </div>

          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">

            <div>

              <h1 className="text-4xl lg:text-5xl font-bold text-white leading-tight">

                Audit History

              </h1>

              <p className="text-slate-400 text-lg mt-4 max-w-2xl leading-8">

                Track all pricing approvals, rejections,
                execution history and governance actions
                across the intelligent pricing system.

              </p>

            </div>

            <div className="grid grid-cols-2 gap-4 min-w-[280px]">

              <MiniStat
                title="Audit Logs"
                value={history.length}
              />

              <MiniStat
                title="Governance"
                value="Enabled"
              />

              <MiniStat
                title="Review Layer"
                value="Active"
              />

              <MiniStat
                title="Tracking"
                value="Live"
              />

            </div>

          </div>

        </div>

      </div>

      {/* HEADER */}

      <div className="flex items-center justify-between flex-wrap gap-4">

        <div>

          <h2 className="text-3xl font-bold text-white">

            Pricing Audit Logs

          </h2>

          <p className="text-slate-400 mt-2">

            Historical approval and rejection activity

          </p>

        </div>

        <button
          onClick={fetchHistory}

          className="
            flex
            items-center
            gap-2
            rounded-2xl
            px-5
            py-3
            text-white
            transition-all
            hover:opacity-90
          "

          style={{
            background:
              "linear-gradient(135deg,#00A19B,#6366f1)",
          }}
        >

          <RefreshCw size={18} />

          Refresh History

        </button>

      </div>

      {/* CONTENT */}

      {loading ? (

        <div className="glass-card p-12 text-center text-slate-400">

          Loading audit history...

        </div>

      ) : history.length === 0 ? (

        <div className="glass-card p-14 text-center">

          <Sparkles
            size={54}
            className="mx-auto text-slate-600 mb-5"
          />

          <h3 className="text-2xl font-semibold text-white mb-3">

            No Audit Logs Found

          </h3>

          <p className="text-slate-400">

            Pricing approval and rejection logs will appear here.

          </p>

        </div>

      ) : (

        <div className="space-y-6">

          {history.map((item) => (

            <motion.div
              key={item.id}

              whileHover={{
                y: -4,
              }}

              className="
                relative
                overflow-hidden
                rounded-3xl
                border
                border-white/10
                bg-[rgba(17,24,39,0.78)]
                p-7
                backdrop-blur-xl
              "
            >

              <div
                style={{
                  position: "absolute",
                  width: 140,
                  height: 140,
                  borderRadius: "50%",

                  background:
                    "rgba(0,161,155,0.08)",

                  filter: "blur(70px)",

                  top: -40,
                  right: -40,
                }}
              />

              <div className="relative z-10">

                {/* TOP */}

                <div className="flex items-start justify-between mb-7 flex-wrap gap-4">

                  <div className="flex items-start gap-4">

                    <div
                      className="
                        w-14
                        h-14
                        rounded-2xl
                        flex
                        items-center
                        justify-center
                        text-white
                      "
                      style={{
                        background:
                          "linear-gradient(135deg,#00A19B,#6366f1)",
                      }}
                    >

                      <History size={24} />

                    </div>

                    <div>

                      <h2 className="text-2xl font-semibold text-white mb-2">

                        {item.product?.name ||
                          "Unknown Product"}

                      </h2>

                      <p className="text-slate-400">

                        SKU: {
                          item.product?.sku ||
                          "N/A"
                        }

                      </p>

                      <p className="text-slate-500 text-sm mt-2">

                        Intelligent pricing audit event

                      </p>

                    </div>

                  </div>

                  <div
                    className={`
                      px-4
                      py-2
                      rounded-full
                      text-sm
                      font-medium
                      flex
                      items-center
                      gap-2
                      capitalize
                      ${getActionColor(item.action_type)}
                    `}
                  >

                    {getActionIcon(
                      item.action_type
                    )}

                    {item.action_type}

                  </div>

                </div>

                {/* GRID */}

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">

                  {/* PREVIOUS */}

                  <InfoCard
                    icon={IndianRupee}
                    title="Previous Price"
                    value={`₹${item.previous_price}`}
                  />

                  {/* EXECUTED */}

                  <InfoCard
                    icon={Activity}
                    title="Executed Price"
                    value={`₹${item.executed_price}`}
                    green
                  />

                  {/* USER */}

                  <InfoCard
                    icon={User}
                    title="Processed By"
                    value={`User #${item.approved_by}`}
                  />

                  {/* TIME */}

                  <InfoCard
                    icon={Clock}
                    title="Timestamp"
                    value={
                      new Date(
                        item.timestamp
                      ).toLocaleString()
                    }
                    small
                  />

                </div>

              </div>

            </motion.div>
          ))}

        </div>
      )}

    </div>
  );
}

function MiniStat({
  title,
  value,
}) {

  return (

    <div
      className="
        rounded-2xl
        border
        border-white/10
        bg-white/5
        px-4
        py-4
        backdrop-blur-xl
      "
    >

      <div className="text-slate-500 text-xs mb-2 uppercase tracking-wide">

        {title}

      </div>

      <div className="text-2xl font-bold text-white">

        {value}

      </div>

    </div>
  );
}

function InfoCard({
  icon: Icon,
  title,
  value,
  green,
  small,
}) {

  return (

    <div
      className="
        rounded-2xl
        border
        border-white/10
        bg-white/5
        p-5
      "
    >

      <div className="flex items-center gap-2 text-slate-400 mb-3">

        <Icon size={16} />

        {title}

      </div>

      <div
        className={`
          ${
            small
              ? "text-sm"
              : "text-2xl"
          }
          font-semibold
          leading-relaxed
          ${
            green
              ? "text-[#00A19B]"
              : "text-white"
          }
        `}
      >

        {value}

      </div>

    </div>
  );
}