"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { CreditCard, ArrowRight, Loader2, Coins, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

export default function BillingPage() {
  const { user, refreshUser } = useAuth();
  const [balanceData, setBalanceData] = useState(null);
  const [history, setHistory] = useState([]);
  const [loadingBalance, setLoadingBalance] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingPortal, setLoadingPortal] = useState(false);
  const [loadingTopUp, setLoadingTopUp] = useState(null);

  // Subscription plan states
  const [billingCycle, setBillingCycle] = useState("monthly");
  const [loadingCheckout, setLoadingCheckout] = useState(null);
  const [brands, setBrands] = useState([]);

  // Pagination states
  const [page, setPage] = useState(1);
  const limit = 10;
  const offset = (page - 1) * limit;

  useEffect(() => {
    api.get("/api/v1/brands").then(data => setBrands(data || [])).catch(() => {});
  }, []);

  const currentTier = brands[0]?.tier || "free";

  const handleCheckout = async (pkg, frequency) => {
    setLoadingCheckout(`${pkg}_${frequency}`);
    try {
      const response = await api.post("/api/v1/billing/checkout-session", {
        package: pkg,
        frequency: frequency,
      });
      if (response.session_url) {
        window.location.href = response.session_url;
      } else {
        toast.error("Failed to create checkout session");
      }
    } catch (e) {
      toast.error(e.message || "Checkout failed");
    } finally {
      setLoadingCheckout(null);
    }
  };

  // Fetch balance info
  const fetchBalance = async () => {
    try {
      setLoadingBalance(true);
      const data = await api.get("/api/v1/credits/balance");
      setBalanceData(data);
    } catch (error) {
      console.error("Failed to load balance details:", error);
      toast.error("Failed to load credit balance");
    } finally {
      setLoadingBalance(false);
    }
  };

  // Fetch history list
  const fetchHistory = async () => {
    try {
      setLoadingHistory(true);
      const data = await api.get(`/api/v1/credits/history?limit=${limit}&offset=${offset}`);
      setHistory(data || []);
    } catch (error) {
      console.error("Failed to load credit history:", error);
      toast.error("Failed to load transaction history");
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    fetchBalance();
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [page]);

  // Handle Stripe customer portal redirect
  const handleManageBilling = async () => {
    setLoadingPortal(true);
    try {
      const response = await api.post("/api/v1/billing/portal-session");
      if (response && response.portal_url) {
        window.location.href = response.portal_url;
      } else {
        throw new Error("Invalid response from portal session API");
      }
    } catch (error) {
      console.error("Stripe Portal Error:", error);
      toast.error(error.message || "Failed to launch billing portal");
    } finally {
      setLoadingPortal(false);
    }
  };

  // Handle Mock Top-up (Starter/Pro/Enterprise)
  const handleMockPurchase = async (pkgName) => {
    setLoadingTopUp(pkgName);
    try {
      const response = await api.post("/api/v1/credits/mock-purchase", { package: pkgName });
      toast.success(response.message || `Successfully purchased ${pkgName} package!`);
      // Refresh context profile details and local state balance/history
      await refreshUser();
      await fetchBalance();
      setPage(1);
      await fetchHistory();
    } catch (error) {
      console.error("Mock Purchase Error:", error);
      toast.error(error.message || "Failed to complete mock purchase");
    } finally {
      setLoadingTopUp(null);
    }
  };

  // Format date helper
  const formatDate = (dateStr) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getTransactionBadge = (type) => {
    const badges = {
      spend: "bg-rose-950/40 border-rose-800/30 text-rose-400",
      top_up: "bg-emerald-950/40 border-emerald-800/30 text-emerald-400",
      refund: "bg-blue-950/40 border-blue-800/30 text-blue-400",
      adjustment: "bg-purple-950/40 border-purple-800/30 text-purple-400",
    };
    return badges[type] || "bg-zinc-850/60 border-zinc-850 text-zinc-400";
  };

  return (
    <div className="space-y-8 max-w-6xl text-zinc-100">
      {/* Header */}
      <div>
        <h2 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100 flex items-center gap-2">
          <CreditCard className="text-purple-500" size={24} />
          Billing & Subscription
        </h2>
        <p className="text-xs text-zinc-400 mt-1">
          Manage your account credit balance, review transaction history, and configure subscription plans.
        </p>
      </div>

      {/* Warnings & Active Alerts */}
      <AnimatePresence>
        {balanceData?.low_credits && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex items-center gap-3 bg-amber-950/30 border border-amber-800/30 p-4 rounded-xl text-amber-400 text-xs"
          >
            <AlertCircle size={18} />
            <div>
              <span className="font-bold">Low Credit Warning:</span> Your GPU credit balance is below the warning threshold ({balanceData.low_credit_threshold} credits). Some model training tasks or batch workflow runs may fail if you run out of credits.
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Top Section Cards */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Subscription Plans */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">Subscription Plans</h2>
              <div className="flex items-center gap-3 bg-zinc-900 border border-zinc-700 rounded-xl p-1">
                <button onClick={() => setBillingCycle("monthly")} className={`px-4 py-1.5 rounded-lg text-xs font-medium transition ${billingCycle === "monthly" ? "bg-purple-600 text-white" : "text-zinc-400 hover:text-white"}`}>Monthly</button>
                <button onClick={() => setBillingCycle("annual")} className={`px-4 py-1.5 rounded-lg text-xs font-medium transition ${billingCycle === "annual" ? "bg-purple-600 text-white" : "text-zinc-400 hover:text-white"}`}>Annual <span className="text-green-400 ml-1">Save 17%</span></button>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { pkg: "lite", name: "Lite", monthly: { price: "$9/mo", credits: "50 credits/mo" }, annual: { price: "$90/yr", credits: "600 credits/yr" }, features: ["50 AI generations/mo", "1 Brand workspace", "Basic support"], color: "border-zinc-700" },
                { pkg: "plus", name: "Plus", monthly: { price: "$29/mo", credits: "250 credits/mo" }, annual: { price: "$290/yr", credits: "3000 credits/yr" }, features: ["250 AI generations/mo", "5 Brand workspaces", "Priority support", "Advanced analytics"], color: "border-purple-600", popular: true },
                { pkg: "pro", name: "Pro", monthly: { price: "$99/mo", credits: "1000 credits/mo" }, annual: { price: "$990/yr", credits: "12000 credits/yr" }, features: ["1000 AI generations/mo", "Unlimited workspaces", "Dedicated support", "Custom workflows", "MLflow integration"], color: "border-indigo-500" },
              ].map(plan => {
                const isActive = currentTier === plan.pkg;
                const isLoading = loadingCheckout === `${plan.pkg}_${billingCycle}`;
                const pricing = billingCycle === "monthly" ? plan.monthly : plan.annual;
                return (
                  <div key={plan.pkg} className={`relative bg-zinc-900/40 border-2 ${plan.color} rounded-2xl p-6 flex flex-col`}>
                    {plan.popular && <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-purple-600 text-white text-xs px-3 py-1 rounded-full font-medium">Most Popular</span>}
                    <h3 className="text-lg font-bold text-white mb-1">{plan.name}</h3>
                    <p className="text-2xl font-bold text-white mb-1">{pricing.price}</p>
                    <p className="text-xs text-zinc-400 mb-4">{pricing.credits}</p>
                    <ul className="space-y-2 mb-6 flex-1">{plan.features.map(f => <li key={f} className="text-xs text-zinc-300 flex items-center gap-2"><span className="text-purple-400">✓</span> {f}</li>)}</ul>
                    {isActive ? (
                      <div className="w-full py-2.5 rounded-xl text-sm font-medium text-center bg-zinc-800 text-zinc-400 border border-zinc-700">Active Plan</div>
                    ) : (
                      <button onClick={() => handleCheckout(plan.pkg, billingCycle)} disabled={isLoading} className={`w-full py-2.5 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2 ${plan.popular ? "bg-purple-600 hover:bg-purple-700 text-white" : "border border-zinc-600 hover:border-purple-500 text-zinc-300 hover:text-white"} disabled:opacity-50`}>
                        {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                        {isLoading ? "Processing..." : "Subscribe"}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

        {/* Credits Balance Card */}
        <div className="bg-zinc-950 border border-zinc-850 p-6 rounded-2xl flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-10">
            <Coins size={120} className="text-purple-500" />
          </div>
          <div className="space-y-2 relative z-10">
            <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider block">
              Active Credit Balance
            </span>
            {loadingBalance ? (
              <div className="h-10 w-24 bg-zinc-900 rounded animate-pulse" />
            ) : (
              <div className="text-4xl font-extrabold text-white flex items-baseline gap-1">
                {balanceData?.balance ?? 0}
                <span className="text-xs font-semibold text-zinc-400">credits</span>
              </div>
            )}
            <p className="text-zinc-500 text-[10px] leading-relaxed max-w-sm">
              Each generated photo consumes 1 credit. Each custom LoRA character model training consumes 10 credits. Rollover applies automatically on active subscriptions.
            </p>
          </div>
          <div className="mt-6 pt-4 border-t border-zinc-900 relative z-10">
            <button
              onClick={handleManageBilling}
              disabled={loadingPortal}
              className="flex items-center gap-1.5 bg-zinc-900 hover:bg-zinc-850 text-zinc-200 hover:text-white border border-zinc-800 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loadingPortal ? (
                <>
                  <Loader2 className="animate-spin" size={14} />
                  Opening Portal...
                </>
              ) : (
                <>
                  Manage Billing
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </div>
        </div>

        {/* Mock Top-Up / Staging Options Card */}
        <div className="bg-zinc-950 border border-zinc-850 p-6 rounded-2xl flex flex-col justify-between">
          <div className="space-y-1">
            <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider block">
              Staging & Testing Top-up
            </span>
            <p className="text-zinc-500 text-[10px] leading-relaxed">
              Simulate credits purchasing without entering billing details. Click below to add credits instantly to this account:
            </p>
          </div>

          <div className="grid grid-cols-3 gap-3 mt-6">
            {[
              { id: "starter", name: "Starter", amt: 100 },
              { id: "pro", name: "Pro", amt: 500 },
              { id: "enterprise", name: "Enterprise", amt: 2000 },
            ].map((pkg) => (
              <button
                key={pkg.id}
                disabled={loadingTopUp !== null}
                onClick={() => handleMockPurchase(pkg.id)}
                className="flex flex-col items-center justify-center border border-zinc-800 hover:border-purple-850 bg-zinc-900/40 hover:bg-purple-950/10 p-3 rounded-xl transition-all cursor-pointer group disabled:opacity-50 disabled:cursor-not-allowed text-center"
              >
                {loadingTopUp === pkg.id ? (
                  <Loader2 className="animate-spin text-purple-400 mb-1" size={16} />
                ) : (
                  <Coins className="text-purple-400 group-hover:scale-110 transition-transform mb-1" size={16} />
                )}
                <span className="text-[10px] font-bold text-zinc-200 group-hover:text-purple-300">
                  {pkg.name}
                </span>
                <span className="text-[9px] text-zinc-500 mt-0.5">
                  +{pkg.amt} Credits
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Credit Transactions Ledger History */}
      <div className="bg-zinc-950 border border-zinc-855 rounded-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-900 flex justify-between items-center bg-zinc-950/40">
          <span className="text-xs font-bold text-zinc-200">Credit Ledger & Transaction Logs</span>
          <span className="text-[9px] text-zinc-500 uppercase tracking-wider font-semibold">
            Chronological Audit Trail
          </span>
        </div>

        <div className="overflow-x-auto">
          {loadingHistory && history.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <Loader2 className="animate-spin text-purple-500" size={24} />
              <span className="text-xs text-zinc-400">Loading ledger transaction logs...</span>
            </div>
          ) : history.length === 0 ? (
            <div className="text-center py-12 space-y-2">
              <Coins className="mx-auto text-zinc-650" size={28} />
              <p className="text-xs font-medium text-zinc-400">No transaction logs recorded yet</p>
              <p className="text-[10px] text-zinc-500 max-w-xs mx-auto">
                Any spends, refunds, or credit top-ups will be displayed here.
              </p>
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-zinc-900 bg-zinc-950/60 text-zinc-500 text-[10px] font-bold uppercase tracking-wider">
                  <th className="px-6 py-4">Transaction Details</th>
                  <th className="px-6 py-4">Type</th>
                  <th className="px-6 py-4">Amount</th>
                  <th className="px-6 py-4">Balance After</th>
                  <th className="px-6 py-4">Date & Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900/60 text-xs">
                {history.map((tx) => {
                  const isPositive = tx.amount > 0;
                  return (
                    <tr key={tx.id} className="hover:bg-zinc-900/10 transition-all text-zinc-300">
                      <td className="px-6 py-4">
                        <div className="flex flex-col gap-0.5">
                          <span className="font-semibold text-zinc-200">{tx.description || "Credit transaction"}</span>
                          {tx.reference_type && (
                            <span className="text-[9px] text-zinc-500">
                              Ref: {tx.reference_type} {tx.reference_id ? `#${tx.reference_id}` : ""}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`text-[9px] uppercase tracking-wider font-semibold border px-2 py-0.5 rounded-full ${getTransactionBadge(tx.transaction_type)}`}>
                          {tx.transaction_type}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`font-bold ${isPositive ? "text-emerald-400" : "text-rose-400"}`}>
                          {isPositive ? "+" : ""}{tx.amount}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-semibold text-zinc-200">
                        {tx.balance_after}
                      </td>
                      <td className="px-6 py-4 text-zinc-500">
                        {formatDate(tx.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination Footer */}
        {history.length > 0 && (
          <div className="px-6 py-4 border-t border-zinc-900 bg-zinc-950/20 flex items-center justify-between">
            <span className="text-[10px] text-zinc-500">
              Showing page {page}
            </span>
            <div className="flex gap-2">
              <button
                disabled={page === 1 || loadingHistory}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 border border-zinc-800 hover:border-zinc-700 bg-zinc-900/40 text-zinc-300 hover:text-white rounded-lg text-xs transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                disabled={history.length < limit || loadingHistory}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 border border-zinc-800 hover:border-zinc-700 bg-zinc-900/40 text-zinc-300 hover:text-white rounded-lg text-xs transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
