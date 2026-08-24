"use client";
import React from "react";
import { CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react";

const STATUS_CONFIG = {
  approved: { icon: <CheckCircle2 className="w-3.5 h-3.5" />, color: "text-emerald-400 bg-emerald-900/30 border-emerald-800" },
  pending: { icon: <Clock className="w-3.5 h-3.5" />, color: "text-amber-400 bg-amber-900/30 border-amber-800" },
  rejected: { icon: <XCircle className="w-3.5 h-3.5" />, color: "text-red-400 bg-red-900/30 border-red-800" },
  revision_required: { icon: <Clock className="w-3.5 h-3.5" />, color: "text-orange-400 bg-orange-900/30 border-orange-800" },
};

export default function TaxonomyTable({ items = [], loading = false, onApprove, onRevise, onReject, updatingId }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-purple-400" />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-zinc-500 text-sm border border-dashed border-zinc-800 rounded-2xl">
        No taxonomy items found
      </div>
    );
  }

  return (
    <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-zinc-800 bg-zinc-900/60">
        <div className="col-span-2 text-xs font-semibold text-zinc-400 uppercase tracking-wider">ID</div>
        <div className="col-span-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Name</div>
        <div className="col-span-2 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Family</div>
        <div className="col-span-1 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Ver</div>
        <div className="col-span-2 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Status</div>
        <div className="col-span-2 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Actions</div>
      </div>

      {/* Rows */}
      <div className="divide-y divide-zinc-800/50">
        {items.map(item => {
          const statusCfg = STATUS_CONFIG[item.approval_status] || STATUS_CONFIG.pending;
          const isUpdating = updatingId === item.id;
          return (
            <div key={item.id} className="grid grid-cols-12 gap-2 px-4 py-3 hover:bg-zinc-800/30 transition items-center">
              <div className="col-span-2">
                <span className="text-xs font-mono text-purple-400">{item.taxonomy_id}</span>
              </div>
              <div className="col-span-3 min-w-0">
                <p className="text-xs font-medium text-zinc-200 truncate">{item.name}</p>
              </div>
              <div className="col-span-2">
                <span className="text-xs text-zinc-400 capitalize">{item.family}</span>
              </div>
              <div className="col-span-1">
                <span className="text-xs text-zinc-500">v{item.version || "1.0"}</span>
              </div>
              <div className="col-span-2">
                <span className={`text-xs px-2 py-0.5 rounded-full border flex items-center gap-1 w-fit ${statusCfg.color}`}>
                  {statusCfg.icon}
                  <span className="capitalize">{item.approval_status}</span>
                </span>
              </div>
              <div className="col-span-2 flex gap-1">
                {item.approval_status !== "approved" && (
                  <button onClick={() => onApprove?.(item.id)} disabled={isUpdating} className="text-xs bg-emerald-900/30 hover:bg-emerald-900/50 border border-emerald-800 text-emerald-400 px-2 py-1 rounded-lg transition disabled:opacity-50">
                    {isUpdating ? <Loader2 className="w-3 h-3 animate-spin" /> : "✓"}
                  </button>
                )}
                {item.approval_status !== "revision_required" && (
                  <button onClick={() => onRevise?.(item.id)} disabled={isUpdating} className="text-xs bg-amber-900/30 hover:bg-amber-900/50 border border-amber-800 text-amber-400 px-2 py-1 rounded-lg transition disabled:opacity-50">
                    ~
                  </button>
                )}
                {item.approval_status !== "rejected" && (
                  <button onClick={() => onReject?.(item.id)} disabled={isUpdating} className="text-xs bg-red-900/30 hover:bg-red-900/50 border border-red-800 text-red-400 px-2 py-1 rounded-lg transition disabled:opacity-50">
                    ✕
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
