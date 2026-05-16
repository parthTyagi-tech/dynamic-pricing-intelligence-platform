import { useEffect, useState } from "react";

import {
  Sparkles,
  Brain,
  RefreshCw,
  TrendingUp,
  Clock,
  Activity,
  Zap,
  BarChart3,
  ArrowUpRight,
} from "lucide-react";

import { motion } from "framer-motion";

import apiClient from "../services/api";

export default function Recommendations() {

  const [products, setProducts] = useState([]);

  const [recommendations, setRecommendations] = useState([]);

  const [loading, setLoading] = useState(true);

  const [generatingId, setGeneratingId] = useState(null);

  const fetchProducts = async () => {

    try {

      const response =
        await apiClient.get("/products");

      setProducts(
        response.data.products || []
      );

    } catch (error) {

      console.error(error);
    }
  };

  const fetchRecommendations = async () => {

    try {

      const response =
        await apiClient.get(
          "/recommendations"
        );

      setRecommendations(
        response.data.recommendations || []
      );

    } catch (error) {

      console.error(error);

    } finally {

      setLoading(false);
    }
  };

  useEffect(() => {

    fetchProducts();

    fetchRecommendations();

  }, []);

  const generateRecommendation = async (productId) => {

    try {

      setGeneratingId(productId);

      await apiClient.post(
        `/recommendations/generate/${productId}`
      );

      fetchRecommendations();

    } catch (error) {

      console.error(error);

      alert(
        error.response?.data?.message ||
        "Failed to generate recommendation"
      );

    } finally {

      setGeneratingId(null);
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
              "rgba(99,102,241,0.12)",

            filter: "blur(100px)",

            top: -60,
            right: -60,
          }}
        />

        <div className="relative z-10">

          <div className="inline-flex items-center gap-2 bg-[#6366f1]/10 border border-[#6366f1]/20 text-[#c7d2fe] px-4 py-2 rounded-full text-sm mb-6">

            <Brain size={16} />

            Intelligent Recommendation Engine

          </div>

          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">

            <div>

              <h1 className="text-4xl lg:text-5xl font-bold text-white leading-tight">

                AI Recommendations

              </h1>

              <p className="text-slate-400 text-lg mt-4 max-w-2xl leading-8">

                Generate intelligent pricing insights using
                demand analytics, market trends, inventory
                behavior and pricing intelligence workflows.

              </p>

            </div>

            <div className="grid grid-cols-2 gap-4 min-w-[280px]">

              <MiniStat
                title="Recommendations"
                value={recommendations.length}
              />

              <MiniStat
                title="Products"
                value={products.length}
              />

              <MiniStat
                title="AI Confidence"
                value="94%"
              />

              <MiniStat
                title="Engine Status"
                value="Active"
              />

            </div>

          </div>

        </div>

      </div>

      {/* ACTION BAR */}

      <div className="flex items-center justify-between flex-wrap gap-4">

        <div>

          <h2 className="text-3xl font-bold text-white">

            Generate Recommendations

          </h2>

          <p className="text-slate-400 mt-2">

            Run pricing intelligence workflows for products

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

          Refresh Analytics

        </button>

      </div>

      {/* PRODUCTS */}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {products.map((product) => (

          <motion.div
            key={product.id}

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
              p-6
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

              <div className="flex items-start justify-between mb-6">

                <div>

                  <h3 className="text-2xl font-semibold text-white mb-2">

                    {product.name}

                  </h3>

                  <p className="text-slate-400">

                    SKU: {product.sku}

                  </p>

                </div>

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

                  <Brain size={24} />

                </div>

              </div>

              <div className="space-y-4 mb-8 text-sm">

                <InfoRow
                  label="Current Price"
                  value={`₹${product.current_price}`}
                />

                <InfoRow
                  label="Inventory"
                  value={product.inventory_quantity}
                />

                <InfoRow
                  label="Margin %"
                  value={`${product.margin_percentage || 0}%`}
                />

                <InfoRow
                  label="Category"
                  value={product.category}
                />

              </div>

              <button
                onClick={() =>
                  generateRecommendation(product.id)
                }

                disabled={
                  generatingId === product.id
                }

                className="
                  w-full
                  rounded-2xl
                  py-4
                  font-semibold
                  text-white
                  transition-all
                  hover:opacity-90
                  flex
                  items-center
                  justify-center
                  gap-2
                "

                style={{
                  background:
                    "linear-gradient(135deg,#00A19B,#6366f1)",
                }}
              >

                <Sparkles size={18} />

                {generatingId === product.id

                  ? "Generating Recommendation..."

                  : "Generate AI Recommendation"}

              </button>

            </div>

          </motion.div>
        ))}

      </div>

      {/* GENERATED RECOMMENDATIONS */}

      <div className="space-y-6">

        <div>

          <h2 className="text-3xl font-bold text-white">

            Generated Recommendations

          </h2>

          <p className="text-slate-400 mt-2">

            Intelligent pricing insights and recommendation analytics

          </p>

        </div>

        {loading ? (

          <div className="glass-card p-10 text-center text-slate-400">

            Loading recommendations...

          </div>

        ) : recommendations.length === 0 ? (

          <div className="glass-card p-12 text-center">

            <Sparkles
              size={50}
              className="mx-auto text-slate-600 mb-5"
            />

            <h3 className="text-2xl font-semibold text-white mb-3">

              No Recommendations Yet

            </h3>

            <p className="text-slate-400">

              Generate recommendations to begin analyzing pricing intelligence.

            </p>

          </div>

        ) : (

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

            {recommendations.map((rec) => (

              <motion.div
                key={rec.id}

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

                  <div className="flex items-start justify-between mb-7">

                    <div>

                      <h3 className="text-2xl font-semibold text-white mb-2">

                        {rec.product?.name ||
                          "Unknown Product"}

                      </h3>

                      <p className="text-slate-400">

                        {rec.product?.sku ||
                          "No SKU"}

                      </p>

                    </div>

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

                      <TrendingUp size={24} />

                    </div>

                  </div>

                  <div className="space-y-4 text-sm mb-7">

                    <InfoRow
                      label="Current Price"
                      value={`₹${rec.product?.current_price || 0}`}
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

                    <InfoRow
                      label="Status"
                      value={rec.status}
                    />

                  </div>

                  {/* AI SUMMARY */}

                  <div className="rounded-2xl border border-white/10 bg-white/5 p-5 mb-5">

                    <div className="flex items-center gap-2 text-[#00A19B] mb-3">

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

                  <div className="rounded-2xl border border-white/10 bg-white/5 p-5 mb-5">

                    <div className="flex items-center gap-2 text-[#6366f1] mb-3">

                      <Clock size={16} />

                      <span className="font-semibold">

                        Pricing Rationale

                      </span>

                    </div>

                    <p className="text-slate-300 leading-7 text-sm">

                      {rec.rationale}

                    </p>

                  </div>

                  {/* AGENT ANALYSIS */}

                  {rec.agent_analysis && (

                    <div className="space-y-5">

                      <div className="flex items-center gap-2 text-white">

                        <Zap
                          size={18}
                          className="text-[#00A19B]"
                        />

                        <h4 className="text-xl font-semibold">

                          Explainability Panel

                        </h4>

                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

                        {/* MARKET */}

                        <AgentCard
                          title="Market Agent"
                          color="text-pink-400"
                          icon={BarChart3}
                          rows={[
                            {
                              label:
                                "Competitor Price",

                              value:
                                `₹${rec.agent_analysis.market_agent?.competitor_price || 0}`,
                            },

                            {
                              label:
                                "Market Trend",

                              value:
                                rec.agent_analysis.market_agent?.market_trend || "N/A",
                            },
                          ]}
                        />

                        {/* DEMAND */}

                        <AgentCard
                          title="Demand Agent"
                          color="text-cyan-400"
                          icon={Activity}
                          rows={[
                            {
                              label:
                                "Demand Score",

                              value:
                                rec.agent_analysis.demand_agent?.demand_score || 0,
                            },

                            {
                              label:
                                "Trend",

                              value:
                                rec.agent_analysis.demand_agent?.trend || "N/A",
                            },
                          ]}
                        />

                        {/* INVENTORY */}

                        <AgentCard
                          title="Inventory Agent"
                          color="text-emerald-400"
                          icon={TrendingUp}
                          rows={[
                            {
                              label:
                                "Inventory",

                              value:
                                rec.agent_analysis.inventory_agent?.inventory_level || 0,
                            },

                            {
                              label:
                                "Stock Status",

                              value:
                                rec.agent_analysis.inventory_agent?.stock_status || "N/A",
                            },
                          ]}
                        />

                      </div>

                    </div>
                  )}

                  <button
                    className="
                      mt-7
                      w-full
                      rounded-2xl
                      py-4
                      font-semibold
                      text-white
                      transition-all
                      hover:opacity-90
                    "

                    style={{
                      background:
                        "linear-gradient(135deg,#00A19B,#6366f1)",
                    }}
                  >

                    <div className="flex items-center justify-center gap-2">

                      Apply Recommendation

                      <ArrowUpRight size={17} />

                    </div>

                  </button>

                </div>

              </motion.div>
            ))}

          </div>
        )}

      </div>

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

function AgentCard({
  title,
  rows,
  color,
  icon: Icon,
}) {

  return (

    <div className="rounded-2xl border border-white/10 bg-white/5 p-5">

      <div className={`flex items-center gap-2 mb-5 ${color}`}>

        <Icon size={16} />

        <h5 className="font-semibold">

          {title}

        </h5>

      </div>

      <div className="space-y-4 text-sm">

        {rows.map((row) => (

          <div
            key={row.label}

            className="flex items-center justify-between"
          >

            <span className="text-slate-400">

              {row.label}

            </span>

            <span className="text-white font-medium capitalize">

              {row.value}

            </span>

          </div>
        ))}

      </div>

    </div>
  );
}