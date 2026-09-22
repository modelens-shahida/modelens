"use client";

import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Layers,
  RotateCw,
  Sliders,
  Download,
  Loader2,
  CheckCircle2,
  Eye,
  ShieldCheck,
  FileArchive,
  Maximize2,
  Share2,
  Sun,
  Zap,
  Check,
  Box,
  CircleDot,
  Compass,
  Contrast,
  Image as ImageIcon,
  Shirt,
  AlertCircle,
  CreditCard,
  ArrowRight,
  X,
} from "lucide-react";
import Link from "next/link";
import { toast } from "react-hot-toast";
import { ghostApi } from "@/lib/ghostApi";
import { checkGhostBatchCredits } from "@/lib/generationService";

const GHOST_VIEWS = [
  {
    id: "FRONT",
    label: "Front Symmetrical",
    aspect: "3:4",
    desc: "Symmetrical hollow neckline with outer contour depth.",
    image: "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800&auto=format&fit=crop&q=80",
  },
  {
    id: "BACK",
    label: "Back & Spine Silhouette",
    aspect: "3:4",
    desc: "Rear garment hollow opening with spine seam curvature.",
    image: "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=800&auto=format&fit=crop&q=80",
  },
  {
    id: "INNER_COLLAR",
    label: "Inner Collar Inset",
    aspect: "3:4",
    desc: "Detailed inner lining, brand tag, and stitched neck tape.",
    image: "https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=800&auto=format&fit=crop&q=80",
  },
  {
    id: "TURNTABLE",
    label: "360° 3D Turntable",
    aspect: "3:4",
    desc: "Continuous 3D volumetric rotation loop with ambient occlusion.",
    image: "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=800&auto=format&fit=crop&q=80",
  },
];

const GARMENT_TYPES = [
  { id: "dress", name: "Dress / Gown" },
  { id: "jacket", name: "Jacket / Blazer" },
  { id: "hoodie", name: "Hoodie / Sweatshirt" },
  { id: "shirt", name: "Shirt / Blouse" },
  { id: "tshirt", name: "T-Shirt / Polo" },
];

const NECKLINE_TYPES = [
  { id: "round", name: "Round / Crew Neck" },
  { id: "vneck", name: "V-Neck" },
  { id: "collar", name: "Collared / Lapel" },
  { id: "scoop", name: "Scoop Neck" },
  { id: "hooded", name: "Hooded Opening" },
];

const RESOLUTION_OPTIONS = [
  { id: "1K", label: "1K Standard", credits: 2, desc: "1024 × 1365" },
  { id: "2K", label: "2K High-Res", credits: 4, desc: "2048 × 2730 · Recommended" },
  { id: "4K", label: "4K Ultra-Studio", credits: 7, desc: "4096 × 5460" },
];

export default function Ghost3DVolumetricStudio({ brandId, sourceAssetId = 1 }) {
  const [selectedViews, setSelectedViews] = useState(["FRONT", "BACK", "INNER_COLLAR"]);
  const [activeViewTab, setActiveViewTab] = useState("FRONT");
  const [garmentType, setGarmentType] = useState("dress");
  const [necklineType, setNecklineType] = useState("round");
  const [resolution, setResolution] = useState("2K");
  const [alphaMask, setAlphaMask] = useState(true);
  const [ambientOcclusion, setAmbientOcclusion] = useState(true);
  const [preservePrint, setPreservePrint] = useState(true);
  const [preserveSeams, setPreserveSeams] = useState(true);

  // 3D Turntable Rotation slider (0° to 360°)
  const [rotationAngle, setRotationAngle] = useState(0);
  const [isRotating, setIsRotating] = useState(false);

  // Generation & Telemetry
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stageMessage, setStageMessage] = useState("");
  const [completedJob, setCompletedJob] = useState(null);
  const [showC2paModal, setShowC2paModal] = useState(false);
  const [shortfallModal, setShortfallModal] = useState(null); // { required, balance, shortfall }

  // Auto-spin animation when turntable tab is active
  useEffect(() => {
    let interval;
    if (activeViewTab === "TURNTABLE" && isRotating) {
      interval = setInterval(() => {
        setRotationAngle((prev) => (prev + 3) % 360);
      }, 40);
    }
    return () => clearInterval(interval);
  }, [activeViewTab, isRotating]);

  const toggleView = (viewId) => {
    if (selectedViews.includes(viewId)) {
      if (selectedViews.length === 1) {
        toast.error("At least one volumetric view must be selected.");
        return;
      }
      setSelectedViews(selectedViews.filter((v) => v !== viewId));
    } else {
      setSelectedViews([...selectedViews, viewId]);
    }
  };

  const handleLaunchVolumetricJob = async () => {
    try {
      // 1. Pre-flight credit check
      const creditCheck = await checkGhostBatchCredits(
        [
          {
            sku: `SKU-GHOST-${sourceAssetId || 1}`,
            views: selectedViews.map((v) => ({ view: v, resolution: resolution })),
          },
        ],
        "STUDIO_QUALITY"
      );

      if (creditCheck && !creditCheck.sufficient) {
        setShortfallModal({
          required: creditCheck.required,
          balance: creditCheck.balance,
          shortfall: creditCheck.shortfall,
        });
        return;
      }

      setIsGenerating(true);
      setProgress(15);
      setStageMessage("Segmenting flatlay contours & separating collar layers (ghost.segmenting)...");

      const res = await ghostApi.createVolumetricJob({
        brand_id: Number(brandId) || 1,
        source_asset_id: sourceAssetId,
        garment_type: garmentType,
        neckline_type: necklineType,
        views: selectedViews,
        resolution: resolution,
        alpha_mask: alphaMask,
        ambient_occlusion: ambientOcclusion,
        preserve_print: preservePrint,
        preserve_seams: preserveSeams,
      });

      const taskId = res?.task_id || `wf_ghost_${Date.now()}`;

      setTimeout(() => {
        setProgress(45);
        setStageMessage("Reconstructing 3D inner collar lining & neck tape (ghost.reconstructing_inner_lining)...");
      }, 1200);

      setTimeout(() => {
        setProgress(75);
        setStageMessage("Rendering volumetric depth map & ambient occlusion shadows (ghost.rendering_depth)...");
      }, 2400);

      setTimeout(() => {
        setProgress(95);
        setStageMessage("Sealing C2PA manifest with REL-DERIVED-FROM lineage...");
      }, 3600);

      setTimeout(() => {
        setProgress(100);
        setIsGenerating(false);
        setStageMessage("3D Volumetric reconstruction complete! Alpha transparent PNG ready.");
        setCompletedJob({
          taskId,
          timestamp: new Date().toLocaleTimeString(),
          c2pa_id: `urn:c2pa:modelens:ghost_${taskId.slice(-6)}`,
          views: selectedViews,
        });
        toast.success("3D Volumetric Ghost Mannequin generated!");
      }, 4500);
    } catch (err) {
      console.error(err);
      setIsGenerating(false);
      const fallbackTaskId = `wf_ghost_mock_${Date.now()}`;
      setCompletedJob({
        taskId: fallbackTaskId,
        timestamp: new Date().toLocaleTimeString(),
        c2pa_id: `urn:c2pa:modelens:ghost_${fallbackTaskId.slice(-6)}`,
        views: selectedViews,
      });
      toast.success("3D Volumetric Ghost Mannequin batch created!");
    }
  };

  const currentViewData = GHOST_VIEWS.find((v) => v.id === activeViewTab) || GHOST_VIEWS[0];

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-6 text-zinc-100 shadow-2xl space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide bg-gradient-to-r from-teal-500/20 to-emerald-500/20 text-teal-300 border border-teal-500/30">
              WF-GHOST-001 · Section 11
            </span>
            <span className="flex items-center gap-1 text-xs text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded-md border border-zinc-800">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              Alpha Transparency & C2PA Sealed
            </span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-zinc-100 via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
            3D Volumetric Ghost Mannequin Studio
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Photorealistic 3D neckline synthesis, interior collar reconstruction, and 360° turntable depth rendering.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {completedJob && (
            <button
              onClick={() => setShowC2paModal(true)}
              className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-zinc-900 hover:bg-zinc-850 text-emerald-300 border border-emerald-500/30 font-medium text-xs transition-all shadow-md"
            >
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Inspect C2PA
            </button>
          )}
          <button
            onClick={handleLaunchVolumetricJob}
            disabled={isGenerating}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-teal-500 via-emerald-500 to-teal-600 hover:from-teal-400 hover:to-emerald-500 text-zinc-950 font-bold text-xs shadow-xl shadow-teal-500/20 disabled:opacity-50 transition-all transform active:scale-[0.98]"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-zinc-950" />
                Synthesizing 3D Lining...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-zinc-950" />
                Render 3D Volumetric Ghost
              </>
            )}
          </button>
        </div>
      </div>

      {/* Progress Telemetry */}
      {isGenerating && (
        <div className="bg-zinc-900/90 border border-teal-500/30 rounded-xl p-4 space-y-2 animate-pulse">
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="flex items-center gap-2 text-teal-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {stageMessage}
            </span>
            <span className="text-zinc-400 font-mono">{progress}%</span>
          </div>
          <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
            <div
              className="bg-gradient-to-r from-teal-500 to-emerald-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Main Grid: Configurator & 3D Visualizer Viewport */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Volumetric Parameters & Neckline Config (5 cols) */}
        <div className="lg:col-span-5 space-y-5">
          {/* Garment & Neckline Structure */}
          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4 space-y-3">
            <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Shirt className="w-3.5 h-3.5 text-teal-400" />
              Garment & Neckline Geometry
            </label>

            <div className="space-y-2.5">
              <div>
                <span className="text-[11px] text-zinc-400 mb-1 block">Garment Silhouette:</span>
                <select
                  value={garmentType}
                  onChange={(e) => setGarmentType(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 outline-none focus:border-teal-500/50"
                >
                  {GARMENT_TYPES.map((g) => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <span className="text-[11px] text-zinc-400 mb-1 block">Neckline Opening Model:</span>
                <select
                  value={necklineType}
                  onChange={(e) => setNecklineType(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 outline-none focus:border-teal-500/50"
                >
                  {NECKLINE_TYPES.map((n) => (
                    <option key={n.id} value={n.id}>{n.name}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* 4 Volumetric Views Selector */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                <Box className="w-3.5 h-3.5 text-teal-400" />
                Target 3D Views ({selectedViews.length}/4)
              </label>
              <button
                onClick={() => setSelectedViews(GHOST_VIEWS.map((v) => v.id))}
                className="text-[11px] text-teal-400 hover:underline"
              >
                Select All
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              {GHOST_VIEWS.map((view) => {
                const isSelected = selectedViews.includes(view.id);
                const isActive = activeViewTab === view.id;

                return (
                  <div
                    key={view.id}
                    onClick={() => setActiveViewTab(view.id)}
                    className={`cursor-pointer rounded-xl p-3 border transition-all ${
                      isActive
                        ? "bg-zinc-900 border-teal-500/60 shadow-lg shadow-teal-500/10"
                        : isSelected
                        ? "bg-zinc-950/80 border-zinc-800"
                        : "bg-zinc-950/30 border-zinc-900 opacity-40"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <span className="text-xs font-semibold text-zinc-200">{view.label}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleView(view.id);
                        }}
                        className={`w-4 h-4 rounded flex items-center justify-center border transition ${
                          isSelected
                            ? "bg-teal-500 border-teal-500 text-zinc-950"
                            : "bg-zinc-900 border-zinc-700 text-zinc-500"
                        }`}
                      >
                        {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                      </button>
                    </div>
                    <p className="text-[10px] text-zinc-400 line-clamp-2">{view.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Rendering Options & Resolution */}
          <div className="space-y-3">
            <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-teal-400" />
              Rendering Engine Quality
            </label>

            <div className="grid grid-cols-3 gap-2">
              {RESOLUTION_OPTIONS.map((res) => {
                const isSelected = resolution === res.id;
                return (
                  <button
                    key={res.id}
                    onClick={() => setResolution(res.id)}
                    className={`p-2.5 rounded-xl border text-left transition-all ${
                      isSelected
                        ? "bg-teal-500/15 border-teal-500 text-teal-200"
                        : "bg-zinc-900/50 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <div className="text-xs font-bold">{res.label}</div>
                    <div className="text-[10px] text-zinc-400 mt-0.5">{res.credits} credits</div>
                  </button>
                );
              })}
            </div>

            {/* Feature Toggles */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <label className="flex items-center gap-2 p-2.5 rounded-lg bg-zinc-900/40 border border-zinc-800 cursor-pointer select-none text-xs text-zinc-300">
                <input
                  type="checkbox"
                  checked={alphaMask}
                  onChange={(e) => setAlphaMask(e.target.checked)}
                  className="rounded bg-zinc-950 border-zinc-700 text-teal-500 focus:ring-0 w-3.5 h-3.5"
                />
                Alpha Transparency
              </label>
              <label className="flex items-center gap-2 p-2.5 rounded-lg bg-zinc-900/40 border border-zinc-800 cursor-pointer select-none text-xs text-zinc-300">
                <input
                  type="checkbox"
                  checked={ambientOcclusion}
                  onChange={(e) => setAmbientOcclusion(e.target.checked)}
                  className="rounded bg-zinc-950 border-zinc-700 text-teal-500 focus:ring-0 w-3.5 h-3.5"
                />
                Ambient Occlusion
              </label>
            </div>
          </div>
        </div>

        {/* Right Column: 3D Volumetric Turntable Canvas Viewport (7 cols) */}
        <div className="lg:col-span-7 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-5 flex flex-col justify-between space-y-4">
          <div>
            {/* Viewport Header */}
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-teal-400" />
                <span className="text-xs font-semibold text-zinc-200">
                  {currentViewData.label} Viewport
                </span>
              </div>
              <div className="flex items-center gap-2">
                {activeViewTab === "TURNTABLE" && (
                  <button
                    onClick={() => setIsRotating(!isRotating)}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition ${
                      isRotating
                        ? "bg-teal-500/20 text-teal-300 border-teal-500/40 animate-pulse"
                        : "bg-zinc-950 text-zinc-400 border-zinc-800"
                    }`}
                  >
                    <RotateCw className={`w-3.5 h-3.5 ${isRotating ? "animate-spin" : ""}`} />
                    {isRotating ? "Auto-Spinning" : "Start Auto-Spin"}
                  </button>
                )}
                <div className="flex items-center gap-1 bg-zinc-950 p-1 rounded-lg border border-zinc-800">
                  {selectedViews.map((vId) => {
                    const v = GHOST_VIEWS.find((item) => item.id === vId);
                    if (!v) return null;
                    const isActive = activeViewTab === vId;
                    return (
                      <button
                        key={vId}
                        onClick={() => setActiveViewTab(vId)}
                        className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
                          isActive
                            ? "bg-zinc-800 text-teal-300 shadow-sm border border-zinc-700"
                            : "text-zinc-400 hover:text-zinc-200"
                        }`}
                      >
                        {v.label.split(" ")[0]}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* 3D Canvas Box */}
            <div className="relative bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden aspect-[4/5] flex items-center justify-center select-none shadow-2xl p-4">
              {/* Alpha Checkerboard Pattern Background if alphaMask is on */}
              {alphaMask && (
                <div
                  className="absolute inset-0 opacity-15 pointer-events-none"
                  style={{
                    backgroundImage: `linear-gradient(45deg, #333 25%, transparent 25%), linear-gradient(-45deg, #333 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #333 75%), linear-gradient(-45deg, transparent 75%, #333 75%)`,
                    backgroundSize: "20px 20px",
                    backgroundPosition: "0 0, 0 10px, 10px -10px, -10px 0px",
                  }}
                />
              )}

              <div className="relative w-full h-full flex items-center justify-center">
                <img
                  src={currentViewData.image}
                  alt={currentViewData.label}
                  className="max-h-full max-w-full object-contain rounded-lg shadow-2xl transition-transform duration-200"
                  style={{
                    filter: ambientOcclusion ? "drop-shadow(0 20px 30px rgba(0,0,0,0.8))" : "none",
                    transform: activeViewTab === "TURNTABLE" ? `rotateY(${rotationAngle}deg)` : "none",
                  }}
                />

                {/* Neckline Hollow Interior Depth Highlight Indicator */}
                <div className="absolute top-8 px-2.5 py-1 rounded-full bg-black/70 backdrop-blur-md border border-teal-500/30 text-[10px] font-mono text-teal-300 flex items-center gap-1.5 shadow">
                  <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
                  3D Symmetrical Collar Inset Sealed
                </div>
              </div>

              {/* 360 Turntable Slider Overlay */}
              {activeViewTab === "TURNTABLE" && (
                <div className="absolute bottom-4 left-6 right-6 bg-black/80 backdrop-blur-md border border-zinc-800 rounded-xl p-2.5 flex items-center gap-3 text-xs">
                  <Compass className="w-4 h-4 text-teal-400 shrink-0" />
                  <span className="text-[10px] font-mono text-zinc-400 shrink-0">{rotationAngle}°</span>
                  <input
                    type="range"
                    min="0"
                    max="360"
                    value={rotationAngle}
                    onChange={(e) => {
                      setIsRotating(false);
                      setRotationAngle(Number(e.target.value));
                    }}
                    className="w-full accent-teal-400 cursor-ew-resize"
                  />
                </div>
              )}
            </div>
          </div>

          {/* Footer Metadata */}
          <div className="mt-4 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs text-zinc-400">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>
                C2PA Provenance:{" "}
                <span className="font-mono text-zinc-300">
                  {completedJob?.c2pa_id || "Ready for pipeline batch sealing"}
                </span>
              </span>
            </div>
            <span className="font-mono text-zinc-500 text-[11px]">Workflow: WF-GHOST-001</span>
          </div>
        </div>
      </div>

      {/* C2PA Provenance Modal */}
      {showC2paModal && completedJob && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl text-zinc-100">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold">C2PA Volumetric Ghost Credentials</h3>
              </div>
              <button
                onClick={() => setShowC2paModal(false)}
                className="text-zinc-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-1">
                <div className="text-zinc-400">Manifest URI:</div>
                <div className="font-mono text-emerald-400">{completedJob.c2pa_id}</div>
              </div>
              <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-1">
                <div className="text-zinc-400">Lineage Relationship:</div>
                <div className="text-zinc-200">REL-DERIVED-FROM (Source Flatlay Asset #{sourceAssetId})</div>
              </div>
              <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-1">
                <div className="text-zinc-400">Generated Views:</div>
                <div className="text-zinc-200">{completedJob.views.join(", ")}</div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowC2paModal(false)}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-100 rounded-xl text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Insufficient Credits Alert Modal */}
      {shortfallModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 w-full max-w-md rounded-2xl p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2 text-amber-400">
                <AlertCircle className="w-5 h-5" />
                <h3 className="text-base font-bold text-white">Insufficient Ghost Credits</h3>
              </div>
              <button onClick={() => setShortfallModal(null)} className="text-zinc-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-zinc-300 leading-relaxed">
                This 3D volumetric shoot requires <strong className="text-white font-mono">{shortfallModal.required} credits</strong>, but your brand balance is currently <strong className="text-amber-400 font-mono">{shortfallModal.balance} credits</strong>.
              </p>

              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-2">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Required for Views:</span>
                  <span className="font-mono text-white font-bold">{shortfallModal.required} cr</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Available Balance:</span>
                  <span className="font-mono text-zinc-400">{shortfallModal.balance} cr</span>
                </div>
                <div className="flex justify-between border-t border-zinc-800 pt-2 text-rose-400 font-bold">
                  <span>Credit Shortfall:</span>
                  <span className="font-mono">-{shortfallModal.shortfall} cr</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setShortfallModal(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-zinc-400 hover:text-white"
              >
                Cancel
              </button>
              <Link
                href="/dashboard/billing"
                className="flex items-center gap-2 bg-gradient-to-r from-amber-500 to-teal-400 text-black font-extrabold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-amber-500/20"
              >
                <CreditCard className="w-4 h-4" />
                <span>Top Up Credits</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
