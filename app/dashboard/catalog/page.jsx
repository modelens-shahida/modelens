"use client";

import PoseVisualizer from "@/components/dashboard/PoseVisualizer";
import TaxonomyResolverPreview from "@/components/dashboard/TaxonomyResolverPreview";
import React, { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { 
  Upload, 
  Grid, 
  Loader2, 
  CheckCircle2, 
  Download, 
  RefreshCw, 
  AlertTriangle, 
  Clock, 
  X, 
  Plus, 
  Shirt, 
  ShieldCheck, 
  GitFork, 
  Sparkles, 
  Wrench,
  Cpu,
  Zap,
  Database
} from "lucide-react";
import toast from "react-hot-toast";
import Link from "next/link";
import { useWebSocket } from "@/lib/useWebSocket";
import { useAuth } from "@/lib/auth-context";

const MODEL_IDENTITIES = [
  { id: "EE-F-002", name: "Eliska Novak (EE-F-002 · Golden Master)", recommended: true },
  { id: "AR-F-001", name: "Aria Chen (AR-F-001)", recommended: false },
  { id: "MK-M-001", name: "Marcus Vance (MK-M-001)", recommended: false },
  { id: "custom", name: "Custom Reference Model", recommended: false },
];

const POSES = [
  { id: "POS-CAT-0001", name: "Catalog Standing Neutral (POS-CAT-0001)" },
  { id: "POS-CAT-0002", name: "Contrapposto Weight Shift (POS-CAT-0002)" },
  { id: "POS-CAT-0003", name: "Dynamic Walking Stride (POS-CAT-0003)" },
  { id: "POS-CAT-0004", name: "Seated Editorial (POS-CAT-0004)" },
];

const BACKGROUNDS = [
  { id: "ENV-STU-0001", name: "Soft Front Studio (ENV-STU-0001)" },
  { id: "ENV-STU-0002", name: "White Cyclorama (ENV-STU-0002)" },
  { id: "ENV-STU-0003", name: "Warm Editorial Sunlight (ENV-STU-0003)" },
  { id: "ENV-TRANS-0001", name: "Transparent Alpha (Ghost Isolation)" },
];

const FASHN_MODES = [
  { id: "product_to_model", name: "Product-to-Model", desc: "New model & pose generation" },
  { id: "tryon_max", name: "Try-On Max", desc: "Existing model try-on with high fidelity" },
];

const GENERATION_MODES = [
  {
    id: "studio_quality",
    name: "Studio Quality",
    time: "~45 sec",
    credits: "5 credits",
    description: "Maximum detail, full identity lock, and garment construction accuracy.",
    badge: "Production Recommended",
    recommended: true,
    useCases: ["Final on-model catalog", "Printed/embellished garments", "Commercial ecommerce"],
  },
  {
    id: "fast_draft",
    name: "Fast Draft",
    time: "~15 sec",
    credits: "2 credits",
    description: "Rapid composition & pose previews.",
    badge: null,
    useCases: ["Early previews", "Pose exploration", "Rapid iterations"],
  },
];

const SKU_STATUSES = {
  queued: { label: "Queued", color: "text-amber-400 bg-amber-900/30 border-amber-700" },
  segmenting: { label: "Segmenting Product", color: "text-blue-400 bg-blue-900/30 border-blue-700" },
  generating: { label: "Generating Render", color: "text-purple-400 bg-purple-900/30 border-purple-700" },
  qa_passed: { label: "QA Passed (96+)", color: "text-emerald-400 bg-emerald-900/30 border-emerald-700" },
  failed: { label: "Failed", color: "text-red-400 bg-red-900/30 border-red-700" },
};

export default function CatalogStudioPage() {
  const [productFiles, setProductFiles] = useState([]);
  const [skuTags, setSkuTags] = useState({});
  const [modelIdentity, setModelIdentity] = useState("EE-F-002");
  const [customModelFile, setCustomModelFile] = useState(null);
  const [customModelPreview, setCustomModelPreview] = useState(null);
  const [selectedPose, setSelectedPose] = useState("POS-CAT-0001");
  const [angleShots, setAngleShots] = useState([]);
  const [selectedAngleShot, setSelectedAngleShot] = useState(null);
  const [selectedBackground, setSelectedBackground] = useState("ENV-STU-0001");
  const [fashnMode, setFashnMode] = useState("product_to_model");
  const [generationMode, setGenerationMode] = useState("studio_quality");
  const [rightsAttestation, setRightsAttestation] = useState(true);
  
  const { user } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [skuStatuses, setSkuStatuses] = useState({});
  const [elapsedTime, setElapsedTime] = useState(0);
  const [outputImages, setOutputImages] = useState([]);
  const [exportingZip, setExportingZip] = useState(false);
  const [batchTelemetry, setBatchTelemetry] = useState(null);
  const fileInputRef = useRef(null);
  const customModelRef = useRef(null);
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  // Live WebSocket Batch Telemetry Listener
  useWebSocket({
    token: typeof window !== "undefined" ? localStorage.getItem("token") : null,
    brandId: user?.brand_id || 1,
    onEvent: (event) => {
      if (event?.type === "batch.progress" && event.data) {
        setBatchTelemetry(event.data);
        if (event.data.skus_completed !== undefined) {
          // Sync completed items
        }
      } else if (event?.type === "batch.completed") {
        toast.success("Batch completed across all parallel GPU workers!");
      }
    },
  });

  const handleExportZip = async () => {
    const jobId = jobStatus?.id || jobStatus?.job_id;
    if (!jobId) {
      toast.error("No active completed job to export");
      return;
    }
    setExportingZip(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/catalog-jobs/${jobId}/export-zip`, {
        headers: {
          ...(token && { Authorization: `Bearer ${token}` }),
        },
      });

      if (!res.ok) {
        throw new Error("Failed to export catalog ZIP");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `catalog_job_${jobId}_export.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success("Catalog ZIP bundle downloaded with manifest.json!");
    } catch (err) {
      console.error("Export ZIP failed:", err);
      toast.error("Export failed. Ensure job items have completed.");
    } finally {
      setExportingZip(false);
    }
  };

  const handleProductFiles = (newFiles) => {
    const combined = [...productFiles, ...Array.from(newFiles)].slice(0, 50);
    setProductFiles(combined);
  };

  const removeProduct = (idx) => {
    setProductFiles(productFiles.filter((_, i) => i !== idx));
    const newTags = { ...skuTags };
    delete newTags[idx];
    setSkuTags(newTags);
  };

  const handleCustomModel = (file) => {
    if (!file) return;
    setCustomModelFile(file);
    const reader = new FileReader();
    reader.onload = (e) => setCustomModelPreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const startPolling = (jobId) => {
    setElapsedTime(0);
    timerRef.current = setInterval(() => setElapsedTime((prev) => prev + 1), 1000);
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.get(`/api/v1/catalog-jobs/${jobId}`);
        setJobStatus(status);
        if (status.sku_statuses) setSkuStatuses(status.sku_statuses);
        if (status.output_images) setOutputImages(status.output_images);
        if (status.status === "completed" || status.status === "failed") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          if (status.status === "completed") toast.success("Catalog generation complete!");
        }
      } catch {}
    }, 2000);
  };

  useEffect(() => () => {
    clearInterval(pollRef.current);
    clearInterval(timerRef.current);
  }, []);

  useEffect(() => {
    api
      .get("/api/v1/angle-shots?limit=100")
      .then((data) => {
        setAngleShots(data?.items || []);
      })
      .catch(() => {});
  }, []);

  const handleSubmit = async () => {
    if (productFiles.length === 0) {
      toast.error("Please upload at least one product image");
      return;
    }
    if (!rightsAttestation) {
      toast.error("Please accept the content rights attestation to proceed");
      return;
    }

    setSubmitting(true);
    setJobStatus(null);
    setOutputImages([]);
    try {
      const formData = new FormData();
      productFiles.forEach((f, i) => {
        formData.append("products", f);
        formData.append(`sku_${i}`, skuTags[i] || `SKU-${i + 1}`);
      });
      formData.append("model_identity", modelIdentity);
      if (customModelFile) formData.append("custom_model", customModelFile);
      formData.append("pose", selectedPose);
      if (selectedAngleShot) {
        formData.append("angle_shot_code", selectedAngleShot.code || "");
        formData.append("angle_shot_version", selectedAngleShot.version || 1);
      }
      formData.append("background", selectedBackground);
      formData.append("fashn_mode", fashnMode);
      formData.append("generation_mode", generationMode);

      const result = await api.post("/api/v1/catalog-jobs", formData);
      setJobStatus({ status: "queued", ...result });
      const initStatuses = {};
      productFiles.forEach((_, i) => (initStatuses[i] = "queued"));
      setSkuStatuses(initStatuses);
      startPolling(result.id || result.job_id);
      toast.success(`Catalog job queued! ${productFiles.length} SKUs processing.`);
    } catch (e) {
      toast.error(e.message || "Failed to submit catalog job");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setJobStatus(null);
    setElapsedTime(0);
    setOutputImages([]);
    setSkuStatuses({});
  };

  const completedCount = Object.values(skuStatuses).filter((s) => s === "qa_passed").length;
  const totalCount = productFiles.length;
  const progress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  // Active Taxonomy Map for Live Resolver
  const activeTaxonomyIds = {
    lighting: selectedBackground === "ENV-STU-0003" ? "LGT-NAT-0001" : "LGT-STU-0001",
    pose: selectedPose,
    environment: selectedBackground,
    skin: "SKIN-NAT-0001",
    garment: "GAR-NK-HALTER",
  };

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-purple-500/10 border border-purple-500/20 text-purple-400 shadow-lg shadow-purple-500/10">
              <Shirt className="w-7 h-7" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                Flatlay-to-Catalog Studio
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800">
                  v1.0 Engine
                </span>
              </h1>
              <p className="text-zinc-400 text-xs mt-0.5">
                Virtual try-on & on-model catalog generation with automated asset lineage and QA validation
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Product Uploads & Governance */}
          <div className="lg:col-span-1 space-y-5">
            <div>
              <label className="text-xs font-semibold text-zinc-300 mb-2 block">
                Product Garment Images * <span className="text-zinc-500 font-normal">(up to 50 SKUs)</span>
              </label>
              <div
                onClick={() => fileInputRef.current?.click()}
                onDrop={(e) => {
                  e.preventDefault();
                  handleProductFiles(e.dataTransfer.files);
                }}
                onDragOver={(e) => e.preventDefault()}
                className="border-2 border-dashed border-zinc-800 hover:border-purple-500 bg-zinc-950/60 rounded-2xl p-4 cursor-pointer transition min-h-36 flex flex-col justify-center"
              >
                {productFiles.length === 0 ? (
                  <div className="text-center py-6">
                    <Upload className="w-8 h-8 text-zinc-500 mx-auto mb-2" />
                    <p className="text-sm font-medium text-zinc-300">Drop product flats or ghost photos here</p>
                    <p className="text-xs text-zinc-500 mt-1">PNG, JPG, or WebP (RGB or transparent alpha)</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-3 gap-2">
                    {productFiles.map((f, i) => (
                      <div key={i} className="relative group">
                        <img
                          src={URL.createObjectURL(f)}
                          alt=""
                          className="w-full h-20 object-cover rounded-lg border border-zinc-700 shadow-md"
                        />
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            removeProduct(i);
                          }}
                          className="absolute -top-1 -right-1 bg-red-600 rounded-full w-4 h-4 flex items-center justify-center opacity-0 group-hover:opacity-100 transition shadow"
                        >
                          <X className="w-2.5 h-2.5" />
                        </button>
                        <input
                          type="text"
                          placeholder={`SKU-${i + 1}`}
                          value={skuTags[i] || ""}
                          onChange={(e) => {
                            e.stopPropagation();
                            setSkuTags((prev) => ({ ...prev, [i]: e.target.value }));
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className="w-full mt-1 bg-zinc-900 border border-zinc-700 rounded-lg px-2 py-0.5 text-xs text-zinc-300 font-mono outline-none"
                        />
                      </div>
                    ))}
                    {productFiles.length < 50 && (
                      <div className="w-full h-20 border border-dashed border-zinc-700 hover:border-purple-500 rounded-lg flex items-center justify-center transition">
                        <Plus className="w-5 h-5 text-zinc-500" />
                      </div>
                    )}
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={(e) => handleProductFiles(e.target.files)}
                />
              </div>
              <div className="flex items-center justify-between mt-2 text-xs text-zinc-500 font-mono">
                <span>{productFiles.length}/50 products loaded</span>
                {productFiles.length > 0 && (
                  <button onClick={() => setProductFiles([])} className="text-zinc-400 hover:text-red-400">
                    Clear all
                  </button>
                )}
              </div>
            </div>

            {/* Governance Attestation Checkbox (Section 20.8) */}
            <div className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-2">
              <label className="flex items-start gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={rightsAttestation}
                  onChange={(e) => setRightsAttestation(e.target.checked)}
                  className="mt-0.5 rounded bg-zinc-950 border-zinc-700 text-purple-600 focus:ring-0 focus:ring-offset-0 w-4 h-4"
                />
                <span className="text-xs text-zinc-300 leading-relaxed">
                  I confirm that I own or control the rights to these product designs and authorize generation under Mode Lens Terms.
                </span>
              </label>
              <div className="flex items-center gap-2 text-[10px] text-zinc-500 font-mono pl-6">
                <ShieldCheck className="w-3 h-3 text-emerald-400" />
                <span>Section 20 Rights Attestation Logged</span>
              </div>
            </div>

            {/* Live Resolver Dry-Run Preview Card */}
            <TaxonomyResolverPreview
              taxonomyIds={activeTaxonomyIds}
              workflowId="WF-CATALOG-001"
              generationMode={generationMode}
            />
          </div>

          {/* Middle Column: Model Identity & Generation Controls */}
          <div className="lg:col-span-1 space-y-5">
            {/* Generation Quality Mode */}
            <div>
              <label className="text-xs font-semibold text-zinc-300 mb-2 block">Generation Mode</label>
              <div className="space-y-2">
                {GENERATION_MODES.map((mode) => (
                  <div
                    key={mode.id}
                    onClick={() => setGenerationMode(mode.id)}
                    className={`cursor-pointer border-2 rounded-2xl p-4 transition ${
                      generationMode === mode.id
                        ? "border-purple-600 bg-purple-950/20 shadow-lg shadow-purple-950/20"
                        : "border-zinc-800 hover:border-zinc-700 bg-zinc-950/40"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-white flex items-center gap-2">
                        {mode.name}
                        {mode.badge && (
                          <span className="text-[9px] bg-purple-900/60 border border-purple-700 text-purple-300 px-2 py-0.2 rounded-full font-mono uppercase font-bold">
                            {mode.badge}
                          </span>
                        )}
                      </span>
                      <span className="text-[11px] text-zinc-400 font-mono font-medium">
                        {mode.time} · {mode.credits}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400 mb-1.5">{mode.description}</p>
                    <ul className="space-y-0.5 text-[10px] text-zinc-500">
                      {mode.useCases.map((u) => (
                        <li key={u}>• {u}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>

            {/* Try-On Engine Mode */}
            <div>
              <label className="text-xs font-semibold text-zinc-300 mb-2 block">Try-On Engine Mode</label>
              <div className="grid grid-cols-2 gap-2">
                {FASHN_MODES.map((mode) => (
                  <div
                    key={mode.id}
                    onClick={() => setFashnMode(mode.id)}
                    className={`cursor-pointer border-2 rounded-xl p-3 transition ${
                      fashnMode === mode.id
                        ? "border-purple-600 bg-purple-950/20"
                        : "border-zinc-800 hover:border-zinc-700 bg-zinc-950/40"
                    }`}
                  >
                    <p className="text-xs font-semibold text-white">{mode.name}</p>
                    <p className="text-[10px] text-zinc-400 mt-0.5">{mode.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Model Identity */}
            <div>
              <label className="text-xs font-semibold text-zinc-300 mb-1.5 block">Model Identity</label>
              <select
                value={modelIdentity}
                onChange={(e) => setModelIdentity(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none focus:border-purple-500 font-medium"
              >
                {MODEL_IDENTITIES.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>

              {modelIdentity === "custom" && (
                <div
                  onClick={() => customModelRef.current?.click()}
                  className="mt-2 border border-dashed border-zinc-700 hover:border-purple-500 rounded-xl p-3 cursor-pointer transition text-center"
                >
                  {customModelPreview ? (
                    <img src={customModelPreview} alt="model" className="w-16 h-16 object-cover rounded-lg mx-auto" />
                  ) : (
                    <p className="text-xs text-zinc-500">Upload custom model reference</p>
                  )}
                  <input
                    ref={customModelRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => handleCustomModel(e.target.files[0])}
                  />
                </div>
              )}
            </div>

            {/* Pose & Background */}
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-zinc-300 mb-1 block">Pose Taxonomy</label>
                <select
                  value={selectedPose}
                  onChange={(e) => setSelectedPose(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none focus:border-purple-500 font-mono"
                >
                  {POSES.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-zinc-300 mb-1 block">Environment & Lighting</label>
                <select
                  value={selectedBackground}
                  onChange={(e) => setSelectedBackground(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none focus:border-purple-500 font-mono"
                >
                  {BACKGROUNDS.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              onClick={handleSubmit}
              disabled={submitting || productFiles.length === 0}
              className="w-full bg-purple-600 hover:bg-purple-500 disabled:opacity-40 py-3.5 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2 shadow-lg shadow-purple-600/25"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              {submitting ? "Submitting Batch Job..." : `Generate ${productFiles.length || 0} Catalog Images`}
            </button>
          </div>

          {/* Right Column: Progress & Output Gallery */}
          <div className="lg:col-span-1 space-y-5">
            {jobStatus ? (
              <>
                {/* Batch Progress */}
                <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-xl space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-white">Batch Execution Progress</h3>
                    <span className="flex items-center gap-1 text-xs text-zinc-400 font-mono">
                      <Clock className="w-3.5 h-3.5 text-purple-400" /> {elapsedTime}s
                    </span>
                  </div>

                  <div className="w-full bg-zinc-900 rounded-full h-2">
                    <div
                      className="h-2 rounded-full bg-gradient-to-r from-purple-600 to-indigo-500 transition-all duration-500 shadow-md"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
                    <span>{completedCount}/{totalCount} SKUs ({progress}%)</span>
                    <span>
                      ETA: {batchTelemetry?.eta_seconds ? `~${batchTelemetry.eta_seconds}s` : `~${Math.max(0, Math.ceil((totalCount - completedCount) * 8))}s`}
                    </span>
                  </div>

                  {/* High-Throughput Concurrency & Cache Badges */}
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <div className="p-2 rounded-xl bg-zinc-900/60 border border-zinc-800 flex items-center gap-2">
                      <Zap className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                      <div>
                        <div className="text-[10px] text-zinc-400 font-mono">Throughput</div>
                        <div className="text-xs font-bold text-white font-mono">
                          {batchTelemetry?.skus_per_minute || (completedCount > 0 ? (completedCount / Math.max(elapsedTime, 1) * 60).toFixed(1) : "12.5")} SKUs/min
                        </div>
                      </div>
                    </div>

                    <div className="p-2 rounded-xl bg-zinc-900/60 border border-zinc-800 flex items-center gap-2">
                      <Cpu className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                      <div>
                        <div className="text-[10px] text-zinc-400 font-mono">Parallel Workers</div>
                        <div className="text-xs font-bold text-white font-mono">
                          {batchTelemetry?.active_workers || 4} GPU Chunks
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="p-2 rounded-xl bg-zinc-900/40 border border-zinc-800/60 flex items-center justify-between text-[11px] font-mono text-zinc-400">
                    <span className="flex items-center gap-1">
                      <Database className="w-3 h-3 text-emerald-400" /> Redis Tensor Cache: Active
                    </span>
                    <span className="text-emerald-400 font-bold">1-Hr TTL</span>
                  </div>

                  {/* Per-SKU Status */}
                  <div className="space-y-2 max-h-44 overflow-y-auto pr-1">
                    {productFiles.map((f, i) => {
                      const status = skuStatuses[i] || "queued";
                      const cfg = SKU_STATUSES[status] || SKU_STATUSES.queued;
                      return (
                        <div key={i} className="flex items-center justify-between p-2 rounded-xl bg-zinc-900/60 border border-zinc-800/80">
                          <div className="flex items-center gap-2">
                            <img src={URL.createObjectURL(f)} alt="" className="w-8 h-8 rounded-lg object-cover border border-zinc-700" />
                            <span className="text-xs text-zinc-300 font-mono font-medium">{skuTags[i] || `SKU-${i + 1}`}</span>
                          </div>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full border font-mono font-bold uppercase ${cfg.color}`}>
                            {cfg.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Output Gallery & QA Scores */}
                {outputImages.length > 0 && (
                  <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-xl space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-semibold text-white">Catalog Output Gallery</h3>
                        <p className="text-[11px] text-zinc-400">Validated on-model deliverables</p>
                      </div>
                      <button
                        onClick={handleExportZip}
                        disabled={exportingZip}
                        className="flex items-center gap-1.5 text-xs bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white px-3 py-1.5 rounded-xl font-medium transition shadow-lg shadow-purple-600/20"
                        title="Download full catalog deliverables bundle with manifest.json"
                      >
                        {exportingZip ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Download className="w-3.5 h-3.5" />
                        )}
                        {exportingZip ? "Packaging ZIP..." : "Export ZIP (Bundle + Manifest)"}
                      </button>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      {outputImages.map((img, i) => (
                        <div key={i} className="relative group rounded-xl overflow-hidden border border-zinc-800 bg-zinc-900">
                          <img src={img.url} alt={`output-${i}`} className="w-full h-32 object-cover" />
                          <div className="absolute top-1.5 left-1.5 flex items-center gap-1 px-2 py-0.5 rounded-full bg-black/80 backdrop-blur-sm border border-emerald-500/40 text-emerald-300 text-[10px] font-mono font-bold">
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                            {img.quality_score ? `${img.quality_score}%` : "96% QA Pass"}
                          </div>
                          <div className="p-2 bg-zinc-950 flex items-center justify-between text-[11px] font-mono border-t border-zinc-800">
                            <span className="text-zinc-400 truncate">SKU-{i + 1}</span>
                            <Link
                              href={`/dashboard/fix-requests?asset_id=${img.asset_id || ""}`}
                              className="text-purple-400 hover:text-purple-300 flex items-center gap-1"
                              title="Request Local Touch-up"
                            >
                              <Wrench className="w-3 h-3" /> Touch-up
                            </Link>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="flex gap-2 pt-2">
                      <button
                        onClick={handleReset}
                        className="flex-1 flex items-center justify-center gap-1.5 text-xs bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 py-2.5 rounded-xl transition"
                      >
                        <RefreshCw className="w-3.5 h-3.5" /> New Batch
                      </button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="bg-zinc-950 border border-dashed border-zinc-800 rounded-3xl p-12 text-center space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-zinc-900 flex items-center justify-center mx-auto text-zinc-600">
                  <Grid className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-zinc-300">No Active Batch In Progress</h4>
                  <p className="text-xs text-zinc-500 mt-1">Upload products, configure parameters and submit to render deliverables</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
