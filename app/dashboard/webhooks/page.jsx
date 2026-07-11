"use client";
import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Plus, Trash2, RefreshCw, CheckCircle2, XCircle, Clock, AlertTriangle, Webhook, Eye } from "lucide-react";
import toast from "react-hot-toast";

const EVENT_TYPES = [
  "job.completed", "job.failed", "asset.processed",
  "training_done", "low_credit", "webhook_failed",
];

const STATUS_COLORS = {
  success: "text-green-400",
  failed: "text-red-400",
  retrying: "text-yellow-400",
  dead: "text-red-600",
};

export default function WebhookDashboardPage() {
  const { user, token } = useAuth();
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [webhooks, setWebhooks] = useState([]);
  const [selectedWebhook, setSelectedWebhook] = useState(null);
  const [deliveryLogs, setDeliveryLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newWebhook, setNewWebhook] = useState({
    url: "", events: [], payload_format: "verbose"
  });

  // Fetch brands
  useEffect(() => {
    if (!token) return;
    api.get("/api/v1/brands").then((res) => {
      setBrands(res.data || []);
      if (res.data?.length > 0) setSelectedBrandId(res.data[0].id);
    }).catch(() => {});
  }, [token]);

  // Fetch webhooks
  const fetchWebhooks = useCallback(async () => {
    if (!selectedBrandId) return;
    setLoading(true);
    try {
      const res = await api.get(`/api/v1/webhooks?brand_id=${selectedBrandId}`);
      setWebhooks(res.data || []);
    } catch {
      toast.error("Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  }, [selectedBrandId]);

  useEffect(() => { fetchWebhooks(); }, [fetchWebhooks]);

  // Fetch delivery logs
  const fetchLogs = async (webhookId) => {
    try {
      const res = await api.get(`/api/v1/webhooks/${webhookId}/delivery-logs`);
      setDeliveryLogs(res.data || []);
    } catch {
      toast.error("Failed to load delivery logs");
    }
  };

  const handleSelectWebhook = (webhook) => {
    setSelectedWebhook(webhook);
    fetchLogs(webhook.id);
  };

  const handleCreateWebhook = async () => {
    if (!newWebhook.url || newWebhook.events.length === 0) {
      toast.error("URL and at least one event are required");
      return;
    }
    try {
      await api.post("/api/v1/webhooks", {
        brand_id: selectedBrandId,
        url: newWebhook.url,
        events: newWebhook.events,
        payload_format: newWebhook.payload_format,
      });
      toast.success("Webhook created!");
      setShowCreateForm(false);
      setNewWebhook({ url: "", events: [], payload_format: "verbose" });
      fetchWebhooks();
    } catch {
      toast.error("Failed to create webhook");
    }
  };

  const handleDeleteWebhook = async (webhookId) => {
    try {
      await api.delete(`/api/v1/webhooks/${webhookId}`);
      toast.success("Webhook deleted");
      setSelectedWebhook(null);
      setDeliveryLogs([]);
      fetchWebhooks();
    } catch {
      toast.error("Failed to delete webhook");
    }
  };

  const handleRetryLog = async (logId) => {
    try {
      await api.post(`/api/v1/webhooks/logs/${logId}/retry`);
      toast.success("Retry queued!");
      fetchLogs(selectedWebhook.id);
    } catch {
      toast.error("Failed to queue retry");
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

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <Webhook className="w-8 h-8 text-purple-400" />
            <div>
              <h1 className="text-2xl font-bold">Webhook Dashboard</h1>
              <p className="text-gray-400 text-sm">Manage subscriptions and monitor delivery logs</p>
            </div>
          </div>
          <div className="flex gap-3">
            <select
              value={selectedBrandId}
              onChange={(e) => setSelectedBrandId(e.target.value)}
              className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm"
            >
              {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <button
              onClick={() => setShowCreateForm(true)}
              className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg text-sm font-medium transition"
            >
              <Plus className="w-4 h-4" /> New Webhook
            </button>
          </div>
        </div>

        {/* Create Form */}
        {showCreateForm && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Register New Webhook</h2>
            <div className="space-y-4">
              <input
                type="url"
                placeholder="https://your-endpoint.com/webhook"
                value={newWebhook.url}
                onChange={(e) => setNewWebhook(prev => ({ ...prev, url: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-600 rounded-lg px-4 py-2 text-sm"
              />
              <div>
                <p className="text-sm text-gray-400 mb-2">Select Events:</p>
                <div className="flex flex-wrap gap-2">
                  {EVENT_TYPES.map(event => (
                    <button
                      key={event}
                      onClick={() => toggleEvent(event)}
                      className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
                        newWebhook.events.includes(event)
                          ? "bg-purple-600 border-purple-500 text-white"
                          : "border-gray-600 text-gray-400 hover:border-purple-500"
                      }`}
                    >
                      {event}
                    </button>
                  ))}
                </div>
              </div>
              <select
                value={newWebhook.payload_format}
                onChange={(e) => setNewWebhook(prev => ({ ...prev, payload_format: e.target.value }))}
                className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm"
              >
                <option value="verbose">Verbose Payload</option>
                <option value="summary">Summary Payload</option>
              </select>
              <div className="flex gap-3">
                <button onClick={handleCreateWebhook} className="bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg text-sm font-medium transition">
                  Create Webhook
                </button>
                <button onClick={() => setShowCreateForm(false)} className="border border-gray-600 px-4 py-2 rounded-lg text-sm font-medium transition hover:border-gray-400">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Webhooks List */}
          <div className="lg:col-span-1">
            <h2 className="text-sm font-semibold text-gray-400 uppercase mb-3">Subscriptions ({webhooks.length})</h2>
            <div className="space-y-2">
              {webhooks.length === 0 && (
                <div className="text-gray-500 text-sm py-8 text-center border border-gray-800 rounded-xl">
                  No webhooks registered
                </div>
              )}
              {webhooks.map(webhook => (
                <div
                  key={webhook.id}
                  onClick={() => handleSelectWebhook(webhook)}
                  className={`p-4 rounded-xl border cursor-pointer transition ${
                    selectedWebhook?.id === webhook.id
                      ? "border-purple-500 bg-purple-950"
                      : "border-gray-800 bg-gray-900 hover:border-gray-600"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`w-2 h-2 rounded-full ${webhook.is_active ? "bg-green-400" : "bg-gray-500"}`} />
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteWebhook(webhook.id); }}
                      className="text-gray-500 hover:text-red-400 transition"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                  <p className="text-xs text-gray-300 truncate">{webhook.url}</p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {(webhook.events || []).map(e => (
                      <span key={e} className="text-xs bg-gray-800 px-2 py-0.5 rounded-full text-gray-400">{e}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Delivery Logs */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-400 uppercase">
                Delivery Logs {selectedWebhook ? `— ${selectedWebhook.url}` : ""}
              </h2>
              {selectedWebhook && (
                <button onClick={() => fetchLogs(selectedWebhook.id)} className="text-gray-400 hover:text-white transition">
                  <RefreshCw className="w-4 h-4" />
                </button>
              )}
            </div>

            {!selectedWebhook && (
              <div className="text-gray-500 text-sm py-16 text-center border border-gray-800 rounded-xl">
                Select a webhook to view delivery logs
              </div>
            )}

            {selectedWebhook && deliveryLogs.length === 0 && (
              <div className="text-gray-500 text-sm py-16 text-center border border-gray-800 rounded-xl">
                No delivery logs yet
              </div>
            )}

            <div className="space-y-2">
              {deliveryLogs.map(log => (
                <div key={log.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {log.status === "success" ? <CheckCircle2 className="w-4 h-4 text-green-400" /> :
                       log.status === "dead" ? <XCircle className="w-4 h-4 text-red-500" /> :
                       log.status === "retrying" ? <Clock className="w-4 h-4 text-yellow-400" /> :
                       <AlertTriangle className="w-4 h-4 text-red-400" />}
                      <span className={`text-xs font-medium ${STATUS_COLORS[log.status] || "text-gray-400"}`}>
                        {log.status?.toUpperCase()}
                      </span>
                      <span className="text-xs text-gray-500">Attempt #{log.attempt_number}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        log.response_status >= 200 && log.response_status < 300
                          ? "bg-green-900 text-green-400"
                          : "bg-red-900 text-red-400"
                      }`}>
                        {log.response_status || "timeout"}
                      </span>
                      {(log.status === "dead" || log.status === "failed") && (
                        <button
                          onClick={() => handleRetryLog(log.id)}
                          className="text-xs bg-purple-800 hover:bg-purple-700 px-2 py-1 rounded-lg transition"
                        >
                          Retry
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-gray-500">
                    <span>{log.event_type}</span>
                    <span className="mx-2">•</span>
                    <span>{log.execution_time_ms}ms</span>
                    <span className="mx-2">•</span>
                    <span>{new Date(log.created_at).toLocaleString()}</span>
                  </div>
                  {log.response_body && (
                    <p className="text-xs text-gray-600 mt-1 truncate">{log.response_body}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
