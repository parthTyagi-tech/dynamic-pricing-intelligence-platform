import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Globe, BarChart2, ArrowRight, ExternalLink, Package, ChevronDown, Zap, TrendingUp, TrendingDown, Minus, ShoppingBag } from "lucide-react";
import apiClient from "../services/api";

const PLATFORM_ICONS = {
  "Amazon":         { icon: "Az", gradient: "from-[#FF9900] to-[#FF6600]" },
  "Flipkart":       { icon: "FK", gradient: "from-[#2874F0] to-[#1A5CC8]" },
  "Walmart":        { icon: "Wm", gradient: "from-[#0071CE] to-[#004C91]" },
  "Myntra":         { icon: "My", gradient: "from-[#FF3F6C] to-[#E5134A]" },
  "Ajio":           { icon: "Aj", gradient: "from-[#3E3E6B] to-[#2A2A4A]" },
  "Meesho":         { icon: "Me", gradient: "from-[#570A57] to-[#3D073D]" },
  "Shopify Stores": { icon: "Sh", gradient: "from-[#96BF48] to-[#7A9E38]" },
  "Brand Website":  { icon: "Bw", gradient: "from-[#1A1A2E] to-[#16213E]" },
};

export default function CompetitorMatcher() {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [platforms, setPlatforms] = useState([]);
  const [crawlStep, setCrawlStep] = useState("");

  // Fetch user's products for the dropdown
  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const res = await apiClient.get("/products");
        setProducts(res.data.products || []);
      } catch (err) {
        console.error("Failed to load products:", err);
      }
    };
    fetchProducts();
  }, []);

  const filteredProducts = products.filter(p =>
    `${p.brand} ${p.name}`.toLowerCase().includes(searchFilter.toLowerCase())
  );

  const handleRunIntelligence = async () => {
    if (!selectedProduct) return;
    setLoading(true);
    setPlatforms([]);

    const steps = [
      "Initializing Market Intelligence Engine...",
      "Deploying crawlers to 8 e-commerce platforms...",
      "Scraping Amazon India live product prices...",
      "Querying Flipkart, Myntra & Ajio catalogs...",
      "Fetching Walmart & Shopify marketplace data...",
      "Cross-referencing brand official store pricing...",
      "Normalizing currencies (INR → USD conversion)...",
      "Computing price gap analysis across all platforms..."
    ];

    for (const step of steps) {
      setCrawlStep(step);
      await new Promise(r => setTimeout(r, 700));
    }

    try {
      const res = await apiClient.post("/startup/matcher", {
        product_id: selectedProduct.id
      });
      setPlatforms(res.data.platforms || []);
    } catch (err) {
      console.error("Error running price intelligence:", err);
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (price, currency) => {
    if (!price || price === 0) return "N/A";
    const symbol = currency === "INR" ? "₹" : "$";
    return `${symbol}${Number(price).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <div className="space-y-6">
      {/* HEADER */}
      <div className="flex justify-between items-center bg-white/5 border border-white/8 rounded-3xl p-6 relative overflow-hidden"
           style={{ background: "rgba(10, 15, 30, 0.7)", backdropFilter: "blur(20px)" }}>
        <div className="absolute top-0 right-0 w-32 h-32 opacity-10 blur-3xl bg-gradient-to-br from-indigo-500 to-purple-600" />
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center bg-gradient-to-br from-indigo-600/30 to-purple-600/30 text-indigo-400 border border-indigo-500/20">
            <Globe size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-wide">Multi-Platform Price Intelligence</h1>
            <p className="text-xs text-slate-400 mt-1">
              Select your product and scan real-time prices across Amazon, Flipkart, Walmart, Myntra, Ajio, Meesho & more.
            </p>
          </div>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT — PRODUCT SELECTOR */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white/5 border border-white/8 rounded-3xl p-6 space-y-5"
               style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Package size={16} className="text-indigo-400" />
              Select Your Product
            </h3>

            {/* Product Dropdown */}
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="w-full flex items-center justify-between bg-white/5 border border-white/10 rounded-xl p-3 text-left cursor-pointer hover:border-indigo-500/40 transition-colors"
              >
                <span className="text-xs text-white truncate">
                  {selectedProduct
                    ? `${selectedProduct.brand ? selectedProduct.brand + " — " : ""}${selectedProduct.name}`
                    : "Choose from your catalog..."}
                </span>
                <ChevronDown size={14} className={`text-slate-400 transition-transform ${dropdownOpen ? "rotate-180" : ""}`} />
              </button>

              <AnimatePresence>
                {dropdownOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    className="absolute z-50 w-full mt-2 bg-[#0D1117] border border-white/10 rounded-xl shadow-2xl shadow-black/50 overflow-hidden"
                  >
                    <div className="p-2 border-b border-white/5">
                      <input
                        type="text"
                        value={searchFilter}
                        onChange={(e) => setSearchFilter(e.target.value)}
                        placeholder="Search products..."
                        className="w-full bg-white/5 border border-white/10 text-white text-xs rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50"
                        autoFocus
                      />
                    </div>
                    <div className="max-h-60 overflow-y-auto">
                      {filteredProducts.length === 0 && (
                        <p className="text-xs text-slate-500 p-3 text-center">No products found</p>
                      )}
                      {filteredProducts.map(p => (
                        <button
                          key={p.id}
                          onClick={() => {
                            setSelectedProduct(p);
                            setDropdownOpen(false);
                            setSearchFilter("");
                            setPlatforms([]);
                          }}
                          className={`w-full text-left p-3 hover:bg-indigo-500/10 transition-colors border-b border-white/5 last:border-0 cursor-pointer ${
                            selectedProduct?.id === p.id ? "bg-indigo-500/15" : ""
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-xs font-semibold text-white">{p.name}</p>
                              <p className="text-[10px] text-slate-400 mt-0.5">
                                {p.brand && <span className="text-indigo-400">{p.brand}</span>}
                                {p.brand && " · "}
                                {p.category}
                              </p>
                            </div>
                            <span className="text-xs font-mono text-emerald-400">₹{p.current_price}</span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Selected Product Details */}
            <AnimatePresence>
              {selectedProduct && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="bg-white/[0.03] border border-white/8 rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Your Product</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-mono">
                        {selectedProduct.sku}
                      </span>
                    </div>
                    <h4 className="text-sm font-bold text-white leading-snug">{selectedProduct.name}</h4>
                    {selectedProduct.brand && (
                      <span className="inline-block text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20 font-semibold">
                        {selectedProduct.brand}
                      </span>
                    )}
                    <div className="grid grid-cols-2 gap-3 pt-1">
                      <div>
                        <p className="text-[10px] text-slate-500">Your Price</p>
                        <p className="text-sm font-bold text-emerald-400 font-mono">₹{selectedProduct.current_price}</p
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500">Cost Price</p>
                        <p className="text-sm font-bold text-slate-300 font-mono">₹{selectedProduct.cost_price}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500">Category</p>
                        <p className="text-xs text-white capitalize">{selectedProduct.category?.replace("_", " ")}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500">Stock</p>
                        <p className="text-xs text-white">{selectedProduct.inventory_quantity} units</p>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <button
              onClick={handleRunIntelligence}
              disabled={loading || !selectedProduct}
              className="w-full flex items-center justify-center gap-2 py-3.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/20 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed select-none transition-all"
            >
              <Zap size={14} />
              Run Price Intelligence Across 8 Platforms
            </button>
          </div>
        </div>

        {/* RIGHT — RESULTS */}
        <div className="lg:col-span-2 bg-white/5 border border-white/8 rounded-3xl p-6 min-h-[400px] flex items-center justify-center relative overflow-hidden"
             style={{ background: "rgba(10, 15, 30, 0.2)" }}>
          
          <AnimatePresence mode="wait">
            {loading && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-5 text-center z-10"
              >
                <div className="relative">
                  <div className="w-20 h-20 rounded-full border-4 border-indigo-500/20 border-t-indigo-400 animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Globe size={24} className="text-indigo-400 animate-pulse" />
                  </div>
                </div>
                <div className="space-y-2">
                  <h4 className="text-sm font-bold text-white tracking-wide">Scanning 8 Marketplaces...</h4>
                  <p className="text-xs text-indigo-300 font-mono max-w-md animate-pulse">{crawlStep}</p>
                </div>
              </motion.div>
            )}

            {!loading && platforms.length === 0 && (
              <motion.div
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center gap-4 text-center"
              >
                <div className="w-20 h-20 rounded-2xl bg-white/[0.03] border border-white/8 flex items-center justify-center">
                  <ShoppingBag size={32} className="text-slate-600" />
                </div>
                <h4 className="text-sm font-semibold text-slate-400">No price data yet</h4>
                <p className="text-xs text-slate-500 max-w-sm">
                  Select a product from your catalog and run the price intelligence engine to compare prices across Amazon, Flipkart, Walmart, Myntra, Ajio, Meesho & more.
                </p>
              </motion.div>
            )}

            {!loading && platforms.length > 0 && (
              <motion.div
                key="results"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="w-full space-y-4"
              >
                {/* Results Header */}
                <div className="flex justify-between items-center">
                  <div>
                    <h4 className="text-sm font-bold text-white">Market Price Map</h4>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      Prices across {platforms.filter(p => p.available).length} platforms · Your price: <span className="text-emerald-400 font-mono">₹{selectedProduct?.current_price}</span>
                    </p>
                  </div>
                  <span className="text-[10px] text-emerald-300 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20 font-semibold font-mono flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Live Data
                  </span>
                </div>

                {/* Platform Cards */}
                <div className="space-y-2">
                  {platforms.map((p, idx) => {
                    const iconData = PLATFORM_ICONS[p.platform_name] || { icon: "??", gradient: "from-slate-600 to-slate-800" };
                    const isAvailable = p.available !== false;
                    const gap = p.price_gap_pct || 0;

                    return (
                      <motion.div
                        key={p.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.06 }}
                      >
                        <a
                          href={isAvailable ? p.url : undefined}
                          target="_blank"
                          rel="noreferrer"
                          className={`block rounded-xl border transition-all group ${
                            isAvailable
                              ? "bg-white/[0.03] border-white/8 hover:bg-white/[0.06] hover:border-white/15 cursor-pointer"
                              : "bg-white/[0.01] border-white/5 opacity-50 cursor-default"
                          }`}
                        >
                          <div className="flex items-center gap-4 p-4">
                            {/* Platform Badge */}
                            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${iconData.gradient} flex items-center justify-center text-white text-xs font-bold flex-shrink-0 shadow-lg`}>
                              {iconData.icon}
                            </div>

                            {/* Platform Name */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold text-white">{p.platform_name}</span>
                                {isAvailable && (
                                  <ExternalLink size={10} className="text-slate-500 group-hover:text-indigo-400 transition-colors" />
                                )}
                              </div>
                              <p className="text-[10px] text-slate-500 mt-0.5">
                                {isAvailable
                                  ? (p.in_stock ? "In Stock" : "Out of Stock")
                                  : "Not available on this platform"}
                              </p>
                            </div>

                            {/* Price */}
                            <div className="text-right flex-shrink-0">
                              {isAvailable && p.price > 0 ? (
                                <>
                                  <p className="text-sm font-bold text-white font-mono">
                                    {formatPrice(p.price, p.currency)}
                                  </p>
                                  {p.currency === "INR" && (
                                    <p className="text-[10px] text-slate-500 font-mono">≈ ${p.price_usd}</p>
                                  )}
                                </>
                              ) : (
                                <p className="text-xs text-slate-600">—</p>
                              )}
                            </div>

                            {/* Price Gap */}
                            <div className="w-20 text-right flex-shrink-0">
                              {isAvailable && p.price > 0 ? (
                                <div className="flex items-center justify-end gap-1">
                                  {gap > 0 ? (
                                    <TrendingUp size={12} className="text-emerald-400" />
                                  ) : gap < 0 ? (
                                    <TrendingDown size={12} className="text-red-400" />
                                  ) : (
                                    <Minus size={12} className="text-slate-400" />
                                  )}
                                  <span className={`text-xs font-bold font-mono ${
                                    gap > 0 ? "text-emerald-400" : gap < 0 ? "text-red-400" : "text-slate-400"
                                  }`}>
                                    {gap > 0 ? "+" : ""}{gap}%
                                  </span>
                                </div>
                              ) : (
                                <span className="text-xs text-slate-600">—</span>
                              )}
                            </div>
                          </div>
                        </a>
                      </motion.div>
                    );
                  })}
                </div>

                {/* Legend */}
                <div className="flex items-center gap-6 pt-2 border-t border-white/5">
                  <div className="flex items-center gap-1.5">
                    <TrendingUp size={10} className="text-emerald-400" />
                    <span className="text-[10px] text-slate-500">Competitor is more expensive (you're cheaper)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <TrendingDown size={10} className="text-red-400" />
                    <span className="text-[10px] text-slate-500">Competitor is cheaper (undercutting you)</span>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
