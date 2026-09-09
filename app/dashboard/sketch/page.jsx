"use client";
import React, { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { 
  Upload, PenTool, Loader2, CheckCircle2, Download, 
  RefreshCw, AlertTriangle, Clock, X, Plus, Sparkles, Layers 
} from "lucide-react";
import toast from "react-hot-toast";
import Link from "next/link";
import TaxonomyResolverPreview from "@/components/dashboard/TaxonomyResolverPreview";
import SketchProductStudio from "@/components/dashboard/SketchProductStudio";
import { ShieldCheck } from "lucide-react";

const MODEL_TIERS = [
  {
    id: "fast_draft",
    name: "Fast Draft",
    time: "~15 sec",
    credits: "1-2 credits",
    description: "Best for quick previews and early concept testing.",
    badge: null,
    useCases: ["Early previews", "Testing briefs", "Background exploration", "Pose exploration", "Rapid iterations"],
  },
  {
    id: "studio_quality",
    name: "Studio Quality",
    time: "~45 sec",
    credits: "4-5 credits",
    description: "Best for final-quality renders and higher garment accuracy.",
    badge: "Recommended for final images",
    recommended: true,
    useCases: [
      "Sketch-to-Image",
      "Final on-model output",
      "Ghost mannequin output",
      "Construction-heavy garments",
      "Printed or embellished garments"
    ],
  },
];

const OUTPUT_MODES = ["On-Model", "Ghost Mannequin", "Product Only", "Flat-Lay"];
const ASPECT_RATIOS = ["1:1", "3:4", "4:5", "9:16"];
const RESOLUTIONS = [
  { value: "1K", label: "1K", credits: "1-2 credits" },
  { value: "2K", label: "2K", credits: "3-4 credits" },
  { value: "4K", label: "4K", credits: "5-7 credits" },
];

const STATUS_STEPS = [
  { status: "queued", label: "Queued", color: "text-amber-400 bg-amber-900/40 border-amber-700", progress: 10 },
  { status: "preprocessing", label: "Preprocessing References", color: "text-blue-400 bg-blue-900/40 border-blue-700", progress: 30 },
  { status: "generating", label: "Generating Render", color: "text-purple-400 bg-purple-900/40 border-purple-700", progress: 65 },
  { status: "quality_check", label: "Quality Check", color: "text-indigo-400 bg-indigo-900/40 border-indigo-700", progress: 85 },
  { status: "completed", label: "Completed", color: "text-emerald-400 bg-emerald-900/40 border-emerald-700", progress: 100 },
  { status: "failed", label: "Failed", color: "text-red-400 bg-red-900/40 border-red-700", progress: 100 },
];

function MultiFileUploader({ label, maxFiles, accept, files, onFilesChange, hint }) {
  const inputRef = useRef(null);
  const handleFiles = (newFiles) => {
    const combined = [...files, ...Array.from(newFiles)].slice(0, maxFiles);
    onFilesChange(combined);
  };
  return (
    <div>
      <div className="flex justify-between items-center mb-1.5">
        <label className="text-xs font-semibold text-zinc-300">{label}</label>
        <span className="text-[10px] text-zinc-500">{files.length}/{maxFiles} {hint && `• ${hint}`}</span>
      </div>
      <div className="border border-dashed border-zinc-700 hover:border-purple-500 rounded-xl p-4 transition cursor-pointer" onClick={() => inputRef.current?.click()}>
        <div className="flex flex-wrap gap-2">
          {files.map((f, i) => (
            <div key={i} className="relative group">
              <img src={URL.createObjectURL(f)} alt="" className="w-14 h-14 object-cover rounded-lg border border-zinc-700" />
              <button onClick={(e) => { e.stopPropagation(); onFilesChange(files.filter((_, fi) => fi !== i)); }} className="absolute -top-1 -right-1 bg-red-600 rounded-full w-4 h-4 flex items-center justify-center opacity-0 group-hover:opacity-100 transition">
                <X className="w-2.5 h-2.5" />
              </button>
            </div>
          ))}
          {files.length < maxFiles && (
            <div className="w-14 h-14 border border-dashed border-zinc-600 rounded-lg flex items-center justify-center">
              <Plus className="w-5 h-5 text-zinc-600" />
            </div>
          )}
        </div>
        {files.length === 0 && <p className="text-xs text-zinc-500 mt-2 text-center">Click to upload</p>}
      </div>
      <input ref={inputRef} type="file" accept={accept} multiple className="hidden" onChange={(e) => handleFiles(e.target.files)} />
    </div>
  );
}

export default function SketchStudioPage() {
  const [activeMainTab, setActiveMainTab] = useState("studio"); // 'studio' | 'legacy'
  const [sketchFiles, setSketchFiles] = useState([]);
  const [fabricFiles, setFabricFiles] = useState([]);
  const [printFiles, setPrintFiles] = useState([]);
  const [constructionFiles, setConstructionFiles] = useState([]);
  const [modelTier, setModelTier] = useState("studio_quality");
  const [outputMode, setOutputMode] = useState("On-Model");
  const [aspectRatio, setAspectRatio] = useState("3:4");
  const [resolution, setResolution] = useState("2K");
  const [productDesc, setProductDesc] = useState("");
  const [materialDesc, setMaterialDesc] = useState("");
  const [modelBrief, setModelBrief] = useState("");
  const [backgroundBrief, setBackgroundBrief] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [angleShots, setAngleShots] = useState([]);
  const [selectedAngleShot, setSelectedAngleShot] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  const startPolling = (jobId) => {
    setElapsedTime(0);
    timerRef.current = setInterval(() => setElapsedTime(t => t + 1), 1000);
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/api/v1/sketch-jobs/${jobId}`);
        setJobStatus(res);
        if (res.status === "completed" || res.status === "failed") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          if (res.status === "completed") toast.success("Sketch render completed!");
          else toast.error("Sketch render failed");
        }
      } catch {
        // ignore poll errors
      }
    }, 3000);
  };

  useEffect(() => {
    return () => {
      clearInterval(pollRef.current);
      clearInterval(timerRef.current);
    };
  }, []);

  useEffect(() => {
    api.get("/api/v1/angle-shots?limit=100").then(data => {
      if (Array.isArray(data)) setAngleShots(data);
    }).catch(() => {});
  }, []);

  const handleSubmit = async () => {
    if (sketchFiles.length === 0) { toast.error("Please upload at least one sketch"); return; }
    if (!productDesc.trim()) { toast.error("Please enter a product description"); return; }
    setSubmitting(true);
    setJobStatus(null);
    try {
      const formData = new FormData();
      sketchFiles.forEach(f => formData.append("sketches", f));
      fabricFiles.forEach(f => formData.append("fabric_refs", f));
      printFiles.forEach(f => formData.append("print_refs", f));
      constructionFiles.forEach(f => formData.append("construction_refs", f));
      formData.append("model_tier", modelTier);
      formData.append("output_mode", outputMode);
      formData.append("aspect_ratio", aspectRatio);
      formData.append("resolution", resolution);
      formData.append("product_description", productDesc);
      formData.append("material_description", materialDesc);
      formData.append("model_brief", modelBrief);
      formData.append("background_brief", backgroundBrief);
      if (selectedAngleShot) {
        formData.append("angle_shot_code", selectedAngleShot.code || "");
        formData.append("angle_shot_version", selectedAngleShot.version || 1);
      }

      const result = await api.post("/api/v1/sketch-jobs", formData);
      setJobStatus({ status: "queued", ...result });
      startPolling(result.id || result.job_id);
      toast.success(`Sketch job queued! ID: #${result.id || result.job_id}`);
    } catch (e) {
      toast.error(e.message || "Failed to submit sketch job");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => { setJobStatus(null); setElapsedTime(0); };
  const currentStep = STATUS_STEPS.find(s => s.status === jobStatus?.status) || STATUS_STEPS[0];

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Navigation Header & Tab Switcher */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800/80 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-950/60 border border-purple-500/40 flex items-center justify-center text-purple-400 shadow-inner">
              <PenTool className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Sketch-to-Product Generative CAD Studio</h1>
              <p className="text-xs text-zinc-400">WF-SKETCH-001 • ControlNet Edge Guidance, 8 Fabric Textures & Pantone Colorways</p>
            </div>
          </div>

          <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-xl p-1 gap-1 self-start sm:self-auto">
            <button
              onClick={() => setActiveMainTab("studio")}
              className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
                activeMainTab === "studio"
                  ? "bg-purple-600 text-white shadow-md"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              CAD Generative Studio
            </button>
            <button
              onClick={() => setActiveMainTab("legacy")}
              className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
                activeMainTab === "legacy"
                  ? "bg-purple-600 text-white shadow-md"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              Multi-Reference Briefs
            </button>
          </div>
        </div>

        {/* Tab 1: State-of-the-Art CAD Generative Studio */}
        {activeMainTab === "studio" ? (
          <SketchProductStudio />
        ) : (
          /* Tab 2: Legacy Multi-Reference Form */
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: Uploaders */}
            <div className="space-y-5 lg:col-span-1">
              <MultiFileUploader label="Sketch References *" maxFiles={12} accept="image/*" files={sketchFiles} onFilesChange={setSketchFiles} hint="CAD or lineart sketches" />
              <MultiFileUploader label="Material / Fabric References" maxFiles={4} accept="image/*" files={fabricFiles} onFilesChange={setFabricFiles} hint="Controls texture, sheen, drape" />
              <MultiFileUploader label="Print References" maxFiles={4} accept="image/*" files={printFiles} onFilesChange={setPrintFiles} hint="Controls pattern motif & color" />
              <MultiFileUploader label="Construction Details" maxFiles={8} accept="image/*" files={constructionFiles} onFilesChange={setConstructionFiles} hint="Collar, sleeve, hem references" />
            </div>

            {/* Middle: Controls & Briefs */}
            <div className="space-y-5 lg:col-span-1">
              <div>
                <label className="text-xs text-zinc-400 mb-2 block font-medium">Generation Mode</label>
                <div className="space-y-2">
                  {MODEL_TIERS.map(tier => (
                    <div
                      key={tier.id}
                      onClick={() => setModelTier(tier.id)}
                      className={`cursor-pointer border-2 rounded-xl p-4 transition ${
                        modelTier === tier.id ? "border-purple-500 bg-purple-950/20" : "border-zinc-800 bg-zinc-900/30 hover:border-zinc-700"
                      }`}
                    >
                      <div className="flex justify-between items-center">
                        <span className="font-semibold text-sm">{tier.name}</span>
                        {tier.badge && <span className="text-[10px] bg-purple-900/60 text-purple-300 border border-purple-700 px-2 py-0.5 rounded-full">{tier.badge}</span>}
                      </div>
                      <p className="text-xs text-zinc-400 mt-1">{tier.description}</p>
                      <p className="text-[10px] text-zinc-500 mt-1">{tier.time} • {tier.credits}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs text-zinc-400 mb-1 block font-medium">Output Mode</label>
                <div className="grid grid-cols-2 gap-2">
                  {OUTPUT_MODES.map(mode => (
                    <button
                      key={mode}
                      onClick={() => setOutputMode(mode)}
                      className={`py-2 px-3 text-xs rounded-xl border transition cursor-pointer ${
                        outputMode === mode ? "border-purple-500 bg-purple-950/40 text-white font-semibold" : "border-zinc-800 bg-zinc-900/20 text-zinc-400 hover:border-zinc-700"
                      }`}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-400 mb-1.5 block font-medium">Aspect Ratio</label>
                  <select value={aspectRatio} onChange={e => setAspectRatio(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white">
                    {ASPECT_RATIOS.map(ar => <option key={ar} value={ar}>{ar}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-400 mb-1.5 block font-medium">Resolution</label>
                  <select value={resolution} onChange={e => setResolution(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white">
                    {RESOLUTIONS.map(r => <option key={r.value} value={r.value}>{r.label} ({r.credits})</option>)}
                  </select>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-xs text-zinc-400 mb-1 block font-medium">Product Description *</label>
                  <textarea value={productDesc} onChange={e => setProductDesc(e.target.value)} rows={2} placeholder="e.g. Silk midi wrap dress with pleated skirt..." className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-3 text-xs text-white placeholder-zinc-500 resize-none" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 mb-1 block font-medium">Material / Finish Notes</label>
                  <input value={materialDesc} onChange={e => setMaterialDesc(e.target.value)} placeholder="e.g. 100% silk charmeuse, matte sheen" className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white placeholder-zinc-500" />
                </div>
                {outputMode === "On-Model" && (
                  <div>
                    <label className="text-xs text-zinc-400 mb-1 block font-medium">Model Brief</label>
                    <input value={modelBrief} onChange={e => setModelBrief(e.target.value)} placeholder="e.g. High fashion, studio neutral pose" className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white placeholder-zinc-500" />
                  </div>
                )}
              </div>

              <button onClick={handleSubmit} disabled={submitting} className="w-full py-3 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-semibold rounded-xl text-sm transition flex items-center justify-center gap-2 cursor-pointer">
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <PenTool className="w-4 h-4" />}
                {submitting ? "Submitting..." : "Generate from Sketch"}
              </button>
            </div>

            {/* Right: Output & Status */}
            <div className="space-y-5 lg:col-span-1">
              {jobStatus ? (
                <>
                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5">
                    <div className="flex justify-between items-center mb-3">
                      <span className="text-xs text-zinc-400">Job #{jobStatus.id || jobStatus.job_id}</span>
                      <span className={`text-xs px-2.5 py-0.5 rounded-full border font-medium ${currentStep.color}`}>
                        {currentStep.label}
                      </span>
                    </div>
                    <div className="w-full bg-zinc-800 rounded-full h-2 mb-3">
                      <div className="bg-purple-600 h-2 rounded-full transition-all duration-500" style={{ width: `${currentStep.progress}%` }} />
                    </div>
                    <div className="flex justify-between text-xs text-zinc-500">
                      <span>Elapsed: {elapsedTime}s</span>
                      <span>Tier: {modelTier}</span>
                    </div>

                    {jobStatus.status === "failed" && (
                      <div className="mt-3 bg-red-950/40 border border-red-800 rounded-xl p-3">
                        <div className="flex items-center gap-2 text-red-400 text-xs font-semibold mb-1">
                          <AlertTriangle className="w-3.5 h-3.5" /> Render Failed
                        </div>
                        <p className="text-[11px] text-zinc-400 mb-2">{jobStatus.error_message || "An error occurred during generation"}</p>
                        <button onClick={handleSubmit} className="text-xs bg-red-800 hover:bg-red-700 text-white px-3 py-1.5 rounded-lg flex items-center gap-1 cursor-pointer">
                          <RefreshCw className="w-3 h-3" /> Retry
                        </button>
                      </div>
                    )}
                  </div>

                  {jobStatus.status === "completed" && (
                    <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5">
                      <h2 className="text-sm font-semibold text-white mb-3">Sketch vs. Render</h2>
                      <div className="grid grid-cols-2 gap-2 mb-3">
                        <div>
                          <p className="text-xs text-zinc-500 mb-1 text-center">Sketch</p>
                          {sketchFiles[0] && <img src={URL.createObjectURL(sketchFiles[0])} alt="sketch" className="w-full h-36 object-contain rounded-xl border border-zinc-700 bg-zinc-800" />}
                        </div>
                        <div>
                          <p className="text-xs text-zinc-500 mb-1 text-center">Render</p>
                          {jobStatus.output_url ? (
                            <img src={jobStatus.output_url} alt="render" className="w-full h-36 object-cover rounded-xl border border-emerald-700" />
                          ) : (
                            <div className="w-full h-36 bg-emerald-950/30 border border-emerald-800 rounded-xl flex items-center justify-center">
                              <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                            </div>
                          )}
                        </div>
                      </div>
                      {jobStatus.quality_score && (
                        <div className="bg-emerald-950/30 border border-emerald-800/40 rounded-xl px-3 py-2 mb-3">
                          <p className="text-xs text-emerald-300">Quality Score: <span className="font-bold">{jobStatus.quality_score}%</span></p>
                        </div>
                      )}
                      <div className="flex gap-2 flex-wrap">
                        <a href={jobStatus.output_url || "#"} download className="flex items-center gap-1.5 text-xs bg-purple-600 hover:bg-purple-700 px-3 py-2 rounded-xl transition">
                          <Download className="w-3 h-3" /> Download PNG
                        </a>
                        <button onClick={handleReset} className="flex items-center gap-1.5 text-xs border border-zinc-700 hover:border-purple-500 px-3 py-2 rounded-xl transition cursor-pointer">
                          <RefreshCw className="w-3 h-3" /> New Render
                        </button>
                        <Link href="/dashboard/fix-requests" className="flex items-center gap-1.5 text-xs border border-zinc-700 hover:border-purple-500 px-3 py-2 rounded-xl transition">
                          Touch-up
                        </Link>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="bg-zinc-900/20 border border-dashed border-zinc-800 rounded-2xl p-12 text-center">
                  <PenTool className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                  <p className="text-zinc-500 text-sm">Upload sketches and submit to see the render result here</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
