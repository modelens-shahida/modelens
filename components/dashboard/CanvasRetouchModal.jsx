"use client";

import React, { useState, useRef, useEffect } from "react";
import { assetRegistryApi } from "@/lib/assetRegistryApi";
import { 
  Wrench, 
  Paintbrush, 
  Eraser, 
  Sparkles, 
  RotateCcw, 
  X, 
  Check, 
  Loader2, 
  Sliders, 
  Layers,
  Info
} from "lucide-react";
import toast from "react-hot-toast";

const DEFECT_PRESETS = [
  { code: "ART-HAND-001", label: "Hand Deformity / Extra Finger", prompt: "perfect anatomically correct human hand, slender fingers, natural pose, detailed skin folds", denoise: 0.55 },
  { code: "ART-HAND-002", label: "Fused Fingers / Clawing", prompt: "clean separated fingers, realistic nails, natural relaxed hand posture", denoise: 0.55 },
  { code: "ART-FACE-001", label: "Facial Asymmetry / Eye Drift", prompt: "symmetrical natural eyes, realistic iris reflections, Golden Character facial structure", denoise: 0.45 },
  { code: "ART-GAR-002", label: "Garment Seam / Stitch Irregularity", prompt: "crisp clean tailored garment seam, continuous stitching, natural fabric drape", denoise: 0.50 },
  { code: "ART-GAR-003", label: "Print / Pattern Distortion", prompt: "sharp aligned textile pattern, exact motif scale, unwarped flat pattern continuity", denoise: 0.52 },
  { code: "ART-SKIN-001", label: "Over-Smoothed / Plastic Skin", prompt: "natural human skin microtexture, fine pores, authentic subsurface scattering", denoise: 0.40 },
];

export default function CanvasRetouchModal({
  isOpen,
  onClose,
  asset,
  initialDefectCode = "ART-HAND-001",
  initialBbox = null,
  onSuccess = () => {},
}) {
  const canvasRef = useRef(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [brushSize, setBrushSize] = useState(24);
  const [tool, setTool] = useState("brush"); // "brush" | "eraser"
  const [defectCode, setDefectCode] = useState(initialDefectCode);
  const [correctionPrompt, setCorrectionPrompt] = useState("");
  const [denoiseStrength, setDenoiseStrength] = useState(0.55);
  const [submitting, setSubmitting] = useState(false);
  const [hasDrawn, setHasDrawn] = useState(false);

  useEffect(() => {
    if (initialDefectCode) {
      const preset = DEFECT_PRESETS.find(p => p.code === initialDefectCode);
      if (preset) {
        setDefectCode(preset.code);
        setCorrectionPrompt(preset.prompt);
        setDenoiseStrength(preset.denoise);
      }
    }
  }, [initialDefectCode]);

  useEffect(() => {
    if (isOpen && canvasRef.current && asset?.storage_uri) {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.src = asset.storage_uri;
      img.onload = () => {
        canvas.width = 480;
        canvas.height = Math.round(480 * (img.height / img.width));
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // If initial bbox provided, pre-paint initial bounding box highlight
        if (initialBbox) {
          const bx = initialBbox.x * canvas.width;
          const by = initialBbox.y * canvas.height;
          const bw = initialBbox.width * canvas.width;
          const bh = initialBbox.height * canvas.height;
          ctx.fillStyle = "rgba(239, 68, 68, 0.4)";
          ctx.fillRect(bx, by, bw, bh);
          setHasDrawn(true);
        }
      };
    }
  }, [isOpen, asset, initialBbox]);

  if (!isOpen || !asset) return null;

  const handlePresetSelect = (code) => {
    setDefectCode(code);
    const preset = DEFECT_PRESETS.find(p => p.code === code);
    if (preset) {
      setCorrectionPrompt(preset.prompt);
      setDenoiseStrength(preset.denoise);
    }
  };

  const startDrawing = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const ctx = canvas.getContext("2d");
    ctx.beginPath();
    ctx.moveTo(x, y);
    setIsDrawing(true);
    setHasDrawn(true);
  };

  const draw = (e) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const ctx = canvas.getContext("2d");
    ctx.lineWidth = brushSize;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    if (tool === "brush") {
      ctx.globalCompositeOperation = "source-over";
      ctx.strokeStyle = "rgba(239, 68, 68, 0.65)";
    } else {
      ctx.globalCompositeOperation = "destination-out";
    }

    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawn(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      let maskBase64 = null;
      if (hasDrawn && canvasRef.current) {
        maskBase64 = canvasRef.current.toDataURL("image/png");
      }

      const payload = {
        defect_code: defectCode,
        mask_base64: maskBase64,
        correction_prompt: correctionPrompt.trim() || undefined,
        denoise_strength: denoiseStrength,
        qa_profile_id: "QA-PROFILE-CATALOG-001",
      };

      const res = await assetRegistryApi.touchUpAsset(asset.id, payload);
      toast.success("Touch-up inpainting job queued (WF-TOUCHUP-001)!");
      onSuccess(res);
      onClose();
    } catch (err) {
      console.error("Touch-up request failed:", err);
      toast.error(err?.message || "Failed to submit touch-up inpainting");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-in fade-in">
      <div className="w-full max-w-4xl bg-zinc-950 border border-zinc-800 rounded-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-zinc-800 bg-zinc-900/40">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Wrench className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                Canvas Retouch & Inpaint Tool
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800">
                  WF-TOUCHUP-001
                </span>
              </h3>
              <p className="text-xs text-zinc-400">
                Paint mask over localized defect to create non-destructive version child (`REL-TOUCHUP-OF`)
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-zinc-800 text-zinc-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Split */}
        <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* Left Canvas View (7 cols) */}
          <div className="md:col-span-7 flex flex-col items-center space-y-3">
            {/* Canvas Container with Background Image */}
            <div className="relative border-2 border-dashed border-zinc-800 rounded-2xl overflow-hidden bg-zinc-900 select-none shadow-inner max-w-full">
              {asset.storage_uri && (
                <img
                  src={asset.storage_uri}
                  alt="Asset Preview"
                  className="w-[480px] h-auto object-cover pointer-events-none"
                />
              )}
              <canvas
                ref={canvasRef}
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
                className="absolute inset-0 cursor-crosshair touch-none"
              />
            </div>

            {/* Brush Controls Toolbar */}
            <div className="flex items-center justify-between w-full max-w-[480px] px-3 py-2 rounded-xl bg-zinc-900/80 border border-zinc-800 text-xs">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setTool("brush")}
                  className={`p-1.5 rounded-lg font-semibold flex items-center gap-1 transition ${
                    tool === "brush" ? "bg-purple-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-white"
                  }`}
                >
                  <Paintbrush className="w-3.5 h-3.5" /> Mask Brush
                </button>
                <button
                  type="button"
                  onClick={() => setTool("eraser")}
                  className={`p-1.5 rounded-lg font-semibold flex items-center gap-1 transition ${
                    tool === "eraser" ? "bg-purple-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-white"
                  }`}
                >
                  <Eraser className="w-3.5 h-3.5" /> Eraser
                </button>
              </div>

              {/* Size Slider */}
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-zinc-400">Size: {brushSize}px</span>
                <input
                  type="range"
                  min="8"
                  max="64"
                  value={brushSize}
                  onChange={(e) => setBrushSize(parseInt(e.target.value))}
                  className="w-20 accent-purple-500"
                />
              </div>

              <button
                type="button"
                onClick={clearCanvas}
                className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-red-400 transition"
                title="Clear mask canvas"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Right Parameters Form (5 cols) */}
          <div className="md:col-span-5 space-y-4">
            {/* Defect Code Selector */}
            <div>
              <label className="text-xs text-zinc-400 block mb-1.5 font-medium">Defect Code Preset</label>
              <select
                value={defectCode}
                onChange={(e) => handlePresetSelect(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs outline-none focus:border-purple-500 font-mono"
              >
                {DEFECT_PRESETS.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.code} — {p.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Correction Prompt */}
            <div>
              <label className="text-xs text-zinc-400 block mb-1.5 font-medium">Correction Inpaint Prompt</label>
              <textarea
                value={correctionPrompt}
                onChange={(e) => setCorrectionPrompt(e.target.value)}
                placeholder="Describe targeted repair detail..."
                rows={3}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs outline-none focus:border-purple-500"
              />
            </div>

            {/* Denoise Strength Slider */}
            <div className="space-y-1.5 p-3 rounded-xl bg-zinc-900/60 border border-zinc-800">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-300 font-medium">Denoise Strength</span>
                <span className="font-mono text-purple-400 font-bold">{denoiseStrength}</span>
              </div>
              <input
                type="range"
                min="0.2"
                max="0.85"
                step="0.05"
                value={denoiseStrength}
                onChange={(e) => setDenoiseStrength(parseFloat(e.target.value))}
                className="w-full accent-purple-500"
              />
              <p className="text-[10px] text-zinc-500">
                Lower = preserve underlying structure · Higher = complete redraw
              </p>
            </div>

            {/* Lineage Notice */}
            <div className="p-3 rounded-xl bg-purple-950/20 border border-purple-900/30 flex items-start gap-2">
              <Info className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
              <p className="text-[11px] text-purple-300">
                This inpaint job will create a child version and establish a <strong>REL-TOUCHUP-OF</strong> lineage relationship, keeping the parent asset intact.
              </p>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-900/40 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-lg shadow-purple-600/20"
          >
            {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            {submitting ? "Queueing Inpaint..." : "Execute Localized Touch-Up"}
          </button>
        </div>
      </div>
    </div>
  );
}
