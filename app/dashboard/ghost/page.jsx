"use client";
import React, { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { Upload, Layers, Loader2, CheckCircle2, Download, RefreshCw, AlertTriangle, Clock } from "lucide-react";
import toast from "react-hot-toast";
import Link from "next/link";

const GARMENT_TYPES = ["dress", "top", "outerwear", "pants", "jumpsuit", "full outfit"];
const VIEWS = ["front", "back", "detail"];
const ASPECT_RATIOS = ["1:1", "3:4", "4:5", "9:16"];
const RESOLUTIONS = [
  { value: "1K", label: "1K", credits: "1-2 credits" },
  { value: "2K", label: "2K", credits: "3-4 credits" },
  { value: "4K", label: "4K", credits: "5-7 credits" },
];

const STATUS_STEPS = [
  { status: "queued", label: "Queued", color: "text-amber-400 bg-amber-900/40 border-amber-700", progress: 10 },
  { status: "preprocessing", label: "Preprocessing", color: "text-blue-400 bg-blue-900/40 border-blue-700", progress: 30 },
  { status: "generating", label: "Generating (Gemini 3 Pro)", color: "text-purple-400 bg-purple-900/40 border-purple-700", progress: 65 },
  { status: "quality_check", label: "Quality Check", color: "text-indigo-400 bg-indigo-900/40 border-indigo-700", progress: 85 },
  { status: "completed", label: "Completed", color: "text-emerald-400 bg-emerald-900/40 border-emerald-700", progress: 100 },
  { status: "failed", label: "Failed", color: "text-red-400 bg-red-900/40 border-red-700", progress: 100 },
];

export default function GhostStudioPage() {
  const [primaryImage, setPrimaryImage] = useState(null);
  const [primaryPreview, setPrimaryPreview] = useState(null);
  const [productHint, setProductHint] = useState("");
  const [garmentType, setGarmentType] = useState("dress");
  const [view, setView] = useState("front");
  const [aspectRatio, setAspectRatio] = useState("3:4");
  const [resolution, setResolution] = useState("2K");
  const [preservePrint, setPreservePrint] = useState(true);
  const [preserveSeams, setPreserveSeams] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [activeJob, setActiveJob] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const pollRef = useRef(null);
  const timerRef = useRef(null);
  const fileInputRef = useRef(null);

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
    timerRef.current = setInterval(() => setElapsedTime(prev => prev + 1), 1000);
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.get(`/api/v1/ghost-jobs/${jobId}`);
        setJobStatus(status);
        if (status.status === "completed" || status.status === "failed") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
        }
      } catch {}
    }, 2000);
  };

  useEffect(() => {
    return () => {
      clearInterval(pollRef.current);
      clearInterval(timerRef.current);
    };
  }, []);

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
      formData.append("preserve_print", preservePrint);
      formData.append("preserve_seams", preserveSeams);

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

  const currentStep = STATUS_STEPS.find(s => s.status === jobStatus?.status) || STATUS_STEPS[0];
  const progress = currentStep.progress;

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Layers className="w-7 h-7 text-purple-400" />
          <div>
            <h1 className="text-2xl font-bold">Image-to-Ghost Studio</h1>
            <p className="text-zinc-400 text-sm">Powered by Gemini 3 Pro Image — Generate 2K/4K ghost mannequin catalog assets</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Uploaders & Controls */}
          <div className="space-y-5">
            {/* Primary Image Dropzone */}
            <div>
              <label className="text-xs text-zinc-400 mb-2 block">Primary Image *</label>
              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-zinc-700 hover:border-purple-500 rounded-2xl p-6 text-center cursor-pointer transition"
              >
                {primaryPreview ? (
                  <img src={primaryPreview} alt="Preview" className="w-full h-48 object-contain rounded-xl" />
                ) : (
                  <div className="py-8">
                    <Upload className="w-8 h-8 text-zinc-500 mx-auto mb-2" />
                    <p className="text-sm text-zinc-400">Drop image here or click to upload</p>
                    <p className="text-xs text-zinc-600 mt-1">JPEG, PNG, WebP, HEIC supported</p>
                  </div>
                )}
                <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp,.heic" className="hidden" onChange={(e) => handleFileSelect(e.target.files[0])} />
              </div>
            </div>

            {/* Product Hint */}
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Product Description *</label>
              <textarea
                value={productHint}
                onChange={(e) => setProductHint(e.target.value)}
                placeholder="e.g. blue floral organic cotton maxi dress"
                rows={3}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-200 outline-none focus:border-purple-500 transition resize-none"
              />
            </div>

            {/* Controls */}
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5 space-y-4">
              <h3 className="text-xs font-semibold text-zinc-300 uppercase">Generation Controls</h3>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">Garment Type</label>
                  <select value={garmentType} onChange={(e) => setGarmentType(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none capitalize">
                    {GARMENT_TYPES.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">View</label>
                  <select value={view} onChange={(e) => setView(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none capitalize">
                    {VIEWS.map(v => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">Aspect Ratio</label>
                  <select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none">
                    {ASPECT_RATIOS.map(a => <option key={a} value={a}>{a}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">Resolution</label>
                  <select value={resolution} onChange={(e) => setResolution(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none">
                    {RESOLUTIONS.map(r => <option key={r.value} value={r.value}>{r.label} ({r.credits})</option>)}
                  </select>
                </div>
              </div>

              {/* Quality Toggles */}
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
            </div>

            <button onClick={handleSubmit} disabled={submitting || !primaryImage || !productHint.trim()} className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 py-3 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2">
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Layers className="w-4 h-4" />}
              {submitting ? "Submitting..." : "Generate Ghost Image"}
            </button>
          </div>

          {/* Right: Progress + Result */}
          <div className="space-y-5">
            {/* Progress Card */}
            {jobStatus && (
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6">
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

            {/* Result Comparison */}
            {jobStatus?.status === "completed" && (
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6">
                <h2 className="text-sm font-semibold text-white mb-4">Result Comparison</h2>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div>
                    <p className="text-xs text-zinc-500 mb-1 text-center">Original</p>
                    {primaryPreview && <img src={primaryPreview} alt="Original" className="w-full h-40 object-cover rounded-xl border border-zinc-700" />}
                  </div>
                  <div>
                    <p className="text-xs text-zinc-500 mb-1 text-center">Ghost Result</p>
                    {jobStatus.output_url ? (
                      <img src={jobStatus.output_url} alt="Result" className="w-full h-40 object-cover rounded-xl border border-emerald-700" />
                    ) : (
                      <div className="w-full h-40 bg-emerald-950/30 border border-emerald-800 rounded-xl flex items-center justify-center">
                        <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                      </div>
                    )}
                  </div>
                </div>

                {/* Quality Score */}
                {jobStatus.quality_score && (
                  <div className="bg-emerald-950/30 border border-emerald-800/40 rounded-xl px-4 py-2 mb-4">
                    <p className="text-xs text-emerald-300">Quality Score: <span className="font-bold">{jobStatus.quality_score}% fidelity pass</span></p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 flex-wrap">
                  <a href={jobStatus.output_url || "#"} download className="flex items-center gap-1.5 text-xs bg-purple-600 hover:bg-purple-700 px-3 py-2 rounded-xl transition">
                    <Download className="w-3 h-3" /> Download PNG
                  </a>
                  <button onClick={handleReset} className="flex items-center gap-1.5 text-xs border border-zinc-700 hover:border-purple-500 px-3 py-2 rounded-xl transition">
                    <RefreshCw className="w-3 h-3" /> Retry
                  </button>
                  <Link href="/dashboard/fix-requests" className="flex items-center gap-1.5 text-xs border border-zinc-700 hover:border-purple-500 px-3 py-2 rounded-xl transition">
                    Request Touch-up
                  </Link>
                </div>
              </div>
            )}

            {/* Empty State */}
            {!jobStatus && (
              <div className="bg-zinc-900/20 border border-dashed border-zinc-800 rounded-2xl p-12 text-center">
                <Layers className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                <p className="text-zinc-500 text-sm">Upload an image and submit to see the ghost mannequin result here</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
