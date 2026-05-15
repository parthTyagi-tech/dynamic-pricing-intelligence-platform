import { useEffect, useState } from "react";

import {
  History,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  IndianRupee,
} from "lucide-react";

import apiClient from "../services/api";

export default function AuditHistory() {

  const [history, setHistory] = useState([]);

  const [loading, setLoading] = useState(true);

  /* ======================================
     FETCH HISTORY
  ====================================== */

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

  /* ======================================
     STATUS ICON
  ====================================== */

  const getActionIcon = (action) => {

    if (action?.toLowerCase() === "approve") {

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

  /* ======================================
     STATUS COLOR
  ====================================== */

  const getActionColor = (action) => {

    if (action?.toLowerCase() === "approve") {

      return "bg-green-500/10 text-green-400";
    }

    return "bg-red-500/10 text-red-400";
  };

  return (
    <div className="p-8 text-white">

      {/* ======================================
          HEADER
      ====================================== */}

      <div className="flex items-center justify-between mb-10">

        <div>

          <h1 className="text-4xl font-bold mb-2">
            Audit History
          </h1>

          <p className="text-slate-400">
            Track all AI approval and rejection actions
          </p>

        </div>

        <button
          onClick={fetchHistory}
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
          Loading history...
        </div>

      ) : history.length === 0 ? (

        <div className="bg-slate-900 border border-white/10 rounded-3xl p-12 text-center text-slate-400">
          No audit history available.
        </div>

      ) : (

        <div className="space-y-6">

          {history.map((item) => (

            <div
              key={item.id}
              className="bg-slate-900 border border-white/10 rounded-3xl p-6"
            >

              {/* ======================================
                  TOP ROW
              ====================================== */}

              <div className="flex items-center justify-between mb-6">

                <div className="flex items-center gap-4">

                  <div className="w-14 h-14 rounded-2xl bg-violet-500/10 flex items-center justify-center">
                    <History
                      className="text-violet-400"
                    />
                  </div>

                  <div>

                    <h2 className="text-2xl font-semibold">
                      <div className="text-2xl font-bold text-white">
    {item.product?.name}
</div>

<div className="text-gray-400">
    SKU: {item.product?.sku}
</div>
                    </h2>

                    <p className="text-slate-400">
                      AI pricing decision log
                    </p>

                  </div>

                </div>

                <div
                  className={`px-4 py-2 rounded-full text-sm font-medium flex items-center gap-2 ${getActionColor(item.action_type)}`}
                >

                  {getActionIcon(item.action_type)}

                  {item.action_type}

                </div>

              </div>

              {/* ======================================
                  DETAILS GRID
              ====================================== */}

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">

                {/* Previous Price */}

                <div className="bg-slate-800/50 rounded-2xl p-5">

                  <div className="flex items-center gap-2 text-slate-400 mb-3">

                    <IndianRupee size={16} />

                    Previous Price

                  </div>

                  <div className="text-2xl font-bold">
                    ₹{item.previous_price}
                  </div>

                </div>

                {/* Executed Price */}

                <div className="bg-slate-800/50 rounded-2xl p-5">

                  <div className="flex items-center gap-2 text-slate-400 mb-3">

                    <IndianRupee size={16} />

                    Executed Price

                  </div>

                  <div className="text-2xl font-bold text-green-400">
                    ₹{item.executed_price}
                  </div>

                </div>

                {/* Approved By */}

                <div className="bg-slate-800/50 rounded-2xl p-5">

                  <div className="flex items-center gap-2 text-slate-400 mb-3">

                    <CheckCircle size={16} />

                    Processed By

                  </div>

                  <div className="text-xl font-semibold">
                    User #{item.approved_by}
                  </div>

                </div>

                {/* Timestamp */}

                <div className="bg-slate-800/50 rounded-2xl p-5">

                  <div className="flex items-center gap-2 text-slate-400 mb-3">

                    <Clock size={16} />

                    Timestamp

                  </div>

                  <div className="text-sm leading-relaxed">
                    {new Date(
                      item.timestamp
                    ).toLocaleString()}
                  </div>

                </div>

              </div>

            </div>

          ))}

        </div>

      )}

    </div>
  );
}