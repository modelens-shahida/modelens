"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { qaApi } from "@/lib/qaApi";
import QADiagnosticCard from "@/components/dashboard/QADiagnosticCard";
import { 
  Award, 
  ShieldCheck, 
  ShieldAlert, 
  AlertTriangle, 
  CheckCircle2, 
  UserCheck, 
  Wrench, 
  Clock, 
  Search, 
  Filter, 
  Eye, 
  ArrowLeftRight, 
  Loader2, 
  SlidersHorizontal,
  Image as ImageIcon,
  Check,
  X
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";

const DECISION_TABS = [
  { value: "all", label: "All Items" },
  { value: "QA-HUMAN-REVIEW", label: "Needs Human Review", badge: "Urgent" },
  { value: "QA-AUTO-CORRECT", label: "Auto-Correct Queue" },
  { value: "QA-PASS-WARNING", label: "Passed with Warnings" },
  { value: "QA-FAIL", label: "Failed Hard Gates" },
  { value: "QA-PASS", label: "Auto-Approved" },
];

export default function AdminQAReviewQueuePage() {
  const [activeTab, setActiveTab] = useState("QA-HUMAN-REVIEW");
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [referenceAsset, setReferenceAsset] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [evalLoading, setEvalLoading] = useState(false);

  // Inspector Zoom / Split mode
  const [inspectorMode, setInspectorMode] = useState("split"); // "split" | "overlay"

  useEffect(() => {
    fetchReviewQueue();
  }, []);

  const fetchReviewQueue = async () => {
    setLoading(true);
    try {
      const res = await api.get("/api/v1/assets");
      const list = res?.assets || res?.items || res || [];
      setAssets(list);
      if (list.length > 0) {
        handleSelectAsset(list[0]);
      }
    } catch (err) {
      console.error("Failed to load assets:", err);
      // Fallback sample mock queue for staging inspection
      const mockList = [
        {
          id: 104,
          name: "EE-F-002_FULL_YAW-L30_NEUTRAL_v01_C01",
          domain: "GEN",
          asset_type: "CHAR-FULL-BODY",
          character_id: "EE-F-002",
          storage_uri: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=800",
          reference_uri: "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800",
          decision: "QA-HUMAN-REVIEW",
          overall_score: 91,
          created_at: new Date().toISOString(),
        },
        {
          id: 105,
          name: "GAR-SILK-SLIP-001_CATALOG_ONMODEL_C02",
          domain: "GEN",
          asset_type: "GAR-CATALOG-DELIVERABLE",
          character_id: "EE-F-002",
          storage_uri: "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800",
          reference_uri: "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=800",
          decision: "QA-AUTO-CORRECT",
          overall_score: 89,
          created_at: new Date().toISOString(),
        },
        {
          id: 106,
          name: "EE-F-002_FACE_YAW-R45_NEUTRAL_v01_C03",
          domain: "GEN",
          asset_type: "CHAR-CANONICAL-VIEW",
          character_id: "EE-F-002",
          storage_uri: "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=800",
          reference_uri: "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800",
          decision: "QA-PASS",
          overall_score: 97,
          created_at: new Date().toISOString(),
        },
      ];
      setAssets(mockList);
      if (mockList.length > 0) {
        handleSelectAsset(mockList[0]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAsset = async (asset) => {
    setSelectedAsset(asset);
    setEvalLoading(true);
    try {
      const data = await qaApi.getEvaluations(asset.id);
      setEvaluation(data?.latest || null);
    } catch {
      setEvaluation(null);
    } finally {
      setEvalLoading(false);
    }
  };

  const handleQuickDecision = async (decision, override = false) => {
    if (!selectedAsset) return;
    const evalId = evaluation?.id || evaluation?.evaluation_id;
    if (!evalId) {
      toast.error("No active evaluation record found to review");
      return;
    }

    try {
      await qaApi.reviewEvaluation(evalId, {
        decision,
        reviewer_notes: `Reviewed via Side-by-Side Inspector (${decision})`,
        override_hard_gate: override,
      });

      toast.success(`Asset marked as ${decision}`);
      handleSelectAsset(selectedAsset);
      fetchReviewQueue();
    } catch (err) {
      toast.error(err?.message || "Failed to update review status");
    }
  };

  const filteredAssets = assets.filter((a) => {
    const matchSearch =
      !search ||
      a.name?.toLowerCase().includes(search.toLowerCase()) ||
      String(a.id).includes(search) ||
      a.character_id?.toLowerCase().includes(search.toLowerCase());
    const matchTab = activeTab === "all" || (a.decision ? a.decision === activeTab : true);
    return matchSearch && matchTab;
  });

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Top Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400 shadow-lg shadow-amber-500/10">
              <Award className="w-7 h-7" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                Admin QA Review Queue & Inspector
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-800">
                  Section 21 System
                </span>
              </h1>
              <p className="text-zinc-400 text-xs mt-0.5">
                Side-by-side ground truth verification, dimensional gate analysis & human review override
              </p>
            </div>
          </div>
        </div>

        {/* Tab Filters */}
        <div className="flex gap-2 overflow-x-auto pb-2 border-b border-zinc-800">
          {DECISION_TABS.map((t) => (
            <button
              key={t.value}
              onClick={() => setActiveTab(t.value)}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition flex items-center gap-1.5 ${
                activeTab === t.value
                  ? "bg-amber-600 text-white shadow-lg shadow-amber-600/20"
                  : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
              }`}
            >
              {t.label}
              {t.badge && (
                <span className="px-1.5 py-0.2 rounded-full bg-red-950 text-red-300 border border-red-800 text-[10px] uppercase font-bold">
                  {t.badge}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Main Split Interface */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Review Queue List (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            {/* Search */}
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-zinc-500" />
              <input
                type="text"
                placeholder="Search queue by Asset ID, name, character..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500"
              />
            </div>

            {/* Queue List Cards */}
            <div className="space-y-2.5 max-h-[75vh] overflow-y-auto pr-1">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-16 text-zinc-500 space-y-2">
                  <Loader2 className="w-6 h-6 animate-spin text-amber-400" />
                  <p className="text-xs">Loading review queue...</p>
                </div>
              ) : filteredAssets.length === 0 ? (
                <div className="p-8 rounded-2xl border border-dashed border-zinc-800 text-center text-zinc-500 text-xs">
                  No assets in this review queue.
                </div>
              ) : (
                filteredAssets.map((asset) => {
                  const isSelected = selectedAsset?.id === asset.id;
                  return (
                    <div
                      key={asset.id}
                      onClick={() => handleSelectAsset(asset)}
                      className={`p-3.5 rounded-2xl border cursor-pointer transition space-y-2 ${
                        isSelected
                          ? "bg-amber-950/20 border-amber-500/80 shadow-lg shadow-amber-500/10"
                          : "bg-zinc-950/60 border-zinc-800 hover:border-zinc-700"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs text-amber-300 font-bold">
                          AST-GEN-{String(asset.id).padStart(6, "0")}
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                          {asset.character_id || "Product"}
                        </span>
                      </div>

                      <p className="text-xs font-semibold text-white truncate">{asset.name}</p>

                      <div className="flex items-center justify-between pt-1 border-t border-zinc-900 text-[11px] font-mono">
                        <span className="text-zinc-400">Score: <strong className="text-white">{asset.overall_score || 92}%</strong></span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-zinc-900 text-amber-400 border border-zinc-800">
                          {asset.decision || "NEEDS REVIEW"}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Column: Side-by-Side Reference Inspector (8 cols) */}
          <div className="lg:col-span-8 space-y-5">
            {selectedAsset ? (
              <>
                {/* Side-by-Side Visual Comparison Card */}
                <div className="p-5 rounded-3xl bg-zinc-950 border border-zinc-800 space-y-4 shadow-2xl">
                  <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                    <div className="flex items-center gap-2">
                      <ArrowLeftRight className="w-4 h-4 text-amber-400" />
                      <h3 className="text-sm font-semibold text-white">Side-by-Side Ground Truth Comparison</h3>
                    </div>

                    {/* Quick Review Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleQuickDecision("QA-PASS", true)}
                        className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition flex items-center gap-1 shadow-lg shadow-emerald-500/20"
                      >
                        <Check className="w-3.5 h-3.5" /> Approve Pass
                      </button>
                      <button
                        onClick={() => handleQuickDecision("QA-AUTO-CORRECT")}
                        className="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition flex items-center gap-1 shadow-lg shadow-purple-500/20"
                      >
                        <Wrench className="w-3.5 h-3.5" /> Touch-Up Route
                      </button>
                      <button
                        onClick={() => handleQuickDecision("QA-FAIL")}
                        className="px-3 py-1.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-semibold transition flex items-center gap-1"
                      >
                        <X className="w-3.5 h-3.5" /> Reject
                      </button>
                    </div>
                  </div>

                  {/* Visual Comparison Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Approved Reference */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                          Approved Canonical Reference
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-300">
                          GT-CANONICAL
                        </span>
                      </div>
                      <div className="relative aspect-[3/4] rounded-2xl overflow-hidden border-2 border-zinc-800 bg-zinc-900">
                        <img
                          src={selectedAsset.reference_uri || "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800"}
                          alt="Canonical Reference"
                          className="w-full h-full object-cover"
                        />
                        <div className="absolute bottom-2 left-2 right-2 p-2 rounded-xl bg-black/80 backdrop-blur-sm text-[11px] font-mono text-zinc-300 border border-zinc-700">
                          Eliska Novak L30 Canonical Reference (GT-01)
                        </div>
                      </div>
                    </div>

                    {/* Generated Candidate Output */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                          <Award className="w-3.5 h-3.5 text-amber-400" />
                          Generated Candidate Output
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950/60 border border-amber-800 text-amber-300">
                          CANDIDATE #{selectedAsset.id}
                        </span>
                      </div>
                      <div className="relative aspect-[3/4] rounded-2xl overflow-hidden border-2 border-amber-500/60 bg-zinc-900 shadow-xl">
                        <img
                          src={selectedAsset.storage_uri || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=800"}
                          alt="Candidate Output"
                          className="w-full h-full object-cover"
                        />
                        <div className="absolute bottom-2 left-2 right-2 p-2 rounded-xl bg-black/80 backdrop-blur-sm text-[11px] font-mono text-zinc-300 border border-zinc-700 flex items-center justify-between">
                          <span className="truncate">{selectedAsset.name}</span>
                          <span className="text-amber-300 font-bold">{selectedAsset.overall_score || 91}% QA</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Multi-Dimensional QA Diagnostic Report */}
                <QADiagnosticCard
                  assetId={selectedAsset.id}
                  qaProfileId="QA-PROFILE-CATALOG-001"
                />
              </>
            ) : (
              <div className="p-16 rounded-3xl bg-zinc-950 border border-dashed border-zinc-800 text-center space-y-3">
                <Award className="w-12 h-12 text-zinc-700 mx-auto" />
                <h4 className="text-sm font-semibold text-zinc-300">Select an asset from the queue</h4>
                <p className="text-xs text-zinc-500">
                  Inspect side-by-side ground truth comparison, view dimensional scores, and submit human review decisions.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
