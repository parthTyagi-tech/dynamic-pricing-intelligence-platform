import { useEffect, useState, useRef } from "react";
import { AnimatePresence } from "framer-motion";

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
  Boxes,
  XCircle,
  CheckCircle,
  ExternalLink,
} from "lucide-react";

import { motion } from "framer-motion";

import { useNavigate, useLocation } from "react-router-dom";

import { getProcessedCompetitors } from "./KlypupDashboard";

import apiClient from "../services/api";

export default function Recommendations() {

  const navigate = useNavigate();
  const location = useLocation();

  const [products, setProducts] = useState([]);

  const [recommendations, setRecommendations] = useState([]);

  const [loading, setLoading] = useState(true);
  const [generatingId, setGeneratingId] = useState(null);
  const [processingId, setProcessingId] = useState(null);
  
  const [toastConfig, setToastConfig] = useState({ show: false, message: "", isWarning: false });
  const recommendationsRef = useRef(null);

  const [selectedRecId, setSelectedRecId] = useState(null);
  const [modalDetails, setModalDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  const openDetailsModal = async (id) => {
    setSelectedRecId(id);
    setDetailsLoading(true);
    setModalDetails(null);
    try {
      const response = await apiClient.get(`/recommendations/${id}/details`);
      setModalDetails(response.data);
    } catch (error) {
      console.error(error);
      alert("Failed to load recommendation details.");
      setSelectedRecId(null);
    } finally {
      setDetailsLoading(false);
    }
  };

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

  useEffect(() => {
    if (location.state && location.state.autoOpenRecId) {
      openDetailsModal(location.state.autoOpenRecId);
      // Clear location state to prevent re-opening on refresh
      window.history.replaceState({}, document.title);
    }
  }, [location]);

  const generateRecommendation = async (productId) => {
    try {
      setGeneratingId(productId);

      const response = await apiClient.post(
        `/recommendations/generate/${productId}`
      );

      const recData = response.data.recommendation;

      if (response.status === 202 && recData && recData.status === "processing") {
        const recommendationId = recData.id;
        
        await new Promise((resolve, reject) => {
          let attempts = 0;
          const interval = setInterval(async () => {
            attempts++;
            if (attempts > 30) {
              clearInterval(interval);
              reject(new Error("Timeout waiting for recommendation pricing queue"));
              return;
            }
            try {
              const statusResponse = await apiClient.get(
                `/recommendations/status/${recommendationId}`
              );
              const statusData = statusResponse.data;
              if (statusData.success && statusData.status !== "processing") {
                clearInterval(interval);
                resolve(statusData);
              }
            } catch (err) {
              clearInterval(interval);
              reject(err);
            }
          }, 2000);
        }).then((statusData) => {
          fetchRecommendations();
          
          if (statusData.fallback_used) {
            setToastConfig({
              show: true,
              message: "Alert: LLM failed! Dynamic pricing defaulted to real catalog price.",
              isWarning: true
            });
          } else {
            setToastConfig({
              show: true,
              message: "Recommendation generated successfully!",
              isWarning: false
            });
          }
          setTimeout(() => setToastConfig({ show: false, message: "", isWarning: false }), 4000);
          
          if (recommendationsRef.current) {
            recommendationsRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        });
      } else {
        fetchRecommendations();
        const fallbackUsed = response.data.recommendation?.agent_analysis?.fallback_used || false;
        
        if (fallbackUsed) {
          setToastConfig({
            show: true,
            message: "Alert: LLM failed! Dynamic pricing defaulted to real catalog price.",
            isWarning: true
          });
        } else {
          setToastConfig({
            show: true,
            message: "Recommendation generated successfully!",
            isWarning: false
          });
        }
        setTimeout(() => setToastConfig({ show: false, message: "", isWarning: false }), 4000);

        if (recommendationsRef.current) {
          recommendationsRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }

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

  const handleApplyRecommendation = (recommendation) => {

    navigate("/approvals", {
      state: {
        recommendation,
      },
    });
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

      <div className="space-y-6" ref={recommendationsRef} style={{ scrollMarginTop: "24px" }}>

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

                onClick={() => openDetailsModal(rec.id)}

                className="
                  relative
                  overflow-hidden
                  rounded-3xl
                  border
                  border-white/10
                  bg-[rgba(17,24,39,0.78)]
                  p-7
                  backdrop-blur-xl
                  cursor-pointer
                  hover:border-[#00A19B]/30
                  transition-all
                  duration-300
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

                  {/* Embedded Audit Breakdown */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-6 border-t border-white/5 pt-5 text-left">
                    {/* Left Column: Matcher & Inventory */}
                    <div className="space-y-5">
                      {/* Competitor Matcher Details */}
                      <div className="glass-card p-4 space-y-3 bg-white/2 rounded-2xl border border-white/5">
                        <h4 className="text-xs font-bold text-white flex items-center gap-2 border-b border-white/5 pb-1.5">
                          <TrendingUp size={13} className="text-[#38bdf8]" />
                          Competitor Price Matcher (Live Data)
                        </h4>
                        <div className="space-y-2 max-h-[180px] overflow-y-auto pr-1 scrollbar-thin">
                          {rec.competitors && rec.competitors.length > 0 ? (
                            getProcessedCompetitors(rec.competitors, rec.product).map((comp) => (
                              <a
                                key={comp.id}
                                href={comp.url}
                                target="_blank"
                                rel="noreferrer"
                                className="flex justify-between items-center text-[11px] bg-white/2 p-1.5 rounded-lg border border-white/5 hover:bg-white/5 hover:border-[#38bdf8]/30 transition-all cursor-pointer group"
                              >
                                <span className="text-slate-355 font-semibold flex items-center gap-1.5 group-hover:text-white transition-colors">
                                  {comp.competitor_name}
                                  <ExternalLink size={8} className="text-slate-500 group-hover:text-[#38bdf8] transition-colors" />
                                </span>
                                <div className="flex items-center gap-1.5">
                                  <span className={comp.in_stock ? "text-emerald-400 font-bold" : "text-rose-400"}>
                                    {comp.in_stock ? "In Stock" : "Out of Stock"}
                                  </span>
                                  <span className="text-slate-400 font-mono font-bold bg-slate-800 px-1.5 py-0.5 rounded border border-white/5 group-hover:bg-slate-750 transition-colors">
                                    ₹{comp.competitor_price.toFixed(2)}
                                  </span>
                                </div>
                              </a>
                            ))
                          ) : (
                            <div className="text-[11px] text-slate-500 italic py-1">No competitor matches recorded.</div>
                          )}
                        </div>
                      </div>

                      {/* Inventory Analysis */}
                      <div className="glass-card p-4 space-y-3.5 bg-white/2 rounded-2xl border border-white/5">
                        <h4 className="text-xs font-bold text-white flex items-center gap-2 border-b border-white/5 pb-1.5">
                          <Boxes size={13} className="text-amber-500" />
                          Inventory & Cost Constraints
                        </h4>
                        <div className="grid grid-cols-2 gap-2.5 text-[11px]">
                          <div className="bg-white/2 p-2 rounded-lg border border-white/5">
                            <span className="text-slate-500 block text-[10px]">Inventory Level</span>
                            <strong className="text-white font-mono">{(rec.product?.inventory_quantity !== undefined ? rec.product.inventory_quantity : 0)} units</strong>
                          </div>
                          <div className="bg-white/2 p-2 rounded-lg border border-white/5">
                            <span className="text-slate-500 block text-[10px]">Cost Price</span>
                            <strong className="text-white font-mono">₹{(rec.product?.cost_price !== undefined ? rec.product.cost_price : 0).toFixed(2)}</strong>
                          </div>
                          <div className="bg-white/2 p-2 rounded-lg border border-white/5">
                            <span className="text-slate-500 block text-[10px]">Current Price</span>
                            <strong className="text-slate-350 font-mono">₹{(rec.product?.current_price !== undefined ? rec.product.current_price : 0).toFixed(2)}</strong>
                          </div>
                          <div className="bg-white/2 p-2 rounded-lg border border-white/5">
                            <span className="text-slate-500 block text-[10px]">Current Margin</span>
                            <strong className="text-[#7FF6EE] font-mono">
                              {(rec.product && rec.product.current_price && rec.product.cost_price) 
                                ? (((rec.product.current_price - rec.product.cost_price) / rec.product.current_price) * 100).toFixed(1) 
                                : "0.0"}%
                            </strong>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Right Column: Buying History & AI Optimization */}
                    <div className="space-y-5">
                      {/* Buying History */}
                      <div className="glass-card p-4 space-y-3 bg-white/2 rounded-2xl border border-white/5 flex flex-col max-h-[155px]">
                        <h4 className="text-xs font-bold text-white flex items-center gap-2 border-b border-white/5 pb-1.5">
                          <Activity size={13} className="text-[#00A19B]" />
                          Storefront Product Buying History
                        </h4>
                        <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin">
                          {rec.sales_history && rec.sales_history.length > 0 ? (
                            rec.sales_history.map((sale) => (
                              <div key={sale.id} className="flex justify-between items-center text-[11px] bg-white/2 p-1.5 rounded-lg border border-white/5">
                                <div>
                                  <div className="text-slate-300 font-semibold">Qty: {sale.quantity} units</div>
                                  <div className="text-[9px] text-slate-500">
                                    {new Date(sale.timestamp).toLocaleString()}
                                  </div>
                                </div>
                                <span className="text-emerald-400 font-bold font-mono bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded">
                                  ₹{sale.total_price.toFixed(2)}
                                </span>
                              </div>
                            ))
                          ) : (
                            <div className="text-[11px] text-slate-500 italic py-4 text-center">No storefront sales history.</div>
                          )}
                        </div>
                      </div>

                      {/* AI Optimization Explainability */}
                      <div className="glass-card p-4 space-y-3 bg-white/2 rounded-2xl border border-white/5">
                        <h4 className="text-xs font-bold text-white flex items-center gap-2 border-b border-white/5 pb-1.5">
                          <Brain size={13} className="text-[#6366f1]" />
                          LLM Pricing Strategy Optimization
                        </h4>
                        <div className="space-y-2 text-[11px] leading-relaxed">
                          <div className="flex justify-between items-center bg-white/2 p-1.5 rounded-lg border border-white/5">
                            <span className="text-slate-400">Optimized Price</span>
                            <strong className="text-emerald-400 font-mono bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded">
                              ₹{rec.recommended_price.toFixed(2)}
                            </strong>
                          </div>
                          <div className="flex justify-between items-center bg-white/2 p-1.5 rounded-lg border border-white/5">
                            <span className="text-slate-400">Confidence Score</span>
                            <strong className="text-white font-mono bg-slate-800 px-1.5 py-0.5 rounded">
                              {rec.confidence_score}%
                            </strong>
                          </div>
                          <div className="bg-slate-900/50 p-2 rounded-lg border border-white/5 space-y-1">
                            <span className="text-slate-400 font-bold block text-[10px] mb-0.5">Pricing Rationale (No Hallucination)</span>
                            <p className="text-slate-300 text-[10px] leading-relaxed line-clamp-3">{rec.rationale}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* AGENT ANALYSIS */}

                  {rec.agent_analysis && (

                    <div className="space-y-5 hidden">

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
                    onClick={(e) => {
                      e.stopPropagation();
                      handleApplyRecommendation(rec);
                    }}

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
      
      {/* SUCCESS/WARNING TOAST POPUP */}
      <AnimatePresence>
        {toastConfig.show && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.9 }}
            className={`fixed bottom-10 right-10 z-50 flex items-center gap-3 text-white px-6 py-4 rounded-2xl shadow-2xl font-semibold ${
              toastConfig.isWarning 
                ? "bg-amber-600 shadow-amber-600/30" 
                : "bg-[#00A19B] shadow-[#00A19B]/30"
            }`}
          >
            <Sparkles size={20} />
            {toastConfig.message}
          </motion.div>
        )}
      </AnimatePresence>

      {/* DETAILS MODAL */}
      {selectedRecId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
          <div 
            className="relative w-full max-w-4xl max-h-[85vh] overflow-y-auto rounded-[28px] border border-white/10 p-6 lg:p-8 space-y-6 scrollbar-thin text-left"
            style={{
              background: "linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(9, 13, 26, 0.98))",
              boxShadow: "0 24px 60px rgba(0,0,0,0.5)"
            }}
          >
            {/* Close Button */}
            <button 
              onClick={() => { setSelectedRecId(null); setModalDetails(null); }}
              className="absolute top-5 right-5 text-slate-400 hover:text-white bg-white/5 hover:bg-white/10 p-2 rounded-full transition-all cursor-pointer"
            >
              <XCircle size={22} />
            </button>

            {detailsLoading ? (
              <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-400">
                <span className="w-8 h-8 border-3 border-[#00A19B] border-t-transparent rounded-full animate-spin" />
                <span>Fetching real-time comparisons & buying history...</span>
              </div>
            ) : modalDetails ? (
              <>
                {/* Header */}
                <div className="border-b border-white/5 pb-4">
                  <div className="flex items-center gap-2.5 text-[#7FF6EE] text-xs font-bold uppercase tracking-wider mb-2">
                    <Sparkles size={14} className="animate-pulse" />
                    AI Pricing Orchestrator Audit
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-1">
                    {modalDetails.product.name}
                  </h3>
                  <p className="text-xs text-slate-400 font-mono">
                    SKU: {modalDetails.product.sku} | Category: {modalDetails.product.category}
                  </p>
                </div>

                {/* Grid Content */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Left Column: Matcher & Inventory */}
                  <div className="space-y-6">
                    {/* Competitor Matcher Details */}
                    <div className="glass-card p-5 space-y-4">
                      <h4 className="text-sm font-bold text-white flex items-center gap-2 border-b border-white/5 pb-2">
                        <TrendingUp size={15} className="text-[#38bdf8]" />
                        Competitor Price Matcher (Live Data)
                      </h4>
                      <div className="space-y-2.5">
                        {modalDetails.competitors && modalDetails.competitors.length > 0 ? (
                          getProcessedCompetitors(modalDetails.competitors, modalDetails.product).map((comp) => (
                            <a
                              key={comp.id}
                              href={comp.url}
                              target="_blank"
                              rel="noreferrer"
                              className="flex justify-between items-center text-xs bg-white/2 p-2 rounded-lg border border-white/5 hover:bg-white/5 hover:border-[#38bdf8]/30 transition-all cursor-pointer group"
                            >
                              <span className="text-slate-300 font-semibold flex items-center gap-1.5 group-hover:text-white transition-colors">
                                {comp.competitor_name}
                                <ExternalLink size={10} className="text-slate-500 group-hover:text-[#38bdf8] transition-colors" />
                              </span>
                              <div className="flex items-center gap-2">
                                <span className={comp.in_stock ? "text-emerald-400 font-bold" : "text-rose-400"}>
                                  {comp.in_stock ? "In Stock" : "Out of Stock"}
                                </span>
                                <span className="text-slate-400 font-mono font-bold bg-slate-800 px-2 py-0.5 rounded border border-white/5 group-hover:bg-slate-750 transition-colors">
                                  ₹{comp.competitor_price.toFixed(2)}
                                </span>
                              </div>
                            </a>
                          ))
                        ) : (
                          <div className="text-xs text-slate-500 italic py-2">No competitor matches recorded.</div>
                        )}
                      </div>
                    </div>

                    {/* Inventory Analysis */}
                    <div className="glass-card p-5 space-y-3">
                      <h4 className="text-sm font-bold text-white flex items-center gap-2 border-b border-white/5 pb-2">
                        <Boxes size={15} className="text-amber-500" />
                        Inventory & Cost Constraints
                      </h4>
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="bg-white/2 p-2.5 rounded-lg border border-white/5 space-y-1">
                          <span className="text-slate-500 block">Inventory Level</span>
                          <strong className="text-white text-sm font-mono">{modalDetails.product.inventory_quantity} units</strong>
                        </div>
                        <div className="bg-white/2 p-2.5 rounded-lg border border-white/5 space-y-1">
                          <span className="text-slate-500 block">Cost Price</span>
                          <strong className="text-white text-sm font-mono">₹{modalDetails.product.cost_price.toFixed(2)}</strong>
                        </div>
                        <div className="bg-white/2 p-2.5 rounded-lg border border-white/5 space-y-1">
                          <span className="text-slate-500 block">Current Price</span>
                          <strong className="text-slate-350 text-sm font-mono">₹{modalDetails.product.current_price.toFixed(2)}</strong>
                        </div>
                        <div className="bg-white/2 p-2.5 rounded-lg border border-white/5 space-y-1">
                          <span className="text-slate-500 block">Current Margin</span>
                          <strong className="text-[#7FF6EE] text-sm font-mono">
                            {(((modalDetails.product.current_price - modalDetails.product.cost_price) / modalDetails.product.current_price) * 100).toFixed(1)}%
                          </strong>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Buying History & AI Optimization */}
                  <div className="space-y-6">
                    {/* Buying History */}
                    <div className="glass-card p-5 space-y-3 flex flex-col max-h-[220px]">
                      <h4 className="text-sm font-bold text-white flex items-center gap-2 border-b border-white/5 pb-2">
                        <Activity size={15} className="text-[#00A19B]" />
                        Storefront Product Buying History
                      </h4>
                      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 scrollbar-thin">
                        {modalDetails.sales_history && modalDetails.sales_history.length > 0 ? (
                          modalDetails.sales_history.map((sale) => (
                            <div key={sale.id} className="flex justify-between items-center text-xs bg-white/2 p-2 rounded-lg border border-white/5">
                              <div>
                                <div className="text-slate-300 font-semibold">Qty: {sale.quantity} units</div>
                                <div className="text-[10px] text-slate-500">
                                  {new Date(sale.timestamp).toLocaleString()}
                                </div>
                              </div>
                              <span className="text-emerald-400 font-bold font-mono bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                                ₹{sale.total_price.toFixed(2)}
                              </span>
                            </div>
                          ))
                        ) : (
                          <div className="text-xs text-slate-500 italic py-6 text-center">No storefront sales history recorded.</div>
                        )}
                      </div>
                    </div>

                    {/* AI Optimization Explainability */}
                    <div className="glass-card p-5 space-y-4">
                      <h4 className="text-sm font-bold text-white flex items-center gap-2 border-b border-white/5 pb-2">
                        <Brain size={15} className="text-[#6366f1]" />
                        LLM Pricing Strategy Optimization
                      </h4>
                      <div className="space-y-3 text-xs leading-relaxed">
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">Optimized Recommendation</span>
                          <strong className="text-emerald-400 font-mono text-sm bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                            ₹{modalDetails.recommendation.recommended_price.toFixed(2)}
                          </strong>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">Confidence Score</span>
                          <strong className="text-white font-mono bg-slate-800 px-2 py-0.5 rounded">
                            {modalDetails.recommendation.confidence_score}%
                          </strong>
                        </div>
                        <div className="bg-white/2 p-3 rounded-lg border border-white/5 space-y-1">
                          <span className="text-slate-500 font-bold block mb-1">Pricing Rationale (No Hallucination)</span>
                          <p className="text-slate-300 text-[11px] leading-relaxed">{modalDetails.recommendation.rationale}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Footer Actions */}
                <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/5">
                  <button 
                    onClick={() => { setSelectedRecId(null); setModalDetails(null); }}
                    className="px-5 py-2.5 text-xs font-semibold text-slate-400 hover:text-white bg-slate-800/50 hover:bg-slate-800 rounded-xl transition-all cursor-pointer"
                  >
                    Close Analysis
                  </button>
                  <button 
                    onClick={async () => {
                      await apiClient.post(`/approvals/reject/${modalDetails.recommendation.id}`);
                      setSelectedRecId(null);
                      setModalDetails(null);
                      fetchRecommendations();
                    }}
                    className="px-5 py-2.5 text-xs font-semibold text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-xl hover:bg-rose-500 hover:text-white transition-all cursor-pointer"
                  >
                    Reject Price
                  </button>
                  <button 
                    onClick={async () => {
                      await apiClient.post(`/approvals/approve/${modalDetails.recommendation.id}`);
                      setSelectedRecId(null);
                      setModalDetails(null);
                      fetchRecommendations();
                    }}
                    className="px-5 py-2.5 text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-xl hover:bg-emerald-500 hover:text-white transition-all cursor-pointer"
                  >
                    Approve Price
                  </button>
                </div>
              </>
            ) : null}
          </div>
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

const formatText = (text) => {

  if (!text || typeof text !== "string") {

    return text;
  }

  return text
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) =>
      char.toUpperCase()
    );
};

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

            className="flex items-start justify-between gap-3"
          >

            <span className="text-slate-400">

              {row.label}

            </span>

            <span className="text-white font-medium break-words text-right">

              {formatText(row.value)}

            </span>

          </div>
        ))}

      </div>

    </div>
  );
}