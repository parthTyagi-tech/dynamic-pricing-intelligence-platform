import { useEffect, useState } from "react";

import {
  Sparkles,
  Brain,
  RefreshCw,
  TrendingUp,
  Clock,
} from "lucide-react";

import apiClient from "../services/api";

export default function Recommendations() {

  const [products, setProducts] = useState([]);

  const [recommendations, setRecommendations] = useState([]);

  const [loading, setLoading] = useState(true);

  const [generatingId, setGeneratingId] = useState(null);

  /* ======================================
     FETCH PRODUCTS
  ====================================== */

  const fetchProducts = async () => {

    try {

      const response = await apiClient.get("/products");

      setProducts(
        response.data.products || []
      );

    } catch (error) {

      console.error(error);

    }
  };

  /* ======================================
     FETCH RECOMMENDATIONS
  ====================================== */

  const fetchRecommendations = async () => {

    try {

      const response = await apiClient.get(
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

  /* ======================================
     GENERATE AI RECOMMENDATION
  ====================================== */

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

    <div className="p-8 text-white">

      {/* ======================================
          HEADER
      ====================================== */}

      <div className="flex items-center justify-between mb-10">

        <div>

          <h1 className="text-4xl font-bold mb-2">
            AI Recommendations
          </h1>

          <p className="text-slate-400">
            Generate AI-powered pricing insights
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
          PRODUCTS SECTION
      ====================================== */}

      <div className="mb-12">

        <h2 className="text-2xl font-semibold mb-6">
          Generate Recommendations
        </h2>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {products.map((product) => (

            <div
              key={product.id}
              className="bg-slate-900 border border-white/10 rounded-3xl p-6"
            >

              <div className="flex items-start justify-between mb-6">

                <div>

                  <h3 className="text-2xl font-semibold mb-2">
                    {product.name}
                  </h3>

                  <p className="text-slate-400">
                    SKU: {product.sku}
                  </p>

                </div>

                <div className="w-14 h-14 rounded-2xl bg-violet-500/20 text-violet-400 flex items-center justify-center">
                  <Brain />
                </div>

              </div>

              <div className="space-y-3 mb-6 text-sm">

                <div className="flex justify-between">
                  <span className="text-slate-400">
                    Current Price
                  </span>

                  <span>
                    ₹{product.current_price}
                  </span>
                </div>

                <div className="flex justify-between">
                  <span className="text-slate-400">
                    Inventory
                  </span>

                  <span>
                    {product.inventory_quantity}
                  </span>
                </div>

                <div className="flex justify-between">
                  <span className="text-slate-400">
                    Margin %
                  </span>

                  <span>
                    {product.margin_percentage}%
                  </span>
                </div>

              </div>

              <button
                onClick={() =>
                  generateRecommendation(product.id)
                }
                disabled={generatingId === product.id}
                className="w-full bg-violet-600 hover:bg-violet-700 rounded-xl py-4 font-semibold transition-all flex items-center justify-center gap-2"
              >

                <Sparkles size={18} />

                {generatingId === product.id
                  ? "Generating..."
                  : "Generate AI Recommendation"}

              </button>

            </div>

          ))}

        </div>

      </div>

      {/* ======================================
          RECOMMENDATIONS SECTION
      ====================================== */}

      <div>

        <h2 className="text-2xl font-semibold mb-6">
          Generated Recommendations
        </h2>

        {loading ? (

          <div className="text-slate-400">
            Loading...
          </div>

        ) : recommendations.length === 0 ? (

          <div className="bg-slate-900 border border-white/10 rounded-3xl p-12 text-center text-slate-400">
            No recommendations generated yet.
          </div>

        ) : (

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

            {recommendations.map((rec) => (

              <div
                key={rec.id}
                className="bg-slate-900 border border-white/10 rounded-3xl p-6"
              >

                <div className="flex items-start justify-between mb-6">

                  <div>

                    <h3 className="text-2xl font-semibold mb-2">
                      {rec.product?.name || "Unknown Product"}
                    </h3>

                    <p className="text-slate-400">
                      {rec.product?.sku || "No SKU"}
                    </p>

                  </div>

                  <div className="w-14 h-14 rounded-2xl bg-pink-500/20 text-pink-400 flex items-center justify-center">
                    <TrendingUp />
                  </div>

                </div>

                <div className="space-y-4 text-sm">

                  <div className="flex justify-between">
                    <span className="text-slate-400">
                      Current Price
                    </span>

                    <span>
                      ₹{rec.product?.current_price || 0}
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

                  <div className="flex justify-between">
                    <span className="text-slate-400">
                      Status
                    </span>

                    <span className="capitalize">
                      {rec.status}
                    </span>
                  </div>

                  {/* ======================================
                      AI SUMMARY
                  ====================================== */}

                  <div className="pt-4 border-t border-white/10">

                    <p className="text-slate-400 mb-2">
                      AI Summary
                    </p>

                    <p>
                      {rec.ai_summary}
                    </p>

                  </div>

                  {/* ======================================
                      RATIONALE
                  ====================================== */}

                  <div className="pt-4 border-t border-white/10">

                    <div className="flex items-center gap-2 text-slate-400 mb-2">
                      <Clock size={16} />
                      Rationale
                    </div>

                    <p>
                      {rec.rationale}
                    </p>

                  </div>

                  {/* ======================================
                      EXPLAINABILITY PANEL
                  ====================================== */}

                  {rec.agent_analysis && (

                    <div className="mt-6 pt-6 border-t border-white/10">

                      <h4 className="text-lg font-semibold mb-4 text-violet-400">
                        AI Explainability
                      </h4>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

                        {/* MARKET AGENT */}

                        <div className="bg-slate-800/60 rounded-2xl p-4">

                          <h5 className="font-semibold text-pink-400 mb-3">
                            Market Agent
                          </h5>

                          <div className="space-y-2 text-sm">

                            <div className="flex justify-between">
                              <span className="text-slate-400">
                                Competitor Price
                              </span>

                              <span>
                                ₹{
                                  rec.agent_analysis.market_agent
                                    ?.competitor_price
                                }
                              </span>
                            </div>

                            <div className="flex justify-between">
                              <span className="text-slate-400">
                                Market Trend
                              </span>

                              <span className="capitalize">
                                {
                                  rec.agent_analysis.market_agent
                                    ?.market_trend
                                }
                              </span>
                            </div>

                          </div>

                        </div>

                        {/* DEMAND AGENT */}

                        <div className="bg-slate-800/60 rounded-2xl p-4">

                          <h5 className="font-semibold text-cyan-400 mb-3">
                            Demand Agent
                          </h5>

                          <div className="space-y-2 text-sm">

                            <div className="flex justify-between">
                              <span className="text-slate-400">
                                Demand Score
                              </span>

                              <span>
                                {
                                  rec.agent_analysis.demand_agent
                                    ?.demand_score
                                }
                              </span>
                            </div>

                            <div className="flex justify-between">
                              <span className="text-slate-400">
                                Demand Trend
                              </span>

                              <span className="capitalize">
                                {
                                  rec.agent_analysis.demand_agent
                                    ?.trend
                                }
                              </span>
                            </div>

                          </div>

                        </div>

                        {/* INVENTORY AGENT */}

                        <div className="bg-slate-800/60 rounded-2xl p-4">

                          <h5 className="font-semibold text-green-400 mb-3">
                            Inventory Agent
                          </h5>

                          <div className="space-y-2 text-sm">

                            <div className="flex justify-between">
                              <span className="text-slate-400">
                                Inventory
                              </span>

                              <span>
                                {
                                  rec.agent_analysis.inventory_agent
                                    ?.inventory_level
                                }
                              </span>
                            </div>

                            <div className="flex justify-between">
                              <span className="text-slate-400">
                                Stock Status
                              </span>

                              <span className="capitalize">
                                {
                                  rec.agent_analysis.inventory_agent
                                    ?.stock_status
                                }
                              </span>
                            </div>

                          </div>

                        </div>

                      </div>

                    </div>

                  )}

                </div>

              </div>

            ))}

          </div>

        )}

      </div>

    </div>
  );
}