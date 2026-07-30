"use client";
import React, { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { Upload, PenTool, Loader2, CheckCircle2, Download, RefreshCw, AlertTriangle, Clock, X, Plus } from "lucide-react";
import toast from "react-hot-toast";
import Link from "next/link";

const MODEL_TIERS = [
  { id: "v1", name: "V1 Fast", model: "Gemini 3.1 Flash", credits: "1-2 credits", description: "Rapid design previews" },
  { id: "v2", name: "V2 Pro", model: "Gemini 3 Pro", credits: "4-5 credits", description: "Detailed multi-reference renders" },
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
      <label className="text-xs text-zinc-400 mb-1 block">{label} <span className="text-zinc-600">(max {maxFiles})</span></label>
      {hint && <p className="text-xs text-zinc-600 mb-2">{hint}</p>}
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
  const [sketchFiles, setSketchFiles] = useState([]);
  const [fabricFiles, setFabricFiles] = useState([]);
  const [printFiles, setPrintFiles] = useState([]);
  const [constructionFiles, setConstructionFiles] = useState([]);
  const [modelTier, setModelTier] = useState("v1");
  const [outputMode, setOutputMode] = useState("On-Model");
  const [aspectRatio, setAspectRatio] = useState("3:4");
  const [resolution, setResolution] = useState("2K");
  const [productDesc, setProductDesc] = useState("");
  const [materialDesc, setMaterialDesc] = useState("");
  const [modelBrief, setModelBrief] = useState("");
  const [backgroundBrief, setBackgroundBrief] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  const startPolling = (jobId) => {
    setElapsedTime(0);
    timerRef.current = setInterval(() => setElapsedTime(prev => prev + 1), 1000);
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.get(`/v1/sketch-jobs/${jobId}`);
        setJobStatus(status);
        if (status.status === "completed" || status.status === "failed") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
        }
      } catch {}
    }, 2000);
  };

  useEffect(() => () => { clearInterval(pollRef.current); clearInterval(timerRef.current); }, []);

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

      const result = await api.post("/v1/sketch-jobs", formData);
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
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <PenTool className="w-7 h-7 text-purple-400" />
          <div>
            <h1 className="text-2xl font-bold">Sketch-to-Image Studio</h1>
            <p className="text-zinc-400 text-sm">V1 (Gemini 3.1 Flash) for previews • V2 (Gemini 3 Pro) for detailed renders</p>
          </div>
        </div>

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
            {/* Model Tier */}
            <div>
              <label className="text-xs text-zinc-400 mb-2 block">Model Tier</label>
              <div className="space-y-2">
                {MODEL_TIERS.map(tier => (
                  <div key={tier.id} onClick={() => setModelTier(tier.id)} className={`cursor-pointer border-2 rounded-xl p-3 transition ${modelTier === tier.id ? "border-purple-600 bg-purple-950/20" : "border-zinc-800 hover:border-zinc-600"}`}>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-white">{tier.name}</span>
                      <span className="text-xs text-purple-400">{tier.credits}</span>
                    </div>
                    <p className="text-xs text-zinc-500">{tier.model} — {tier.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Output Mode */}
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Output Mode</label>
              <select value={outputMode} onChange={(e) => setOutputMode(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-200 outline-none">
                {OUTPUT_MODES.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>

            {/* Aspect Ratio & Resolution */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Aspect Ratio</label>
                <select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none">
                  {ASPECT_RATIOS.map(a => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Resolution</label>
                <select value={resolution} onChange={(e) => setResolution(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none">
                  {RESOLUTIONS.map(r => <option key={r.value} value={r.value}>{r.label} ({r.credits})</option>)}
                </select>
              </div>
            </div>

            {/* Text Briefs */}
            {[
              { label: "Product Description *", value: productDesc, setter: setProductDesc, placeholder: "e.g. navy blue wool blazer with double buttons" },
              { label: "Material Description", value: materialDesc, setter: setMaterialDesc, placeholder: "e.g. 100% merino wool, matte finish" },
              { label: "Model Brief", value: modelBrief, setter: setModelBrief, placeholder: "e.g. standing pose, neutral expression" },
              { label: "Background & Lighting", value: backgroundBrief, setter: setBackgroundBrief, placeholder: "e.g. studio white background, soft light" },
            ].map(({ label, value, setter, placeholder }) => (
              <div key={label}>
                <label className="text-xs text-zinc-400 mb-1 block">{label}</label>
                <textarea value={value} onChange={(e) => setter(e.target.value)} placeholder={placeholder} rows={2} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none focus:border-purple-500 transition resize-none" />
              </div>
            ))}

            <button onClick={handleSubmit} disabled={submitting || sketchFiles.length === 0 || !productDesc.trim()} className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 py-3 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2">
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <PenTool className="w-4 h-4" />}
              {submitting ? "Submitting..." : "Generate Render"}
            </button>
          </div>

          {/* Right: Progress + Result */}
          <div className="space-y-5 lg:col-span-1">
            {jobStatus ? (
              <>
                <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-semibold text-white">Active Job</h2>
                    <span className="flex items-center gap-1 text-xs text-zinc-500"><Clock className="w-3 h-3" /> {elapsedTime}s</span>
                  </div>
                  <div className="w-full bg-zinc-800 rounded-full h-2 mb-3">
                    <div className={`h-2 rounded-full transition-all duration-500 ${jobStatus.status === "failed" ? "bg-red-500" : "bg-purple-500"}`} style={{ width: `${currentStep.progress}%` }} />
                  </div>
                  <span className={`text-xs px-3 py-1 rounded-full border ${currentStep.color}`}>{currentStep.label}</span>
                  {jobStatus.status === "failed" && (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center gap-2 text-xs text-red-400 bg-red-950/30 border border-red-800/40 rounded-xl px-3 py-2">
                        <AlertTriangle className="w-3 h-3" /> {jobStatus.error_message || "Generation failed"}
                      </div>
                      <button onClick={handleReset} className="flex items-center gap-1.5 text-xs border border-zinc-700 px-3 py-2 rounded-xl transition hover:border-purple-500">
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
                      <button onClick={handleReset} className="flex items-center gap-1.5 text-xs border border-zinc-700 hover:border-purple-500 px-3 py-2 rounded-xl transition">
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
      </div>
    </div>
  );
}
