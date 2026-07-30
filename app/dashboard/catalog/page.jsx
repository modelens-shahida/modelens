"use client";
import React, { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { Upload, Grid, Loader2, CheckCircle2, Download, RefreshCw, AlertTriangle, Clock, X, Plus, Shirt } from "lucide-react";
import toast from "react-hot-toast";
import Link from "next/link";

const MODEL_IDENTITIES = ["Maya", "Elena", "Marcus", "Custom Reference"];
const POSES = ["Full-body 85mm", "Catalog Standing", "Sitting", "Dynamic Walking"];
const BACKGROUNDS = ["Soft Front Studio", "White Cyclorama", "Warm Studio", "Transparent"];
const FASHN_MODES = [
  { id: "product_to_model", name: "Product-to-Model", desc: "New model & pose generation" },
  { id: "tryon_max", name: "Try-On Max", desc: "Existing model try-on" },
];

const SKU_STATUSES = {
  queued: { label: "Queued", color: "text-amber-400 bg-amber-900/30 border-amber-700" },
  segmenting: { label: "Segmenting SAM2", color: "text-blue-400 bg-blue-900/30 border-blue-700" },
  generating: { label: "Generating FASHN", color: "text-purple-400 bg-purple-900/30 border-purple-700" },
  qa_passed: { label: "QA Passed", color: "text-emerald-400 bg-emerald-900/30 border-emerald-700" },
  failed: { label: "Failed", color: "text-red-400 bg-red-900/30 border-red-700" },
};

export default function CatalogStudioPage() {
  const [productFiles, setProductFiles] = useState([]);
  const [skuTags, setSkuTags] = useState({});
  const [modelIdentity, setModelIdentity] = useState("Maya");
  const [customModelFile, setCustomModelFile] = useState(null);
  const [customModelPreview, setCustomModelPreview] = useState(null);
  const [pose, setPose] = useState("Catalog Standing");
  const [background, setBackground] = useState("Soft Front Studio");
  const [fashnMode, setFashnMode] = useState("product_to_model");
  const [submitting, setSubmitting] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [skuStatuses, setSkuStatuses] = useState({});
  const [elapsedTime, setElapsedTime] = useState(0);
  const [outputImages, setOutputImages] = useState([]);
  const fileInputRef = useRef(null);
  const customModelRef = useRef(null);
  const pollRef = useRef(null);
  const timerRef = useRef(null);

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
    timerRef.current = setInterval(() => setElapsedTime(prev => prev + 1), 1000);
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.get(`/v1/catalog-jobs/${jobId}`);
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

  useEffect(() => () => { clearInterval(pollRef.current); clearInterval(timerRef.current); }, []);

  const handleSubmit = async () => {
    if (productFiles.length === 0) { toast.error("Please upload at least one product image"); return; }
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
      formData.append("pose", pose);
      formData.append("background", background);
      formData.append("fashn_mode", fashnMode);

      const result = await api.post("/v1/catalog-jobs", formData);
      setJobStatus({ status: "queued", ...result });
      const initStatuses = {};
      productFiles.forEach((_, i) => initStatuses[i] = "queued");
      setSkuStatuses(initStatuses);
      startPolling(result.id || result.job_id);
      toast.success(`Catalog job queued! ${productFiles.length} SKUs processing.`);
    } catch (e) {
      toast.error(e.message || "Failed to submit catalog job");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => { setJobStatus(null); setElapsedTime(0); setOutputImages([]); setSkuStatuses({}); };

  const completedCount = Object.values(skuStatuses).filter(s => s === "qa_passed").length;
  const totalCount = productFiles.length;
  const progress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Shirt className="w-7 h-7 text-purple-400" />
          <div>
            <h1 className="text-2xl font-bold">Flatlay-to-Catalog Studio</h1>
            <p className="text-zinc-400 text-sm">Virtual try-on engine powered by FASHN API — Product-to-Model & Try-On Max</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Product Upload */}
          <div className="lg:col-span-1 space-y-5">
            <div>
              <label className="text-xs text-zinc-400 mb-2 block">Product Images * <span className="text-zinc-600">(up to 50 SKUs)</span></label>
              <div
                onClick={() => fileInputRef.current?.click()}
                onDrop={(e) => { e.preventDefault(); handleProductFiles(e.dataTransfer.files); }}
                onDragOver={(e) => e.preventDefault()}
                className="border-2 border-dashed border-zinc-700 hover:border-purple-500 rounded-2xl p-4 cursor-pointer transition min-h-32"
              >
                {productFiles.length === 0 ? (
                  <div className="text-center py-6">
                    <Upload className="w-8 h-8 text-zinc-500 mx-auto mb-2" />
                    <p className="text-sm text-zinc-400">Drop product images here</p>
                    <p className="text-xs text-zinc-600 mt-1">Flat-lay, ghost, or hanger photos</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-3 gap-2">
                    {productFiles.map((f, i) => (
                      <div key={i} className="relative group">
                        <img src={URL.createObjectURL(f)} alt="" className="w-full h-20 object-cover rounded-lg border border-zinc-700" />
                        <button onClick={(e) => { e.stopPropagation(); removeProduct(i); }} className="absolute -top-1 -right-1 bg-red-600 rounded-full w-4 h-4 flex items-center justify-center opacity-0 group-hover:opacity-100 transition">
                          <X className="w-2.5 h-2.5" />
                        </button>
                        <input
                          type="text"
                          placeholder={`SKU-${i+1}`}
                          value={skuTags[i] || ""}
                          onChange={(e) => { e.stopPropagation(); setSkuTags(prev => ({...prev, [i]: e.target.value})); }}
                          onClick={(e) => e.stopPropagation()}
                          className="w-full mt-1 bg-zinc-900 border border-zinc-700 rounded-lg px-2 py-0.5 text-xs text-zinc-300 outline-none"
                        />
                      </div>
                    ))}
                    {productFiles.length < 50 && (
                      <div className="w-full h-20 border border-dashed border-zinc-600 rounded-lg flex items-center justify-center">
                        <Plus className="w-5 h-5 text-zinc-600" />
                      </div>
                    )}
                  </div>
                )}
                <input ref={fileInputRef} type="file" accept="image/*" multiple className="hidden" onChange={(e) => handleProductFiles(e.target.files)} />
              </div>
              <p className="text-xs text-zinc-500 mt-1">{productFiles.length}/50 products uploaded</p>
            </div>
          </div>

          {/* Middle: Model & Studio Controls */}
          <div className="lg:col-span-1 space-y-5">
            {/* FASHN Mode */}
            <div>
              <label className="text-xs text-zinc-400 mb-2 block">FASHN Engine Mode</label>
              <div className="space-y-2">
                {FASHN_MODES.map(mode => (
                  <div key={mode.id} onClick={() => setFashnMode(mode.id)} className={`cursor-pointer border-2 rounded-xl p-3 transition ${fashnMode === mode.id ? "border-purple-600 bg-purple-950/20" : "border-zinc-800 hover:border-zinc-600"}`}>
                    <p className="text-sm font-semibold text-white">{mode.name}</p>
                    <p className="text-xs text-zinc-500">{mode.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Model Identity */}
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Model Identity</label>
              <select value={modelIdentity} onChange={(e) => setModelIdentity(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-200 outline-none mb-2">
                {MODEL_IDENTITIES.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              {modelIdentity === "Custom Reference" && (
                <div onClick={() => customModelRef.current?.click()} className="border border-dashed border-zinc-700 hover:border-purple-500 rounded-xl p-3 cursor-pointer transition text-center">
                  {customModelPreview ? (
                    <img src={customModelPreview} alt="model" className="w-16 h-16 object-cover rounded-lg mx-auto" />
                  ) : (
                    <p className="text-xs text-zinc-500">Upload custom model reference</p>
                  )}
                  <input ref={customModelRef} type="file" accept="image/*" className="hidden" onChange={(e) => handleCustomModel(e.target.files[0])} />
                </div>
              )}
            </div>

            {/* Pose & Background */}
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Pose & Framing</label>
              <select value={pose} onChange={(e) => setPose(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-200 outline-none mb-3">
                {POSES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
              <label className="text-xs text-zinc-400 mb-1 block">Background & Lighting</label>
              <select value={background} onChange={(e) => setBackground(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-200 outline-none">
                {BACKGROUNDS.map(b => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>

            <button onClick={handleSubmit} disabled={submitting || productFiles.length === 0} className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 py-3 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2">
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shirt className="w-4 h-4" />}
              {submitting ? "Submitting..." : `Generate ${productFiles.length} Catalog Images`}
            </button>
          </div>

          {/* Right: Progress + Output */}
          <div className="lg:col-span-1 space-y-5">
            {jobStatus ? (
              <>
                {/* Batch Progress */}
                <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-semibold text-white">Batch Progress</h2>
                    <span className="flex items-center gap-1 text-xs text-zinc-500"><Clock className="w-3 h-3" /> {elapsedTime}s</span>
                  </div>
                  <div className="w-full bg-zinc-800 rounded-full h-2 mb-2">
                    <div className="h-2 rounded-full bg-purple-500 transition-all duration-500" style={{ width: `${progress}%` }} />
                  </div>
                  <p className="text-xs text-zinc-400 mb-4">{completedCount}/{totalCount} SKUs completed</p>

                  {/* Per-SKU Status */}
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {productFiles.map((f, i) => {
                      const status = skuStatuses[i] || "queued";
                      const cfg = SKU_STATUSES[status] || SKU_STATUSES.queued;
                      return (
                        <div key={i} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <img src={URL.createObjectURL(f)} alt="" className="w-8 h-8 rounded object-cover border border-zinc-700" />
                            <span className="text-xs text-zinc-300">{skuTags[i] || `SKU-${i+1}`}</span>
                          </div>
                          <span className={`text-xs px-2 py-0.5 rounded-full border ${cfg.color}`}>{cfg.label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Output Gallery */}
                {outputImages.length > 0 && (
                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5">
                    <div className="flex items-center justify-between mb-3">
                      <h2 className="text-sm font-semibold text-white">Catalog Output</h2>
                      <a href="#" download className="flex items-center gap-1.5 text-xs bg-purple-600 hover:bg-purple-700 px-3 py-1.5 rounded-xl transition">
                        <Download className="w-3 h-3" /> Download ZIP
                      </a>
                    </div>
                    <div className="grid grid-cols-2 gap-2 mb-3">
                      {outputImages.map((img, i) => (
                        <div key={i} className="relative">
                          <img src={img.url} alt={`output-${i}`} className="w-full h-28 object-cover rounded-xl border border-zinc-700" />
                          {img.quality_score && (
                            <span className="absolute bottom-1 right-1 text-xs bg-black/70 text-emerald-400 px-1.5 py-0.5 rounded-full">{img.quality_score}%</span>
                          )}
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <button onClick={handleReset} className="flex-1 flex items-center justify-center gap-1.5 text-xs border border-zinc-700 hover:border-purple-500 py-2 rounded-xl transition">
                        <RefreshCw className="w-3 h-3" /> New Batch
                      </button>
                      <Link href="/dashboard/fix-requests" className="flex-1 flex items-center justify-center text-xs border border-zinc-700 hover:border-purple-500 py-2 rounded-xl transition">
                        Bulk Touch-up
                      </Link>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="bg-zinc-900/20 border border-dashed border-zinc-800 rounded-2xl p-12 text-center">
                <Grid className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                <p className="text-zinc-500 text-sm">Upload products and submit to see catalog results here</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
