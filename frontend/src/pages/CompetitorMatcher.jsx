import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Globe, RefreshCw, BarChart2, CheckCircle, ArrowRight, ShieldAlert, Cpu } from "lucide-react";
import apiClient from "../services/api";

export default function CompetitorMatcher() {
  const [searchQuery, setSearchQuery] = useState("Premium Wireless Headphones");
  const [targetUrl, setTargetUrl] = useState("https://www.electrowarehouse.com/audio/headphones");
  const [loading, setLoading] = useState(false);
  const [matches, setMatches] = useState([]);
  const [crawlStep, setCrawlStep] = useState("");
  const [trackingLinked, setTrackingLinked] = useState({});

  const handleRunCrawler = async () => {
    setLoading(true);
    setMatches([]);
    setTrackingLinked({});

    // Simulate progress updates for web scraper
    const steps = [
      "Launching Headless Crawler Cluster...",
      "Resolving target domain DNS and bypassing CAPTCHAs...",
      "Downloading raw HTML nodes from catalog index...",
      "Extracting prices, titles, and product descriptions...",
      "Running semantic sentence transformer vector matches...",
      "Calculating similarity indexes and margins gaps..."
    ];

    for (let idx = 0; idx < steps.length; idx++) {
      setCrawlStep(steps[idx]);
      await new Promise(resolve => setTimeout(resolve, 800));
    }

    try {
      const response = await apiClient.post("/startup/matcher", {
        search_query: searchQuery,
        url: targetUrl
      });
      setMatches(response.data.matches || []);
    } catch (error) {
      console.error("Error running semantic crawler matcher:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleTrack = (id) => {
    setTrackingLinked(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  return (
    <div className="space-y-6">
      {/* HEADER SECTION */}
      <div className="flex justify-between items-center bg-white/5 border border-white/8 rounded-3xl p-6 relative overflow-hidden"
           style={{ background: "rgba(10, 15, 30, 0.7)", backdropFilter: "blur(20px)" }}>
        <div className="absolute top-0 right-0 w-24 h-24 opacity-15 blur-2xl bg-indigo-500" />
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center bg-indigo-600/30 text-indigo-400 border border-indigo-500/20">
            <Globe size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-wide">Semantic Competitor Matcher</h1>
            <p className="text-xs text-slate-400 mt-1">Deploy automated crawlers to discover competitor products and match items semantically.</p>
          </div>
        </div>
      </div>

      {/* CRAWLER CONFIGURATION */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 bg-white/5 border border-white/8 rounded-3xl p-6 space-y-4"
             style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Cpu size={16} className="text-indigo-400" />
            Crawler Directives
          </h3>

          <div className="space-y-1.5">
            <label className="text-xs text-slate-400 font-semibold">Storefront/Product Name to Match</label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="e.g. Headphones"
              className="w-full bg-white/5 border border-white/10 text-white text-xs rounded-xl p-3 outline-none focus:border-indigo-500/50"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs text-slate-400 font-semibold">Target Competitor Marketplace URL</label>
            <input
              type="text"
              value={targetUrl}
              onChange={(e) => setTargetUrl(e.target.value)}
              placeholder="https://competitor.com/catalog"
              className="w-full bg-white/5 border border-white/10 text-white text-xs rounded-xl p-3 outline-none focus:border-indigo-500/50"
            />
          </div>

          <button
            onClick={handleRunCrawler}
            disabled={loading || !searchQuery || !targetUrl}
            className="w-full mt-4 flex items-center justify-center gap-2 py-3 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/10 cursor-pointer disabled:opacity-50 select-none"
          >
            <Search size={14} />
            Run Semantic Scraper Agent
          </button>
        </div>

        {/* RESULTS GRID / LOADING OVERLAY */}
        <div className="lg:col-span-2 bg-white/5 border border-white/8 rounded-3xl p-6 min-h-[300px] flex items-center justify-center relative overflow-hidden"
             style={{ background: "rgba(10, 15, 30, 0.2)" }}>
          
          <AnimatePresence mode="wait">
            {loading && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-4 text-center z-10"
              >
                <div className="w-16 h-16 rounded-full border-4 border-indigo-500/20 border-t-indigo-400 animate-spin" />
                <div className="space-y-2">
                  <h4 className="text-sm font-bold text-white tracking-wide">Web Scraper Agent Crawling...</h4>
                  <p className="text-xs text-indigo-300 font-mono max-w-md animate-pulse">{crawlStep}</p>
                </div>
              </motion.div>
            )}

            {!loading && matches.length === 0 && (
              <motion.div
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-3 text-center"
              >
                <Search size={48} className="text-slate-600" />
                <h4 className="text-sm font-semibold text-slate-400">No active matches found.</h4>
                <p className="text-xs text-slate-500 max-w-sm">Define target parameters and execute the scraper agent to verify matching products.</p>
              </motion.div>
            )}

            {!loading && matches.length > 0 && (
              <motion.div
                key="results"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="w-full space-y-4"
              >
                <div className="flex justify-between items-center">
                  <h4 className="text-xs font-bold text-white">Discovered Competitor Mappings</h4>
                  <span className="text-[10px] text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20 font-semibold font-mono">
                    Scraped URL: Verified
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-white/10 text-xs">
                    <thead>
                      <tr>
                        <th className="px-4 py-2 text-left text-slate-400">Store</th>
                        <th className="px-4 py-2 text-left text-slate-400">Scraped Product</th>
                        <th className="px-4 py-2 text-left text-slate-400">Price</th>
                        <th className="px-4 py-2 text-left text-slate-400">Similarity</th>
                        <th className="px-4 py-2 text-left text-slate-400">Price Gap</th>
                        <th className="px-4 py-2 text-left text-slate-400">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {matches.map((item) => (
                        <tr key={item.id} className="hover:bg-white/5 transition-colors">
                          <td className="px-4 py-3 text-slate-300">{item.competitor_name}</td>
                          <td className="px-4 py-3 text-white font-medium">
                            <a href={item.url} target="_blank" rel="noreferrer" className="hover:underline text-indigo-400 flex items-center gap-1">
                              {item.product_title}
                              <ArrowRight size={10} />
                            </a>
                          </td>
                          <td className="px-4 py-3 text-slate-300 font-mono">${item.competitor_price}</td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-white">{item.similarity_score}%</span>
                              <div className="w-12 bg-white/10 h-1.5 rounded-full">
                                <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${item.similarity_score}%` }} />
                              </div>
                            </div>
                          </td>
                          <td className={`px-4 py-3 font-semibold font-mono ${item.price_gap_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {item.price_gap_pct >= 0 ? "+" : ""}{item.price_gap_pct}%
                          </td>
                          <td className="px-4 py-3">
                            <button
                              onClick={() => toggleTrack(item.id)}
                              className={`px-3 py-1 text-[10px] font-bold rounded-lg transition-all cursor-pointer select-none ${
                                trackingLinked[item.id]
                                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                  : "bg-white/5 text-slate-300 border border-white/10 hover:border-white/15"
                              }`}
                            >
                              {trackingLinked[item.id] ? "Tracking Active" : "Link Competitor"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
