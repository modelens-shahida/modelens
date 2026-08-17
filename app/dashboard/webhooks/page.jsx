"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { 
  Plus, 
  Trash2, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  AlertTriangle, 
  Webhook, 
  Eye, 
  EyeOff,
  Key, 
  Sliders, 
  Play, 
  Activity, 
  ChevronRight, 
  Copy, 
  Check, 
  Code,
  Calendar,
  AlertCircle
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";

const EVENT_TYPES = [
  "job.completed", 
  "job.failed", 
  "asset.processed",
  "character.training.completed", 
  "character.training.failed",
];

const STATUS_BADGE_STYLE = {
  success: "bg-emerald-950/40 border-emerald-800/30 text-emerald-400",
  failed: "bg-red-950/40 border-red-800/30 text-red-400",
  retrying: "bg-amber-950/40 border-amber-800/30 text-amber-400",
  dead: "bg-zinc-950/80 border-zinc-800 text-zinc-500",
};

export default function WebhookDashboardPage() {
  const { token } = useAuth();
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [webhooks, setWebhooks] = useState([]);
  const [selectedWebhook, setSelectedWebhook] = useState(null);
  const [activeSubTab, setActiveSubTab] = useState("logs"); // "logs" | "metrics" | "security"
  const [deliveryLogs, setDeliveryLogs] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState(false);
  const [copiedText, setCopiedText] = useState(false);
  const [selectedLog, setSelectedLog] = useState(null); // For details drawer/modal
  const [retryingLogId, setRetryingLogId] = useState(null);
  const [rotatingSecret, setRotatingSecret] = useState(false);

  const [newWebhook, setNewWebhook] = useState({
    url: "", 
    events: [], 
    payload_format: "verbose",
    filterRuleKey: "",
    filterRuleValue: ""
  });

  // Fetch brands
  useEffect(() => {
    if (!token) return;
    api.get("/api/v1/brands")
      .then((res) => {
        const brandList = res || [];
        setBrands(brandList);
        if (brandList.length > 0) {
          setSelectedBrandId(brandList[0].id);
        }
      })
      .catch((err) => {
        console.error("Failed to load brands:", err);
      });
  }, [token]);

  // Fetch webhooks list
  const fetchWebhooks = useCallback(async () => {
    if (!selectedBrandId) return;
    setLoading(true);
    try {
      const res = await api.get(`/api/v1/webhooks?brand_id=${selectedBrandId}`);
      const data = res || [];
      setWebhooks(data);
      
      // Auto-select first webhook if none selected, or update selected reference
      if (data.length > 0) {
        if (!selectedWebhook) {
          handleSelectWebhook(data[0]);
        } else {
          const updated = data.find(w => w.id === selectedWebhook.id);
          if (updated) setSelectedWebhook(updated);
        }
      } else {
        setSelectedWebhook(null);
        setDeliveryLogs([]);
        setMetrics(null);
      }
    } catch (err) {
      toast.error("Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  }, [selectedBrandId, selectedWebhook]);

  useEffect(() => { 
    // eslint-disable-next-line react-hooks/exhaustive-deps
    fetchWebhooks(); 
  }, [selectedBrandId]);

  // Fetch delivery logs
  const fetchLogs = async (webhookId) => {
    setLogsLoading(true);
    try {
      const res = await api.get(`/api/v1/webhooks/${webhookId}/delivery-logs?limit=50`);
      setDeliveryLogs(res || []);
    } catch {
      toast.error("Failed to load delivery logs");
    } finally {
      setLogsLoading(false);
    }
  };

  // Fetch metrics/telemetry
  const fetchMetrics = async (webhookId) => {
    setMetricsLoading(true);
    try {
      const res = await api.get(`/api/v1/webhooks/${webhookId}/metrics?time_range=7d`);
      setMetrics(res || null);
    } catch (err) {
      console.error("Failed to load metrics:", err);
    } finally {
      setMetricsLoading(false);
    }
  };

  const handleSelectWebhook = (webhook) => {
    setSelectedWebhook(webhook);
    setRevealedSecret(false);
    fetchLogs(webhook.id);
    if (activeSubTab === "metrics") {
      fetchMetrics(webhook.id);
    }
  };

  useEffect(() => {
    if (selectedWebhook) {
      if (activeSubTab === "metrics") {
        fetchMetrics(selectedWebhook.id);
      } else if (activeSubTab === "logs") {
        fetchLogs(selectedWebhook.id);
      }
    }
  }, [activeSubTab, selectedWebhook?.id]);

  const handleCreateWebhook = async () => {
    if (!newWebhook.url || newWebhook.events.length === 0) {
      toast.error("URL and at least one event subscription are required");
      return;
    }
    if (!newWebhook.url.startsWith("http")) {
      toast.error("Please enter a valid webhook URL starting with http:// or https://");
      return;
    }

    try {
      let filter_rules = null;
      if (newWebhook.filterRuleKey.trim() && newWebhook.filterRuleValue.trim()) {
        filter_rules = { [newWebhook.filterRuleKey.trim()]: newWebhook.filterRuleValue.trim() };
      }

      await api.post("/api/v1/webhooks", {
        brand_id: parseInt(selectedBrandId),
        url: newWebhook.url,
        events: newWebhook.events,
        payload_format: newWebhook.payload_format,
        filter_rules: filter_rules
      });
      toast.success("Webhook created successfully!");
      setShowCreateForm(false);
      setNewWebhook({ url: "", events: [], payload_format: "verbose", filterRuleKey: "", filterRuleValue: "" });
      // eslint-disable-next-line react-hooks/exhaustive-deps
    fetchWebhooks();
    } catch (err) {
      toast.error(err.message || "Failed to create webhook");
    }
  };

  const handleDeleteWebhook = async (webhookId) => {
    if (!confirm("Are you sure you want to permanently delete this webhook subscription?")) return;
    try {
      await api.delete(`/api/v1/webhooks/${webhookId}`);
      toast.success("Webhook deleted successfully.");
      setSelectedWebhook(null);
      setDeliveryLogs([]);
      setMetrics(null);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    fetchWebhooks();
    } catch {
      toast.error("Failed to delete webhook");
    }
  };

  const handleRetryLog = async (logId, e) => {
    if (e) e.stopPropagation();
    setRetryingLogId(logId);
    try {
      await api.post(`/api/v1/webhooks/logs/${logId}/retry`);
      toast.success("Retry delivery task queued successfully!");
      if (selectedWebhook) {
        fetchLogs(selectedWebhook.id);
      }
    } catch {
      toast.error("Failed to queue retry delivery");
    } finally {
      setRetryingLogId(null);
    }
  };

  const handleRotateSecret = async () => {
    if (!selectedWebhook) return;
    if (!confirm("Are you sure you want to rotate the signing secret? Any legacy servers verifying events with the old secret will fail validation immediately.")) return;

    setRotatingSecret(true);
    try {
      const res = await api.post(`/api/v1/webhooks/${selectedWebhook.id}/rotate-secret`);
      if (res && res.secret_token) {
        toast.success("Signing secret rotated successfully!");
        setSelectedWebhook(prev => ({
          ...prev,
          secret_token: res.secret_token
        }));
      }
    } catch (err) {
      toast.error("Failed to rotate signing secret");
    } finally {
      setRotatingSecret(false);
    }
  };

  const toggleEvent = (event) => {
    setNewWebhook(prev => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter(e => e !== event)
        : [...prev.events, event]
    }));
  };

  const copySecretToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedText(true);
    toast.success("Secret token copied!");
    setTimeout(() => setCopiedText(false), 2000);
  };

  return (
    <div className="space-y-8">
      {/* 1. Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Webhook size={28} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">Webhook Dashboard</h1>
            <p className="text-zinc-400 text-sm mt-1">Configure event listeners and monitor delivery payloads</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedBrandId}
            onChange={(e) => setSelectedBrandId(e.target.value)}
            className="bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-xs font-semibold text-zinc-300 focus:border-purple-500 outline-none transition-all"
          >
            {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 px-4 py-2.5 rounded-xl text-xs font-bold transition-all shadow-md shadow-purple-950/20 active:scale-95 cursor-pointer"
          >
            <Plus size={14} /> New Webhook
          </button>
        </div>
      </div>

      {/* 2. Create Webhook Modal/Form */}
      <AnimatePresence>
        {showCreateForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="bg-zinc-950/30 border border-zinc-800/80 rounded-2xl p-6 space-y-5 backdrop-blur-xl">
              <div>
                <h3 className="text-base font-bold text-white">Register Webhook Endpoint</h3>
                <p className="text-xs text-zinc-500 mt-0.5">Receive JSON payloads signed with HMAC-SHA256 headers</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Payload URL</label>
                  <input
                    type="url"
                    placeholder="https://api.yourdomain.com/v1/webhooks/modelens"
                    value={newWebhook.url}
                    onChange={(e) => setNewWebhook(prev => ({ ...prev, url: e.target.value }))}
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-200 outline-none transition-all"
                  />
                </div>
                
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Payload Format</label>
                  <select
                    value={newWebhook.payload_format}
                    onChange={(e) => setNewWebhook(prev => ({ ...prev, payload_format: e.target.value }))}
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-200 outline-none transition-all"
                  >
                    <option value="verbose">Verbose Payload (Complete DB models)</option>
                    <option value="summary">Summary Payload (Lightweight stats)</option>
                  </select>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Subscribe to Events</label>
                <div className="flex flex-wrap gap-2">
                  {EVENT_TYPES.map(event => {
                    const isSelected = newWebhook.events.includes(event);
                    return (
                      <button
                        key={event}
                        type="button"
                        onClick={() => toggleEvent(event)}
                        className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
                          isSelected
                            ? "bg-purple-600/20 border-purple-500 text-purple-300"
                            : "border-zinc-800 bg-zinc-900/10 text-zinc-500 hover:border-zinc-700"
                        }`}
                      >
                        {event}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Advanced Filter Rules */}
              <div className="space-y-2 border-t border-zinc-850/50 pt-4">
                <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">Custom Filter Rule (Optional)</label>
                <p className="text-[11px] text-zinc-500">Only dispatch webhooks if a key in the event payload matches the specified value.</p>
                <div className="grid grid-cols-2 gap-4 max-w-lg">
                  <input
                    type="text"
                    placeholder="Payload key (e.g. status)"
                    value={newWebhook.filterRuleKey}
                    onChange={(e) => setNewWebhook(prev => ({ ...prev, filterRuleKey: e.target.value }))}
                    className="bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-200 outline-none"
                  />
                  <input
                    type="text"
                    placeholder="Expected value (e.g. completed)"
                    value={newWebhook.filterRuleValue}
                    onChange={(e) => setNewWebhook(prev => ({ ...prev, filterRuleValue: e.target.value }))}
                    className="bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-200 outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={handleCreateWebhook}
                  className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all shadow-md shadow-purple-950/20 cursor-pointer"
                >
                  Create Subscription
                </button>
                <button
                  onClick={() => setShowCreateForm(false)}
                  className="border border-zinc-800 hover:bg-zinc-900 px-4 py-2.5 rounded-xl text-xs font-semibold text-zinc-400 transition-all cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 3. Main Dashboard Layout (Subscriptions on Left, details on Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Side: Subscriptions Grid */}
        <div className="lg:col-span-1 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[11px] font-bold text-zinc-500 uppercase tracking-widest">Active Subscriptions ({webhooks.length})</h2>
          </div>
          
          <div className="space-y-3">
            {webhooks.length === 0 && !loading && (
              <div className="text-zinc-500 text-xs py-12 text-center border border-dashed border-zinc-850 rounded-2xl bg-zinc-950/10">
                <Webhook className="mx-auto text-zinc-700 mb-2" size={24} />
                No webhooks registered.
              </div>
            )}
            
            {loading && webhooks.length === 0 && (
              <div className="flex justify-center p-12">
                <RefreshCw className="animate-spin text-purple-500" size={24} />
              </div>
            )}

            {webhooks.map(webhook => {
              const isSelected = selectedWebhook?.id === webhook.id;
              return (
                <motion.div
                  key={webhook.id}
                  onClick={() => handleSelectWebhook(webhook)}
                  whileHover={{ y: -1 }}
                  className={`p-4 rounded-2xl border cursor-pointer transition-all flex flex-col justify-between gap-3 ${
                    isSelected
                      ? "border-purple-500/80 bg-purple-950/10 shadow-lg shadow-purple-950/10"
                      : "border-zinc-850 bg-zinc-900/10 hover:border-zinc-805 hover:bg-zinc-900/20"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 max-w-[85%]">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${webhook.is_active ? "bg-emerald-500" : "bg-zinc-600"}`} />
                      <span className="text-xs font-bold text-zinc-200 truncate font-mono">{webhook.url}</span>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteWebhook(webhook.id); }}
                      className="p-1 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-950/20 transition-all shrink-0 cursor-pointer"
                      title="Delete Subscription"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                  
                  <div className="flex flex-wrap gap-1.5">
                    {(webhook.events || []).map(e => (
                      <span key={e} className="text-[9px] bg-zinc-900 border border-zinc-850 px-2 py-0.5 rounded text-zinc-400 font-mono">
                        {e}
                      </span>
                    ))}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* Right Side: Subscription Details Sub-dashboard */}
        <div className="lg:col-span-2">
          {!selectedWebhook ? (
            <div className="flex flex-col items-center justify-center p-16 text-center border border-zinc-850 rounded-2xl bg-zinc-950/10 text-zinc-500 min-h-[400px]">
              <Webhook className="text-zinc-700 mb-3" size={32} />
              <h3 className="text-sm font-semibold text-zinc-300">No Webhook Selected</h3>
              <p className="text-xs text-zinc-500 max-w-sm mt-1">
                Select an existing webhook subscription from the panel or register a new one to view its telemetry metrics and delivery logs.
              </p>
            </div>
          ) : (
            <div className="border border-zinc-850 rounded-2xl bg-zinc-900/10 backdrop-blur-xl flex flex-col overflow-hidden min-h-[400px]">
              {/* Subscription Detail Header */}
              <div className="p-6 border-b border-zinc-850 bg-zinc-950/30">
                <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className={`h-2.5 w-2.5 rounded-full ${selectedWebhook.is_active ? "bg-emerald-500" : "bg-zinc-600"}`} />
                      <h3 className="text-base font-bold text-white truncate font-mono">{selectedWebhook.url}</h3>
                    </div>
                    <p className="text-xs text-zinc-400">
                      Payload Format: <span className="font-semibold text-purple-400 uppercase font-mono">{selectedWebhook.payload_format}</span>
                    </p>
                  </div>
                  
                  {/* Action Tabs selector */}
                  <div className="flex bg-zinc-950 border border-zinc-850 p-1 rounded-xl text-xs font-semibold">
                    <button
                      onClick={() => setActiveSubTab("logs")}
                      className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                        activeSubTab === "logs" 
                          ? "bg-purple-600 text-white" 
                          : "text-zinc-400 hover:text-zinc-200"
                      }`}
                    >
                      Delivery Logs
                    </button>
                    <button
                      onClick={() => setActiveSubTab("metrics")}
                      className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                        activeSubTab === "metrics" 
                          ? "bg-purple-600 text-white" 
                          : "text-zinc-400 hover:text-zinc-200"
                      }`}
                    >
                      Metrics & Telemetry
                    </button>
                    <button
                      onClick={() => setActiveSubTab("security")}
                      className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                        activeSubTab === "security" 
                          ? "bg-purple-600 text-white" 
                          : "text-zinc-400 hover:text-zinc-200"
                      }`}
                    >
                      Overview & Security
                    </button>
                  </div>
                </div>
              </div>

              {/* Sub-tab Content Area */}
              <div className="p-6 flex-1">
                
                {/* SUB-TAB 1: DELIVERY LOGS */}
                {activeSubTab === "logs" && (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Recent Deliveries</h4>
                      <button
                        onClick={() => fetchLogs(selectedWebhook.id)}
                        disabled={logsLoading}
                        className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 border border-zinc-800 transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
                        title="Refresh Logs"
                      >
                        <RefreshCw className={logsLoading ? "animate-spin text-purple-400" : ""} size={14} />
                      </button>
                    </div>

                    {logsLoading && deliveryLogs.length === 0 ? (
                      <div className="flex justify-center py-16">
                        <RefreshCw className="animate-spin text-purple-500" size={24} />
                      </div>
                    ) : deliveryLogs.length === 0 ? (
                      <div className="text-zinc-500 text-xs py-16 text-center border border-dashed border-zinc-850 rounded-xl bg-zinc-950/10">
                        No delivery attempts logged yet for this webhook.
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                        {deliveryLogs.map(log => (
                          <div 
                            key={log.id} 
                            onClick={() => setSelectedLog(log)}
                            className="bg-zinc-900/10 border border-zinc-850/80 rounded-xl p-4 hover:border-zinc-800 hover:bg-zinc-900/20 transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                          >
                            <div className="flex items-start gap-3">
                              <div className="mt-0.5 shrink-0">
                                {log.status === "success" ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> :
                                 log.status === "dead" ? <XCircle className="w-4 h-4 text-zinc-500" /> :
                                 log.status === "retrying" ? <Clock className="w-4 h-4 text-amber-400" /> :
                                 <AlertTriangle className="w-4 h-4 text-rose-400" />}
                              </div>
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${STATUS_BADGE_STYLE[log.status] || STATUS_BADGE_STYLE.failed}`}>
                                    {log.status}
                                  </span>
                                  <span className="text-[10px] text-zinc-500 font-semibold font-mono">Attempt #{log.attempt_number}</span>
                                </div>
                                <div className="text-[11px] text-zinc-300 font-mono truncate max-w-[250px] sm:max-w-md">
                                  {log.event_type}
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0">
                              <div className="text-right">
                                <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded border ${
                                  log.response_status >= 200 && log.response_status < 300
                                    ? "bg-emerald-950/40 border-emerald-900/30 text-emerald-400"
                                    : "bg-red-950/40 border-red-900/30 text-red-400"
                                }`}>
                                  {log.response_status || "TIMEOUT"}
                                </span>
                                <div className="text-[9px] text-zinc-500 font-mono mt-1">
                                  {log.execution_time_ms ? `${log.execution_time_ms}ms` : "—"} • {new Date(log.created_at).toLocaleTimeString()}
                                </div>
                              </div>
                              <ChevronRight className="text-zinc-600 hidden sm:block" size={14} />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* SUB-TAB 2: METRICS & TELEMETRY */}
                {activeSubTab === "metrics" && (
                  <div className="space-y-6">
                    <div className="flex justify-between items-center">
                      <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">7-Day Telemetry</h4>
                      <button
                        onClick={() => fetchMetrics(selectedWebhook.id)}
                        disabled={metricsLoading}
                        className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 border border-zinc-800 transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
                      >
                        <RefreshCw className={metricsLoading ? "animate-spin text-purple-400" : ""} size={14} />
                      </button>
                    </div>

                    {metricsLoading && !metrics ? (
                      <div className="flex justify-center py-16">
                        <RefreshCw className="animate-spin text-purple-500" size={24} />
                      </div>
                    ) : !metrics ? (
                      <div className="text-zinc-500 text-xs py-16 text-center border border-dashed border-zinc-850 rounded-xl bg-zinc-950/10">
                        Failed to calculate metrics or no deliveries registered.
                      </div>
                    ) : (
                      <div className="space-y-6">
                        
                        {/* Summary Grid */}
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                          {/* Deliveries */}
                          <div className="p-4 rounded-xl bg-zinc-950/40 border border-zinc-850/60">
                            <div className="flex items-center gap-2 text-zinc-500 mb-1">
                              <Play size={13} className="text-purple-400" />
                              <span className="text-[10px] font-bold uppercase tracking-wider">Total Deliveries</span>
                            </div>
                            <div className="text-xl font-bold font-mono text-white">{metrics.total_deliveries}</div>
                          </div>

                          {/* Success Rate */}
                          <div className="p-4 rounded-xl bg-zinc-950/40 border border-zinc-850/60">
                            <div className="flex items-center gap-2 text-zinc-500 mb-1">
                              <CheckCircle2 size={13} className="text-emerald-400" />
                              <span className="text-[10px] font-bold uppercase tracking-wider">Success Rate</span>
                            </div>
                            <div className="text-xl font-bold font-mono text-emerald-400">{metrics.success_rate}%</div>
                          </div>

                          {/* Latency */}
                          <div className="p-4 rounded-xl bg-zinc-950/40 border border-zinc-850/60">
                            <div className="flex items-center gap-2 text-zinc-500 mb-1">
                              <Clock size={13} className="text-amber-400" />
                              <span className="text-[10px] font-bold uppercase tracking-wider">Avg Latency</span>
                            </div>
                            <div className="text-xl font-bold font-mono text-zinc-300">{metrics.avg_latency_ms}ms</div>
                          </div>
                        </div>

                        {/* Status Code Breakdown and Queue Health */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          
                          {/* Deliveries Breakdown */}
                          <div className="p-4 rounded-xl bg-zinc-950/10 border border-zinc-850/40 space-y-3">
                            <h5 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Delivery Breakdown</h5>
                            <div className="space-y-2 text-xs">
                              <div className="flex justify-between items-center">
                                <span className="text-zinc-500 font-semibold flex items-center gap-1.5">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Successes
                                </span>
                                <span className="font-mono text-zinc-300 font-bold">{metrics.status_breakdown?.success || 0}</span>
                              </div>
                              <div className="flex justify-between items-center">
                                <span className="text-zinc-500 font-semibold flex items-center gap-1.5">
                                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Retrying
                                </span>
                                <span className="font-mono text-zinc-300 font-bold">{metrics.status_breakdown?.retrying || 0}</span>
                              </div>
                              <div className="flex justify-between items-center">
                                <span className="text-zinc-500 font-semibold flex items-center gap-1.5">
                                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> Failures
                                </span>
                                <span className="font-mono text-zinc-300 font-bold">{metrics.status_breakdown?.failed || 0}</span>
                              </div>
                              <div className="flex justify-between items-center">
                                <span className="text-zinc-500 font-semibold flex items-center gap-1.5">
                                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-500" /> Dead (DLQ)
                                </span>
                                <span className="font-mono text-zinc-300 font-bold">{metrics.status_breakdown?.dead || 0}</span>
                              </div>
                            </div>
                          </div>

                          {/* HTTP Status Code Distribution */}
                          <div className="p-4 rounded-xl bg-zinc-950/10 border border-zinc-850/40 space-y-3">
                            <h5 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">HTTP Status Codes</h5>
                            <div className="space-y-2 text-xs max-h-[120px] overflow-y-auto pr-1">
                              {Object.keys(metrics.status_code_distribution || {}).length === 0 ? (
                                <div className="text-zinc-600 text-xs py-4 text-center">No HTTP statuses recorded.</div>
                              ) : (
                                Object.entries(metrics.status_code_distribution).map(([code, count]) => {
                                  const is2xx = code.startsWith("2");
                                  return (
                                    <div key={code} className="flex justify-between items-center">
                                      <span className={`font-mono font-bold ${is2xx ? "text-emerald-400" : "text-rose-400"}`}>
                                        HTTP {code}
                                      </span>
                                      <span className="font-mono text-zinc-400">{count} occurrences</span>
                                    </div>
                                  );
                                })
                              )}
                            </div>
                          </div>

                        </div>

                      </div>
                    )}
                  </div>
                )}

                {/* SUB-TAB 3: OVERVIEW & SECURITY */}
                {activeSubTab === "security" && (
                  <div className="space-y-6">
                    <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Subscription & Signature Config</h4>
                    
                    {/* Event Subscriptions */}
                    <div className="space-y-2">
                      <span className="text-xs text-zinc-500 font-semibold block">Subscribed Events</span>
                      <div className="flex flex-wrap gap-2">
                        {selectedWebhook.events.map(ev => (
                          <span key={ev} className="text-xs bg-zinc-950 border border-zinc-850 px-3 py-1 rounded-xl text-zinc-300 font-mono">
                            {ev}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Filter Rules display if any */}
                    <div className="space-y-2 pt-2 border-t border-zinc-850/30">
                      <span className="text-xs text-zinc-500 font-semibold block">Payload Dispatch Rules</span>
                      {selectedWebhook.filter_rules && Object.keys(selectedWebhook.filter_rules).length > 0 ? (
                        <div className="flex items-center gap-2 text-xs">
                          <Sliders size={12} className="text-purple-400" />
                          <span className="text-zinc-400">Match rule:</span>
                          {Object.entries(selectedWebhook.filter_rules).map(([k, v]) => (
                            <span key={k} className="font-mono text-purple-300 border border-purple-900/30 bg-purple-950/20 px-2 py-0.5 rounded-lg">
                              {k} == "{String(v)}"
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-zinc-600 italic">No custom filter rules configured. Dispatching all event payloads immediately.</p>
                      )}
                    </div>

                    {/* Signing Secret Box */}
                    <div className="space-y-3 pt-4 border-t border-zinc-850/30">
                      <div className="flex justify-between items-center">
                        <div className="space-y-1">
                          <span className="text-xs text-zinc-500 font-semibold flex items-center gap-1.5">
                            <Key size={13} className="text-purple-400" /> Signing Secret Token
                          </span>
                          <p className="text-[10px] text-zinc-600">This token is used to construct the HMAC-SHA256 signature header for verification.</p>
                        </div>
                        <button
                          onClick={handleRotateSecret}
                          disabled={rotatingSecret}
                          className="flex items-center gap-1 text-[10px] font-bold text-purple-400 hover:text-purple-300 hover:bg-purple-950/20 px-2 py-1 border border-purple-900/40 rounded-lg cursor-pointer disabled:opacity-50"
                        >
                          {rotatingSecret ? <RefreshCw className="animate-spin" size={10} /> : <RefreshCw size={10} />}
                          Rotate
                        </button>
                      </div>

                      <div className="flex justify-between items-center bg-zinc-950/40 border border-zinc-850 rounded-xl px-4 py-3 gap-3">
                        <span className="font-mono text-xs text-zinc-300 tracking-wider overflow-x-auto select-all max-w-[80%]">
                          {revealedSecret ? selectedWebhook.secret_token : "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••"}
                        </span>
                        
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => copySecretToClipboard(selectedWebhook.secret_token)}
                            className="p-1 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-all cursor-pointer"
                            title="Copy Token"
                          >
                            {copiedText ? <Check className="text-emerald-400" size={13} /> : <Copy size={13} />}
                          </button>
                          <button
                            onClick={() => setRevealedSecret(!revealedSecret)}
                            className="p-1 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-all cursor-pointer"
                            title={revealedSecret ? "Hide Secret" : "Reveal Secret"}
                          >
                            {revealedSecret ? <EyeOff size={13} /> : <Eye size={13} />}
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Developer Guide */}
                    <div className="p-4 rounded-xl bg-zinc-950/20 border border-zinc-850/40 space-y-2 text-xs leading-relaxed text-zinc-400">
                      <span className="font-semibold text-zinc-300 block">How to verify requests:</span>
                      <p>
                        Each delivery includes a signature header: <code className="font-mono text-purple-300 bg-zinc-900 px-1 py-0.5 rounded">X-ModelLens-Signature</code>.
                      </p>
                      <p>
                        Calculate the HMAC-SHA256 signature using the raw payload body and this secret, and verify it matches the signature header to validate request authenticity.
                      </p>
                    </div>

                  </div>
                )}

              </div>
            </div>
          )}
        </div>

      </div>

      {/* 4. Log Details Inspector Slide-over/Modal */}
      <AnimatePresence>
        {selectedLog && (
          <div className="fixed inset-0 z-50 flex items-center justify-end">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedLog(null)}
              className="fixed inset-0 bg-black"
            />

            {/* Slide-over Card */}
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", bounce: 0, duration: 0.3 }}
              className="bg-zinc-900 border-l border-zinc-800 w-full max-w-2xl h-screen relative z-10 shadow-2xl p-6 flex flex-col justify-between"
            >
              <div className="flex-1 overflow-y-auto space-y-6 pr-1">
                {/* Header */}
                <div className="flex justify-between items-start border-b border-zinc-850 pb-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-bold uppercase tracking-wider border px-2 py-0.5 rounded-full ${STATUS_BADGE_STYLE[selectedLog.status] || STATUS_BADGE_STYLE.failed}`}>
                        {selectedLog.status}
                      </span>
                      <span className="text-xs text-zinc-500 font-semibold font-mono">Attempt #{selectedLog.attempt_number}</span>
                    </div>
                    <h3 className="text-base font-bold text-white font-mono break-all mt-2">{selectedLog.event_type}</h3>
                  </div>
                  <button 
                    onClick={() => setSelectedLog(null)}
                    className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg border border-zinc-800 hover:border-zinc-700 cursor-pointer"
                  >
                    <EyeOff size={16} />
                  </button>
                </div>

                {/* Details Table */}
                <div className="grid grid-cols-2 gap-4 text-xs bg-zinc-950/20 p-4 border border-zinc-850/50 rounded-xl">
                  <div className="space-y-0.5">
                    <span className="text-zinc-500 font-semibold block">Execution Time</span>
                    <span className="font-mono text-zinc-300">{selectedLog.execution_time_ms ? `${selectedLog.execution_time_ms}ms` : "—"}</span>
                  </div>
                  <div className="space-y-0.5">
                    <span className="text-zinc-500 font-semibold block">HTTP Status Code</span>
                    <span className="font-mono font-bold text-purple-400">{selectedLog.response_status || "TIMEOUT"}</span>
                  </div>
                  <div className="space-y-0.5">
                    <span className="text-zinc-500 font-semibold block flex items-center gap-1"><Calendar size={11} /> Timestamp</span>
                    <span className="text-zinc-400">{new Date(selectedLog.created_at).toLocaleString()}</span>
                  </div>
                  <div className="space-y-0.5">
                    <span className="text-zinc-500 font-semibold block">Log ID</span>
                    <span className="font-mono text-zinc-400">#{selectedLog.id}</span>
                  </div>
                </div>

                {/* Payload Sent Block */}
                <div className="space-y-2">
                  <span className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                    <Code size={13} className="text-purple-400" /> Request Payload (Sent JSON)
                  </span>
                  <div className="bg-zinc-950 border border-zinc-850 p-4 rounded-xl overflow-x-auto max-h-[250px] font-mono text-[11px] text-zinc-300">
                    <pre>{JSON.stringify(selectedLog.payload, null, 2)}</pre>
                  </div>
                </div>

                {/* Response Body Block */}
                <div className="space-y-2">
                  <span className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                    <AlertCircle size={13} className="text-amber-400" /> Response Body (Received)
                  </span>
                  <div className="bg-zinc-950 border border-zinc-850 p-4 rounded-xl overflow-x-auto max-h-[200px] font-mono text-[11px] text-zinc-400">
                    <pre>{selectedLog.response_body || "— (Empty or Timeout response)"}</pre>
                  </div>
                </div>

              </div>

              {/* Action Footer */}
              <div className="border-t border-zinc-850 pt-4 flex gap-3">
                {(selectedLog.status === "failed" || selectedLog.status === "dead") && (
                  <button
                    onClick={() => handleRetryLog(selectedLog.id)}
                    disabled={retryingLogId === selectedLog.id}
                    className="flex-1 flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 text-white py-3 px-4 rounded-xl text-xs font-bold transition-all active:scale-[0.98] disabled:opacity-50 cursor-pointer"
                  >
                    {retryingLogId === selectedLog.id ? <RefreshCw className="animate-spin" size={14} /> : <RefreshCw size={14} />}
                    {retryingLogId === selectedLog.id ? "Queuing Retry..." : "Retry Delivery Now"}
                  </button>
                )}
                <button
                  onClick={() => setSelectedLog(null)}
                  className="flex-1 border border-zinc-800 hover:bg-zinc-800 text-zinc-300 py-3 px-4 rounded-xl text-xs font-bold transition-all cursor-pointer text-center"
                >
                  Close Inspector
                </button>
              </div>

            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
