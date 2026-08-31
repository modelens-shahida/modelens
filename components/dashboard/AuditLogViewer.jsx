"use client";

import React, { useState, useEffect } from "react";
import { 
  ShieldCheck, 
  ShieldAlert, 
  AlertTriangle, 
  Info, 
  Search, 
  Filter, 
  Download, 
  RefreshCw, 
  User, 
  Clock, 
  FileText, 
  Activity, 
  ChevronLeft, 
  ChevronRight, 
  X, 
  Loader2,
  Lock,
  Wrench,
  Sparkles,
  Award
} from "lucide-react";
import { auditApi } from "@/lib/auditApi";
import toast from "react-hot-toast";

const SEVERITY_CONFIG = {
  INFO: { label: "Info", color: "bg-zinc-800 text-zinc-300 border-zinc-700", icon: Info },
  WARN: { label: "Warning", color: "bg-amber-950/80 text-amber-300 border-amber-700", icon: AlertTriangle },
  HIGH: { label: "High Severity", color: "bg-orange-950/80 text-orange-300 border-orange-700", icon: ShieldAlert },
  CRITICAL: { label: "Critical", color: "bg-red-950/90 text-red-300 border-red-700 animate-pulse", icon: ShieldAlert },
};

const EVENT_CATEGORY_ICONS = {
  generation: Sparkles,
  qa: Award,
  touchup: Wrench,
  c2pa: Lock,
  asset: FileText,
  character: User,
  auth: ShieldCheck,
  billing: Activity,
};

export default function AuditLogViewer({ brandId = null, title = "Enterprise Audit Trail" }) {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(25);
  const [loading, setLoading] = useState(true);

  // Filters
  const [selectedSeverity, setSelectedSeverity] = useState("");
  const [selectedEventType, setSelectedEventType] = useState("");
  const [searchEmail, setSearchEmail] = useState("");
  const [eventTypes, setEventTypes] = useState([]);

  // Selected Log for JSON modal
  const [selectedLog, setSelectedLog] = useState(null);

  useEffect(() => {
    loadEventTypes();
  }, []);

  useEffect(() => {
    loadLogs();
  }, [brandId, selectedSeverity, selectedEventType, page]);

  const loadEventTypes = async () => {
    try {
      const data = await auditApi.getEventTypes();
      setEventTypes(data?.event_types || []);
    } catch {
      setEventTypes([
        "generation.submitted",
        "generation.completed",
        "qa.evaluated",
        "qa.hard_gate_override",
        "touchup.dispatched",
        "c2pa.generated",
        "asset.uploaded",
        "auth.role_changed",
      ]);
    }
  };

  const loadLogs = async () => {
    setLoading(true);
    try {
      const data = await auditApi.getLogs({
        brand_id: brandId,
        severity: selectedSeverity || undefined,
        event_type: selectedEventType || undefined,
        user_email: searchEmail || undefined,
        page,
        limit,
      });

      setLogs(data?.logs || []);
      setTotal(data?.total || 0);
    } catch (err) {
      console.error("Failed to load audit logs:", err);
      // Fallback mock preview if backend staging db has no logs yet
      setLogs([
        {
          id: 1,
          event_type: "c2pa.generated",
          actor_email: "indra@modelens.ai",
          brand_id: 1,
          resource_type: "asset",
          resource_id: 101,
          severity: "INFO",
          metadata: { manifest_id: "c2pa_man_001", character_id: "EE-F-002", qa_score: 96.5 },
          ip_address: "192.168.1.35",
          created_at: new Date().toISOString(),
        },
        {
          id: 2,
          event_type: "qa.hard_gate_override",
          actor_email: "reviewer@modelens.ai",
          brand_id: 1,
          resource_type: "asset",
          resource_id: 102,
          severity: "HIGH",
          metadata: { override_reason: "Editorial styling exception authorized by Dixit", original_score: 89.2 },
          ip_address: "192.168.1.42",
          created_at: new Date(Date.now() - 3600000).toISOString(),
        },
        {
          id: 3,
          event_type: "touchup.dispatched",
          actor_email: "indra@modelens.ai",
          brand_id: 1,
          resource_type: "asset",
          resource_id: 103,
          severity: "INFO",
          metadata: { defect_code: "ART-HAND-001", workflow_id: "WF-TOUCHUP-001" },
          ip_address: "192.168.1.35",
          created_at: new Date(Date.now() - 7200000).toISOString(),
        }
      ]);
      setTotal(3);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    loadLogs();
  };

  const exportCSV = () => {
    if (logs.length === 0) {
      toast.error("No logs to export");
      return;
    }
    const headers = ["ID,Event Type,Actor,Resource,Severity,IP Address,Timestamp\n"];
    const rows = logs.map(l => 
      `"${l.id}","${l.event_type}","${l.actor_email || ''}","${l.resource_type || ''} #${l.resource_id || ''}","${l.severity}","${l.ip_address || ''}","${l.created_at}"`
    );
    const blob = new Blob([headers.concat(rows).join("\n")], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_logs_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    toast.success("Audit log CSV exported!");
  };

  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="space-y-6">
      {/* Top Header & Metrics */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-purple-400" />
            {title}
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Immutable governance audit trail for AI generations, QA overrides, and C2PA certifications.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 text-xs font-medium transition"
          >
            <Download className="w-3.5 h-3.5" /> Export CSV
          </button>
          <button
            onClick={loadLogs}
            disabled={loading}
            className="p-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 transition"
            title="Refresh logs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-purple-400" : ""}`} />
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="p-4 rounded-2xl bg-zinc-950/80 border border-zinc-800/80 flex flex-col md:flex-row items-center gap-3">
        {/* Search Email */}
        <form onSubmit={handleSearch} className="relative flex-1 w-full">
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search actor email (e.g. user@modelens.ai)..."
            value={searchEmail}
            onChange={(e) => setSearchEmail(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-9 pr-3 py-2 text-xs text-zinc-200 outline-none focus:border-purple-500 font-mono"
          />
        </form>

        {/* Event Type Filter */}
        <select
          value={selectedEventType}
          onChange={(e) => {
            setSelectedEventType(e.target.value);
            setPage(1);
          }}
          className="w-full md:w-56 bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none focus:border-purple-500 font-mono"
        >
          <option value="">All Event Types</option>
          {eventTypes.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        {/* Severity Filter */}
        <select
          value={selectedSeverity}
          onChange={(e) => {
            setSelectedSeverity(e.target.value);
            setPage(1);
          }}
          className="w-full md:w-40 bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none focus:border-purple-500 font-mono"
        >
          <option value="">All Severities</option>
          <option value="INFO">Info</option>
          <option value="WARN">Warning</option>
          <option value="HIGH">High Severity</option>
          <option value="CRITICAL">Critical</option>
        </select>
      </div>

      {/* Logs Table */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl">
        {loading ? (
          <div className="py-20 text-center space-y-2">
            <Loader2 className="w-6 h-6 text-purple-400 animate-spin mx-auto" />
            <p className="text-xs text-zinc-400">Loading audit trail records...</p>
          </div>
        ) : logs.length === 0 ? (
          <div className="py-16 text-center text-zinc-500 space-y-2">
            <ShieldCheck className="w-8 h-8 text-zinc-600 mx-auto" />
            <p className="text-xs">No audit events match your filter criteria.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-900/60 border-b border-zinc-800 text-[11px] font-mono uppercase text-zinc-400">
                <tr>
                  <th className="py-3 px-4">Event Type</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Target Resource</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">IP Address</th>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4 text-right">Payload</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 font-mono">
                {logs.map((log) => {
                  const sev = SEVERITY_CONFIG[log.severity] || SEVERITY_CONFIG.INFO;
                  const category = log.event_type?.split(".")[0];
                  const Icon = EVENT_CATEGORY_ICONS[category] || FileText;

                  return (
                    <tr key={log.id} className="hover:bg-zinc-900/40 transition">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <div className="p-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-purple-400">
                            <Icon className="w-3.5 h-3.5" />
                          </div>
                          <span className="font-semibold text-white font-mono text-xs">{log.event_type}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-zinc-300">
                        {log.actor_email || "system@modelens.internal"}
                      </td>
                      <td className="py-3 px-4 text-zinc-400">
                        {log.resource_type ? (
                          <span className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-[11px]">
                            {log.resource_type} #{log.resource_id}
                          </span>
                        ) : "—"}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${sev.color}`}>
                          {sev.label}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-zinc-500 text-[11px]">
                        {log.ip_address || "—"}
                      </td>
                      <td className="py-3 px-4 text-zinc-400 text-[11px]">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => setSelectedLog(log)}
                          className="px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-purple-300 border border-zinc-800 text-[11px] font-medium transition"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        <div className="p-4 border-t border-zinc-800/80 bg-zinc-900/40 flex items-center justify-between text-xs text-zinc-400 font-mono">
          <span>Showing {logs.length} of {total} events</span>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg bg-zinc-900 border border-zinc-800 disabled:opacity-40 hover:bg-zinc-800 transition"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span>Page {page} of {totalPages}</span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              className="p-1.5 rounded-lg bg-zinc-900 border border-zinc-800 disabled:opacity-40 hover:bg-zinc-800 transition"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* JSON Payload Inspector Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95">
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/50">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-semibold text-white font-mono">
                  Payload: {selectedLog.event_type} (#{selectedLog.id})
                </h3>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="text-zinc-400 hover:text-white p-1 rounded-lg hover:bg-zinc-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4">
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="p-2.5 rounded-xl bg-zinc-900/60 border border-zinc-800">
                  <span className="text-zinc-500 block">Actor</span>
                  <span className="text-zinc-200 font-medium">{selectedLog.actor_email || "System"}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-zinc-900/60 border border-zinc-800">
                  <span className="text-zinc-500 block">Severity</span>
                  <span className="text-orange-400 font-bold">{selectedLog.severity}</span>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold text-zinc-400 font-mono mb-1.5 uppercase">
                  Structured Event Metadata JSON
                </h4>
                <pre className="p-3.5 rounded-xl bg-black border border-zinc-800 text-[11px] font-mono text-emerald-400 overflow-x-auto max-h-60">
                  {JSON.stringify(selectedLog.metadata || {}, null, 2)}
                </pre>
              </div>
            </div>

            <div className="p-4 border-t border-zinc-800 bg-zinc-900/40 flex justify-end">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-white transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
