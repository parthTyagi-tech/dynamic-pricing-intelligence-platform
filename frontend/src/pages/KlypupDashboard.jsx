import { useState, useEffect, useCallback } from "react";
import apiClient from "../services/api";

import {
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import {
  TrendingUp,
  Activity,
  Brain,
  DollarSign,
  IndianRupee,
  ShoppingCart,
  Percent,
  Eye,
  Crosshair,
  Sparkles,
  Zap,
  Database,
  RefreshCw,
  Layers,
  Globe,
  ChevronRight,
  ExternalLink,
  Terminal,
  Check,
  X,
  ShieldAlert,
  ShoppingBag,
  Boxes,
  XCircle,
} from "lucide-react";

import { motion } from "framer-motion";

import { useAuth } from "../context/AuthContext";

/* ── Static data for pipeline workflow cards ── */
const workflowSteps = [
  { icon: Database, label: "Market Data", desc: "Real-time ingestion from 500+ sources", color: "#10b981" },
  { icon: Brain, label: "AI Processing", desc: "ML models analyze patterns & signals", color: "#10b981" },
  { icon: Activity, label: "Prediction Engine", desc: "Demand forecasting & price elasticity", color: "#818cf8" },
  { icon: Zap, label: "Pricing Output", desc: "Optimal price delivered in <50ms", color: "#34d399" },
];

const aiCards = [
  { icon: Brain, title: "Machine Learning", desc: "Gradient Boosting + Neural Networks trained on 10M+ pricing events", tag: "Core AI", accent: "from-[#059669] to-[#14b8a6]", color: "#10b981" },
  { icon: TrendingUp, title: "Predictive Analytics", desc: "Time-series forecasting with 94.2% demand accuracy", tag: "Forecasting", accent: "from-emerald-500 to-teal-500", color: "#34d399" },
  { icon: Globe, title: "Market Intelligence", desc: "Real-time crawl of 2,400+ competitor storefronts", tag: "Intelligence", accent: "from-sky-500 to-cyan-500", color: "#10b981" },
  { icon: Activity, title: "Real-time Engine", desc: "Sub-50ms pricing decisions at 1M+ RPM capacity", tag: "Performance", accent: "from-[#059669] to-[#8b5cf6]", color: "#818cf8" },
  { icon: RefreshCw, title: "Demand Forecasting", desc: "LSTM + seasonal decomposition for 30-day outlook", tag: "Forecasting", accent: "from-rose-500 to-pink-500", color: "#f472b6" },
  { icon: Layers, title: "Competitive AI", desc: "Automated gap analysis and undercutting alerts", tag: "Competition", accent: "from-amber-500 to-orange-500", color: "#fb923c" },
];

const howItWorksSteps = [
  { step: "01", title: "Data Ingestion", icon: Database, desc: "We continuously pull pricing signals from competitor sites, market feeds, historical sales, seasonal patterns, and consumer behavior datasets — processing over 2 million data points per hour." },
  { step: "02", title: "Pattern Recognition", icon: Brain, desc: "Our ML pipeline identifies non-obvious pricing patterns: demand elasticity curves, time-of-day effects, competitor response latency, and category-level price sensitivity." },
  { step: "03", title: "Price Prediction", icon: TrendingUp, desc: "A stacked ensemble of XGBoost, LightGBM, and LSTM neural networks outputs confidence-weighted price recommendations per product SKU, updated every 15 minutes." },
  { step: "04", title: "Recommendation Output", icon: Zap, desc: "Optimal prices are pushed via API to your storefront or ERP system. Every recommendation includes rationale, confidence score, and projected revenue impact." },
];

/* ── Description list for 5 Agent Workflow Roles (What is for what) ── */
const agentsWorkflow = [
  {
    name: "Market Intelligence Agent",
    icon: Globe,
    color: "#10b981",
    whatIsFor: "Competitor Price Tracking & Gap Estimation",
    desc: "Crawl sites like Amazon, Walmart, and Flipkart in real time. Analyzes competitive pricing spreads, tracks category pricing trends, and flags competitor markdowns or stockouts."
  },
  {
    name: "Demand Forecast Agent",
    icon: TrendingUp,
    color: "#34d399",
    whatIsFor: "Price Elasticity & Sales Velocity Predictions",
    desc: "Calculates seasonal cycles, historical consumer velocity, and demand curves. Predicts how customer order volume shifts at different price levels to capture margin on hot items."
  },
  {
    name: "Inventory Cost Agent",
    icon: ShoppingBag,
    color: "#10b981",
    whatIsFor: "Stock Optimization & Clearance Triggering",
    desc: "Tracks warehouse stock quantities and days-of-supply metrics. Triggers strategic price decreases to clear slow-moving inventory, or tags premiums to optimize yield on scarce stock."
  },
  {
    name: "Compliance Agent",
    icon: ShieldAlert,
    color: "#fb923c",
    whatIsFor: "Enforcing Business Constraints & Margin Floors",
    desc: "Reviews all generated recommendations against organizational rules: checks that minimum profit margin is kept and limits maximum daily price fluctuations to prevent runaway anomalies."
  },
  {
    name: "Pricing Strategy Agent",
    icon: Brain,
    color: "#818cf8",
    whatIsFor: "Orchestrating Composite Recommendations & Explanations",
    desc: "Acts as the pipeline controller. Synthesizes inputs from the other 4 agents, calculates the finalized confidence score, and structures full natural-language explainability rationales."
  }
];

const DIRECT_PRODUCT_URLS = {
  "Premium Wireless Headphones": {
    "Amazon": "https://www.amazon.in/Sony-WH-1000XM4-Wireless-Cancelling-Headphones/dp/B08C5FM5AQ",
    "Flipkart": "https://www.flipkart.com/sony-wh-1000xm4-bluetooth-headset/p/itm9e4f5a432890c",
    "Walmart": "https://www.walmart.com/ip/Sony-WH-1000XM4-Wireless-Noise-Canceling-Over-Ear-Headphones-Black/568856234",
    "Ebay": "https://www.ebay.com/itm/324289056231",
    "BestBuy": "https://www.bestbuy.com/site/sony-wh-1000xm4-wireless-noise-cancelling-over-the-ear-headphones-black/6408359.p?skuId=6408359",
    "Target": "https://www.target.com/p/sony-wh-1000xm4-wireless-noise-cancelling-over-ear-headphones/-/A-80177724"
  },
  "Mechanical Gaming Keyboard": {
    "Amazon": "https://www.amazon.in/Razer-BlackWidow-Mechanical-Gaming-Keyboard/dp/B08ADLFFS5",
    "Flipkart": "https://www.flipkart.com/razer-blackwidow-v3-mechanical-gaming-keyboard/p/itmd5c4a4f8902be",
    "Walmart": "https://www.walmart.com/ip/Razer-BlackWidow-V3-Mechanical-Gaming-Keyboard-Green-Switch/902847120",
    "Ebay": "https://www.ebay.com/itm/284102948123",
    "BestBuy": "https://www.bestbuy.com/site/razer-blackwidow-v3-wired-gaming-mechanical-keyboard-green-switches-black/6425936.p?skuId=6425936",
    "Target": "https://www.target.com/p/razer-blackwidow-v3-mechanical-gaming-keyboard/-/A-81284719"
  },
  "Ultra HD Projector 4K": {
    "Amazon": "https://www.amazon.in/BenQ-TK850-Projector-Brightness-Keystone/dp/B083M12D8C",
    "Flipkart": "https://www.flipkart.com/benq-tk850-ultra-hd-4k-projector/p/itm5d8c4a938210e",
    "Walmart": "https://www.walmart.com/ip/BenQ-TK850-True-4K-UHD-Home-Theater-Projector/567283490",
    "Ebay": "https://www.ebay.com/itm/193290481023",
    "BestBuy": "https://www.bestbuy.com/site/benq-tk850-4k-projector-white/6398402.p?skuId=6398402",
    "Target": "https://www.target.com/p/benq-tk850-4k-uhd-home-theater-projector/-/A-79284391"
  },
  "Smart Watch Series X": {
    "Amazon": "https://www.amazon.in/Apple-Watch-GPS-41mm-Aluminium/dp/B09G9F1B25",
    "Flipkart": "https://www.flipkart.com/apple-watch-series-8-gps-41mm/p/itmd8a4d432890bc",
    "Walmart": "https://www.walmart.com/ip/Apple-Watch-Series-8-GPS-41mm-Midnight-Aluminum-Case/128392810",
    "Ebay": "https://www.ebay.com/itm/154382910482",
    "BestBuy": "https://www.bestbuy.com/site/apple-watch-series-8-gps-41mm-midnight-aluminum-case/6500329.p?skuId=6500329",
    "Target": "https://www.target.com/p/apple-watch-series-8-gps-41mm/-/A-86284910"
  },
  "Running Sneakers Zoom": {
    "Amazon": "https://www.amazon.in/Nike-Air-Zoom-Pegasus-Sneakers/dp/B09248F12B",
    "Flipkart": "https://www.flipkart.com/nike-air-zoom-pegasus-39-running-shoes-men/p/itm9d4f5a3289abc",
    "Walmart": "https://www.walmart.com/ip/Nike-Air-Zoom-Pegasus-39-Men-s-Running-Shoes/492810398",
    "Ebay": "https://www.ebay.com/itm/234190284712",
    "BestBuy": "https://www.bestbuy.com/site/nike-mens-air-zoom-pegasus-39-black/6510398.p?skuId=6510398",
    "Target": "https://www.target.com/p/nike-men-s-air-zoom-pegasus-39-running-shoes/-/A-84284912"
  },
  "Waterproof Windbreaker Jacket": {
    "Amazon": "https://www.amazon.in/North-Face-Resolve-Waterproof-Windbreaker/dp/B004LI9Y9E",
    "Flipkart": "https://www.flipkart.com/the-north-face-mens-resolve-2-jacket/p/itm4b3d8c2e987f0",
    "Walmart": "https://www.walmart.com/ip/The-North-Face-Men-s-Resolve-2-Waterproof-Jacket/589128391",
    "Ebay": "https://www.ebay.com/itm/114928103984",
    "BestBuy": "https://www.bestbuy.com/site/the-north-face-mens-resolve-2-jacket/6491283.p?skuId=6491283",
    "Target": "https://www.target.com/p/the-north-face-men-s-resolve-2-jacket/-/A-82192841"
  },
  "Classic Denim Jeans": {
    "Amazon": "https://www.amazon.in/Levis-Mens-511-Slim-Jeans/dp/B0018OR12A",
    "Flipkart": "https://www.flipkart.com/levi-s-511-slim-fit-men-jeans/p/itmd5f4a8e9b0c2e",
    "Walmart": "https://www.walmart.com/ip/Levi-s-Men-s-511-Slim-Fit-Jeans/502810982",
    "Ebay": "https://www.ebay.com/itm/334190827391",
    "BestBuy": "https://www.bestbuy.com/site/levis-mens-511-slim-fit-jeans/6419283.p?skuId=6419283",
    "Target": "https://www.target.com/p/levi-s-men-s-511-slim-fit-jeans/-/A-80129845"
  },
  "Ergonomic Office Chair": {
    "Amazon": "https://www.amazon.in/Herman-Miller-Aeron-Chair-Size/dp/B01N8X63X7",
    "Flipkart": "https://www.flipkart.com/herman-miller-aeron-ergonomic-office-chair/p/itm4d9e2b0c3f5a8",
    "Walmart": "https://www.walmart.com/ip/Herman-Miller-Aeron-Ergonomic-Office-Chair-Size-B/293810293",
    "Ebay": "https://www.ebay.com/itm/184918290182",
    "BestBuy": "https://www.bestbuy.com/site/herman-miller-aeron-chair/6492019.p?skuId=6492019",
    "Target": "https://www.target.com/p/herman-miller-aeron-office-chair/-/A-81289381"
  },
  "Cold Brew Coffee Maker": {
    "Amazon": "https://www.amazon.in/Bodum-11683-01USA-Chambord-Coffee-34-Ounce/dp/B004278F3W",
    "Flipkart": "https://www.flipkart.com/bodum-cold-brew-coffee-maker-carafe/p/itm5a4d32890efbc",
    "Walmart": "https://www.walmart.com/ip/Bodum-Cold-Brew-Coffee-Maker-carafe/928391029",
    "Ebay": "https://www.ebay.com/itm/274910283912",
    "BestBuy": "https://www.bestbuy.com/site/bodum-cold-brew-coffee-maker/6328491.p?skuId=6328491",
    "Target": "https://www.target.com/p/bodum-cold-brew-coffee-maker/-/A-84291839"
  },
  "Dimmable LED Desk Lamp": {
    "Amazon": "https://www.amazon.in/Philips-Dimmable-Table-Integrated-White/dp/B07954LFFW",
    "Flipkart": "https://www.flipkart.com/philips-smart-led-desk-lamp/p/itm4c5a9b8d2ef01",
    "Walmart": "https://www.walmart.com/ip/Philips-Smart-LED-Desk-Lamp-Dimmable/304918290",
    "Ebay": "https://www.ebay.com/itm/114920183948",
    "BestBuy": "https://www.bestbuy.com/site/philips-smart-desk-lamp/6492810.p?skuId=6492810",
    "Target": "https://www.target.com/p/philips-smart-led-desk-lamp/-/A-82193810"
  },
  "Hydrating Face Serum": {
    "Amazon": "https://www.amazon.in/Ordinary-Hyaluronic-Acid-2-B5/dp/B01MXV547V",
    "Flipkart": "https://www.flipkart.com/the-ordinary-hyaluronic-acid-2-b5-serum/p/itm9e4d5c3b8a1f2",
    "Walmart": "https://www.walmart.com/ip/The-Ordinary-Hyaluronic-Acid-2-B5-Hydrating-Serum/593810291",
    "Ebay": "https://www.ebay.com/itm/354928193821",
    "BestBuy": "https://www.bestbuy.com/site/the-ordinary-hyaluronic-acid-serum/6429182.p?skuId=6429182",
    "Target": "https://www.target.com/p/the-ordinary-hyaluronic-acid-2-b5/-/A-80293810"
  },
  "Mineral Sunscreen SPF 50": {
    "Amazon": "https://www.amazon.in/Roche-Posay-Anthelios-Mineral-Sunscreen-Fluid/dp/B004W55086",
    "Flipkart": "https://www.flipkart.com/la-roche-posay-anthelios-spf-50-sunscreen/p/itmd5f4e9bc2e1a0",
    "Walmart": "https://www.walmart.com/ip/La-Roche-Posay-Anthelios-Mineral-Sunscreen-SPF-50/293810298",
    "Ebay": "https://www.ebay.com/itm/334918290182",
    "BestBuy": "https://www.bestbuy.com/site/la-roche-posay-mineral-sunscreen/6428391.p?skuId=6428391",
    "Target": "https://www.target.com/p/la-roche-posay-anthelios-mineral-sunscreen-spf-50/-/A-80129381"
  },
  "Resistance Bands Set": {
    "Amazon": "https://www.amazon.in/Boldfit-Resistance-Workout-Exercises-Stretch/dp/B08F5G3C5D",
    "Flipkart": "https://www.flipkart.com/boldfit-resistance-bands-set-loop/p/itm4d9e2c0b3a8f9",
    "Walmart": "https://www.walmart.com/ip/Boldfit-Heavy-Duty-Resistance-Bands-Set/583920193",
    "Ebay": "https://www.ebay.com/itm/274928103984",
    "BestBuy": "https://www.bestbuy.com/site/boldfit-resistance-bands/6492819.p?skuId=6492819",
    "Target": "https://www.target.com/p/boldfit-resistance-bands-set/-/A-83291839"
  },
  "Premium Yoga Mat": {
    "Amazon": "https://www.amazon.in/Manduka-PRO-Yoga-Mat-Black/dp/B00078A1D4",
    "Flipkart": "https://www.flipkart.com/manduka-pro-yoga-mat-extra-thick/p/itm5a4e9bc2e1f8d",
    "Walmart": "https://www.walmart.com/ip/Manduka-PRO-Yoga-Mat-6mm-Thick/938210398",
    "Ebay": "https://www.ebay.com/itm/194928103810",
    "BestBuy": "https://www.bestbuy.com/site/manduka-pro-yoga-mat/6328498.p?skuId=6328498",
    "Target": "https://www.target.com/p/manduka-pro-yoga-mat-6mm/-/A-84291038"
  }
};

export const getProcessedCompetitors = (competitorList, productInput) => {
  if (!competitorList) return [];
  
  let product = { name: "", brand: "", current_price: 15840 };
  if (typeof productInput === "string") {
    product.name = productInput;
    const brands = ["Sony", "Razer", "BenQ", "Apple", "Nike", "The North Face", "Levi's", "Herman Miller", "Bodum", "Philips", "The Ordinary", "La Roche-Posay", "Boldfit", "Manduka"];
    const foundBrand = brands.find(b => productInput.toLowerCase().includes(b.toLowerCase()));
    if (foundBrand) {
      product.brand = foundBrand;
    }
  } else if (productInput && typeof productInput === "object") {
    product = {
      name: productInput.name || "",
      brand: productInput.brand || productInput.brand_name || "",
      current_price: productInput.current_price || 15840
    };
  }

  const platforms = ["Amazon", "Flipkart", "Walmart", "Ebay", "BestBuy", "Target"];
  const uniqueMatches = {};
  
  platforms.forEach((platform) => {
    uniqueMatches[platform] = {
      id: platform,
      competitor_name: platform,
      competitor_price: 0,
      in_stock: true
    };
  });
  
  competitorList.forEach((c) => {
    let name = c.competitor_name;
    if (name === "AI Market Agent") {
      const emptyPlatform = platforms.find(p => uniqueMatches[p].competitor_price === 0);
      if (emptyPlatform) {
        name = emptyPlatform;
      } else {
        return;
      }
    }
    
    if (platforms.includes(name)) {
      uniqueMatches[name] = {
        id: c.id || name,
        competitor_name: name,
        competitor_price: c.competitor_price || uniqueMatches[name].competitor_price,
        in_stock: c.in_stock !== undefined ? c.in_stock : true
      };
    }
  });
  
  const getSearchUrl = (platformName, pObj) => {
    const name = pObj.name || "";
    const brand = pObj.brand || "";
    const basePrice = pObj.current_price || 15840;
    
    const isUSD = platformName === "Walmart" || platformName === "Ebay" || platformName === "BestBuy" || platformName === "Target";
    const priceInLocal = isUSD ? (basePrice / 83) : basePrice;
    
    const minPrice = Math.round(priceInLocal * 0.85);
    const maxPrice = Math.round(priceInLocal * 1.15);
    
    const searchQuery = brand && !name.toLowerCase().includes(brand.toLowerCase())
      ? `${brand} ${name}`
      : name;
    
    const encodedQuery = encodeURIComponent(searchQuery || "product");
    const encodedBrand = encodeURIComponent(brand || "");

    switch (platformName) {
      case "Amazon":
        return `https://www.amazon.in/s?k=${encodedQuery}${brand ? `&rh=p_89%3A${encodedBrand}` : ""}&low-price=${minPrice}&high-price=${maxPrice}`;
      case "Flipkart":
        return `https://www.flipkart.com/search?q=${encodedQuery}&p%5B%5D=facets.price_range.from%3D${minPrice}&p%5B%5D=facets.price_range.to%3D${maxPrice}`;
      case "Walmart":
        return `https://www.walmart.com/search?q=${encodedQuery}&min_price=${minPrice}&max_price=${maxPrice}`;
      case "Ebay":
        return `https://www.ebay.com/sch/i.html?_nkw=${encodedQuery}&_udlo=${minPrice}&_udhi=${maxPrice}`;
      case "BestBuy":
        return `https://www.bestbuy.com/site/searchpage.jsp?st=${encodedQuery}&qp=currentprice_facet%3DPrice~${minPrice}-${maxPrice}`;
      case "Target":
        return `https://www.target.com/s?searchTerm=${encodedQuery}&priceRange=${minPrice}-${maxPrice}`;
      default:
        return `https://www.google.com/search?q=${platformName}+${encodedQuery}`;
    }
  };

  return Object.values(uniqueMatches).map(c => ({
    ...c,
    competitor_price: c.competitor_price || 15840.0,
    url: getSearchUrl(c.competitor_name, product)
  })).slice(0, 6);
};

export default function KlypupDashboard() {
  const { user } = useAuth();

  const [metrics, setMetrics] = useState({});
  const [revenue, setRevenue] = useState([]);
  const [pricingTrends, setPricingTrends] = useState([]);
  const [demand, setDemand] = useState([]);
  const [aiPerf, setAiPerf] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [liveFeed, setLiveFeed] = useState([]);
  const [liveSales, setLiveSales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actioningId, setActioningId] = useState(null);

  const [selectedRecId, setSelectedRecId] = useState(null);
  const [modalDetails, setModalDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  const fetchDashboard = useCallback(async (isSilent = false) => {
    if (!isSilent) {
      setLoading(true);
    }

    try {
      const [
        metricsRes,
        revenueRes,
        pricingRes,
        demandRes,
        aiPerfRes,
        recommendationsRes,
        liveFeedRes,
        liveSalesRes,
      ] = await Promise.all([
        apiClient.get("/dashboard/metrics"),
        apiClient.get("/dashboard/revenue"),
        apiClient.get("/dashboard/pricing-trends"),
        apiClient.get("/dashboard/demand"),
        apiClient.get("/dashboard/ai-performance"),
        apiClient.get("/dashboard/recommendations"),
        apiClient.get("/dashboard/live-activity").catch(() => ({ data: { feed: [] } })),
        apiClient.get("/dashboard/live-sales").catch(() => ({ data: { sales: [] } })),
      ]);

      setMetrics(metricsRes.data || {});
      setRevenue(revenueRes.data || []);
      setPricingTrends(pricingRes.data || []);
      setDemand(demandRes.data || []);
      setAiPerf(aiPerfRes.data || []);
      setRecommendations(recommendationsRes.data || []);
      setLiveFeed(liveFeedRes.data?.feed || []);
      setLiveSales(liveSalesRes.data?.sales || []);
    } catch (error) {
      console.error("Dashboard Fetch Error:", error);
    } finally {
      if (!isSilent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchDashboard(false);

    // Dynamic 5-second polling interval for real-time visual updates
    const interval = setInterval(() => {
      fetchDashboard(true);
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchDashboard]);

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

  const handleApprove = async (id) => {
    try {
      setActioningId(id);
      await apiClient.post(`/approvals/approve/${id}`);
      await fetchDashboard(true);
    } catch (error) {
      console.error("Approval Error:", error);
      alert(error.response?.data?.message || "Failed to approve recommendation.");
    } finally {
      setActioningId(null);
    }
  };

  const handleReject = async (id) => {
    try {
      setActioningId(id);
      await apiClient.post(`/approvals/reject/${id}`);
      await fetchDashboard(true);
    } catch (error) {
      console.error("Rejection Error:", error);
      alert(error.response?.data?.message || "Failed to reject recommendation.");
    } finally {
      setActioningId(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="glass-card px-10 py-8 flex flex-col items-center gap-5">
          <div
            style={{
              width: 54,
              height: 54,
              borderRadius: "50%",
              border: "4px solid rgba(255,255,255,0.08)",
              borderTop: "4px solid #059669",
              animation: "spin 1s linear infinite",
            }}
          />
          <div className="text-center">
            <h2 className="text-xl font-bold text-white">Klypup AI</h2>
            <p className="text-slate-400 mt-1 text-sm">Loading dashboard analytics...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-10">
      {/* ── Hero Banner ── */}
      <div
        className="relative overflow-hidden rounded-[28px] border border-white/10 p-8 lg:p-10"
        style={{
          background: "linear-gradient(135deg,rgba(8,8,8,0.72),rgba(0,0,0,0.85))",
          boxShadow: "0 24px 60px rgba(0,0,0,0.35)",
        }}
      >
        <div
          style={{
            position: "absolute",
            width: 260,
            height: 260,
            borderRadius: "50%",
            background: "rgba(0,161,155,0.16)",
            filter: "blur(100px)",
            top: -80,
            right: -40,
          }}
        />

        <div className="relative z-10">
          <div className="flex items-center justify-between flex-wrap gap-4 mb-6">
            <div className="inline-flex items-center gap-2 bg-[#059669]/10 border border-[#059669]/20 text-[#ffffff] px-4 py-2 rounded-full text-sm">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              Active Real-time Intelligence Connected
            </div>
            
            {/* Real-time Inventory Stock Indicator */}
            <div className="text-xs text-slate-300 bg-white/5 border border-white/10 px-4 py-2 rounded-xl backdrop-blur-md">
              Catalog Total Stock: <strong className="text-white font-mono text-sm">{(metrics?.totalInventory || 0).toLocaleString()}</strong> units
            </div>
          </div>

          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-8">
            <div className="space-y-4">
              <h1 className="text-4xl lg:text-5xl font-bold text-white leading-tight">
                Welcome back,
                <span className="gradient-text"> {user?.name || "User"}</span>
              </h1>
              <p className="text-slate-400 text-base max-w-2xl leading-7">
                Monitor live pricing intelligence, demand analytics, revenue performance, and recommendation activity in real time.
              </p>
              
              {/* Product Category Stock Breakdown Dashboard (Live) */}
              <div className="pt-2">
                <span className="text-slate-500 uppercase tracking-widest text-[10px] font-semibold block mb-2.5">
                  Dynamic Category Stock Catalog
                </span>
                <div className="flex flex-wrap gap-2.5">
                  <div className="bg-slate-900/60 border border-white/5 px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 text-slate-300">
                    <span className="text-teal-400">🖥️</span> Electronics: 
                    <strong className="text-white font-mono font-bold">{metrics?.categoryDistribution?.electronics || 0}</strong>
                  </div>
                  <div className="bg-slate-900/60 border border-white/5 px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 text-slate-300">
                    <span className="text-sky-400">👕</span> Apparel: 
                    <strong className="text-white font-mono font-bold">{metrics?.categoryDistribution?.apparel || 0}</strong>
                  </div>
                  <div className="bg-slate-900/60 border border-white/5 px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 text-slate-300">
                    <span className="text-indigo-400">🏠</span> Home Goods: 
                    <strong className="text-white font-mono font-bold">{metrics?.categoryDistribution?.home_goods || 0}</strong>
                  </div>
                  <div className="bg-slate-900/60 border border-white/5 px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 text-slate-300">
                    <span className="text-pink-400">💄</span> Beauty: 
                    <strong className="text-white font-mono font-bold">{metrics?.categoryDistribution?.beauty || 0}</strong>
                  </div>
                  <div className="bg-slate-900/60 border border-white/5 px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 text-slate-300">
                    <span className="text-amber-400">⚽</span> Sports: 
                    <strong className="text-white font-mono font-bold">{metrics?.categoryDistribution?.sports || 0}</strong>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 min-w-[280px] lg:self-center">
              <MiniStat title="Active Models" value={metrics?.activeModelsCount || 5} />
              <MiniStat title="AI Signals" value={`${metrics?.aiSignalsStrength || 98}%`} />
              <MiniStat title="Live Products" value={metrics?.liveProducts || 0} />
              <MiniStat title="Reviews Queue" value={metrics?.reviewsQueueCount || 0} />
            </div>
          </div>
        </div>
      </div>

      {/* ── Metric Cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        <MetricCard
          icon={IndianRupee}
          title="Dynamic Revenue"
          value={`₹${(metrics?.totalRevenue || 0).toLocaleString()}`}
          sub="Live catalog valuation"
          accent="from-[#059669] to-[#14b8a6]"
        />
        <MetricCard
          icon={Crosshair}
          title="Pricing Accuracy"
          value={`${metrics?.pricingAccuracy || 0}%`}
          sub="Predictive pricing fidelity"
          accent="from-[#059669] to-[#8b5cf6]"
        />
        <MetricCard
          icon={Activity}
          title="Market Volatility"
          value={`${metrics?.marketVolatility || 0}%`}
          sub="Competitor offset spread"
          accent="from-amber-500 to-orange-500"
        />
        <MetricCard
          icon={Brain}
          title="AI Confidence"
          value={`${metrics?.aiConfidence || 0}%`}
          sub="Average decision confidence"
          accent="from-emerald-500 to-teal-500"
        />
        <MetricCard
          icon={Eye}
          title="Competitor Actions"
          value={metrics?.competitorChanges || 0}
          sub="Price logs captured"
          accent="from-rose-500 to-pink-500"
        />
        <MetricCard
          icon={Percent}
          title="Approval Conversion"
          value={`${metrics?.conversionRate || 0}%`}
          sub="Analysts accept rate"
          accent="from-sky-500 to-cyan-500"
        />
      </div>

      {/* ── Real-Time Interactive Charts Grid ── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Revenue Performance Area Chart */}
        <div className="glass-card p-6 relative overflow-hidden">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <DollarSign size={18} className="text-[#059669]" />
              Revenue Optimization Impact
            </h3>
            <span className="text-xs text-slate-400 bg-slate-800 px-2.5 py-1 rounded-full font-mono">
              Monthly Active Lift
            </span>
          </div>
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={revenue} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#059669" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#059669" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#059669" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#059669" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" stroke="rgba(255,255,255,0.4)" fontSize={11} />
                <YAxis stroke="rgba(255,255,255,0.4)" fontSize={11} />
                <Tooltip
                  contentStyle={{ background: "rgba(15,23,42,0.95)", borderColor: "rgba(255,255,255,0.08)", borderRadius: 16 }}
                  labelStyle={{ color: "#fff", fontWeight: "bold" }}
                />
                <Area type="monotone" dataKey="actual" stroke="#059669" strokeWidth={3} fillOpacity={1} fill="url(#colorActual)" name="Actual Revenue (₹)" />
                <Area type="monotone" dataKey="predicted" stroke="#059669" strokeWidth={3} fillOpacity={1} fill="url(#colorPredicted)" name="AI Target Revenue (₹)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pricing Trends Line Chart */}
        <div className="glass-card p-6 relative overflow-hidden">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <TrendingUp size={18} className="text-[#10b981]" />
              Live Pricing Signal Trends
            </h3>
            <span className="text-xs text-slate-400 bg-slate-800 px-2.5 py-1 rounded-full font-mono">
              Live Hourly Feed
            </span>
          </div>
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={pricingTrends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="time" stroke="rgba(255,255,255,0.4)" fontSize={11} />
                <YAxis stroke="rgba(255,255,255,0.4)" fontSize={11} />
                <Tooltip
                  contentStyle={{ background: "rgba(15,23,42,0.95)", borderColor: "rgba(255,255,255,0.08)", borderRadius: 16 }}
                />
                <Line type="monotone" dataKey="aiPrice" stroke="#14b8a6" strokeWidth={3} dot={{ r: 4 }} name="AI Suggested (₹)" />
                <Line type="monotone" dataKey="competitorPrice" stroke="#fb923c" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="3 3" name="Competitor Avg (₹)" />
                <Line type="monotone" dataKey="marketAverage" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} name="Market Avg (₹)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Category Demand Bar Chart */}
        <div className="glass-card p-6 relative overflow-hidden">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Layers size={18} className="text-amber-500" />
              Category Demand Elasticity Velocity
            </h3>
            <span className="text-xs text-slate-400 bg-slate-800 px-2.5 py-1 rounded-full font-mono">
              Signals Index
            </span>
          </div>
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={demand} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="category" stroke="rgba(255,255,255,0.4)" fontSize={11} />
                <YAxis stroke="rgba(255,255,255,0.4)" fontSize={11} />
                <Tooltip
                  contentStyle={{ background: "rgba(15,23,42,0.95)", borderColor: "rgba(255,255,255,0.08)", borderRadius: 16 }}
                />
                <Bar dataKey="demand" fill="#059669" radius={[6, 6, 0, 0]} name="Demand Strength" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* AI Performance Radar Chart */}
        <div className="glass-card p-6 relative overflow-hidden">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Brain size={18} className="text-violet-400" />
              AI Decision Engine Health
            </h3>
            <span className="text-xs text-slate-400 bg-slate-800 px-2.5 py-1 rounded-full font-mono">
              Diagnostic Scores
            </span>
          </div>
          <div className="h-[280px] w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="80%" data={aiPerf}>
                <PolarGrid stroke="rgba(255,255,255,0.08)" />
                <PolarAngleAxis dataKey="metric" stroke="rgba(255,255,255,0.6)" fontSize={11} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="rgba(255,255,255,0.3)" fontSize={9} />
                <Radar name="AI Metrics" dataKey="score" stroke="#818cf8" fill="#818cf8" fillOpacity={0.35} />
                <Tooltip
                  contentStyle={{ background: "rgba(15,23,42,0.95)", borderColor: "rgba(255,255,255,0.08)", borderRadius: 16 }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Live Recommendation Queue, Live Purchases & Live Activity Ingestion Stream ── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Live Recommendation Queue (1/3 width) */}
        <div className="glass-card p-6 flex flex-col h-[400px]">
          <div className="flex items-center justify-between mb-6 flex-shrink-0">
            <div className="flex items-center gap-2">
              <Brain size={18} className="text-[#059669]" />
              <h3 className="text-lg font-bold text-white">Live AI Pricing Queue</h3>
            </div>
            <span className="text-xs text-slate-400 bg-slate-800 px-3 py-1 rounded-full font-mono">
              {recommendations.length} Pending
            </span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-4 pr-1 scrollbar-thin">
            {recommendations.length > 0 ? (
              recommendations.map((rec) => (
                <div
                  key={rec.id}
                  onClick={() => openDetailsModal(rec.id)}
                  className="flex flex-col gap-2 p-3.5 rounded-xl border border-white/5 bg-white/2 hover:border-[#059669]/30 transition-all duration-300 text-xs cursor-pointer"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-white font-semibold line-clamp-1">{rec.productName}</span>
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#059669]/10 text-[#ffffff] shrink-0">
                      {rec.confidence}%
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">{rec.reason}</p>
                  
                  <div className="flex items-center justify-between gap-2 pt-1 border-t border-white/5">
                    <div className="flex flex-col">
                      <span className="text-[10px] text-slate-500">Current</span>
                      <strong className="text-slate-300 font-mono">₹{Number(rec.currentPrice).toFixed(2)}</strong>
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[10px] text-slate-500">AI Recommended</span>
                      <strong className="text-[#ffffff] font-mono">₹{Number(rec.suggestedPrice).toFixed(2)}</strong>
                    </div>
                    <span
                      className={`font-bold font-mono self-end ${
                        rec.suggestedPrice >= rec.currentPrice ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {rec.suggestedPrice >= rec.currentPrice
                        ? `+₹${(rec.suggestedPrice - rec.currentPrice).toFixed(2)}`
                        : `-₹${(rec.currentPrice - rec.suggestedPrice).toFixed(2)}`}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 mt-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleReject(rec.id); }}
                      disabled={actioningId !== null}
                      className="flex-1 flex items-center justify-center gap-1 py-1 text-[10px] font-semibold text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-md hover:bg-rose-500 hover:text-white transition-all disabled:opacity-50 cursor-pointer"
                    >
                      {actioningId === rec.id ? (
                        <span className="w-3 h-3 border-2 border-t-transparent rounded-full animate-spin border-rose-400" />
                      ) : (
                        <>
                          <X size={11} />
                          Reject
                        </>
                      )}
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleApprove(rec.id); }}
                      disabled={actioningId !== null}
                      className="flex-1 flex items-center justify-center gap-1 py-1 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-md hover:bg-emerald-500 hover:text-white transition-all disabled:opacity-50 cursor-pointer"
                    >
                      {actioningId === rec.id ? (
                        <span className="w-3 h-3 border-2 border-t-transparent rounded-full animate-spin border-emerald-400" />
                      ) : (
                        <>
                          <Check size={11} />
                          Approve
                        </>
                      )}
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-500 italic text-sm">
                <Sparkles size={24} className="text-slate-600 animate-pulse" />
                Pricing Queue Cleared!
              </div>
            )}
          </div>
        </div>

        {/* Live Storefront Purchases Feed (1/3 width) */}
        <div className="glass-card p-6 flex flex-col h-[400px]">
          <div className="flex items-center justify-between mb-6 flex-shrink-0">
            <div className="flex items-center gap-2">
              <ShoppingCart size={18} className="text-[#059669]" />
              <h3 className="text-lg font-bold text-white">Live Purchases Feed</h3>
            </div>
            <span className="text-xs text-slate-400 bg-slate-800 px-3 py-1 rounded-full font-mono">
              {liveSales.length} Sales
            </span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1 scrollbar-thin">
            {liveSales.length > 0 ? (
              liveSales.map((sale) => (
                <div
                  key={sale.id}
                  className="flex items-center justify-between gap-3 p-3 rounded-xl border border-white/5 bg-white/2 hover:border-[#059669]/20 transition-all duration-300"
                >
                  <div className="space-y-0.5">
                    <div className="text-white font-semibold text-xs leading-snug line-clamp-1">
                      {sale.product_name}
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-slate-400">
                      <span>Qty: <strong>{sale.quantity}</strong></span>
                      <span>•</span>
                      <span>{new Date(sale.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
                    </div>
                  </div>
                  
                  <div className="text-right flex-shrink-0 space-y-0.5">
                    <div className="text-[#ffffff] font-bold font-mono text-xs">
                      ₹{sale.total_price.toFixed(2)}
                    </div>
                    <div className="text-[9px] text-slate-500 font-mono">
                      Stock: {sale.remaining_inventory}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-500 italic text-sm">
                <ShoppingBag size={24} className="text-slate-600 animate-pulse" />
                Waiting for storefront purchases...
              </div>
            )}
          </div>
        </div>

        {/* Live Activity Terminal Ingestion Feed (1/3 width) */}
        <div className="glass-card p-6 flex flex-col h-[400px]">
          <div className="flex items-center justify-between mb-4 flex-shrink-0">
            <div className="flex items-center gap-2">
              <Terminal size={18} className="text-[#059669]" />
              <h3 className="text-lg font-bold text-white">Live Ingestion Stream</h3>
            </div>
            <span className="inline-flex items-center gap-1.5 text-xs text-slate-400 bg-slate-800 px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Ingestion Active
            </span>
          </div>

          <div className="flex-1 overflow-y-auto font-mono text-[11px] bg-black/40 p-4 rounded-xl border border-white/5 space-y-2.5 scrollbar-thin">
            {liveFeed.length > 0 ? (
              liveFeed.map((item, idx) => (
                <div key={idx} className="flex gap-2 items-start leading-relaxed text-left">
                  <span className="text-slate-600 flex-shrink-0">
                    {new Date(item.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </span>
                  <span className={item.type === "price_action" ? "text-[#10b981]" : (item.type === "purchase" ? "text-emerald-400" : "text-slate-300")}>
                    <span className={item.type === "price_action" ? "text-[#059669] font-bold" : (item.type === "purchase" ? "text-emerald-500 font-bold" : "text-amber-500/80 font-bold")}>
                      {item.type === "price_action" ? "[ACTION] " : (item.type === "purchase" ? "[PURCHASE] " : "[SCRAPE] ")}
                    </span>
                    {item.message}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-slate-500 italic text-center py-10">Waiting for live signal activity...</div>
            )}
          </div>
        </div>
      </div>

      {/* ── Agent Ingestion & Decision Workflow Matrix (What is for what) ── */}
      <div className="space-y-6">
        <SectionHeading
          label="AGENT ROLES EXPLAINED"
          title="Agent Workflow Matrix: What is for What?"
          desc="Understand exactly how each of Klypup's 5 autonomous backend AI agents operates to evaluate and secure maximum product yield."
        />
        
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {agentsWorkflow.map((agent) => (
            <motion.div
              key={agent.name}
              whileHover={{ y: -4 }}
              className="glass-card p-6 border border-white/10 relative overflow-hidden flex flex-col justify-between"
            >
              <div className="absolute top-0 right-0 w-24 h-24 opacity-10 blur-2xl" style={{ backgroundColor: agent.color }} />
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/5 border border-white/10">
                    <agent.icon size={20} style={{ color: agent.color }} />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white leading-tight">{agent.name}</h4>
                    <span className="text-[10px] uppercase font-bold tracking-wider" style={{ color: agent.color }}>
                      {agent.whatIsFor}
                    </span>
                  </div>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">{agent.desc}</p>
              </div>
              <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-[10px] text-slate-500">
                <span>Domain: {agent.name.split(" ")[0]}</span>
                <span className="font-mono text-[#059669]">Status: Active</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ── What Powers Klypup ── */}
      <div className="space-y-6">
        <SectionHeading
          label="AI ARCHITECTURE"
          title="What Powers Klypup?"
          desc="A multi-model AI system trained on billions of pricing signals, running 24/7 to maximize your revenue."
        />

        {/* Workflow pipeline */}
        <div className="flex items-stretch gap-0 flex-wrap">
          {workflowSteps.map((step, i) => (
            <div key={i} className="flex items-center flex-1 min-w-[140px]">
              <motion.div
                whileHover={{ y: -3 }}
                className="flex-1 glass-card p-4 text-center"
                style={{ borderColor: step.color + "33" }}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-3"
                  style={{ background: step.color + "18" }}
                >
                  <step.icon size={18} style={{ color: step.color }} />
                </div>
                <div className="text-sm font-semibold text-white mb-1">{step.label}</div>
                <div className="text-xs text-slate-400 leading-relaxed">{step.desc}</div>
              </motion.div>
              {i < workflowSteps.length - 1 && (
                <ChevronRight size={18} className="text-slate-600 flex-shrink-0 mx-1" />
              )}
            </div>
          ))}
        </div>

        {/* AI capability cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {aiCards.map((card) => (
            <motion.div
              key={card.title}
              whileHover={{ y: -4 }}
              className="glass-card p-5 relative overflow-hidden"
            >
              <div
                className={`absolute top-0 right-0 w-24 h-24 opacity-15 blur-3xl bg-gradient-to-br ${card.accent}`}
              />
              <div className="relative z-10">
                <div className="flex items-start justify-between mb-4">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center"
                    style={{ background: card.color + "18" }}
                  >
                    <card.icon size={18} style={{ color: card.color }} />
                  </div>
                  <span
                    className="text-xs font-semibold px-2 py-1 rounded-md"
                    style={{ background: card.color + "15", color: card.color }}
                  >
                    {card.tag}
                  </span>
                </div>
                <div className="text-sm font-semibold text-white mb-2">{card.title}</div>
                <div className="text-xs text-slate-400 leading-relaxed">{card.desc}</div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ── How Our AI Works ── */}
      <div className="space-y-5">
        <SectionHeading
          label="AI TRANSPARENCY"
          title="How Our AI Works"
          desc="A step-by-step look inside the Klypup pricing intelligence pipeline."
        />

        <div className="flex flex-col gap-3">
          {howItWorksSteps.map((s, i) => (
            <motion.div
              key={i}
              whileHover={{ x: 4 }}
              className="glass-card p-5 flex gap-5"
            >
              <div
                className="text-4xl font-extrabold flex-shrink-0 leading-none select-none"
                style={{ color: "rgba(0,161,155,0.2)" }}
              >
                {s.step}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ background: "rgba(0,161,155,0.12)" }}
                  >
                    <s.icon size={15} style={{ color: "#10b981" }} />
                  </div>
                  <div className="text-sm font-semibold text-white">{s.title}</div>
                </div>
                <p className="text-sm text-slate-400 leading-relaxed">{s.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

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
                <span className="w-8 h-8 border-3 border-[#059669] border-t-transparent rounded-full animate-spin" />
                <span>Fetching real-time comparisons & buying history...</span>
              </div>
            ) : modalDetails ? (
              <>
                {/* Header */}
                <div className="border-b border-white/5 pb-4">
                  <div className="flex items-center gap-2.5 text-[#ffffff] text-xs font-bold uppercase tracking-wider mb-2">
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
                        <TrendingUp size={15} className="text-[#10b981]" />
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
                              className="flex justify-between items-center text-xs bg-white/2 p-2 rounded-lg border border-white/5 hover:bg-white/5 hover:border-[#10b981]/30 transition-all cursor-pointer group"
                            >
                              <span className="text-slate-300 font-semibold flex items-center gap-1.5 group-hover:text-white transition-colors">
                                {comp.competitor_name}
                                <ExternalLink size={10} className="text-slate-500 group-hover:text-[#10b981] transition-colors" />
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
                          <strong className="text-[#ffffff] text-sm font-mono">
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
                        <Activity size={15} className="text-[#059669]" />
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
                        <Brain size={15} className="text-[#059669]" />
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
                      await handleReject(modalDetails.recommendation.id);
                      setSelectedRecId(null);
                      setModalDetails(null);
                    }}
                    className="px-5 py-2.5 text-xs font-semibold text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-xl hover:bg-rose-500 hover:text-white transition-all cursor-pointer"
                  >
                    Reject Price
                  </button>
                  <button 
                    onClick={async () => {
                      await handleApprove(modalDetails.recommendation.id);
                      setSelectedRecId(null);
                      setModalDetails(null);
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

/* ── Sub-components ── */

function SectionHeading({ label, title, desc }) {
  return (
    <div>
      <div className="inline-flex items-center gap-2 bg-[#059669]/10 border border-[#059669]/20 text-[#ffffff] px-3 py-1.5 rounded-full text-xs font-semibold mb-3 tracking-wide">
        <Sparkles size={11} />
        {label}
      </div>
      <h2 className="text-2xl font-sentient font-normal text-white mb-1">{title}</h2>
      {desc && <p className="text-slate-400 text-sm">{desc}</p>}
    </div>
  );
}

function MetricCard({ icon: Icon, title, value, sub, accent }) {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="glass-card p-6 relative overflow-hidden"
    >
      <div
        className={`absolute top-0 right-0 w-28 h-28 opacity-20 blur-3xl bg-gradient-to-br ${accent}`}
      />

      <div className="relative z-10 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between mb-4">
          <div
            className={`w-12 h-12 rounded-2xl flex items-center justify-center bg-gradient-to-br ${accent}`}
          >
            <Icon className="text-white" size={24} />
          </div>
        </div>

        <div>
          <div className="text-3xl font-bold text-white mb-1 tracking-tight">
            {value}
          </div>
          <div className="text-white font-semibold text-sm mb-0.5">
            {title}
          </div>
          {sub && (
            <div className="text-slate-400 text-xs">
              {sub}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function MiniStat({ title, value }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3.5 backdrop-blur-xl">
      <div className="text-slate-500 text-xs mb-1.5 uppercase tracking-wide">
        {title}
      </div>
      <div className="text-2xl font-bold text-white font-mono">
        {value}
      </div>
    </div>
  );
}
