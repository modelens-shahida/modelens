"use client";

import React, { useState } from "react";
import { 
  CheckCircle2, RotateCcw, Edit, AlertOctagon, Download, ShieldCheck, 
  ChevronDown, ChevronUp, Image as ImageIcon, Sparkles, Layers, Sliders,
  FolderPlus, FileArchive, ShoppingCart, Check, X, Loader2, Info
} from "lucide-react";
import { MOCK_ELISKA_CHARACTER } from "@/lib/characterSchema";
import { 
  overrideQaEvaluation, 
  regenerateAsset, 
  createLookbookCollection, 
  exportAssetsZip, 
  exportShopifyPreset 
} from "@/lib/generationService";
import { toast } from "react-hot-toast";

export default function ReviewComparisonWorkspace({
  resultAsset = {
    id: "AST-2027-001",
    angle: "L30",
    framing: "Full-Body",
    character: MOCK_ELISKA_CHARACTER,
    productName: "Silk Bias Cut Slip Dress",
    originalUrl: "/api/placeholder/450/600",
    resultUrl: "/api/placeholder/450/600",
    qaScore: {
      identity: "98.2% PASS",
      garment: "98.1% PASS",
      hands: "99.0% PASS",
      feet: "97.4% PASS",
      artifacts: "CLEAN",
    },
    overall_qa_status: "APPROVED",
  },
}) {
  const [showQaDetails, setShowQaDetails] = useState(true);
  const [approvalState, setApprovalState] = useState(resultAsset.overall_qa_status || "APPROVED");
  
  // Modals state
  const [activeModal, setActiveModal] = useState(null); // "qa_override" | "regenerate" | "lookbook" | "export_zip" | "export_shopify"
  const [loadingAction, setLoadingAction] = useState(false);

  // QA Override form
  const [overrideStatus, setOverrideStatus] = useState("APPROVED");
  const [reviewerNote, setReviewerNote] = useState("");

  // Regenerate form
  const [faceIdentityWeight, setFaceIdentityWeight] = useState(0.85);
  const [fixType, setFixType] = useState("face_detail_enhancement");
  const [regenQuality, setRegenQuality] = useState("studio_quality");

  // Lookbook form
  const [collectionName, setCollectionName] = useState("Spring 2027 Lookbook");
  const [projectName, setProjectName] = useState("Spring 2027 Runway Campaign");

  // Export State
  const [exportManifest, setExportManifest] = useState(null);
  const [shopifySpec, setShopifySpec] = useState(null);

  // Handle QA Override
  const handleQaOverrideSubmit = async () => {
    try {
      setLoadingAction(true);
      const res = await overrideQaEvaluation(resultAsset.id, {
        override_status: overrideStatus,
        reviewer_note: reviewerNote,
      });
      setApprovalState(overrideStatus);
      toast.success(`QA status overridden to: ${overrideStatus}`);
      setActiveModal(null);
    } catch (err) {
      toast.error(err.message || "Failed to override QA");
    } finally {
      setLoadingAction(false);
    }
  };

  // Handle Parameterized Regeneration
  const handleRegenerateSubmit = async () => {
    try {
      setLoadingAction(true);
      const res = await regenerateAsset({
        asset_id: resultAsset.id,
        angle_code: resultAsset.angle,
        face_identity_weight: parseFloat(faceIdentityWeight),
        fix_type: fixType,
        quality_mode: regenQuality,
      });
      toast.success(`Regeneration job queued: ${res.job_id} (Face Weight: ${faceIdentityWeight})`);
      setActiveModal(null);
    } catch (err) {
      toast.error(err.message || "Failed to trigger regeneration");
    } finally {
      setLoadingAction(false);
    }
  };

  // Handle Create Lookbook Collection
  const handleCreateLookbook = async () => {
    try {
      setLoadingAction(true);
      const res = await createLookbookCollection({
        collection_name: collectionName,
        project_name: projectName,
        character_id: resultAsset.character?.code || "EE-F-002",
        asset_ids: [resultAsset.id],
      });
      toast.success(`Lookbook Collection "${res.collection_name}" created!`);
      setActiveModal(null);
    } catch (err) {
      toast.error(err.message || "Failed to create collection");
    } finally {
      setLoadingAction(false);
    }
  };

  // Handle Export ZIP
  const handleExportZip = async () => {
    try {
      setLoadingAction(true);
      const res = await exportAssetsZip({
        asset_ids: [resultAsset.id],
        include_c2pa: true,
        preset: "master_archive",
      });
      setExportManifest(res);
      toast.success("ZIP archive with C2PA manifest generated!");
    } catch (err) {
      toast.error(err.message || "Export ZIP failed");
    } finally {
      setLoadingAction(false);
    }
  };

  // Handle Export Shopify
  const handleExportShopify = async () => {
    try {
      setLoadingAction(true);
      const res = await exportShopifyPreset(resultAsset.id);
      setShopifySpec(res);
      toast.success("Shopify 2048x2048 export preset ready!");
    } catch (err) {
      toast.error(err.message || "Shopify export failed");
    } finally {
      setLoadingAction(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header & Meta Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">Editorial Asset Review & QA Workspace</h1>
            <span
              className={`px-3 py-0.5 text-xs font-mono font-bold rounded-full border ${
                approvalState === "APPROVED" || approvalState === "PASS"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : approvalState === "HOLD"
                  ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                  : "bg-rose-500/10 text-rose-400 border-rose-500/30"
              }`}
            >
              {approvalState}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1 font-mono">
            Asset ID: {resultAsset.id} • Angle: {resultAsset.angle} ({resultAsset.framing}) • Model: {resultAsset.character?.display_name || "ELISKA"}
          </p>
        </div>

        {/* Action Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* QA Override Action */}
          <button
            onClick={() => setActiveModal("qa_override")}
            className="flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs px-4 py-2 rounded-xl transition-all shadow-md shadow-emerald-500/20"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>QA OVERRIDE</span>
          </button>

          {/* Regenerate Action */}
          <button 
            onClick={() => setActiveModal("regenerate")}
            className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 hover:text-cyan-400 px-3.5 py-2 rounded-xl transition-all"
          >
            <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />
            <span>REGENERATE</span>
          </button>

          {/* Save to Lookbook */}
          <button 
            onClick={() => setActiveModal("lookbook")}
            className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 hover:text-purple-400 px-3.5 py-2 rounded-xl transition-all"
          >
            <FolderPlus className="w-3.5 h-3.5 text-purple-400" />
            <span>LOOKBOOK</span>
          </button>

          {/* Export Dropdown Trigger */}
          <button 
            onClick={() => setActiveModal("export_menu")}
            className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 hover:text-white px-3.5 py-2 rounded-xl transition-all"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" />
            <span>EXPORT & DELIVERY</span>
          </button>
        </div>
      </div>

      {/* Split-Screen Review Workspace (Original vs Generated Result) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Original Product Panel */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 backdrop-blur-md shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
              Original Garment Input
            </span>
            <span className="text-[11px] text-zinc-500">{resultAsset.productName}</span>
          </div>

          <div className="aspect-[3/4] bg-zinc-950 rounded-xl border border-zinc-800/80 flex items-center justify-center relative overflow-hidden group">
            <div className="text-center space-y-2 text-zinc-600">
              <ImageIcon className="w-12 h-12 mx-auto stroke-[1]" />
              <span className="text-xs font-mono text-zinc-500 block">ORIGINAL FLAT LAY INPUT</span>
            </div>
          </div>
        </div>

        {/* Generated Result Panel */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 backdrop-blur-md shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <span className="text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              <span>AI Generated Editorial Result</span>
            </span>
            <span className="text-[11px] text-zinc-400">Model: {resultAsset.character?.display_name || "ELISKA"}</span>
          </div>

          <div className="aspect-[3/4] bg-zinc-950 rounded-xl border border-cyan-500/30 flex items-center justify-center relative overflow-hidden group shadow-inner">
            <div className="text-center space-y-2 text-cyan-400/80">
              <ImageIcon className="w-12 h-12 mx-auto stroke-[1.5]" />
              <span className="text-xs font-mono block text-cyan-400">GENERATED RESULT ({resultAsset.angle})</span>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30">
                QA STATUS: {approvalState}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Technical QA Details Breakdown */}
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl overflow-hidden backdrop-blur-md">
        <button
          onClick={() => setShowQaDetails(!showQaDetails)}
          className="w-full px-6 py-4 text-xs font-bold text-white flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
            <span>Automated QA & High-Precision Quality Metrics</span>
          </div>
          <div className="flex items-center gap-2 text-zinc-400">
            <span>{showQaDetails ? "Collapse Details" : "Expand Details"}</span>
            {showQaDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {showQaDetails && (
          <div className="p-6 border-t border-zinc-800 grid grid-cols-2 md:grid-cols-5 gap-4 text-xs">
            <div className="bg-zinc-950 border border-zinc-800/80 p-3.5 rounded-xl">
              <span className="text-zinc-500 block text-[10px] uppercase">Identity Similarity</span>
              <p className="font-bold text-emerald-400 mt-1">{resultAsset.qaScore.identity}</p>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 p-3.5 rounded-xl">
              <span className="text-zinc-500 block text-[10px] uppercase">Garment Fidelity</span>
              <p className="font-bold text-emerald-400 mt-1">{resultAsset.qaScore.garment}</p>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 p-3.5 rounded-xl">
              <span className="text-zinc-500 block text-[10px] uppercase">Hands Anatomy</span>
              <p className="font-bold text-emerald-400 mt-1">{resultAsset.qaScore.hands}</p>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 p-3.5 rounded-xl">
              <span className="text-zinc-500 block text-[10px] uppercase">Feet Grounding</span>
              <p className="font-bold text-emerald-400 mt-1">{resultAsset.qaScore.feet}</p>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 p-3.5 rounded-xl">
              <span className="text-zinc-500 block text-[10px] uppercase">Artifact Audit</span>
              <p className="font-bold text-cyan-400 mt-1">{resultAsset.qaScore.artifacts}</p>
            </div>
          </div>
        )}
      </div>

      {/* ================= MODAL: QA OVERRIDE ================= */}
      {activeModal === "qa_override" && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 w-full max-w-md rounded-2xl p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <span>QA Gate Override</span>
              </h3>
              <button onClick={() => setActiveModal(null)} className="text-zinc-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="block text-zinc-400 font-semibold mb-1.5 uppercase tracking-wider text-[10px]">
                  Override Status
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {["APPROVED", "PASS", "HOLD", "FAIL", "REJECTED"].map((st) => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => setOverrideStatus(st)}
                      className={`py-2 px-3 rounded-xl font-mono font-bold text-xs border transition-all ${
                        overrideStatus === st
                          ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                          : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:border-zinc-700"
                      }`}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-zinc-400 font-semibold mb-1.5 uppercase tracking-wider text-[10px]">
                  Reviewer Note / Decision Rationale
                </label>
                <textarea
                  value={reviewerNote}
                  onChange={(e) => setReviewerNote(e.target.value)}
                  placeholder="e.g., Fabric texture matches swatch; identity similarity within acceptable tolerance for editorial billboard."
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-cyan-500 resize-none h-24"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-zinc-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleQaOverrideSubmit}
                disabled={loadingAction}
                className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-60 text-black font-bold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-emerald-500/20"
              >
                {loadingAction ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                <span>Save Override</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL: PARAMETERIZED REGENERATION ================= */}
      {activeModal === "regenerate" && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 w-full max-w-lg rounded-2xl p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <RotateCcw className="w-5 h-5 text-cyan-400" />
                <span>Regenerate with Adjusted Parameters</span>
              </h3>
              <button onClick={() => setActiveModal(null)} className="text-zinc-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="text-zinc-400 font-semibold uppercase tracking-wider text-[10px]">
                    Face Identity Weight (ArcFace Guidance)
                  </label>
                  <span className="font-mono text-cyan-400 font-bold">{faceIdentityWeight}</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.05"
                  value={faceIdentityWeight}
                  onChange={(e) => setFaceIdentityWeight(e.target.value)}
                  className="w-full accent-cyan-400"
                />
                <div className="flex justify-between text-[10px] text-zinc-500 font-mono mt-1">
                  <span>0.5 (Creative Drift)</span>
                  <span>0.85 (Recommended)</span>
                  <span>1.0 (Strict Lock)</span>
                </div>
              </div>

              <div>
                <label className="block text-zinc-400 font-semibold mb-1.5 uppercase tracking-wider text-[10px]">
                  Target Fix / Refinement Type
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: "face_detail_enhancement", label: "Face Detail Refinement" },
                    { id: "fabric_texture_preserve", label: "Fabric Drape & Texture" },
                    { id: "lighting_balance", label: "Shadow & Key Light" },
                    { id: "hand_anatomy_refine", label: "Hand Anatomy Clean" },
                  ].map((fix) => (
                    <button
                      key={fix.id}
                      type="button"
                      onClick={() => setFixType(fix.id)}
                      className={`p-2.5 rounded-xl text-left border transition-all ${
                        fixType === fix.id
                          ? "bg-cyan-500/10 text-cyan-300 border-cyan-500/40"
                          : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:border-zinc-700"
                      }`}
                    >
                      <span className="font-bold block">{fix.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-zinc-400 font-semibold mb-1.5 uppercase tracking-wider text-[10px]">
                  Quality Preset
                </label>
                <div className="flex items-center gap-2">
                  {["studio_quality", "master_4k"].map((qm) => (
                    <button
                      key={qm}
                      type="button"
                      onClick={() => setRegenQuality(qm)}
                      className={`flex-1 py-2 rounded-xl font-bold border transition-all ${
                        regenQuality === qm
                          ? "bg-zinc-800 text-white border-zinc-700"
                          : "bg-zinc-950 text-zinc-500 border-zinc-800"
                      }`}
                    >
                      {qm === "master_4k" ? "Master 4K Ultra" : "Studio Quality"}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-zinc-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleRegenerateSubmit}
                disabled={loadingAction}
                className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-60 text-black font-bold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-cyan-500/20"
              >
                {loadingAction ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                <span>Trigger Adjusted Regeneration</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL: LOOKBOOK CREATION ================= */}
      {activeModal === "lookbook" && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 w-full max-w-md rounded-2xl p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <FolderPlus className="w-5 h-5 text-purple-400" />
                <span>Save to Lookbook Collection</span>
              </h3>
              <button onClick={() => setActiveModal(null)} className="text-zinc-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="block text-zinc-400 font-semibold mb-1.5 uppercase tracking-wider text-[10px]">
                  Collection Name
                </label>
                <input
                  type="text"
                  value={collectionName}
                  onChange={(e) => setCollectionName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-zinc-400 font-semibold mb-1.5 uppercase tracking-wider text-[10px]">
                  Parent Project / Campaign
                </label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800/80 text-[11px] text-zinc-400">
                <span>Adding Asset: </span>
                <strong className="text-purple-300 font-mono">{resultAsset.id} ({resultAsset.angle})</strong>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-zinc-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateLookbook}
                disabled={loadingAction}
                className="flex items-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-60 text-white font-bold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-purple-600/20"
              >
                {loadingAction ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderPlus className="w-4 h-4" />}
                <span>Create Lookbook</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL: EXPORT & DELIVERY MENU ================= */}
      {activeModal === "export_menu" && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 w-full max-w-lg rounded-2xl p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Download className="w-5 h-5 text-cyan-400" />
                <span>Export & Multi-Format Delivery</span>
              </h3>
              <button onClick={() => setActiveModal(null)} className="text-zinc-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Option 1: ZIP + C2PA Manifest */}
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 flex flex-col justify-between space-y-4">
                <div>
                  <div className="flex items-center gap-2 text-cyan-400 font-bold text-xs">
                    <FileArchive className="w-4 h-4" />
                    <span>Master ZIP + C2PA</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 mt-1">
                    Production archive with cryptographic C2PA Content Credentials provenance manifest.
                  </p>
                </div>

                <button
                  onClick={handleExportZip}
                  disabled={loadingAction}
                  className="w-full bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 text-xs font-bold py-2.5 rounded-xl transition-all flex items-center justify-center gap-2"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Generate ZIP</span>
                </button>
              </div>

              {/* Option 2: Shopify E-commerce Preset */}
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 flex flex-col justify-between space-y-4">
                <div>
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs">
                    <ShoppingCart className="w-4 h-4" />
                    <span>Shopify E-Commerce Preset</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 mt-1">
                    2048x2048px square crop, optimized JPEG (92% quality), calibrated sRGB color profile.
                  </p>
                </div>

                <button
                  onClick={handleExportShopify}
                  disabled={loadingAction}
                  className="w-full bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-xs font-bold py-2.5 rounded-xl transition-all flex items-center justify-center gap-2"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export Shopify Preset</span>
                </button>
              </div>
            </div>

            {/* Export Manifest Preview */}
            {(exportManifest || shopifySpec) && (
              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-2 text-xs">
                <div className="flex items-center gap-1.5 text-cyan-400 font-bold">
                  <Info className="w-4 h-4" />
                  <span>Delivery Ready</span>
                </div>
                {exportManifest && (
                  <p className="text-zinc-300 text-[11px] font-mono">
                    Download URL: <span className="text-cyan-300 underline">{exportManifest.download_url}</span> (C2PA: Included)
                  </p>
                )}
                {shopifySpec && (
                  <p className="text-zinc-300 text-[11px] font-mono">
                    Shopify Dimensions: {shopifySpec.dimensions?.width}x{shopifySpec.dimensions?.height} • Format: {shopifySpec.dimensions?.format} ({shopifySpec.dimensions?.color_space})
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

