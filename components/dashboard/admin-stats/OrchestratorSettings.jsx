"use client";

import React, { useState, useEffect } from "react";
import { adminSettingsApi } from "@/lib/admin-settings";
import { 
  Sliders, 
  Activity, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Play, 
  Save 
} from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "react-hot-toast";

export default function OrchestratorSettings() {
  const [rateLimit, setRateLimit] = useState(10);
  const [metrics, setMetrics] = useState({
    campaigns_total: 0,
    campaigns_success: 0,
    campaigns_failed: 0,
    campaigns_retries: 0,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  async function fetchSettings(isSilent = false) {
    try {
      if (!isSilent) setLoading(true);
      else setRefreshing(true);

      const data = await adminSettingsApi.getSettings();
      if (data) {
        setRateLimit(data.orchestrator_rate_limit || 10);
        if (data.metrics) {
          setMetrics(data.metrics);
        }
      }
    } catch (error) {
      console.error("Failed to load settings:", error);
      toast.error("Failed to fetch current settings or metrics");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    fetchSettings();
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    try {
      setSaving(true);
      const res = await adminSettingsApi.updateSettings(rateLimit);
      if (res && res.status === "success") {
        toast.success(`Rate limit updated to ${rateLimit} requests/min`);
        await fetchSettings(true);
      } else {
        throw new Error("Invalid response");
      }
    } catch (error) {
      console.error("Failed to save settings:", error);
      toast.error("Failed to save settings to backend");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-32 items-center justify-center rounded-xl border border-zinc-800/50 bg-zinc-950/20 p-6">
        <RefreshCw className="animate-spin text-purple-500" size={24} />
      </div>
    );
  }

  // Calculate success rate percentage
  const total = metrics.campaigns_total || 0;
  const success = metrics.campaigns_success || 0;
  const successRate = total > 0 ? ((success / total) * 100).toFixed(1) : "0.0";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      {/* 1. Dynamic Throttling Controller */}
      <motion.div 
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="lg:col-span-1 p-6 rounded-2xl border border-zinc-800 bg-zinc-950/30 backdrop-blur-xl flex flex-col justify-between"
      >
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
                <Sliders size={20} />
              </div>
              <h2 className="text-xl font-bold text-white">Dynamic Throttling</h2>
            </div>
          </div>
          
          <p className="text-sm text-zinc-400 mb-6 leading-relaxed">
            Adjust the platform-wide rate limit for campaign generation jobs. Persisted in Redis and enforced immediately without reboot.
          </p>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-zinc-300">Orchestrator Limit</span>
              <span className="px-3 py-1 rounded-md bg-purple-500/10 text-purple-400 font-mono text-sm border border-purple-500/20">
                {rateLimit} RPM
              </span>
            </div>
            
            <input 
              type="range" 
              min="1" 
              max="200" 
              value={rateLimit} 
              onChange={(e) => setRateLimit(parseInt(e.target.value))}
              className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-purple-500 focus:outline-none"
            />
            <div className="flex justify-between text-[11px] text-zinc-500 font-mono">
              <span>1 RPM</span>
              <span>100 RPM</span>
              <span>200 RPM</span>
            </div>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="mt-8 w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-semibold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-lg shadow-purple-950/20 border border-purple-500/30 transition-all active:scale-[0.98] disabled:opacity-50"
        >
          {saving ? (
            <RefreshCw className="animate-spin" size={16} />
          ) : (
            <Save size={16} />
          )}
          {saving ? "Saving Changes..." : "Save Settings"}
        </button>
      </motion.div>

      {/* 2. Prometheus Pipeline Metrics */}
      <motion.div 
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
        className="lg:col-span-2 p-6 rounded-2xl border border-zinc-800 bg-zinc-950/30 backdrop-blur-xl flex flex-col justify-between"
      >
        <div>
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                <Activity size={20} />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Pipeline Telemetry</h2>
                <p className="text-xs text-zinc-500 mt-0.5">Real-time stats from custom Prometheus instrumentation</p>
              </div>
            </div>

            <button
              onClick={() => fetchSettings(true)}
              disabled={refreshing}
              className="p-2 rounded-lg hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 transition-all text-zinc-400 active:scale-95 disabled:opacity-50"
              title="Refresh Telemetry"
            >
              <RefreshCw className={`${refreshing ? 'animate-spin text-purple-400' : ''}`} size={16} />
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            
            {/* Total */}
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60 hover:border-zinc-700/50 transition-all">
              <div className="flex items-center gap-2 text-zinc-500 mb-2">
                <Play size={14} className="text-purple-400" />
                <span className="text-xs font-medium">Total Runs</span>
              </div>
              <div className="text-2xl font-bold text-white font-mono">{metrics.campaigns_total}</div>
            </div>

            {/* Success */}
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60 hover:border-zinc-700/50 transition-all">
              <div className="flex items-center gap-2 text-zinc-500 mb-2">
                <CheckCircle2 size={14} className="text-emerald-400" />
                <span className="text-xs font-medium">Successes</span>
              </div>
              <div className="text-2xl font-bold text-white font-mono text-emerald-400">{metrics.campaigns_success}</div>
            </div>

            {/* Failed */}
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60 hover:border-zinc-700/50 transition-all">
              <div className="flex items-center gap-2 text-zinc-500 mb-2">
                <XCircle size={14} className="text-rose-400" />
                <span className="text-xs font-medium">Failures</span>
              </div>
              <div className="text-2xl font-bold text-white font-mono text-rose-400">{metrics.campaigns_failed}</div>
            </div>

            {/* Retries */}
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60 hover:border-zinc-700/50 transition-all">
              <div className="flex items-center gap-2 text-zinc-500 mb-2">
                <AlertCircle size={14} className="text-amber-400" />
                <span className="text-xs font-medium">Retries</span>
              </div>
              <div className="text-2xl font-bold text-white font-mono text-amber-400">{metrics.campaigns_retries}</div>
            </div>

          </div>
        </div>

        {/* Visual Progress Bar */}
        <div className="mt-8 p-4 rounded-xl bg-zinc-900/20 border border-zinc-800/30 flex items-center justify-between gap-6">
          <div className="flex-1">
            <div className="flex justify-between items-center text-xs mb-1.5 font-medium">
              <span className="text-zinc-400">Pipeline Success Rate</span>
              <span className="text-emerald-400 font-mono">{successRate}%</span>
            </div>
            <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: `${successRate}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="bg-gradient-to-r from-emerald-500 to-teal-400 h-full rounded-full"
              />
            </div>
          </div>
          <div className="text-[11px] text-zinc-500 max-w-[150px] leading-relaxed">
            Goal is &gt;99.5% uptime. Throttling helps keep failures low by reducing GPU enqueue pressure.
          </div>
        </div>

      </motion.div>

    </div>
  );
}
