import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, CreditCard, DollarSign, Award, CheckCircle, BarChart2, Activity, RefreshCw } from "lucide-react";
import apiClient from "../services/api";

export default function Billing() {
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [paySuccess, setPaySuccess] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState("Pro Growth Plan");

  const fetchBilling = async () => {
    try {
      const response = await apiClient.get("/startup/billing");
      setBilling(response.data);
    } catch (error) {
      console.error("Error loading billing details:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBilling();
  }, []);

  const handlePayInvoice = () => {
    setPaying(true);
    // Simulate Stripe popup overlay and processing delay
    setTimeout(() => {
      setPaying(false);
      setPaySuccess(true);
      
      // Keep PAID status visual for 4 seconds then return to normal
      setTimeout(() => {
        setPaySuccess(false);
      }, 4000);
    }, 2000);
  };

  if (loading || !billing) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="w-10 h-10 border-4 border-t-indigo-500 border-white/10 rounded-full animate-spin" />
      </div>
    );
  }

  const sub = billing.subscription;
  const metrics = billing.usage_metrics;
  const history = billing.billing_history || [];

  const invoiceAmount = paySuccess ? 0.00 : metrics.total_invoice_due;

  return (
    <div className="space-y-6">
      {/* HEADER SECTION */}
      <div className="flex justify-between items-center bg-white/5 border border-white/8 rounded-3xl p-6 relative overflow-hidden"
           style={{ background: "rgba(10, 15, 30, 0.7)", backdropFilter: "blur(20px)" }}>
        <div className="absolute top-0 right-0 w-24 h-24 opacity-15 blur-2xl bg-emerald-500" />
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center bg-emerald-600/30 text-emerald-400 border border-emerald-500/20">
            <CreditCard size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-wide">SaaS Plans & Billing Panel</h1>
            <p className="text-xs text-slate-400 mt-1">Review active membership plans, audit dynamic revenue commission margins, and pay Stripe invoices.</p>
          </div>
        </div>
      </div>

      {/* SUBSCRIPTION PLAN SELECTION CARDS */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {[
          { name: "Starter Tier", price: 49, limit: "Up to 500 orders/mo", fee: "1.0% Lift Comm.", desc: "Ideal for fresh startups testing dynamic pricing policies." },
          { name: "Pro Growth Plan", price: 149, limit: "Unlimited catalog items", fee: "0.5% Lift Comm.", desc: "Default plan containing 5-agent parallel pipeline optimizations.", popular: true },
          { name: "Enterprise Custom", price: 499, limit: "Dedicated ML Models", fee: "0.2% Lift Comm.", desc: "Custom SLA, dedicated server shards, and custom APIs." }
        ].map((plan, idx) => {
          const isSelected = selectedPlan === plan.name;
          return (
            <div
              key={idx}
              onClick={() => setSelectedPlan(plan.name)}
              className={`bg-white/5 border rounded-3xl p-6 flex flex-col justify-between relative cursor-pointer transition-all hover:scale-[1.01] select-none ${
                isSelected 
                  ? "border-emerald-500 bg-emerald-500/5 shadow-lg shadow-emerald-500/5" 
                  : "border-white/8 hover:border-white/12"
              }`}
              style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}
            >
              {plan.popular && (
                <span className="absolute -top-3.5 right-6 bg-gradient-to-r from-emerald-500 to-teal-400 text-slate-950 font-extrabold text-[9px] px-3 py-1 rounded-full uppercase tracking-wider">
                  Popular
                </span>
              )}
              
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h4 className="text-sm font-bold text-white">{plan.name}</h4>
                  <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 font-bold">{plan.fee}</span>
                </div>
                
                <div>
                  <span className="text-2xl font-extrabold text-white">₹{plan.price}</span>
                  <span className="text-xs text-slate-400"> / month</span>
                </div>

                <p className="text-xs text-slate-400 leading-relaxed">{plan.desc}</p>
                <div className="text-[10px] text-slate-500 font-semibold">• {plan.limit}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* STRIPE CURRENT INVOICE CARD */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-gradient-to-r from-slate-900 to-indigo-950/40 border border-white/8 rounded-3xl p-6 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 opacity-10 blur-2xl bg-indigo-500" />
          
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Shield size={16} className="text-indigo-400" />
              Usage-Based Stripe Invoice Summary
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 py-2">
              <div className="bg-white/5 border border-white/5 p-4 rounded-2xl">
                <span className="text-[10px] text-slate-400 font-semibold">AI Net Profit Lift</span>
                <h4 className="text-base font-bold text-white mt-1">₹{metrics.ai_assisted_revenue_lift.toLocaleString()}</h4>
              </div>
              <div className="bg-white/5 border border-white/5 p-4 rounded-2xl">
                <span className="text-[10px] text-slate-400 font-semibold">Commission ({metrics.commission_rate_pct}%)</span>
                <h4 className="text-base font-bold text-teal-400 mt-1">₹{metrics.commission_due.toFixed(2)}</h4>
              </div>
              <div className="bg-white/5 border border-white/5 p-4 rounded-2xl">
                <span className="text-[10px] text-slate-400 font-semibold">Base Subscription</span>
                <h4 className="text-base font-bold text-white mt-1">₹{metrics.subscription_due.toFixed(2)}</h4>
              </div>
            </div>
          </div>

          <div className="flex justify-between items-center border-t border-white/5 pt-6 mt-6">
            <div>
              <span className="text-xs text-slate-400 font-medium">Current Amount Outstanding</span>
              <h4 className="text-lg font-bold text-white mt-1 font-mono">₹{invoiceAmount.toFixed(2)}</h4>
            </div>

            <AnimatePresence mode="wait">
              {paySuccess ? (
                <motion.div
                  key="paid"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 px-6 py-3 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-xl text-xs font-bold font-mono"
                >
                  <CheckCircle size={16} />
                  INVOICE PAID SUCCESS
                </motion.div>
              ) : (
                <button
                  onClick={handlePayInvoice}
                  disabled={paying || invoiceAmount === 0}
                  className="flex items-center gap-2 px-6 py-3 bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold rounded-xl shadow-lg shadow-emerald-500/10 cursor-pointer disabled:opacity-50 select-none"
                >
                  {paying ? (
                    <>
                      <RefreshCw size={14} className="animate-spin" />
                      Contacting Stripe Gateway...
                    </>
                  ) : (
                    <>
                      <CreditCard size={14} />
                      Pay Invoice With Stripe
                    </>
                  )}
                </button>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* BILLING HISTORY LOGS */}
        <div className="bg-white/5 border border-white/8 rounded-3xl p-6"
             style={{ background: "rgba(10, 15, 30, 0.4)", backdropFilter: "blur(12px)" }}>
          <h3 className="text-sm font-bold text-white mb-4">Invoice Logs History</h3>
          <div className="space-y-4">
            {history.map((inv, idx) => (
              <div key={idx} className="flex justify-between items-center text-xs border-b border-white/5 pb-3 last:border-0 last:pb-0">
                <div>
                  <span className="font-semibold text-white font-mono">{inv.invoice_id}</span>
                  <p className="text-[10px] text-slate-500">{new Date(inv.date).toLocaleDateString()}</p>
                </div>
                <div className="text-right">
                  <span className="font-bold text-white font-mono">₹{inv.amount.toFixed(2)}</span>
                  <span className="block text-[9px] text-emerald-400 font-extrabold uppercase mt-0.5">{inv.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
