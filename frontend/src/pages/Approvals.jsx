import { useEffect, useState } from "react";

import {
  CheckCircle,
  XCircle,
  RefreshCw,
  Clock,
  Brain,
  TrendingUp,
} from "lucide-react";

import apiClient from "../services/api";

export default function Approvals() {

  const [recommendations, setRecommendations] = useState([]);

  const [loading, setLoading] = useState(true);

  const [processingId, setProcessingId] = useState(null);

  /* ======================================
     FETCH RECOMMENDATIONS
  ====================================== */

  const fetchRecommendations = async () => {

    try {

      const response = await apiClient.get(
        "/recommendations"
      );

      const allRecommendations =
        response.data.recommendations || [];

      // ======================================
      // ONLY SHOW PENDING RECOMMENDATIONS
      // ======================================

      const pendingRecommendations =
        allRecommendations.filter(
          (rec) =>
            rec.status?.toLowerCase() === "pending"
        );

      // ======================================
      // SORT NEWEST FIRST
      // ======================================

      const sortedRecommendations =
        pendingRecommendations.sort(

          (a, b) =>
            new Date(b.created_at)
            - new Date(a.created_at)
        );

      setRecommendations(
        [...sortedRecommendations]
      );

    } catch (error) {

      console.error(error);

    } finally {

      setLoading(false);

    }
  };

  useEffect(() => {

    fetchRecommendations();

  }, []);

  /* ======================================
     APPROVE RECOMMENDATION
  ====================================== */

  const approveRecommendation = async (id) => {

    try {

      console.log(
        "APPROVING:",
        id
      );

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

  /* ======================================
     REJECT RECOMMENDATION
  ====================================== */

  const rejectRecommendation = async (id) => {

    try {

      console.log(
        "REJECTING:",
        id
      );

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

  /* ======================================
     STATUS COLORS
  ====================================== */

  const getStatusColor = (status) => {

    switch (status?.toLowerCase()) {

      case "approved":

        return "text-green-400 bg-green-500/10";

      case "rejected":

        return "text-red-400 bg-red-500/10";

      default:

        return "text-yellow-400 bg-yellow-500/10";
    }
  };

  return (

    <div className="p-8 text-white">

      {/* ======================================
          HEADER
      ====================================== */}

      <div className="flex items-center justify-between mb-10">

        <div>

          <h1 className="text-4xl font-bold mb-2">

            Approvals Workflow

          </h1>

          <p className="text-slate-400">

            Human approval system
            for AI pricing decisions

          </p>

        </div>

        <button
          onClick={fetchRecommendations}
          className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 px-5 py-3 rounded-xl transition-all"
        >

          <RefreshCw size={18} />

          Refresh

        </button>

      </div>

      {/* ======================================
          CONTENT
      ====================================== */}

      {loading ? (

        <div className="text-slate-400">

          Loading...

        </div>

      ) : recommendations.length === 0 ? (

        <div className="bg-slate-900 border border-white/10 rounded-3xl p-12 text-center text-slate-400">

          No pending recommendations available.

        </div>

      ) : (

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

          {recommendations.map((rec) => (

            <div
              key={`${rec.id}-${rec.created_at}`}
              className="bg-slate-900 border border-white/10 rounded-3xl p-6"
            >

              {/* ======================================
                  CARD HEADER
              ====================================== */}

              <div className="flex items-start justify-between mb-6">

                <div>

                  <h2 className="text-2xl font-semibold mb-2">

                    {rec.product?.name ||
                      rec.product_name}

                  </h2>

                  <p className="text-slate-400">

                    {rec.product?.sku ||
                      rec.product_sku}

                  </p>

                </div>

                <div className="w-14 h-14 rounded-2xl bg-violet-500/20 text-violet-400 flex items-center justify-center">

                  <Brain />

                </div>

              </div>

              {/* ======================================
                  DETAILS
              ====================================== */}

              <div className="space-y-4 text-sm mb-6">

                <div className="flex justify-between">

                  <span className="text-slate-400">

                    Current Price

                  </span>

                  <span>

                    ₹{
                      rec.product?.current_price ||
                      rec.current_price
                    }

                  </span>

                </div>

                <div className="flex justify-between">

                  <span className="text-slate-400">

                    Recommended Price

                  </span>

                  <span className="text-green-400">

                    ₹{rec.recommended_price}

                  </span>

                </div>

                <div className="flex justify-between">

                  <span className="text-slate-400">

                    Confidence

                  </span>

                  <span>

                    {rec.confidence_score}%

                  </span>

                </div>

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

              {/* ======================================
                  AI SUMMARY
              ====================================== */}

              <div className="border-t border-white/10 pt-5 mb-5">

                <div className="flex items-center gap-2 mb-3 text-slate-400">

                  <TrendingUp size={16} />

                  AI Summary

                </div>

                <p>

                  {rec.ai_summary}

                </p>

              </div>

              {/* ======================================
                  RATIONALE
              ====================================== */}

              <div className="border-t border-white/10 pt-5 mb-6">

                <div className="flex items-center gap-2 mb-3 text-slate-400">

                  <Clock size={16} />

                  Rationale

                </div>

                <p className="leading-8 text-slate-200">

                  {rec.rationale}

                </p>

              </div>

              {/* ======================================
                  ACTION BUTTONS
              ====================================== */}

              <div className="grid grid-cols-2 gap-4">

                <button
                  onClick={() =>
                    approveRecommendation(rec.id)
                  }

                  disabled={
                    processingId === rec.id
                  }

                  className="bg-green-600 hover:bg-green-700 rounded-xl py-4 font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-60"
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

                  className="bg-red-600 hover:bg-red-700 rounded-xl py-4 font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-60"
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

          ))}

        </div>

      )}

    </div>
  );
}