"use client";
import React, { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { Search, Filter, ChevronLeft, ChevronRight, Shield, FileText, CreditCard, Users, Loader2, CheckCircle2, XCircle, AlertCircle } from "lucide-react";

const CATEGORIES = [
  { value: "", label: "All Categories" },
  { value: "auth", label: "Auth" },
  { value: "asset", label: "Assets" },
  { value: "billing", label: "Billing" },
  { value: "user", label: "Users" },
  { value: "webhook", label: "Webhooks" },
];

const CATEGORY_ICONS = {
  auth: <Shield className="w-3.5 h-3.5 text-purple-400" />,
  asset: <FileText className="w-3.5 h-3.5 text-blue-400" />,
  billing: <CreditCard className="w-3.5 h-3.5 text-emerald-400" />,
  user: <Users className="w-3.5 h-3.5 text-amber-400" />,
  webhook: <Shield className="w-3.5 h-3.5 text-indigo-400" />,
};

const STATUS_CONFIG = {
  success: { icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />, color: "text-emerald-400 bg-emerald-900/30 border-emerald-800" },
  failed: { icon: <XCircle className="w-3.5 h-3.5 text-red-400" />, color: "text-red-400 bg-red-900/30 border-red-800" },
  warning: { icon: <AlertCircle className="w-3.5 h-3.5 text-amber-400" />, color: "text-amber-400 bg-amber-900/30 border-amber-800" },
};

export default function AuditLogsList({ brandId }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchEmail, setSearchEmail] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const LIMIT = 20;

  const fetchLogs = useCallback(async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: LIMIT,
        offset: (page - 1) * LIMIT,
      });
      if (category) params.append("category", category);
      if (searchEmail) params.append("user_email", searchEmail);

      const data = await api.get(`/api/v1/brands/${brandId}/audit-logs?${params}`);
      setLogs(data?.logs || data || []);
      setTotal(data?.total || 0);
      setTotalPages(Math.ceil((data?.total || 0) / LIMIT) || 1);
    } catch {
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }, [brandId, page, category, searchEmail]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleSearch = (e) => {
    setSearchEmail(e.target.value);
    setPage(1);
  };

  const handleCategoryChange = (val) => {
    setCategory(val);
    setPage(1);
  };

  return (
    <div className="space-y-4">
      {/* Search & Filter Bar */}
      <div className="flex gap-3 flex-wrap">
        <div className="flex-1 flex items-center gap-2 bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 min-w-48">
          <Search className="w-4 h-4 text-zinc-500 shrink-0" />
          <input
            type="text"
            value={searchEmail}
            onChange={handleSearch}
            placeholder="Search by user email..."
            className="flex-1 bg-transparent text-sm text-zinc-200 outline-none placeholder-zinc-600"
          />
        </div>
        <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2">
          <Filter className="w-4 h-4 text-zinc-500" />
          <select
            value={category}
            onChange={(e) => handleCategoryChange(e.target.value)}
            className="bg-transparent text-sm text-zinc-200 outline-none"
          >
            {CATEGORIES.map(c => <option key={c.value} value={c.value} className="bg-zinc-900">{c.label}</option>)}
          </select>
        </div>
        <div className="flex items-center text-xs text-zinc-500 px-2">
          {total} events
        </div>
      </div>

      {/* Logs Table */}
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl overflow-hidden">
        {/* Table Header */}
        <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-zinc-800 bg-zinc-900/60">
          <div className="col-span-4 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Event</div>
          <div className="col-span-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">User</div>
          <div className="col-span-2 text-xs font-semibold text-zinc-400 uppercase tracking-wider">IP</div>
          <div className="col-span-1 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Status</div>
          <div className="col-span-2 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Time</div>
        </div>

        {/* Table Body */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-5 h-5 animate-spin text-purple-400" />
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-12 text-zinc-500 text-sm">
            No audit logs found
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/50">
            {logs.map((log, idx) => {
              const statusCfg = STATUS_CONFIG[log.status] || STATUS_CONFIG.success;
              const categoryIcon = CATEGORY_ICONS[log.category] || CATEGORY_ICONS.auth;
              return (
                <div key={log.id || idx} className="grid grid-cols-12 gap-2 px-4 py-3 hover:bg-zinc-800/30 transition">
                  <div className="col-span-4 flex items-center gap-2 min-w-0">
                    {categoryIcon}
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-zinc-200 truncate">{log.event_name || log.action}</p>
                      {log.category && <p className="text-xs text-zinc-500 capitalize">{log.category}</p>}
                    </div>
                  </div>
                  <div className="col-span-3 flex items-center min-w-0">
                    <p className="text-xs text-zinc-300 truncate">{log.user_email || log.user?.email || "—"}</p>
                  </div>
                  <div className="col-span-2 flex items-center">
                    <p className="text-xs text-zinc-500 font-mono">{log.ip_address || "—"}</p>
                  </div>
                  <div className="col-span-1 flex items-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full border flex items-center gap-1 ${statusCfg.color}`}>
                      {statusCfg.icon}
                    </span>
                  </div>
                  <div className="col-span-2 flex items-center">
                    <p className="text-xs text-zinc-500">
                      {log.created_at ? new Date(log.created_at).toLocaleString() : "—"}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-zinc-500">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex items-center gap-1 text-xs border border-zinc-700 hover:border-purple-500 disabled:opacity-40 px-3 py-1.5 rounded-xl transition"
            >
              <ChevronLeft className="w-3.5 h-3.5" /> Prev
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="flex items-center gap-1 text-xs border border-zinc-700 hover:border-purple-500 disabled:opacity-40 px-3 py-1.5 rounded-xl transition"
            >
              Next <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
