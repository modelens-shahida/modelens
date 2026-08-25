"use client";

import React, { useState, useEffect } from "react";
import { assetRegistryApi } from "@/lib/assetRegistryApi";
import { GitFork, ArrowRight, Layers, FileImage, ShieldCheck, Loader2, Plus, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import toast from "react-hot-toast";

const RELATIONSHIP_CONFIG = {
  "REL-DERIVED-FROM": { label: "Derived From", color: "bg-blue-950/60 text-blue-300 border-blue-800" },
  "REL-CROPPED-FROM": { label: "Cropped From", color: "bg-amber-950/60 text-amber-300 border-amber-800" },
  "REL-TOUCHUP-OF": { label: "Touch-Up Of", color: "bg-purple-950/60 text-purple-300 border-purple-800" },
  "REL-GENERATED-FROM": { label: "Generated From", color: "bg-emerald-950/60 text-emerald-300 border-emerald-800" },
  "REL-TRAINED-FROM": { label: "Trained From", color: "bg-pink-950/60 text-pink-300 border-pink-800" },
};

export default function AssetLineageGraph({ assetId, className = "" }) {
  const [data, setData] = useState({ parents: [], children: [] });
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [targetAssetId, setTargetAssetId] = useState("");
  const [relType, setRelType] = useState("REL-DERIVED-FROM");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (assetId) {
      fetchLineage();
    }
  }, [assetId]);

  const fetchLineage = async () => {
    setLoading(true);
    try {
      const res = await assetRegistryApi.getRelationships(assetId, "both");
      setData(res || { parents: [], children: [] });
    } catch (err) {
      console.error("Failed to load lineage:", err);
      setData({ parents: [], children: [] });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRelationship = async (e) => {
    e.preventDefault();
    if (!targetAssetId) return;

    setSubmitting(true);
    try {
      await assetRegistryApi.createRelationship({
        source_asset_id: parseInt(assetId),
        target_asset_id: parseInt(targetAssetId),
        relationship_type: relType,
      });

      toast.success("Relationship linked successfully");
      setShowAddModal(false);
      setTargetAssetId("");
      fetchLineage();
    } catch (err) {
      console.error("Failed to link relationship:", err);
      toast.error(err?.message || "Failed to link relationship");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-zinc-500 space-y-2">
        <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
        <p className="text-xs">Loading lineage graph...</p>
      </div>
    );
  }

  const parents = data?.parents || [];
  const children = data?.children || [];

  return (
    <div className={`p-5 rounded-2xl bg-zinc-950 border border-zinc-800 text-zinc-100 shadow-xl ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <GitFork className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">Asset Lineage & Derivation Tree</h4>
            <p className="text-xs text-zinc-400">Trace parent origins and downstream generated descendants</p>
          </div>
        </div>

        <button
          onClick={() => setShowAddModal(!showAddModal)}
          className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition flex items-center gap-1"
        >
          <Plus className="w-3.5 h-3.5" />
          Link Relationship
        </button>
      </div>

      {/* Add Modal */}
      {showAddModal && (
        <form onSubmit={handleCreateRelationship} className="p-3 mb-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-2 text-xs">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Target Asset ID</label>
              <input
                type="number"
                value={targetAssetId}
                onChange={(e) => setTargetAssetId(e.target.value)}
                placeholder="e.g. 104"
                required
                className="w-full px-2.5 py-1.5 rounded bg-zinc-950 border border-zinc-800 text-white font-mono text-xs focus:border-indigo-500 outline-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Relationship Type</label>
              <select
                value={relType}
                onChange={(e) => setRelType(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded bg-zinc-950 border border-zinc-800 text-white text-xs focus:border-indigo-500 outline-none"
              >
                <option value="REL-DERIVED-FROM">REL-DERIVED-FROM</option>
                <option value="REL-CROPPED-FROM">REL-CROPPED-FROM</option>
                <option value="REL-TOUCHUP-OF">REL-TOUCHUP-OF</option>
                <option value="REL-GENERATED-FROM">REL-GENERATED-FROM</option>
                <option value="REL-TRAINED-FROM">REL-TRAINED-FROM</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setShowAddModal(false)}
              className="px-2.5 py-1 rounded bg-zinc-800 text-zinc-300 text-[11px]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-3 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium"
            >
              {submitting ? "Linking..." : "Save Link"}
            </button>
          </div>
        </form>
      )}

      {/* Visual Tree Graph */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
        {/* Parent Nodes */}
        <div className="space-y-2">
          <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 block mb-1">
            Parent Sources ({parents.length})
          </span>
          {parents.length === 0 ? (
            <div className="p-3 rounded-xl border border-dashed border-zinc-800 text-center text-zinc-500 text-xs italic">
              Foundational Root (No Parents)
            </div>
          ) : (
            parents.map((p, idx) => {
              const rel = RELATIONSHIP_CONFIG[p.relationship_type] || {
                label: p.relationship_type,
                color: "bg-zinc-800 text-zinc-300 border-zinc-700",
              };
              return (
                <div key={idx} className="p-3 rounded-xl bg-zinc-900/80 border border-zinc-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-white">Asset #{p.source_asset_id}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded border uppercase font-mono ${rel.color}`}>
                      {rel.label}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Current Central Node */}
        <div className="p-4 rounded-2xl bg-indigo-950/40 border-2 border-indigo-500/60 shadow-lg shadow-indigo-500/10 text-center space-y-1">
          <div className="inline-flex p-2 rounded-xl bg-indigo-500/20 text-indigo-300 mb-1">
            <FileImage className="w-5 h-5" />
          </div>
          <h5 className="text-sm font-bold text-white font-mono">Current Asset #{assetId}</h5>
          <span className="inline-block px-2.5 py-0.5 rounded-full bg-indigo-900/60 border border-indigo-700 text-indigo-200 text-[10px] uppercase font-bold tracking-wider">
            Inspecting Node
          </span>
        </div>

        {/* Children Nodes */}
        <div className="space-y-2">
          <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 block mb-1">
            Generated Derivatives ({children.length})
          </span>
          {children.length === 0 ? (
            <div className="p-3 rounded-xl border border-dashed border-zinc-800 text-center text-zinc-500 text-xs italic">
              No Downstream Derivatives
            </div>
          ) : (
            children.map((c, idx) => {
              const rel = RELATIONSHIP_CONFIG[c.relationship_type] || {
                label: c.relationship_type,
                color: "bg-zinc-800 text-zinc-300 border-zinc-700",
              };
              return (
                <div key={idx} className="p-3 rounded-xl bg-zinc-900/80 border border-zinc-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-white">Asset #{c.target_asset_id}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded border uppercase font-mono ${rel.color}`}>
                      {rel.label}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
