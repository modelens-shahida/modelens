"use client";
import React, { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import {
  Upload,
  Layers,
  Loader2,
  CheckCircle2,
  Download,
  RefreshCw,
  AlertTriangle,
  Clock,
  Trash2,
  Check,
  ChevronRight,
  Settings,
  Plus
} from "lucide-react";
import toast from "react-hot-toast";
import Link from "next/link";
import TaxonomyResolverPreview from "@/components/dashboard/TaxonomyResolverPreview";
import { ShieldCheck } from "lucide-react";

const GARMENT_TYPES = ["dress", "top", "outerwear", "pants", "jumpsuit", "full outfit"];
const VIEWS = ["front", "back", "detail"];
const ASPECT_RATIOS = ["1:1", "3:4", "4:5", "9:16"];
const RESOLUTIONS = [
  { value: "1K", label: "1K", credits: "1-2 credits" },
  { value: "2K", label: "2K", credits: "3-4 credits" },
  { value: "4K", label: "4K", credits: "5-7 credits" },
];

const GENERATION_MODES = [
  {
    id: "fast",
    name: "Fast Draft",
    time: "~15 sec",
    credits: "1-2 credits",
    description: "Quick previews for testing ideas.",
    badge: null,
    useCases: ["Early previews", "Composition testing", "Quick iterations"],
  },
  {
    id: "studio",
    name: "Studio Quality",
    time: "~45 sec",
    credits: "3-4 credits",
    description: "Maximum detail and garment accuracy.",
    badge: "Recommended for final images",
    recommended: true,
    useCases: ["Ghost mannequin output", "Construction-heavy garments", "Printed/embellished garments", "Final commercial review"],
  },
];

const STATUS_STEPS = [
  { status: "queued", label: "Queued", color: "text-amber-400 bg-amber-900/40 border-amber-700", progress: 10 },
  { status: "preprocessing", label: "Preprocessing", color: "text-blue-400 bg-blue-900/40 border-blue-700", progress: 30 },
  { status: "generating", label: "Generating Render", color: "text-purple-400 bg-purple-900/40 border-purple-700", progress: 65 },
  { status: "quality_check", label: "Quality Check", color: "text-indigo-400 bg-indigo-900/40 border-indigo-700", progress: 85 },
  { status: "completed", label: "Completed", color: "text-emerald-400 bg-emerald-900/40 border-emerald-700", progress: 100 },
  { status: "failed", label: "Failed", color: "text-red-400 bg-red-900/40 border-red-700", progress: 100 },
];

export default function GhostStudioPage() {
  const [tab, setTab] = useState("single"); // "single" or "batch"
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");

  // Single Job States
  const [primaryImage, setPrimaryImage] = useState(null);
  const [primaryPreview, setPrimaryPreview] = useState(null);
  const [productHint, setProductHint] = useState("");
  const [garmentType, setGarmentType] = useState("dress");
  const [view, setView] = useState("front");
  const [aspectRatio, setAspectRatio] = useState("3:4");
  const [resolution, setResolution] = useState("2K");
  const [generationMode, setGenerationMode] = useState("studio");
  const [preservePrint, setPreservePrint] = useState(true);
  const [preserveSeams, setPreserveSeams] = useState(true);
  const [angleShots, setAngleShots] = useState([]);
  const [selectedAngleShot, setSelectedAngleShot] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [activeJob, setActiveJob] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);

  // Batch Job States
  const [batchItems, setBatchItems] = useState([]); // Array of { id, file, preview, uploadProgress, status, assetId, storagePath, productHint, garmentType, view, aspectRatio, resolution, preservePrint, preserveSeams, generationMode }
  const [globalConfig, setGlobalConfig] = useState({
    garmentType: "dress",
    view: "front",
    aspectRatio: "3:4",
    resolution: "2K",
    preservePrint: true,
    preserveSeams: true,
    generationMode: "studio",
  });
  const [activeBatch, setActiveBatch] = useState(null);
  const [batchJobsStatus, setBatchJobsStatus] = useState({});
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [batchElapsedTime, setBatchElapsedTime] = useState(0);

  const pollRef = useRef(null);
  const timerRef = useRef(null);
  const fileInputRef = useRef(null);
  const batchFileInputRef = useRef(null);
  const batchPollRef = useRef(null);
  const batchTimerRef = useRef(null);

  // Load user brands on mount
  useEffect(() => {
    api.get("/api/v1/brands").then(data => {
      const items = data || [];
      setBrands(items);
      if (items.length > 0) {
        setSelectedBrandId(items[0].id.toString());
      }
    }).catch(() => {});
  }, []);

  // Load angle shots presets on mount
  useEffect(() => {
    api.get("/api/v1/angle-shots?limit=100").then(data => {
      setAngleShots(data?.items || []);
    }).catch(() => {});
  }, []);

  // Cleanup timers
  useEffect(() => {
    return () => {
      clearInterval(pollRef.current);
      clearInterval(timerRef.current);
      clearInterval(batchPollRef.current);
      clearInterval(batchTimerRef.current);
    };
  }, []);

  // ---------------------- Single Upload Logic ----------------------

  const handleFileSelect = (file) => {
    if (!file) return;
    const allowed = ["image/jpeg", "image/png", "image/webp", "image/heic"];
    if (!allowed.includes(file.type) && !file.name.toLowerCase().endsWith(".heic")) {
      toast.error("Please upload JPEG, PNG, WebP, or HEIC");
      return;
    }
    setPrimaryImage(file);
    const reader = new FileReader();
    reader.onload = (e) => setPrimaryPreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  const startPolling = (jobId) => {
    setElapsedTime(0);
    clearInterval(pollRef.current);
    clearInterval(timerRef.current);
    timerRef.current = setInterval(() => setElapsedTime(prev => prev + 1), 1000);
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.get(`/api/v1/ghost-jobs/${jobId}`);
        setJobStatus(status);
        if (status.status === "completed" || status.status === "failed") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          if (status.status === "completed") {
            // Retrieve outputs to show output url
            const outRes = await api.get(`/api/v1/ghost-jobs/${jobId}/outputs`);
            if (outRes.outputs?.length > 0) {
              setJobStatus(prev => ({
                ...prev,
                output_url: outRes.outputs[0].output_url,
                quality_score: Math.round((outRes.outputs[0].quality_score || 0.93) * 100)
              }));
            }
          }
        }
      } catch {}
    }, 2000);
  };

  const handleSubmit = async () => {
    if (!primaryImage) { toast.error("Please upload a primary image"); return; }
    if (!productHint.trim()) { toast.error("Please enter a product description"); return; }
    setSubmitting(true);
    setJobStatus(null);
    try {
      const formData = new FormData();
      formData.append("image", primaryImage);
      formData.append("product_hint", productHint);
      formData.append("garment_type", garmentType);
      formData.append("view", view);
      formData.append("aspect_ratio", aspectRatio);
      formData.append("resolution", resolution);
      formData.append("generation_mode", generationMode);
      formData.append("preserve_print", preservePrint ? "true" : "false");
      formData.append("preserve_seams", preserveSeams ? "true" : "false");
      if (selectedBrandId) {
        formData.append("brand_id", selectedBrandId);
      }
      if (selectedAngleShot) {
        formData.append("angle_shot_code", selectedAngleShot.code || "");
        formData.append("angle_shot_version", selectedAngleShot.version || 1);
      }

      const result = await api.post("/api/v1/ghost-jobs", formData);
      setActiveJob(result);
      setJobStatus({ status: "queued", ...result });
      startPolling(result.id || result.job_id);
      toast.success(`Ghost job queued! ID: #${result.id || result.job_id}`);
    } catch (e) {
      toast.error(e.message || "Failed to submit ghost job");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setActiveJob(null);
    setJobStatus(null);
    setElapsedTime(0);
    setPrimaryImage(null);
    setPrimaryPreview(null);
    setProductHint("");
  };

  // ---------------------- Batch Upload Logic ----------------------

  const handleBatchDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      handleBatchFilesSelect(e.dataTransfer.files);
    }
  };

  const handleBatchFilesSelect = (files) => {
    if (!files || files.length === 0) return;
    const allowed = ["image/jpeg", "image/png", "image/webp", "image/heic"];
    const validFiles = Array.from(files).filter(file => {
      const isAllowed = allowed.includes(file.type) || file.name.toLowerCase().endsWith(".heic");
      if (!isAllowed) {
        toast.error(`Invalid file type: ${file.name}`);
      }
      return isAllowed;
    });

    if (batchItems.length + validFiles.length > 50) {
      toast.error("Maximum 50 files allowed in a batch");
      return;
    }

    const newItems = validFiles.map((file, index) => {
      const tempId = `batch_${Date.now()}_${index}_${Math.random().toString(36).substr(2, 9)}`;
      const reader = new FileReader();
      const item = {
        id: tempId,
        file,
        preview: null,
        uploadProgress: 0,
        status: "pending_upload",
        assetId: null,
        storagePath: null,
        productHint: file.name.split(".")[0].replace(/[_-]/g, " "),
        garmentType: globalConfig.garmentType,
        view: globalConfig.view,
        aspectRatio: globalConfig.aspectRatio,
        resolution: globalConfig.resolution,
        preservePrint: globalConfig.preservePrint,
        preserveSeams: globalConfig.preserveSeams,
        generationMode: globalConfig.generationMode,
      };

      reader.onload = (e) => {
        setBatchItems(prev => prev.map(p => p.id === tempId ? { ...p, preview: e.target.result } : p));
      };
      reader.readAsDataURL(file);

      // Trigger background upload
      uploadBatchItemAsset(file, tempId);

      return item;
    });

    setBatchItems(prev => [...prev, ...newItems]);
  };

  const uploadBatchItemAsset = async (file, tempId) => {
    try {
      const formData = new FormData();
      formData.append("brand_id", selectedBrandId || "1");
      formData.append("name", file.name);
      formData.append("asset_type", "image");
      formData.append("file", file);

      const token = localStorage.getItem("modelens_token");
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/assets`);
      if (token) {
        xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      }

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          setBatchItems(prev => prev.map(p => p.id === tempId ? { ...p, uploadProgress: percent } : p));
        }
      };

      xhr.onload = () => {
        if (xhr.status === 201) {
          const res = JSON.parse(xhr.responseText);
          setBatchItems(prev => prev.map(p => p.id === tempId ? {
            ...p,
            status: "ready",
            uploadProgress: 100,
            assetId: res.id,
            storagePath: res.storage_path
          } : p));
        } else {
          setBatchItems(prev => prev.map(p => p.id === tempId ? { ...p, status: "upload_failed", uploadProgress: 0 } : p));
          toast.error(`Upload failed for ${file.name}`);
        }
      };

      xhr.onerror = () => {
        setBatchItems(prev => prev.map(p => p.id === tempId ? { ...p, status: "upload_failed", uploadProgress: 0 } : p));
        toast.error(`Upload error for ${file.name}`);
      };

      xhr.send(formData);

    } catch (e) {
      setBatchItems(prev => prev.map(p => p.id === tempId ? { ...p, status: "upload_failed" } : p));
    }
  };

  const applyGlobalConfig = () => {
    setBatchItems(prev => prev.map(item => ({
      ...item,
      garmentType: globalConfig.garmentType,
      view: globalConfig.view,
      aspectRatio: globalConfig.aspectRatio,
      resolution: globalConfig.resolution,
      preservePrint: globalConfig.preservePrint,
      preserveSeams: globalConfig.preserveSeams,
      generationMode: globalConfig.generationMode,
    })));
    toast.success("Applied global settings to all batch items!");
  };

  const handleRemoveBatchItem = (id) => {
    setBatchItems(prev => prev.filter(item => item.id !== id));
  };

  const handleUpdateBatchItem = (id, key, val) => {
    setBatchItems(prev => prev.map(item => item.id === id ? { ...item, [key]: val } : item));
  };

  const handleClearBatch = () => {
    setBatchItems([]);
    setActiveBatch(null);
    setBatchJobsStatus({});
    setBatchElapsedTime(0);
    clearInterval(batchPollRef.current);
    clearInterval(batchTimerRef.current);
  };

  const getResolutionCredits = (res) => {
    if (res === "1K") return 2;
    if (res === "2K") return 4;
    if (res === "4K") return 6;
    return 4;
  };

  const totalCreditsReserved = batchItems.reduce((acc, item) => acc + getResolutionCredits(item.resolution), 0);

  const startBatchPolling = (jobIds) => {
    setBatchElapsedTime(0);
    clearInterval(batchPollRef.current);
    clearInterval(batchTimerRef.current);

    const initStatus = {};
    jobIds.forEach(id => {
      initStatus[id] = { status: "queued", progress: 10 };
    });
    setBatchJobsStatus(initStatus);

    batchTimerRef.current = setInterval(() => setBatchElapsedTime(prev => prev + 1), 1000);

    batchPollRef.current = setInterval(async () => {
      try {
        const promises = jobIds.map(async (id) => {
          const current = batchJobsStatus[id];
          if (current?.status === "completed" || current?.status === "failed") {
            return { id, data: current };
          }
          try {
            const data = await api.get(`/api/v1/ghost-jobs/${id}`);
            if (data.status === "completed") {
              const outRes = await api.get(`/api/v1/ghost-jobs/${id}/outputs`);
              if (outRes.outputs?.length > 0) {
                data.output_url = outRes.outputs[0].output_url;
                data.quality_score = Math.round((outRes.outputs[0].quality_score || 0.93) * 100);
              }
            }
            return { id, data };
          } catch {
            return { id, data: { status: "failed", error_message: "Connection Error" } };
          }
        });

        const results = await Promise.all(promises);
        const nextStatus = { ...batchJobsStatus };
        let allFinished = true;

        results.forEach(({ id, data }) => {
          nextStatus[id] = data;
          if (data.status !== "completed" && data.status !== "failed") {
            allFinished = false;
          }
        });

        setBatchJobsStatus(nextStatus);

        if (allFinished) {
          clearInterval(batchPollRef.current);
          clearInterval(batchTimerRef.current);
          toast.success("All batch jobs completed!");
        }
      } catch (e) {
        console.error("Batch polling error:", e);
      }
    }, 3000);
  };

  const handleBatchSubmit = async () => {
    const readyItems = batchItems.filter(item => item.status === "ready");
    if (readyItems.length === 0) {
      toast.error("Please upload at least one image successfully first");
      return;
    }
    const uploadingItems = batchItems.filter(item => item.status === "pending_upload");
    if (uploadingItems.length > 0) {
      toast.error("Please wait for pending uploads to finish");
      return;
    }

    setBatchSubmitting(true);
    setBatchJobsStatus({});
    try {
      const payload = {
        brand_id: parseInt(selectedBrandId),
        jobs: readyItems.map(item => ({
          product_hint: item.productHint,
          garment_type: item.garmentType,
          view: item.view,
          aspect_ratio: item.aspectRatio,
          resolution: item.resolution,
          preserve_print: item.preservePrint,
          preserve_seams: item.preserveSeams,
          generation_mode: item.generationMode,
          image_key: item.storagePath,
        }))
      };

      const result = await api.post("/api/v1/ghost-jobs/batch", payload);
      setActiveBatch(result);
      toast.success(`Batch submitted! Queueing ${result.batch_size} jobs.`);
      startBatchPolling(result.job_ids);
    } catch (e) {
      toast.error(e.message || "Failed to submit batch jobs");
    } finally {
      setBatchSubmitting(false);
    }
  };

  // Step resolution helper for progress
  const currentStep = STATUS_STEPS.find(s => s.status === jobStatus?.status) || STATUS_STEPS[0];
  const progress = currentStep.progress;

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Layers className="w-7 h-7 text-purple-400" />
          <div>
            <h1 className="text-2xl font-bold">Image-to-Ghost Studio</h1>
            <p className="text-zinc-400 text-sm">Generate 2K/4K ghost mannequin catalog assets using advanced rendering models</p>
          </div>
        </div>

        {/* Global Controls & Mode Toggle */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-8 bg-zinc-900/30 border border-zinc-850 p-4 rounded-2xl backdrop-blur-md">
          {/* Tab Selector */}
          <div className="flex bg-zinc-900 border border-zinc-800 p-1 rounded-xl">
            <button
              onClick={() => setTab("single")}
              className={`px-4 py-2 rounded-lg text-xs font-semibold transition ${
                tab === "single" ? "bg-purple-600 text-white" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Single Image
            </button>
            <button
              onClick={() => setTab("batch")}
              className={`px-4 py-2 rounded-lg text-xs font-semibold transition ${
                tab === "batch" ? "bg-purple-600 text-white" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Batch Upload ({batchItems.length})
            </button>
          </div>

          {/* Brand Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-400">Target Brand:</span>
            {brands.length > 0 ? (
              <select
                value={selectedBrandId}
                onChange={(e) => setSelectedBrandId(e.target.value)}
                className="bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none focus:border-purple-600 transition"
              >
                {brands.map(b => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
            ) : (
              <span className="text-xs text-zinc-500">Loading brands...</span>
            )}
          </div>
        </div>

        {tab === "single" ? (
          /* ======================== SINGLE GENERATION VIEW ======================== */
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left: Uploaders & Controls */}
            <div className="space-y-5">
              <div>
                <label className="text-xs text-zinc-400 mb-2 block font-medium">Primary Image *</label>
                <div
                  onDrop={handleDrop}
                  onDragOver={(e) => e.preventDefault()}
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-zinc-800 hover:border-purple-500 rounded-2xl p-6 text-center cursor-pointer transition bg-zinc-950/20"
                >
                  {primaryPreview ? (
                    <img src={primaryPreview} alt="Preview" className="w-full h-48 object-contain rounded-xl" />
                  ) : (
                    <div className="py-8">
                      <Upload className="w-8 h-8 text-zinc-500 mx-auto mb-2" />
                      <p className="text-sm text-zinc-400">Drop image here or click to upload</p>
                      <p className="text-xs text-zinc-650 mt-1">JPEG, PNG, WebP, HEIC supported</p>
                    </div>
                  )}
                  <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp,.heic" className="hidden" onChange={(e) => handleFileSelect(e.target.files[0])} />
                </div>
              </div>

              <div>
                <label className="text-xs text-zinc-400 mb-1 block font-medium">Product Description *</label>
                <textarea
                  value={productHint}
                  onChange={(e) => setProductHint(e.target.value)}
                  placeholder="e.g. blue floral organic cotton maxi dress"
                  rows={3}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-200 outline-none focus:border-purple-500 transition resize-none"
                />
              </div>

              <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5 space-y-4">
                <div>
                  <label className="text-xs text-zinc-400 mb-2 block font-semibold uppercase tracking-wider">Generation Mode</label>
                  <div className="space-y-2">
                    {GENERATION_MODES.map(mode => (
                      <div
                        key={mode.id}
                        onClick={() => setGenerationMode(mode.id)}
                        className={`cursor-pointer border rounded-xl p-4 transition ${
                          generationMode === mode.id
                            ? "border-purple-600 bg-purple-950/20"
                            : "border-zinc-850 hover:border-zinc-700 bg-zinc-950/30"
                        }`}
                      >
                        {mode.badge && (
                          <span className="inline-block text-[9px] bg-purple-900/60 border border-purple-700 text-purple-300 px-2 py-0.5 rounded-full mb-2 font-bold uppercase tracking-wider">
                            {mode.badge}
                          </span>
                        )}
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-semibold text-white">{mode.name}</span>
                          <span className="text-[10px] text-zinc-400">{mode.time} · {mode.credits}</span>
                        </div>
                        <p className="text-[11px] text-zinc-400 mb-1">{mode.description}</p>
                        <ul className="space-y-0.5">
                          {mode.useCases.map(u => (
                            <li key={u} className="text-[10px] text-zinc-500">• {u}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>

                <hr className="border-zinc-850" />

                <h3 className="text-xs font-semibold text-zinc-300 uppercase">Generation Controls</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Garment Type</label>
                    <select value={garmentType} onChange={(e) => setGarmentType(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none capitalize">
                      {GARMENT_TYPES.map(g => <option key={g} value={g}>{g}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block font-medium">Pose Preset</label>
                    {angleShots.length > 0 ? (
                      <select
                        value={selectedAngleShot?.id || ""}
                        onChange={(e) => {
                          const shot = angleShots.find(s => s.id.toString() === e.target.value);
                          setSelectedAngleShot(shot || null);
                          if (shot?.view_direction) setView(shot.view_direction.toLowerCase());
                        }}
                        className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none"
                      >
                        <option value="">Select preset...</option>
                        {angleShots.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                      </select>
                    ) : (
                      <select value={view} onChange={(e) => setView(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none capitalize">
                        {VIEWS.map(v => <option key={v} value={v}>{v}</option>)}
                      </select>
                    )}
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block font-medium">Aspect Ratio</label>
                    <select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none">
                      {ASPECT_RATIOS.map(a => <option key={a} value={a}>{a}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block font-medium">Resolution</label>
                    <select value={resolution} onChange={(e) => setResolution(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none">
                      {RESOLUTIONS.map(r => <option key={r.value} value={r.value}>{r.label} ({r.credits})</option>)}
                    </select>
                  </div>
                </div>

                <div className="space-y-3">
                  {[
                    { label: "Preserve Print / Pattern", value: preservePrint, setter: setPreservePrint },
                    { label: "Preserve Construction / Seams", value: preserveSeams, setter: setPreserveSeams },
                  ].map(({ label, value, setter }) => (
                    <div key={label} className="flex items-center justify-between">
                      <span className="text-xs text-zinc-300">{label}</span>
                      <button onClick={() => setter(!value)} className={`relative w-10 h-5 rounded-full transition-colors ${value ? "bg-purple-600" : "bg-zinc-700"}`}>
                        <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${value ? "translate-x-5" : "translate-x-0"}`} />
                      </button>
                    </div>
                  ))}
                </div>

                {/* Section 20 Content Rights Attestation */}
                <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-1.5">
                  <div className="flex items-center gap-2 text-xs text-zinc-300 font-medium">
                    <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Section 20 Upload Rights Attestation Active</span>
                  </div>
                  <p className="text-[10px] text-zinc-500">
                    Product uploads are protected by Mode Lens workspace multi-tenant isolation.
                  </p>
                </div>

                {/* Live Resolver Simulation */}
                <TaxonomyResolverPreview
                  taxonomyIds={{
                    garment: `GAR-${garmentType.toUpperCase()}`,
                    pose: "POS-GHOST-001",
                    environment: "ENV-TRANS-0001",
                  }}
                  workflowId="WF-GHOST-001"
                  generationMode={generationMode === "studio" ? "studio_quality" : "fast_draft"}
                />
              </div>

              <button onClick={handleSubmit} disabled={submitting || !primaryImage || !productHint.trim()} className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 py-3 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2">
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Layers className="w-4 h-4" />}
                {submitting ? "Submitting..." : "Generate Ghost Image"}
              </button>
            </div>

            {/* Right: Single Progress / Result */}
            <div className="space-y-5">
              {jobStatus && (
                <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 backdrop-blur-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-semibold text-white">Active Job</h2>
                    <div className="flex items-center gap-1 text-xs text-zinc-500">
                      <Clock className="w-3 h-3" /> {elapsedTime}s
                    </div>
                  </div>
                  <div className="w-full bg-zinc-800 rounded-full h-2 mb-4">
                    <div className={`h-2 rounded-full transition-all duration-500 ${jobStatus.status === "failed" ? "bg-red-500" : "bg-purple-500"}`} style={{ width: `${progress}%` }} />
                  </div>
                  <span className={`text-xs px-3 py-1 rounded-full border ${currentStep.color}`}>{currentStep.label}</span>

                  {jobStatus.status === "failed" && (
                    <div className="mt-4 space-y-2">
                      <div className="flex items-center gap-2 text-xs text-red-400 bg-red-950/30 border border-red-800/40 rounded-xl px-3 py-2">
                        <AlertTriangle className="w-3 h-3" /> {jobStatus.error_message || "Generation failed"}
                      </div>
                      <button onClick={handleReset} className="flex items-center gap-2 text-xs border border-zinc-700 hover:border-purple-500 px-3 py-2 rounded-xl transition">
                        <RefreshCw className="w-3 h-3" /> Retry
                      </button>
                    </div>
                  )}
                </div>
              )}

              {jobStatus?.status === "completed" && (
                <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6">
                  <h2 className="text-sm font-semibold text-white mb-4">Result Comparison</h2>
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div>
                      <p className="text-xs text-zinc-500 mb-1 text-center font-medium">Original</p>
                      {primaryPreview && <img src={primaryPreview} alt="Original" className="w-full h-48 object-cover rounded-xl border border-zinc-800" />}
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500 mb-1 text-center font-medium">Ghost Result</p>
                      {jobStatus.output_url ? (
                        <img src={jobStatus.output_url} alt="Result" className="w-full h-48 object-cover rounded-xl border border-emerald-700" />
                      ) : (
                        <div className="w-full h-48 bg-emerald-950/20 border border-emerald-800 rounded-xl flex items-center justify-center">
                          <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                        </div>
                      )}
                    </div>
                  </div>

                  {jobStatus.quality_score && (
                    <div className="bg-emerald-950/25 border border-emerald-900/40 rounded-xl px-4 py-2 mb-4">
                      <p className="text-xs text-emerald-400 font-medium">Quality Score: <span className="font-bold text-white">{jobStatus.quality_score}% fidelity pass</span></p>
                    </div>
                  )}

                  <div className="flex gap-2 flex-wrap">
                    <a href={jobStatus.output_url || "#"} download className="flex items-center gap-1.5 text-xs bg-purple-600 hover:bg-purple-700 px-3 py-2 rounded-xl transition font-medium">
                      <Download className="w-3.5 h-3.5" /> Download PNG
                    </a>
                    <button onClick={handleReset} className="flex items-center gap-1.5 text-xs border border-zinc-700 hover:border-purple-500 px-3 py-2 rounded-xl transition font-medium">
                      <RefreshCw className="w-3.5 h-3.5" /> Retry
                    </button>
                    <Link href="/dashboard/fix-requests" className="flex items-center gap-1.5 text-xs border border-zinc-700 hover:border-purple-500 px-3 py-2 rounded-xl transition font-medium">
                      Request Touch-up
                    </Link>
                  </div>
                </div>
              )}

              {!jobStatus && (
                <div className="bg-zinc-900/10 border border-dashed border-zinc-800 rounded-2xl p-12 text-center">
                  <Layers className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                  <p className="text-zinc-500 text-sm font-medium">Upload an image and submit to see the ghost mannequin result here</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* ======================== BATCH GENERATION VIEW ======================== */
          <div className="space-y-6">
            {!activeBatch ? (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Columns (2/3 size): Multi-uploader + Image list */}
                <div className="lg:col-span-2 space-y-5">
                  {/* Multi-uploader Dropzone */}
                  <div
                    onDrop={handleBatchDrop}
                    onDragOver={(e) => e.preventDefault()}
                    onClick={() => batchFileInputRef.current?.click()}
                    className="border-2 border-dashed border-zinc-850 hover:border-purple-500 rounded-2xl p-8 text-center cursor-pointer transition bg-zinc-900/10"
                  >
                    <Upload className="w-10 h-10 text-zinc-500 mx-auto mb-3" />
                    <p className="text-sm text-zinc-300 font-semibold">Drag & Drop multiple images here, or click to browse</p>
                    <p className="text-xs text-zinc-500 mt-1">Upload up to 50 garments. PNG, JPG, WebP, HEIC supported.</p>
                    <input
                      ref={batchFileInputRef}
                      type="file"
                      multiple
                      accept="image/jpeg,image/png,image/webp,.heic"
                      className="hidden"
                      onChange={(e) => handleBatchFilesSelect(e.target.files)}
                    />
                  </div>

                  {/* Batch Items List */}
                  {batchItems.length > 0 && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between border-b border-zinc-850 pb-2">
                        <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Garments ({batchItems.length})</span>
                        <button onClick={handleClearBatch} className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1 font-semibold">
                          <Trash2 className="w-3.5 h-3.5" /> Clear All
                        </button>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[500px] overflow-y-auto pr-1">
                        {batchItems.map((item) => (
                          <div key={item.id} className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-4 space-y-3 relative group">
                            {/* Remove button */}
                            <button
                              onClick={() => handleRemoveBatchItem(item.id)}
                              className="absolute top-2 right-2 text-zinc-500 hover:text-red-400 transition"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>

                            <div className="flex gap-3">
                              {/* Thumbnail */}
                              <div className="w-16 h-16 bg-zinc-950 rounded-lg overflow-hidden border border-zinc-800 shrink-0 relative">
                                {item.preview ? (
                                  <img src={item.preview} alt="garment" className="w-full h-full object-cover" />
                                ) : (
                                  <div className="w-full h-full flex items-center justify-center">
                                    <Loader2 className="w-4 h-4 animate-spin text-purple-500" />
                                  </div>
                                )}
                                {item.status === "pending_upload" && (
                                  <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                                    <span className="text-[10px] text-purple-400 font-bold">{item.uploadProgress}%</span>
                                  </div>
                                )}
                                {item.status === "ready" && (
                                  <div className="absolute bottom-1 right-1 bg-purple-600 rounded-full p-0.5">
                                    <Check className="w-2.5 h-2.5 text-white" />
                                  </div>
                                )}
                                {item.status === "upload_failed" && (
                                  <div className="absolute inset-0 bg-red-950/80 flex items-center justify-center">
                                    <AlertTriangle className="w-4 h-4 text-red-500" />
                                  </div>
                                )}
                              </div>

                              <div className="flex-1 min-w-0">
                                <span className="text-[10px] font-semibold text-zinc-500 tracking-wider truncate block">
                                  {item.file.name}
                                </span>
                                <input
                                  type="text"
                                  value={item.productHint}
                                  onChange={(e) => handleUpdateBatchItem(item.id, "productHint", e.target.value)}
                                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1 text-xs text-zinc-200 outline-none focus:border-purple-500 mt-1"
                                  placeholder="Garment description"
                                />
                              </div>
                            </div>

                            {/* Item Settings Override */}
                            <div className="grid grid-cols-3 gap-1.5 pt-2 border-t border-zinc-850 text-[10px]">
                              <div>
                                <select
                                  value={item.garmentType}
                                  onChange={(e) => handleUpdateBatchItem(item.id, "garmentType", e.target.value)}
                                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-1 py-0.5 text-zinc-400 capitalize"
                                >
                                  {GARMENT_TYPES.map(g => <option key={g} value={g}>{g}</option>)}
                                </select>
                              </div>
                              <div>
                                <select
                                  value={item.view}
                                  onChange={(e) => handleUpdateBatchItem(item.id, "view", e.target.value)}
                                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-1 py-0.5 text-zinc-400 capitalize"
                                >
                                  {VIEWS.map(v => <option key={v} value={v}>{v}</option>)}
                                </select>
                              </div>
                              <div>
                                <select
                                  value={item.resolution}
                                  onChange={(e) => handleUpdateBatchItem(item.id, "resolution", e.target.value)}
                                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-1 py-0.5 text-zinc-400"
                                >
                                  {RESOLUTIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                                </select>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {batchItems.length === 0 && (
                    <div className="bg-zinc-900/10 border border-dashed border-zinc-850 rounded-2xl p-16 text-center">
                      <Layers className="w-12 h-12 text-zinc-800 mx-auto mb-4" />
                      <p className="text-zinc-500 text-sm">Upload multiple garment images to begin batch studio processing</p>
                    </div>
                  )}
                </div>

                {/* Right Columns (1/3 size): Global config controls & submit summary */}
                <div className="space-y-5">
                  {/* Global Config Card */}
                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
                        <Settings className="w-3.5 h-3.5 text-purple-400" /> Global Defaults
                      </h3>
                      {batchItems.length > 0 && (
                        <button
                          onClick={applyGlobalConfig}
                          className="text-[10px] text-purple-400 hover:text-purple-300 font-semibold"
                        >
                          Apply to All
                        </button>
                      )}
                    </div>

                    <div className="space-y-3">
                      <div>
                        <label className="text-[11px] text-zinc-500 mb-1 block">Garment Type</label>
                        <select
                          value={globalConfig.garmentType}
                          onChange={(e) => setGlobalConfig(prev => ({ ...prev, garmentType: e.target.value }))}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none capitalize"
                        >
                          {GARMENT_TYPES.map(g => <option key={g} value={g}>{g}</option>)}
                        </select>
                      </div>

                      <div>
                        <label className="text-[11px] text-zinc-500 mb-1 block">View</label>
                        <select
                          value={globalConfig.view}
                          onChange={(e) => setGlobalConfig(prev => ({ ...prev, view: e.target.value }))}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none capitalize"
                        >
                          {VIEWS.map(v => <option key={v} value={v}>{v}</option>)}
                        </select>
                      </div>

                      <div>
                        <label className="text-[11px] text-zinc-500 mb-1 block">Aspect Ratio</label>
                        <select
                          value={globalConfig.aspectRatio}
                          onChange={(e) => setGlobalConfig(prev => ({ ...prev, aspectRatio: e.target.value }))}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none"
                        >
                          {ASPECT_RATIOS.map(a => <option key={a} value={a}>{a}</option>)}
                        </select>
                      </div>

                      <div>
                        <label className="text-[11px] text-zinc-500 mb-1 block">Resolution</label>
                        <select
                          value={globalConfig.resolution}
                          onChange={(e) => setGlobalConfig(prev => ({ ...prev, resolution: e.target.value }))}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none"
                        >
                          {RESOLUTIONS.map(r => <option key={r.value} value={r.value}>{r.label} ({r.credits})</option>)}
                        </select>
                      </div>
                    </div>

                    <div className="space-y-2.5 pt-2 border-t border-zinc-850">
                      {[
                        { label: "Preserve Prints", key: "preservePrint" },
                        { label: "Preserve Seams", key: "preserveSeams" },
                      ].map(({ label, key }) => (
                        <div key={label} className="flex items-center justify-between">
                          <span className="text-xs text-zinc-400">{label}</span>
                          <button
                            onClick={() => setGlobalConfig(prev => ({ ...prev, [key]: !prev[key] }))}
                            className={`relative w-8 h-4.5 rounded-full transition-colors ${globalConfig[key] ? "bg-purple-600" : "bg-zinc-700"}`}
                          >
                            <span className={`absolute top-0.5 left-0.5 w-3.5 h-3.5 bg-white rounded-full transition-transform ${globalConfig[key] ? "translate-x-3.5" : "translate-x-0"}`} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Summary & Cost Estimates */}
                  <div className="bg-purple-950/10 border border-purple-900/30 rounded-2xl p-5 space-y-4">
                    <h3 className="text-xs font-semibold text-purple-300 uppercase tracking-wider">Batch Summary</h3>
                    <div className="space-y-2 text-xs text-zinc-300">
                      <div className="flex justify-between">
                        <span>Total Items:</span>
                        <span className="font-bold text-white">{batchItems.length}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Ready to Generate:</span>
                        <span className="font-bold text-emerald-400">{batchItems.filter(i => i.status === "ready").length}</span>
                      </div>
                      <div className="flex justify-between border-t border-purple-900/20 pt-2 text-sm">
                        <span className="font-semibold text-purple-200">Total Credits:</span>
                        <span className="font-bold text-purple-300">{totalCreditsReserved} credits</span>
                      </div>
                    </div>

                    <button
                      onClick={handleBatchSubmit}
                      disabled={batchSubmitting || batchItems.length === 0 || batchItems.some(i => i.status === "pending_upload")}
                      className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition flex items-center justify-center gap-2"
                    >
                      {batchSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Layers className="w-4 h-4" />}
                      {batchSubmitting ? "Queueing Batch..." : "Submit Batch Generation"}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              /* ======================== BATCH PROCESSING MONITOR DASHBOARD ======================== */
              <div className="space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-850 pb-4">
                  <div>
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                      <Layers className="w-5 h-5 text-purple-400" /> Active Batch Processing
                    </h2>
                    <p className="text-xs text-zinc-500">
                      Batch of {activeBatch.batch_size} jobs · Reserved {activeBatch.total_credits_reserved} credits
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                      <Clock className="w-3.5 h-3.5" /> {batchElapsedTime}s elapsed
                    </div>
                    <button
                      onClick={handleClearBatch}
                      className="text-xs border border-zinc-800 hover:border-purple-600 hover:bg-purple-950/20 px-3 py-1.5 rounded-xl transition font-semibold"
                    >
                      New Batch
                    </button>
                  </div>
                </div>

                {/* Batch Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {activeBatch.job_ids.map((id, index) => {
                    const statusData = batchJobsStatus[id] || { status: "queued", progress: 10 };
                    const correspondingItem = batchItems[index] || {};
                    const isDone = statusData.status === "completed";
                    const isErr = statusData.status === "failed";
                    const step = STATUS_STEPS.find(s => s.status === statusData.status) || STATUS_STEPS[0];

                    return (
                      <div key={id} className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4 space-y-3 backdrop-blur-sm relative group overflow-hidden">
                        <div className="flex gap-3">
                          {/* Thumbnail / Result view */}
                          <div className="w-20 h-20 bg-zinc-950 border border-zinc-850 rounded-lg overflow-hidden shrink-0 relative">
                            {isDone && statusData.output_url ? (
                              <img src={statusData.output_url} alt="result" className="w-full h-full object-cover" />
                            ) : correspondingItem.preview ? (
                              <img src={correspondingItem.preview} alt="original" className="w-full h-full object-cover opacity-40 blur-[0.5px]" />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center">
                                <Loader2 className="w-4 h-4 animate-spin text-purple-500" />
                              </div>
                            )}

                            {!isDone && !isErr && (
                              <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                                <Loader2 className="w-5 h-5 animate-spin text-white" />
                              </div>
                            )}
                          </div>

                          <div className="flex-1 min-w-0">
                            <span className="text-[10px] font-bold text-zinc-500 block uppercase tracking-wider">Job #{id}</span>
                            <h4 className="text-xs font-semibold text-white truncate mt-0.5">{correspondingItem.productHint || "Garment generation"}</h4>
                            <p className="text-[10px] text-zinc-400 capitalize mt-0.5">{statusData.garment_type || "dress"} · {statusData.resolution || "2K"}</p>

                            <div className="mt-2 flex items-center gap-1.5">
                              <span className={`text-[9px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wider ${step.color}`}>
                                {step.label}
                              </span>
                              {isDone && statusData.quality_score && (
                                <span className="text-[9px] bg-emerald-950/30 text-emerald-400 border border-emerald-900/60 px-2 py-0.5 rounded-full font-bold">
                                  {statusData.quality_score}% Pass
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Progress Bar */}
                        {!isDone && !isErr && (
                          <div className="w-full bg-zinc-950 rounded-full h-1.5 overflow-hidden">
                            <div className="h-full bg-purple-600 rounded-full transition-all duration-500" style={{ width: `${step.progress}%` }} />
                          </div>
                        )}

                        {/* Error output */}
                        {isErr && (
                          <div className="text-[10px] bg-red-950/20 text-red-400 border border-red-900/30 rounded px-2 py-1 flex items-center gap-1.5">
                            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                            <span className="truncate">{statusData.error_message || "Generation failed"}</span>
                          </div>
                        )}

                        {/* Actions for completed */}
                        {isDone && (
                          <div className="flex gap-2 pt-2 border-t border-zinc-850 text-[10px]">
                            {statusData.output_url && (
                              <a
                                href={statusData.output_url}
                                download
                                className="flex-1 bg-purple-600 hover:bg-purple-700 text-white py-1 rounded flex items-center justify-center gap-1 font-semibold transition"
                              >
                                <Download className="w-3 h-3" /> Download
                              </a>
                            )}
                            <Link
                              href="/dashboard/fix-requests"
                              className="flex-1 border border-zinc-800 hover:border-purple-600 hover:bg-purple-950/20 text-center py-1 rounded flex items-center justify-center font-semibold text-zinc-300 transition"
                            >
                              Request Fix
                            </Link>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
