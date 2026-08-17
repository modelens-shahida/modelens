"use client";
import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { BarChart3, Download, Loader2, CheckCircle2, XCircle, Webhook, CreditCard } from "lucide-react";
import toast from "react-hot-toast";

export default function AnalyticsDashboardPage() {
  const { user } = useAuth();
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [userRole, setUserRole] = useState("viewer");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    api.get("/api/v1/brands").then(data => {
      setBrands(data || []);
      if (data?.length > 0) setSelectedBrandId(data[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedBrandId) return;
    fetchStats();
    fetchUserRole();
  }, [selectedBrandId]);

  const fetchUserRole = async () => {
    try {
      const members = await api.get(`/api/v1/brands/${selectedBrandId}/members`);
      const me = members.find(m => m.user_id === user?.id);
      setUserRole(me?.role || "viewer");
    } catch {}
  };

  const fetchStats = async () => {
    setLoading(true);
    try {
      const jobs = await api.get(`/api/v1/jobs?brand_id=${selectedBrandId}&limit=100`);
      const jobList = jobs?.jobs || jobs || [];
      const completed = jobList.filter(j => j.status === "completed").length;
      const failed = jobList.filter(j => j.status === "failed").length;
      const total = jobList.length;
      const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;
      setStats({ completed, failed, total, successRate });
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format) => {
    if (!selectedBrandId) {
      toast.error("Please select a brand");
      return;
    }
    setExporting(true);
    try {
      const today = new Date().toISOString().split("T")[0];
      const filename = `modelens_analytics_brand_${selectedBrandId}_${today}.${format}`;

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/analytics/export?brand_id=${selectedBrandId}&format=${format}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token") || ""}`,
          },
        }
      );

      if (!response.ok) throw new Error("Export failed");

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${format.toUpperCase()} report downloaded!`);
    } catch (e) {
      toast.error("Failed to export analytics");
    } finally {
      setExporting(false);
    }
  };

  const canExport = userRole === "owner" || userRole === "admin";

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-7 h-7 text-purple-400" />
            <div>
              <h1 className="text-2xl font-bold text-white">Analytics & Reports</h1>
              <p className="text-zinc-400 text-sm">Workspace performance and export dashboard</p>
            </div>
          </div>
          <select
            value={selectedBrandId}
            onChange={(e) => setSelectedBrandId(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2 text-sm text-zinc-200 outline-none"
          >
            <option value="">Select brand...</option>
            {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {/* Generation Jobs */}
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 className="w-4 h-4 text-green-400" />
              <h2 className="text-xs font-semibold text-zinc-300 uppercase">Generation Jobs</h2>
            </div>
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin text-purple-400" />
            ) : stats ? (
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-400">Completed</span>
                  <span className="text-green-400 font-semibold">{stats.completed}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-400">Failed</span>
                  <span className="text-red-400 font-semibold">{stats.failed}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-400">Success Rate</span>
                  <span className="text-white font-bold">{stats.successRate}%</span>
                </div>
                <div className="w-full bg-zinc-800 rounded-full h-1.5 mt-2">
                  <div className="bg-green-500 h-1.5 rounded-full" style={{width: `${stats.successRate}%`}} />
                </div>
              </div>
            ) : (
              <p className="text-zinc-500 text-xs">Select a brand to view stats</p>
            )}
          </div>

          {/* Credits */}
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <CreditCard className="w-4 h-4 text-purple-400" />
              <h2 className="text-xs font-semibold text-zinc-300 uppercase">Credit Usage</h2>
            </div>
            <p className="text-xs text-zinc-500 mb-2">Last 30 days</p>
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-zinc-400">Catalog Generation</span>
                <span className="text-purple-400 font-semibold">{stats?.completed || 0} credits</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-zinc-400">Total Jobs</span>
                <span className="text-white font-semibold">{stats?.total || 0}</span>
              </div>
            </div>
          </div>

          {/* Webhook */}
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <Webhook className="w-4 h-4 text-blue-400" />
              <h2 className="text-xs font-semibold text-zinc-300 uppercase">Webhook Health</h2>
            </div>
            <p className="text-xs text-zinc-500 mb-2">Delivery telemetry</p>
            <div className="text-xs text-zinc-400">
              View detailed webhook metrics in the <span className="text-purple-400">Webhooks</span> section.
            </div>
          </div>
        </div>

        {/* Export Panel */}
        <div className="bg-gradient-to-br from-zinc-900/80 to-purple-950/20 border border-zinc-800 rounded-2xl p-6">
          <h2 className="text-sm font-semibold text-white mb-1">Export Analytics Report</h2>
          <p className="text-xs text-zinc-400 mb-5">
            Download a full workspace analytics report including generation history, credit usage, and performance metrics.
          </p>

          {!canExport ? (
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-xs text-zinc-500">
              ⚠️ Export is available to Admin and Owner roles only.
            </div>
          ) : (
            <div className="flex gap-3">
              <button
                onClick={() => handleExport("csv")}
                disabled={exporting || !selectedBrandId}
                className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-40 px-5 py-2.5 rounded-xl text-sm font-semibold transition"
              >
                {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Export CSV
              </button>
              <button
                onClick={() => handleExport("json")}
                disabled={exporting || !selectedBrandId}
                className="flex items-center gap-2 border border-purple-600 hover:bg-purple-600/20 disabled:opacity-40 px-5 py-2.5 rounded-xl text-sm font-semibold text-purple-300 transition"
              >
                {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Export JSON
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
