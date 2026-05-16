import { useEffect, useState } from "react";

import {
  CheckCircle,
  XCircle,
  RefreshCw,
  Clock,
  Brain,
  TrendingUp,
  ShieldCheck,
  Activity,
  Sparkles,
} from "lucide-react";

import { motion } from "framer-motion";

import apiClient from "../services/api";

export default function Approvals() {

  const [recommendations, setRecommendations] = useState([]);

  const [loading, setLoading] = useState(true);

  const [processingId, setProcessingId] = useState(null);

  const fetchRecommendations = async () => {

    try {

      const response = await apiClient.get(
        "/recommendations"
      );

      const allRecommendations =
        response.data.recommendations || [];

      const pendingRecommendations =
        allRecommendations.filter(
          (rec) =>
            rec.status?.toLowerCase() === "pending"
        );

      const sortedRecommendations =
        pendingRecommendations.sort(
          (a, b) =>
            new Date(b.created_at) -
            new Date(a.created_at)
        );

      setRecommendations([
        ...sortedRecommendations,
      ]);

    } catch (error) {

      console.error(error);

    } finally {

      setLoading(false);
    }
  };

  useEffect(() => {

    fetchRecommendations();

  }, []);

  const approveRecommendation = async (id) => {

    try {

      setProcessingId(id);

      await apiClient.post(
        `/approvals/approve/${id}`
      );

      await fetchRecommendations();

    } catch (error) {

      console.error(error);

      alert(
        error.response?.data?.message ||
        "Approval failed"
      );

    } finally {

      setProcessingId(null);
    }
  };

  const rejectRecommendation = async (id) => {

    try {

      setProcessingId(id);

      await apiClient.post(
        `/approvals/reject/${id}`
      );

      await fetchRecommendations();

    } catch (error) {

      console.error(error);

      alert(
        error.response?.data?.message ||
        "Rejection failed"
      );

    } finally {

      setProcessingId(null);
    }
  };

  const getStatusColor = (status) => {

    switch (status?.toLowerCase()) {

      case "approved":

        return "text-green-400 bg-green-500/10 border border-green-500/20";

      case "rejected":

        return "text-red-400 bg-red-500/10 border border-red-500/20";

      default:

        return "text-yellow-400 bg-yellow-500/10 border border-yellow-500/20";
    }
  };

  return (

    <div className="space-y-8">

      {/* HERO */}

      <div
        className="relative overflow-hidden rounded-[28px] border border-white/10 p-8 lg:p-10"
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
              "rgba(0,161,155,0.12)",
            filter: "blur(100px)",
            top: -60,
            right: -60,
          }}
        />

        <div className="relative z-10">

          <div className="inline-flex items-center gap-2 bg-[#00A19B]/10 border border-[#00A19B]/20 text-[#7FF6EE] px-4 py-2 rounded-full text-sm mb-6">

            <ShieldCheck size={16} />

            Human Approval Workflow Active

          </div>

          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">

            <div>

              <h1 className="text-4xl lg:text-5xl font-bold text-white leading-tight">

                Approval Workflow

              </h1>

              <p className="text-slate-400 text-lg mt-4 max-w-2xl leading-8">

                Review intelligent pricing recommendations before
                deployment using enterprise approval workflows
                and controlled pricing governance systems.

              </p>

            </div>

            <div className="grid grid-cols-2 gap-4 min-w-[280px]">

              <MiniStat
                title="Pending"
                value={recommendations.length}
              />

              <MiniStat
                title="Review Queue"
                value="Active"
              />

              <MiniStat
                title="Governance"
                value="Enabled"
              />

              <MiniStat
                title="Approval Layer"
                value="Online"
              />

            </div>

          </div>

        </div>

      </div>

      {/* HEADER */}

      <div className="flex items-center justify-between flex-wrap gap-4">

        <div>

          <h2 className="text-3xl font-bold text-white">

            Pending Recommendations

          </h2>

          <p className="text-slate-400 mt-2">

            Human review required before pricing deployment

          </p>

        </div>

        <button
          onClick={fetchRecommendations}

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

          Refresh Queue

        </button>

      </div>

      {/* CONTENT */}

      {loading ? (

        <div className="glass-card p-12 text-center text-slate-400">

          Loading approval queue...

        </div>

      ) : recommendations.length === 0 ? (

        <div className="glass-card p-14 text-center">

          <Sparkles
            size={54}
            className="mx-auto text-slate-600 mb-5"
          />

          <h3 className="text-2xl font-semibold text-white mb-3">

            No Pending Approvals

          </h3>

          <p className="text-slate-400">

            All pricing recommendations have been processed.

          </p>

        </div>

      ) : (

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

          {recommendations.map((rec) => (

            <motion.div
              key={`${rec.id}-${rec.created_at}`}

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
                    "rgba(99,102,241,0.08)",
                  filter: "blur(70px)",
                  top: -40,
                  right: -40,
                }}
              />

              <div className="relative z-10">

                {/* HEADER */}

                <div className="flex items-start justify-between mb-7">

                  <div>

                    <h2 className="text-2xl font-semibold text-white mb-2">

                      {rec.product?.name ||
                        rec.product_name}

                    </h2>

                    <p className="text-slate-400">

                      {rec.product?.sku ||
                        rec.product_sku}

                    </p>

                  </div>

                  <div
                    className="
                      w-14
                      h-14
                      rounded-2xl
                      text-white
                      flex
                      items-center
                      justify-center
                    "
                    style={{
                      background:
                        "linear-gradient(135deg,#00A19B,#6366f1)",
                    }}
                  >

                    <Brain size={24} />

                  </div>

                </div>

                {/* DETAILS */}

                <div className="space-y-4 text-sm mb-7">

                  <InfoRow
                    label="Current Price"
                    value={`₹${
                      rec.product?.current_price ||
                      rec.current_price
                    }`}
                  />

                  <InfoRow
                    label="Recommended Price"
                    value={`₹${rec.recommended_price}`}
                    green
                  />

                  <InfoRow
                    label="Confidence"
                    value={`${rec.confidence_score}%`}
                  />

                  <div className="flex justify-between items-center">

                    <span className="text-slate-400">

                      Status

                    </span>

                    <span
                      className={`px-3 py-1 rounded-full text-xs font-medium capitalize ${getStatusColor(rec.status)}`}
                    >

                      {rec.status}

                    </span>

                  </div>

                </div>

                {/* AI SUMMARY */}

                <div className="rounded-2xl border border-white/10 bg-white/5 p-5 mb-5">

                  <div className="flex items-center gap-2 mb-3 text-[#00A19B]">

                    <Activity size={16} />

                    <span className="font-semibold">

                      AI Summary

                    </span>

                  </div>

                  <p className="text-slate-300 leading-7 text-sm">

                    {rec.ai_summary}

                  </p>

                </div>

                {/* RATIONALE */}

                <div className="rounded-2xl border border-white/10 bg-white/5 p-5 mb-6">

                  <div className="flex items-center gap-2 mb-3 text-[#6366f1]">

                    <Clock size={16} />

                    <span className="font-semibold">

                      Pricing Rationale

                    </span>

                  </div>

                  <p className="text-slate-300 leading-7 text-sm">

                    {rec.rationale}

                  </p>

                </div>

                {/* ACTIONS */}

                <div className="grid grid-cols-2 gap-4">

                  <button
                    onClick={() =>
                      approveRecommendation(rec.id)
                    }

                    disabled={
                      processingId === rec.id
                    }

                    className="
                      rounded-2xl
                      py-4
                      font-semibold
                      flex
                      items-center
                      justify-center
                      gap-2
                      transition-all
                      disabled:opacity-60
                      text-white
                    "

                    style={{
                      background:
                        "linear-gradient(135deg,#10b981,#059669)",
                    }}
                  >

                    <CheckCircle size={18} />

                    {
                      processingId === rec.id
                        ? "Processing..."
                        : "Approve"
                    }

                  </button>

                  <button
                    onClick={() =>
                      rejectRecommendation(rec.id)
                    }

                    disabled={
                      processingId === rec.id
                    }

                    className="
                      rounded-2xl
                      py-4
                      font-semibold
                      flex
                      items-center
                      justify-center
                      gap-2
                      transition-all
                      disabled:opacity-60
                      text-white
                    "

                    style={{
                      background:
                        "linear-gradient(135deg,#ef4444,#dc2626)",
                    }}
                  >

                    <XCircle size={18} />

                    {
                      processingId === rec.id
                        ? "Processing..."
                        : "Reject"
                    }

                  </button>

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

    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4 backdrop-blur-xl">

      <div className="text-slate-500 text-xs mb-2 uppercase tracking-wide">

        {title}

      </div>

      <div className="text-2xl font-bold text-white">

        {value}

      </div>

    </div>
  );
}

function InfoRow({
  label,
  value,
  green,
}) {

  return (

    <div className="flex items-center justify-between">

      <span className="text-slate-400">

        {label}

      </span>

      <span
        className={`font-medium ${
          green
            ? "text-[#00A19B]"
            : "text-white"
        }`}
      >

        {value}

      </span>

    </div>
  );
}