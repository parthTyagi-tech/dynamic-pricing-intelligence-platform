import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, AlertCircle, ShoppingCart, RefreshCw, Layers, Terminal, ToggleLeft, ToggleRight, Settings2 } from "lucide-react";
import apiClient from "../services/api";

export default function Integrations() {
  const [integrations, setIntegrations] = useState(null);
  const [webhookLogs, setWebhookLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncingPlatform, setSyncingPlatform] = useState("");
  const [expandedLogId, setExpandedLogId] = useState(null);

  // Connection settings states
  const [shopifyUrl, setShopifyUrl] = useState("");
  const [woocommerceUrl, setWoocommerceUrl] = useState("");
  const [showConfigModal, setShowConfigModal] = useState("");

  const fetchIntegrations = async () => {
    try {
      const response = await apiClient.get("/integrations");
      setIntegrations(response.data.integrations);
      setWebhookLogs(response.data.webhook_logs || []);
      setShopifyUrl(response.data.integrations?.shopify?.store_url || "");
      setWoocommerceUrl(response.data.integrations?.woocommerce?.store_url || "");
    } catch (error) {
      console.error("Error loading integrations status:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntegrations();
  }, []);

  const handleToggleConnection = async (platform, currentStatus) => {
    const isConnecting = !currentStatus;
    if (isConnecting) {
      // Open credentials edit configuration modal
      setShowConfigModal(platform);
      return;
    }

    // Disconnecting platform
    setLoading(true);
    try {
      await apiClient.post("/integrations", {
        platform,
        connected: false,
        store_url: ""
      });
      fetchIntegrations();
    } catch (error) {
      console.error("Error toggling integration connection:", error);
      setLoading(false);
    }
  };

  const handleSaveConfig = async () => {
    const platform = showConfigModal;
    const url = platform === "shopify" ? shopifyUrl : woocommerceUrl;

    if (!url) return;
    setLoading(true);
    try {
      await apiClient.post("/integrations", {
        platform,
        connected: true,
        store_url: url
      });
      setShowConfigModal("");
      fetchIntegrations();
    } catch (error) {
      console.error("Error saving integration config:", error);
      setLoading(false);
    }
  };

  const handleManualSync = async (platform) => {
    setSyncingPlatform(platform);
    // Simulate syncing pipeline delay
    await new Promise(resolve => setTimeout(resolve, 2000));
    setSyncingPlatform("");
    alert(`${platform.toUpperCase()} Catalog synced successfully!`);
  };

  if (loading && !integrations) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="w-10 h-10 border-4 border-t-indigo-500 border-white/10 rounded-full animate-spin" />
      </div>
    );
  }

  const shopify = integrations?.shopify || { connected: false, store_url: "" };
  const woocommerce = integrations?.woocommerce || { connected: false, store_url: "" };

  return (
    <div className="space-y-6">
      {/* HEADER SECTION */}
      <div className="flex justify-between items-center bg-white/5 border border-white/8 rounded-3xl p-6 relative overflow-hidden"
           style={{ background: "rgba(10, 15, 30, 0.7)", backdropFilter: "blur(20px)" }}>
        <div className="absolute top-0 right-0 w-24 h-24 opacity-15 blur-2xl bg-violet-500" />
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center bg-violet-600/30 text-violet-400 border border-violet-500/20">
            <ShoppingCart size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-wide">Platform Integrations Hub</h1>
            <p className="text-xs text-slate-400 mt-1">Connect your active Shopify or WooCommerce storefronts to sync catalog inventories and push pricing changes.</p>
          </div>
        </div>
      </div>

      {/* PLATFORMS CARDS LIST */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* SHOPIFY CARD */}
        <div className="bg-white/5 border border-white/8 rounded-3xl p-6 flex flex-col justify-between"
             style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
          <div className="space-y-4">
            <div className="flex justify-between items-start">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-600/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold">
                  S
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Shopify</h3>
                  <span className="text-[10px] text-slate-400">Direct GraphQL Sync</span>
                </div>
              </div>

              {/* Toggle Connect Button */}
              <button
                onClick={() => handleToggleConnection("shopify", shopify.connected)}
                className="cursor-pointer"
              >
                {shopify.connected ? (
                  <ToggleRight size={38} className="text-emerald-400" />
                ) : (
                  <ToggleLeft size={38} className="text-slate-600" />
                )}
              </button>
            </div>

            {shopify.connected ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-emerald-400 font-semibold">Active connection:</span>
                  <span className="text-white font-mono">{shopify.store_url}</span>
                </div>
                <div className="text-[10px] text-slate-500">API Access: OAuth Configured • Webhooks Active</div>
              </div>
            ) : (
              <p className="text-xs text-slate-500">Shopify storefront is not connected. Configure OAuth credentials to link catalog inventories.</p>
            )}
          </div>

          {shopify.connected && (
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => handleManualSync("shopify")}
                disabled={syncingPlatform !== ""}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-white/5 hover:bg-white/10 text-white rounded-xl border border-white/10 hover:border-white/15 text-xs font-semibold cursor-pointer disabled:opacity-50 select-none"
              >
                <RefreshCw size={12} className={syncingPlatform === "shopify" ? "animate-spin" : ""} />
                Sync Shopify Catalog
              </button>
              <button
                onClick={() => setShowConfigModal("shopify")}
                className="px-3 py-2.5 bg-white/5 hover:bg-white/10 text-slate-300 rounded-xl border border-white/10 hover:border-white/15 cursor-pointer"
              >
                <Settings2 size={14} />
              </button>
            </div>
          )}
        </div>

        {/* WOOCOMMERCE CARD */}
        <div className="bg-white/5 border border-white/8 rounded-3xl p-6 flex flex-col justify-between"
             style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
          <div className="space-y-4">
            <div className="flex justify-between items-start">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-purple-600/10 border border-purple-500/20 text-purple-400 flex items-center justify-center font-bold">
                  W
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">WooCommerce</h3>
                  <span className="text-[10px] text-slate-400">REST API Integration</span>
                </div>
              </div>

              <button
                onClick={() => handleToggleConnection("woocommerce", woocommerce.connected)}
                className="cursor-pointer"
              >
                {woocommerce.connected ? (
                  <ToggleRight size={38} className="text-emerald-400" />
                ) : (
                  <ToggleLeft size={38} className="text-slate-600" />
                )}
              </button>
            </div>

            {woocommerce.connected ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-emerald-400 font-semibold">Active connection:</span>
                  <span className="text-white font-mono">{woocommerce.store_url}</span>
                </div>
                <div className="text-[10px] text-slate-500">API Access: Key Configured • Webhooks Active</div>
              </div>
            ) : (
              <p className="text-xs text-slate-500">WooCommerce storefront is not connected. Configure API credentials to link catalog inventories.</p>
            )}
          </div>

          {woocommerce.connected && (
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => handleManualSync("woocommerce")}
                disabled={syncingPlatform !== ""}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-white/5 hover:bg-white/10 text-white rounded-xl border border-white/10 hover:border-white/15 text-xs font-semibold cursor-pointer disabled:opacity-50 select-none"
              >
                <RefreshCw size={12} className={syncingPlatform === "woocommerce" ? "animate-spin" : ""} />
                Sync WooCommerce Catalog
              </button>
              <button
                onClick={() => setShowConfigModal("woocommerce")}
                className="px-3 py-2.5 bg-white/5 hover:bg-white/10 text-slate-300 rounded-xl border border-white/10 hover:border-white/15 cursor-pointer"
              >
                <Settings2 size={14} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* WEBHOOK LISTENERS FEED */}
      <div className="bg-white/5 border border-white/8 rounded-3xl p-6"
           style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Terminal size={16} className="text-violet-400" />
            Live Webhooks Event Stream Logs
          </h3>
          <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-ping" /> Webhook Listener Online
          </span>
        </div>

        <div className="space-y-3">
          {webhookLogs.map((log) => {
            const isExpanded = expandedLogId === log.payload_id;
            return (
              <div key={log.payload_id} className="bg-slate-900/60 border border-white/5 rounded-2xl p-4 overflow-hidden">
                <div className="flex justify-between items-center text-xs">
                  <div className="flex items-center gap-3">
                    <span className="px-2 py-0.5 rounded-full text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-semibold font-mono">
                      {log.event}
                    </span>
                    <span className="text-slate-400 font-medium">{log.topic}</span>
                    <span className="text-[10px] text-slate-600 font-mono">Payload: {log.payload_id}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-slate-500">{new Date(log.timestamp).toLocaleTimeString()}</span>
                    <button
                      onClick={() => setExpandedLogId(isExpanded ? null : log.payload_id)}
                      className="text-indigo-400 hover:text-indigo-300 hover:underline text-[10px] font-bold cursor-pointer"
                    >
                      {isExpanded ? "Collapse" : "Inspect Payload"}
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <pre className="mt-3 text-[10px] text-slate-400 bg-slate-950 p-3 rounded-xl border border-white/5 overflow-x-auto font-mono">
                    {JSON.stringify({
                      event_type: log.event,
                      resource: "orders",
                      id: log.payload_id,
                      customer: { name: "John Doe", email: "john@example.com" },
                      pricing_applied: log.ai_adjusted ? "AI dynamic price adjusted" : "Store default baseline",
                      webhook_verified: "HMAC Sha256 Match",
                      trace_status: log.status
                    }, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* CONFIGURATION MODAL DIALOG */}
      {showConfigModal !== "" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-[450px] bg-slate-900 border border-white/10 rounded-3xl p-6 space-y-4">
            <div className="flex justify-between items-center">
              <h4 className="text-sm font-bold text-white uppercase tracking-wide">
                Link {showConfigModal} Storefront
              </h4>
              <button
                onClick={() => setShowConfigModal("")}
                className="text-slate-400 hover:text-white cursor-pointer font-bold text-xs"
              >
                Cancel
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="text-slate-400 font-semibold">Store URL Endpoint</label>
                <input
                  type="text"
                  value={showConfigModal === "shopify" ? shopifyUrl : woocommerceUrl}
                  onChange={(e) => {
                    if (showConfigModal === "shopify") setShopifyUrl(e.target.value);
                    else setWoocommerceUrl(e.target.value);
                  }}
                  placeholder="e.g. acme-wear.myshopify.com"
                  className="w-full bg-white/5 border border-white/10 text-white rounded-xl p-3 outline-none focus:border-indigo-500/50"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-slate-400 font-semibold">Admin API Access Token / Password</label>
                <input
                  type="password"
                  defaultValue="shpat_abcdefg123456"
                  className="w-full bg-white/5 border border-white/10 text-white rounded-xl p-3 outline-none focus:border-indigo-500/50"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-slate-400 font-semibold">Webhook Encryption Signature (Secret)</label>
                <input
                  type="password"
                  defaultValue="whsec_0987654321fedcba"
                  className="w-full bg-white/5 border border-white/10 text-white rounded-xl p-3 outline-none"
                />
              </div>
            </div>

            <button
              onClick={handleSaveConfig}
              className="w-full mt-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/10 cursor-pointer"
            >
              Verify & Connect Storefront
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
