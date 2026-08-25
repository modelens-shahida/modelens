"use client";

import React, { useState, useEffect } from "react";
import { assetRegistryApi } from "@/lib/assetRegistryApi";
import { Layers, Plus, ShieldCheck, Check, Sparkles, User, Image as ImageIcon, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

export default function CharacterReferenceSetManager({ characterId = null, className = "" }) {
  const [sets, setSets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form State
  const [setName, setSetName] = useState("");
  const [setDescription, setSetDescription] = useState("");
  const [primaryAssetId, setPrimaryAssetId] = useState("");
  const [detailAssetId, setDetailAssetId] = useState("");
  const [skinAssetId, setSkinAssetId] = useState("");

  useEffect(() => {
    fetchReferenceSets();
  }, [characterId]);

  const fetchReferenceSets = async () => {
    setLoading(true);
    try {
      const data = await assetRegistryApi.listReferenceSets(characterId);
      setSets(data?.reference_sets || []);
    } catch (err) {
      console.error("Failed to load reference sets:", err);
      setSets([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!setName.trim()) return;

    setSubmitting(true);
    try {
      const items = [];
      if (primaryAssetId) items.push({ asset_id: parseInt(primaryAssetId), role: "PRIMARY", priority: 1 });
      if (detailAssetId) items.push({ asset_id: parseInt(detailAssetId), role: "DETAIL", priority: 2 });
      if (skinAssetId) items.push({ asset_id: parseInt(skinAssetId), role: "SKIN", priority: 3 });

      await assetRegistryApi.createReferenceSet({
        name: setName.trim(),
        character_id: characterId ? parseInt(characterId) : null,
        description: setDescription.trim() || undefined,
        items,
      });

      toast.success("Reference set created successfully");
      setShowCreateModal(false);
      setSetName("");
      setSetDescription("");
      setPrimaryAssetId("");
      setDetailAssetId("");
      setSkinAssetId("");
      fetchReferenceSets();
    } catch (err) {
      console.error("Failed to create reference set:", err);
      toast.error(err?.message || "Failed to create reference set");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={`p-5 rounded-2xl bg-zinc-950 border border-zinc-800 text-zinc-100 shadow-xl ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-pink-500/10 border border-pink-500/20 text-pink-400">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">Character Reference Sets (`REFSET-*`)</h4>
            <p className="text-xs text-zinc-400">Standardized reference pairings for viewpoint-aware conditioning</p>
          </div>
        </div>

        <button
          onClick={() => setShowCreateModal(!showCreateModal)}
          className="px-3 py-1.5 rounded-lg bg-pink-600 hover:bg-pink-500 text-white text-xs font-medium transition flex items-center gap-1 shadow-lg shadow-pink-500/20"
        >
          <Plus className="w-3.5 h-3.5" />
          Create Reference Set
        </button>
      </div>

      {/* Create Modal Form */}
      {showCreateModal && (
        <form onSubmit={handleCreate} className="p-4 mb-4 rounded-xl bg-zinc-900 border border-pink-500/30 space-y-3 text-xs">
          <h5 className="font-semibold text-pink-300 uppercase tracking-wider text-[11px]">
            New Reference Set Specification
          </h5>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Set Name *</label>
              <input
                type="text"
                value={setName}
                onChange={(e) => setSetName(e.target.value)}
                placeholder="REFSET-ELISKA-L30-001"
                required
                className="w-full px-2.5 py-1.5 rounded bg-zinc-950 border border-zinc-800 text-white text-xs focus:border-pink-500 outline-none font-mono"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Description (Optional)</label>
              <input
                type="text"
                value={setDescription}
                onChange={(e) => setSetDescription(e.target.value)}
                placeholder="L30 Canonical + Close crop pair"
                className="w-full px-2.5 py-1.5 rounded bg-zinc-950 border border-zinc-800 text-white text-xs focus:border-pink-500 outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Primary Asset ID *</label>
              <input
                type="number"
                value={primaryAssetId}
                onChange={(e) => setPrimaryAssetId(e.target.value)}
                placeholder="e.g. 101"
                required
                className="w-full px-2.5 py-1.5 rounded bg-zinc-950 border border-zinc-800 text-white text-xs font-mono focus:border-pink-500 outline-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Detail / Close Crop ID</label>
              <input
                type="number"
                value={detailAssetId}
                onChange={(e) => setDetailAssetId(e.target.value)}
                placeholder="e.g. 102"
                className="w-full px-2.5 py-1.5 rounded bg-zinc-950 border border-zinc-800 text-white text-xs font-mono focus:border-pink-500 outline-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Skin Reference ID</label>
              <input
                type="number"
                value={skinAssetId}
                onChange={(e) => setSkinAssetId(e.target.value)}
                placeholder="e.g. 103"
                className="w-full px-2.5 py-1.5 rounded bg-zinc-950 border border-zinc-800 text-white text-xs font-mono focus:border-pink-500 outline-none"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setShowCreateModal(false)}
              className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 rounded bg-pink-600 hover:bg-pink-500 text-white text-xs font-medium flex items-center gap-1.5"
            >
              {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Save Set
            </button>
          </div>
        </form>
      )}

      {/* Sets List */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-8 text-zinc-500 space-y-2">
          <Loader2 className="w-5 h-5 animate-spin text-pink-400" />
          <p className="text-xs">Loading reference sets...</p>
        </div>
      ) : sets.length === 0 ? (
        <div className="p-6 rounded-xl border border-dashed border-zinc-800 text-center text-zinc-500 text-xs italic">
          No reference sets configured for this character yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {sets.map((s) => (
            <div key={s.id} className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-white">{s.name}</span>
                <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono text-[10px] uppercase">
                  {s.items?.length || 0} Assets
                </span>
              </div>
              {s.description && <p className="text-xs text-zinc-400">{s.description}</p>}

              {/* Items in set */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {s.items?.map((item, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded bg-zinc-950 border border-zinc-800 font-mono text-[10px] text-zinc-300 flex items-center gap-1"
                  >
                    <span className="text-pink-400 font-bold">{item.role}:</span> Asset #{item.asset_id}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
