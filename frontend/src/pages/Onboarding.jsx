import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Building2, 
  UploadCloud, 
  FileSpreadsheet, 
  CheckCircle2, 
  ArrowRight, 
  Store, 
  Link2, 
  Activity, 
  Zap, 
  Sparkles,
  AlertCircle,
  Globe,
  Settings,
  ShoppingBag
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import apiClient from "../services/api";
import { useNavigate } from "react-router-dom";

export default function Onboarding() {
  const { user, updateUser } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [companyName, setCompanyName] = useState(user?.organization_name || "");
  const [importSource, setImportSource] = useState(null); // 'csv' or 'integration'
  const [csvFile, setCsvFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState(false);
  
  // Generalized Integration States
  const [activePlatform, setActivePlatform] = useState(null); // 'shopify', 'walmart', 'amazon', 'ebay', 'woocommerce', 'magento', 'bigcommerce'
  const [connectedStore, setConnectedStore] = useState(null); 
  const [shopDomain, setShopDomain] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [connecting, setConnecting] = useState(false);

  // Finalizing Activation States
  const [activating, setActivating] = useState(false);
  const [activationProgress, setActivationProgress] = useState(0);

  const handleNextStep = () => {
    setStep((prev) => prev + 1);
  };

  const handlePrevStep = () => {
    setStep((prev) => prev - 1);
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) validateAndSetFile(file);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) validateAndSetFile(file);
  };

  const validateAndSetFile = (file) => {
    setUploadError("");
    setUploadSuccess(false);
    if (!file.name.endsWith(".csv")) {
      setUploadError("Only CSV files are supported at this time.");
      return;
    }
    setCsvFile(file);
  };

  const handleCsvUpload = async () => {
    if (!csvFile) return;
    setUploading(true);
    setUploadError("");
    
    const formData = new FormData();
    formData.append("file", csvFile);

    try {
      const response = await apiClient.post("/products/import-csv", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      if (response.data.success) {
        setUploadSuccess(true);
        setTimeout(() => {
          handleNextStep();
        }, 1500);
      }
    } catch (err) {
      console.error(err);
      setUploadError(err.response?.data?.message || "Failed to parse CSV file. Ensure columns 'name' and 'current_price' exist.");
    } finally {
      setUploading(false);
    }
  };

  const handleConnectStore = async (e, platformName) => {
    e.preventDefault();
    setConnecting(true);
    
    try {
      const response = await apiClient.post("/auth/connect-integration", {
        platform: platformName,
        domain: shopDomain || `${platformName}-store`
      });
      if (response.data.success) {
        setConnectedStore(platformName);
        updateUser(response.data.user);
        setTimeout(() => {
          handleNextStep();
        }, 1200);
      }
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.message || "Failed to establish store connection link. Please check parameters.");
    } finally {
      setConnecting(false);
    }
  };

  const triggerActivation = async () => {
    setActivating(true);
    
    // Simulate pipeline tasks progress: DB checks, agent sync
    const intervals = [
      { text: "Verifying catalog listings...", delay: 800 },
      { text: "Seeding market price matrices...", delay: 1600 },
      { text: "Spawning multi-agent orchestrator...", delay: 2400 },
      { text: "Activating real-time price rules...", delay: 3200 }
    ];

    intervals.forEach((item, index) => {
      setTimeout(() => {
        setActivationProgress(index + 1);
      }, item.delay);
    });

    setTimeout(async () => {
      try {
        const response = await apiClient.post("/auth/complete-onboarding");
        if (response.data.success) {
          updateUser(response.data.user);
          navigate("/dashboard");
        }
      } catch (err) {
        console.error(err);
        alert("Failed to complete onboarding. Please try again.");
        setActivating(false);
        setActivationProgress(0);
      }
    }, 4000);
  };

  const stepVariants = {
    hidden: { opacity: 0, x: 50 },
    visible: { opacity: 1, x: 0, transition: { type: "spring", stiffness: 300, damping: 30 } },
    exit: { opacity: 0, x: -50, transition: { duration: 0.2 } }
  };

  // Capitalize helpers
  const capitalize = (str) => str ? str.charAt(0).toUpperCase() + str.slice(1) : "";

  // Available integrations metadata
  const integrationPlatforms = [
    { id: "shopify", name: "Shopify Store", desc: "Sync direct collections & variants", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "hover:border-emerald-500/30", icon: Store },
    { id: "walmart", name: "Walmart Marketplace", desc: "Connect as a registered seller", color: "text-sky-400", bg: "bg-sky-500/10", border: "hover:border-sky-500/30", icon: ShoppingBag },
    { id: "amazon", name: "Amazon Seller Central", desc: "Optimize globally through SP-API", color: "text-amber-500", bg: "bg-amber-500/10", border: "hover:border-amber-500/30", icon: Globe },
    { id: "ebay", name: "eBay Marketplace", desc: "Integrate merchant listing cycles", color: "text-orange-400", bg: "bg-orange-400/10", border: "hover:border-orange-400/30", icon: ShoppingBag },
    { id: "woocommerce", name: "WooCommerce WP", desc: "Connect open-source databases", color: "text-purple-400", bg: "bg-purple-400/10", border: "hover:border-purple-400/30", icon: Link2 },
    { id: "magento", name: "Adobe Magento", desc: "Corporate scale catalog API integration", color: "text-rose-400", bg: "bg-rose-400/10", border: "hover:border-rose-400/30", icon: Settings },
    { id: "bigcommerce", name: "BigCommerce SaaS", desc: "Connect cloud store catalog structures", color: "text-indigo-400", bg: "bg-indigo-500/10", border: "hover:border-indigo-500/30", icon: Activity },
  ];

  return (
    <div 
      className="min-h-screen flex items-center justify-center relative overflow-hidden px-4 py-12"
      style={{
        background: "linear-gradient(135deg, #060814 0%, #0b1329 50%, #0d1e3d 100%)"
      }}
    >
      {/* Background ambient lighting */}
      <div className="absolute w-[400px] h-[400px] rounded-full bg-teal-500/10 blur-[120px] -top-20 -right-20 pointer-events-none" />
      <div className="absolute w-[350px] h-[350px] rounded-full bg-indigo-500/10 blur-[120px] -bottom-20 -left-20 pointer-events-none" />

      <div 
        className="w-full max-w-2xl relative z-10 p-8 md:p-10"
        style={{
          borderRadius: 32,
          background: "rgba(10, 15, 30, 0.8)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          boxShadow: "0 30px 70px rgba(0, 0, 0, 0.5)"
        }}
      >
        {/* Header Progress indicator */}
        {!activating && (
          <div className="flex items-center justify-between mb-8 border-b border-white/5 pb-5">
            <div className="flex items-center gap-2">
              <Sparkles className="text-teal-400" size={18} />
              <span className="text-xs uppercase tracking-widest text-slate-400 font-semibold font-mono">
                Setup Wizard
              </span>
            </div>
            <div className="flex items-center gap-2">
              {[1, 2, 3].map((s) => (
                <div 
                  key={s}
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    step === s ? "w-6 bg-teal-400" : "w-2 bg-white/20"
                  }`}
                />
              ))}
            </div>
          </div>
        )}

        <AnimatePresence mode="wait">
          {/* STEP 1: ORGANIZATION CONFIRMATION */}
          {step === 1 && (
            <motion.div 
              key="step1" 
              variants={stepVariants} 
              initial="hidden" 
              animate="visible" 
              exit="exit"
              className="space-y-6"
            >
              <div className="space-y-2">
                <h2 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                  Welcome to Klypup AI
                </h2>
                <p className="text-sm text-slate-400">
                  Let's configure your workspace parameters to get started.
                </p>
              </div>

              <div className="space-y-4 pt-4">
                <label className="block text-sm font-semibold text-slate-300">
                  Company / Organization Name
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-500">
                    <Building2 size={18} />
                  </div>
                  <input
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="Enter company name..."
                    className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-4 text-white placeholder-slate-500 focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-400 transition-all font-medium"
                  />
                </div>
              </div>

              <div className="pt-6">
                <button
                  disabled={!companyName.trim()}
                  onClick={handleNextStep}
                  className="w-full py-4 rounded-2xl font-bold text-white flex items-center justify-center gap-2 transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{
                    background: "linear-gradient(135deg, #00A19B, #6366F1)"
                  }}
                >
                  Continue
                  <ArrowRight size={18} />
                </button>
              </div>
            </motion.div>
          )}

          {/* STEP 2: CHOOSE SOURCE & DATA IMPORT */}
          {step === 2 && (
            <motion.div 
              key="step2" 
              variants={stepVariants} 
              initial="hidden" 
              animate="visible" 
              exit="exit"
              className="space-y-6"
            >
              <div className="space-y-2">
                <h2 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                  Import Product Catalog
                </h2>
                <p className="text-sm text-slate-400">
                  Connect your existing database or upload a catalog file to populate your dashboard.
                </p>
              </div>

              {importSource === null ? (
                /* CHOOSE SOURCE VIEW */
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4">
                    {/* CSV FILE CARD */}
                    <div 
                      onClick={() => setImportSource("csv")}
                      className="group rounded-2xl border border-white/10 bg-white/5 p-6 hover:bg-white/10 hover:border-teal-500/50 cursor-pointer transition-all duration-300 flex flex-col justify-between"
                    >
                      <div>
                        <div className="w-12 h-12 rounded-xl bg-teal-500/10 flex items-center justify-center text-teal-400 mb-4 group-hover:scale-105 transition-transform">
                          <FileSpreadsheet size={22} />
                        </div>
                        <h3 className="text-base font-bold text-white mb-2">Offline Catalog</h3>
                        <p className="text-xs text-slate-400 leading-relaxed">
                          Upload raw spreadsheets containing your inventory list, current prices, and costs via CSV.
                        </p>
                      </div>
                      <span className="text-xs text-teal-400 font-bold mt-6 flex items-center gap-1">
                        Upload CSV File <ArrowRight size={14} />
                      </span>
                    </div>

                    {/* INTEGRATIONS CARD */}
                    <div 
                      onClick={() => setImportSource("integration")}
                      className="group rounded-2xl border border-white/10 bg-white/5 p-6 hover:bg-white/10 hover:border-indigo-500/50 cursor-pointer transition-all duration-300 flex flex-col justify-between"
                    >
                      <div>
                        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 mb-4 group-hover:scale-105 transition-transform">
                          <Store size={22} />
                        </div>
                        <h3 className="text-base font-bold text-white mb-2">E-Commerce Sync</h3>
                        <p className="text-xs text-slate-400 leading-relaxed">
                          Connect Shopify, Walmart, Amazon, or other major global integrations to automatically sync store data.
                        </p>
                      </div>
                      <span className="text-xs text-indigo-400 font-bold mt-6 flex items-center gap-1">
                        Connect Integration <ArrowRight size={14} />
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={handlePrevStep}
                    className="w-full py-4 rounded-2xl border border-white/10 text-white font-semibold hover:bg-white/5 transition-all text-sm animate-pulse"
                  >
                    Back to Profile Setup
                  </button>
                </div>
              ) : importSource === "csv" ? (
                /* CSV UPLOAD INTERFACE */
                <div className="space-y-5">
                  <div 
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={handleFileDrop}
                    className="border-2 border-dashed border-white/10 hover:border-teal-500/40 rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer bg-white/5 transition-all relative overflow-hidden"
                  >
                    <input 
                      type="file" 
                      accept=".csv" 
                      id="csv-file-picker" 
                      className="hidden" 
                      onChange={handleFileSelect} 
                    />
                    <label htmlFor="csv-file-picker" className="cursor-pointer flex flex-col items-center">
                      <UploadCloud className="text-teal-400 mb-4 animate-pulse" size={36} />
                      <p className="text-sm font-semibold text-white mb-1">
                        {csvFile ? csvFile.name : "Drag & Drop CSV File"}
                      </p>
                      <p className="text-xs text-slate-500">
                        {csvFile ? `${(csvFile.size / 1024).toFixed(1)} KB` : "or click to browse local files"}
                      </p>
                    </label>
                  </div>

                  {/* Header Guidelines Info */}
                  <div className="bg-white/5 border border-white/5 rounded-2xl p-4 flex gap-3 text-xs text-slate-400">
                    <AlertCircle className="text-slate-500 shrink-0" size={16} />
                    <p>
                      Your CSV must include columns for <strong>name</strong> and <strong>current_price</strong>. Optional columns include <em>sku, category, cost_price</em>, and <em>inventory_quantity</em>.
                    </p>
                  </div>

                  {uploadError && (
                    <div className="text-red-400 text-xs flex items-center gap-1 bg-red-500/10 border border-red-500/20 px-4 py-3 rounded-xl">
                      <AlertCircle size={14} />
                      <span>{uploadError}</span>
                    </div>
                  )}

                  {uploadSuccess && (
                    <div className="text-teal-400 text-xs flex items-center gap-1 bg-teal-500/10 border border-teal-500/20 px-4 py-3 rounded-xl">
                      <CheckCircle2 size={14} />
                      <span>Catalog parsed and imported successfully! Advancing setup...</span>
                    </div>
                  )}

                  <div className="flex gap-4 pt-4">
                    <button 
                      onClick={() => { setImportSource(null); setCsvFile(null); }}
                      className="w-1/3 py-4 rounded-xl border border-white/10 text-white font-semibold hover:bg-white/5 transition-all text-sm"
                    >
                      Back
                    </button>
                    <button 
                      disabled={!csvFile || uploading || uploadSuccess}
                      onClick={handleCsvUpload}
                      className="flex-1 py-4 rounded-xl font-semibold text-white flex items-center justify-center gap-2 hover:opacity-90 transition-all disabled:opacity-50 text-sm"
                      style={{
                        background: "linear-gradient(135deg, #00A19B, #6366F1)"
                      }}
                    >
                      {uploading ? "Importing Data..." : "Upload & Sync"}
                    </button>
                  </div>
                </div>
              ) : (
                /* INTEGRATION CONNECTIONS INTERFACE */
                <div className="space-y-6">
                  {connectedStore === null ? (
                    <div className="space-y-5">
                      {activePlatform === null ? (
                        /* INTEGRATION SELECTOR GRID */
                        <div className="space-y-4">
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider text-slate-400 border-b border-white/5 pb-2">
                            Select E-Commerce Store Platform
                          </h3>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[320px] overflow-y-auto pr-1">
                            {integrationPlatforms.map((platform) => {
                              const Icon = platform.icon;
                              return (
                                <div
                                  key={platform.id}
                                  onClick={() => setActivePlatform(platform.id)}
                                  className={`flex items-center gap-3 p-4 rounded-2xl border border-white/10 bg-white/5 cursor-pointer transition-all duration-300 ${platform.border}`}
                                >
                                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${platform.bg} ${platform.color} shrink-0`}>
                                    <Icon size={18} />
                                  </div>
                                  <div className="text-left">
                                    <h4 className="text-sm font-bold text-white">{platform.name}</h4>
                                    <p className="text-[10px] text-slate-500 font-medium leading-tight">{platform.desc}</p>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ) : (
                        /* DYNAMIC PLATFORM FORM */
                        <motion.div 
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="border border-white/10 rounded-2xl p-5 bg-white/5 space-y-4"
                        >
                          <div className="flex items-center justify-between border-b border-white/5 pb-3">
                            <div className="flex items-center gap-2">
                              <Store className="text-teal-400" size={18} />
                              <span className="font-bold text-white text-sm">
                                Connect {capitalize(activePlatform)}
                              </span>
                            </div>
                            <span className="text-[9px] uppercase font-bold px-2 py-0.5 rounded bg-teal-500/10 text-teal-400">
                              Direct Sync
                            </span>
                          </div>

                          <form onSubmit={(e) => handleConnectStore(e, activePlatform)} className="space-y-4">
                            {/* Shopify URL Form */}
                            {activePlatform === "shopify" && (
                              <div className="space-y-2">
                                <label className="block text-xs font-semibold text-slate-400">Shop URL</label>
                                <input
                                  type="text"
                                  value={shopDomain}
                                  onChange={(e) => setShopDomain(e.target.value)}
                                  placeholder="my-shop.myshopify.com"
                                  required
                                  className="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-400 transition-all"
                                />
                              </div>
                            )}

                            {/* Walmart Form */}
                            {activePlatform === "walmart" && (
                              <div className="space-y-3">
                                <div>
                                  <label className="block text-xs font-semibold text-slate-400 mb-1">Walmart Client ID</label>
                                  <input
                                    type="text"
                                    value={clientId}
                                    onChange={(e) => setClientId(e.target.value)}
                                    placeholder="Enter Client ID..."
                                    required
                                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-400 transition-all"
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-semibold text-slate-400 mb-1">Client Secret</label>
                                  <input
                                    type="password"
                                    value={clientSecret}
                                    onChange={(e) => setClientSecret(e.target.value)}
                                    placeholder="••••••••••••••••"
                                    required
                                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-400 transition-all"
                                  />
                                </div>
                              </div>
                            )}

                            {/* Standard General Form for Amazon/eBay/WooCommerce/Magento/BigCommerce */}
                            {activePlatform !== "shopify" && activePlatform !== "walmart" && (
                              <div className="space-y-3">
                                <div>
                                  <label className="block text-xs font-semibold text-slate-400 mb-1">Connection Host URL / Tenant ID</label>
                                  <input
                                    type="text"
                                    value={shopDomain}
                                    onChange={(e) => setShopDomain(e.target.value)}
                                    placeholder={`e.g. connection-host.${activePlatform}.com`}
                                    required
                                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-400 transition-all"
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-semibold text-slate-400 mb-1">API Key / Merchant Token</label>
                                  <input
                                    type="password"
                                    value={clientId}
                                    onChange={(e) => setClientId(e.target.value)}
                                    placeholder="Enter access credentials..."
                                    required
                                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-400 transition-all"
                                  />
                                </div>
                              </div>
                            )}

                            <div className="flex gap-3 pt-2">
                              <button
                                type="button"
                                onClick={() => { setActivePlatform(null); setShopDomain(""); setClientId(""); setClientSecret(""); }}
                                className="w-1/3 py-3 rounded-xl border border-white/10 hover:bg-white/5 text-white font-semibold text-xs transition-all"
                              >
                                Cancel
                              </button>
                              <button
                                type="submit"
                                disabled={connecting}
                                className="flex-1 py-3 rounded-xl bg-indigo-500 hover:bg-indigo-600 font-bold text-white text-xs transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                              >
                                {connecting ? "Establishing Secure Link..." : `Sync ${capitalize(activePlatform)} Catalog`}
                                <Link2 size={14} />
                              </button>
                            </div>
                          </form>
                        </motion.div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-6 space-y-3 bg-teal-500/5 border border-teal-500/10 rounded-2xl">
                      <CheckCircle2 className="text-teal-400 mx-auto" size={42} />
                      <h4 className="text-white font-bold text-base">{capitalize(connectedStore)} Connected!</h4>
                      <p className="text-xs text-slate-400">Successfully synced store credentials. Proceeding to final step...</p>
                    </div>
                  )}

                  <div className="flex gap-4">
                    <button 
                      onClick={() => {
                        if (activePlatform !== null) {
                          setActivePlatform(null);
                        } else {
                          setImportSource(null);
                        }
                      }}
                      className="w-1/3 py-4 rounded-xl border border-white/10 text-white font-semibold hover:bg-white/5 transition-all text-sm"
                    >
                      Back
                    </button>
                    {connectedStore && (
                      <button 
                        onClick={handleNextStep}
                        className="flex-1 py-4 rounded-xl font-semibold text-white flex items-center justify-center gap-2 hover:opacity-90 transition-all text-sm"
                        style={{
                          background: "linear-gradient(135deg, #00A19B, #6366F1)"
                        }}
                      >
                        Continue
                        <ArrowRight size={16} />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {/* STEP 3: PIPELINE COMPILATION & REDIRECT */}
          {step === 3 && (
            <motion.div 
              key="step3" 
              variants={stepVariants} 
              initial="hidden" 
              animate="visible" 
              exit="exit"
              className="space-y-8 py-6 text-center"
            >
              <div className="space-y-3">
                <h2 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                  Finalizing Platform Activation
                </h2>
                <p className="text-sm text-slate-400 max-w-md mx-auto">
                  Initializing backend databases, setting margin floors, and activating the dynamic agent pipeline for {companyName}.
                </p>
              </div>

              {!activating ? (
                /* INITIAL ACTIVATE VIEW */
                <div className="pt-4 max-w-sm mx-auto space-y-4">
                  <button
                    onClick={triggerActivation}
                    className="w-full py-4 rounded-2xl font-bold text-white flex items-center justify-center gap-2 shadow-xl shadow-teal-500/20 hover:scale-[1.02] active:scale-95 transition-all"
                    style={{
                      background: "linear-gradient(135deg, #00A19B, #6366F1)"
                    }}
                  >
                    Activate Dashboard
                    <Zap size={18} />
                  </button>
                  <button
                    onClick={handlePrevStep}
                    className="w-full py-3 rounded-2xl border border-white/10 text-white font-semibold hover:bg-white/5 transition-all text-xs"
                  >
                    Back to Catalog Import
                  </button>
                </div>
              ) : (
                /* LOADING ACTIVATING VIEW */
                <div className="space-y-6 pt-4 max-w-md mx-auto">
                  <div className="relative w-20 h-20 mx-auto">
                    {/* Pulsing glow ring */}
                    <div className="absolute inset-0 rounded-full border-2 border-teal-500/20 scale-110 animate-ping" />
                    {/* Spinning ring */}
                    <div className="w-20 h-20 rounded-full border-4 border-white/5 border-t-teal-400 animate-spin" />
                    {/* Center icon */}
                    <div className="absolute inset-0 flex items-center justify-center text-teal-400">
                      <Activity size={24} className="animate-pulse" />
                    </div>
                  </div>

                  {/* Progress Logs */}
                  <div className="space-y-2 border border-white/5 bg-white/5 rounded-2xl p-5 text-left font-mono text-xs text-slate-400">
                    <div className="flex items-center gap-2">
                      <span className={activationProgress >= 1 ? "text-teal-400" : "text-slate-600"}>✓</span>
                      <span className={activationProgress >= 1 ? "text-slate-200" : "text-slate-500"}>Verifying catalog listings...</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={activationProgress >= 2 ? "text-teal-400" : "text-slate-600"}>✓</span>
                      <span className={activationProgress >= 2 ? "text-slate-200" : "text-slate-500"}>Seeding market price matrices...</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={activationProgress >= 3 ? "text-teal-400" : "text-slate-600"}>✓</span>
                      <span className={activationProgress >= 3 ? "text-slate-200" : "text-slate-500"}>Spawning multi-agent orchestrator...</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={activationProgress >= 4 ? "text-teal-400" : "text-slate-600"}>✓</span>
                      <span className={activationProgress >= 4 ? "text-slate-200" : "text-slate-500"}>Activating real-time price rules...</span>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
