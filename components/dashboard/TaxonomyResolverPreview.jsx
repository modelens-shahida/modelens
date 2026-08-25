"use client";

import React, { useState, useEffect } from "react";
import { taxonomyResolverApi } from "@/lib/taxonomyResolverApi";
import { Sparkles, AlertTriangle, ShieldAlert, CheckCircle2, Sliders, Coins, RefreshCw, Cpu, Layers } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function TaxonomyResolverPreview({
  taxonomyIds = {},
  workflowId = "WF-CATALOG-001",
  generationMode = "studio_quality",
  productType = "",
  modelAgeGroup = "adult",
  className = "",
}) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("params"); // "params" | "mappings" | "compatibility"

  useEffect(() => {
    if (!taxonomyIds || Object.keys(taxonomyIds).length === 0) {
      setResult(null);
      return;
    }

    const timer = setTimeout(() => {
      runDryRunResolve();
    }, 300);

    return () => clearTimeout(timer);
  }, [taxonomyIds, workflowId, generationMode, productType, modelAgeGroup]);

  const runDryRunResolve = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await taxonomyResolverApi.resolve({
        taxonomy_ids: taxonomyIds,
        workflow_id: workflowId,
        generation_mode: generationMode,
        dry_run: true,
        product_type: productType,
        model_age_group: modelAgeGroup,
      });
      setResult(data);
    } catch (err) {
      console.error("Resolver preview error:", err);
      setError(err?.message || "Failed to resolve taxonomy parameters");
    } finally {
      setLoading(false);
    }
  };

  const hasBlocking = result?.blocking_reasons && result.blocking_reasons.length > 0;
  const hasWarnings = result?.warnings && result.warnings.length > 0;
  const isCompatible = result?.compatibility?.is_compatible !== false && !hasBlocking;

  return (
    <div className={`rounded-xl border border-zinc-800 bg-zinc-950/80 backdrop-blur-md p-4 text-zinc-100 shadow-2xl ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white flex items-center gap-2">
              Taxonomy Resolver Preview
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                DRY RUN
              </span>
            </h4>
            <p className="text-xs text-zinc-400">Real-time parameters, node mapping & credit calculation</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Estimated Credits */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-semibold">
            <Coins className="w-3.5 h-3.5" />
            <span>{result?.credits_estimated ?? (generationMode === "studio_quality" ? 5 : 2)} Credits</span>
          </div>

          <button
            onClick={runDryRunResolve}
            disabled={loading}
            className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-white transition"
            title="Refresh Resolver Simulation"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-400" : ""}`} />
          </button>
        </div>
      </div>

      {/* Compatibility Badge Status */}
      <div className="mb-3">
        {hasBlocking ? (
          <div className="flex items-start gap-2 p-2.5 rounded-lg bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
            <ShieldAlert className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Generation Blocked by Compatibility Rule</p>
              <ul className="list-disc list-inside text-red-200/80 mt-1 space-y-0.5">
                {result.blocking_reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : hasWarnings ? (
          <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-950/30 border border-amber-800/50 text-amber-300 text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Compatibility Nuances Detected</p>
              <ul className="list-disc list-inside text-amber-200/80 mt-1 space-y-0.5">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : isCompatible && result ? (
          <div className="flex items-center gap-2 p-2 rounded-lg bg-emerald-950/30 border border-emerald-800/40 text-emerald-300 text-xs">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>All taxonomy selections are fully compatible & production-ready.</span>
          </div>
        ) : null}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-zinc-800/60 mb-3">
        <button
          onClick={() => setActiveTab("params")}
          className={`px-3 py-1.5 text-xs font-medium rounded-t-lg transition flex items-center gap-1.5 ${
            activeTab === "params"
              ? "bg-zinc-800 text-white border-t border-x border-zinc-700"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          Resolved Params ({Object.keys(result?.workflow_params || {}).length})
        </button>
        <button
          onClick={() => setActiveTab("mappings")}
          className={`px-3 py-1.5 text-xs font-medium rounded-t-lg transition flex items-center gap-1.5 ${
            activeTab === "mappings"
              ? "bg-zinc-800 text-white border-t border-x border-zinc-700"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Cpu className="w-3.5 h-3.5" />
          ComfyUI Node Map ({Object.keys(result?.resolved?.node_mappings || {}).length})
        </button>
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        {activeTab === "params" && (
          <motion.div
            key="params"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-2 max-h-48 overflow-y-auto pr-1 text-xs"
          >
            {result?.resolved && Object.keys(result.resolved).length > 0 ? (
              Object.entries(result.resolved).map(([type, item]) => (
                <div key={type} className="flex items-start justify-between p-2 rounded-lg bg-zinc-900/60 border border-zinc-800">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">
                      {type}
                    </span>
                    <span className="font-medium text-white">{item.display_name || item.name}</span>
                    <span className="text-[11px] font-mono text-zinc-400 ml-2">({item.taxonomy_id})</span>
                  </div>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border uppercase font-mono ${
                    item.approval_status === "approved"
                      ? "bg-emerald-950/40 text-emerald-300 border-emerald-800"
                      : "bg-amber-950/40 text-amber-300 border-amber-800"
                  }`}>
                    {item.approval_status || "approved"}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-zinc-500 text-center py-4 text-xs italic">
                Select taxonomy elements to simulate execution resolution.
              </p>
            )}
          </motion.div>
        )}

        {activeTab === "mappings" && (
          <motion.div
            key="mappings"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-1.5 max-h-48 overflow-y-auto pr-1 text-xs"
          >
            {result?.resolved?.node_mappings && Object.keys(result.resolved.node_mappings).length > 0 ? (
              Object.entries(result.resolved.node_mappings).map(([nodeId, map]) => (
                <div key={nodeId} className="flex items-center justify-between p-2 rounded bg-zinc-900/80 font-mono text-[11px] border border-zinc-800">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                      Node {nodeId}
                    </span>
                    <span className="text-zinc-300">{map.field_name}</span>
                  </div>
                  <span className="text-zinc-400">{map.taxonomy_id}</span>
                </div>
              ))
            ) : (
              <div className="p-3 rounded-lg bg-zinc-900/40 text-center text-zinc-500 text-xs italic">
                No active ComfyUI node overrides required for this configuration.
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
