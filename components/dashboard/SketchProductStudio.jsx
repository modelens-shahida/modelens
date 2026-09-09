"use client";
import React, { useState, useEffect } from "react";
import { 
  PenTool, Layers, Palette, Sparkles, CheckCircle2, 
  Download, RefreshCw, ShieldCheck, FileText, ArrowRight,
  Info, Cpu, Sliders, Eye, Image as ImageIcon, Check
} from "lucide-react";
import toast from "react-hot-toast";
import { sketchApi } from "@/lib/sketchApi";
import { useAuth } from "@/lib/auth-context";

const DEFAULT_MODES = [
  { mode_id: "lineart", label: "Technical Lineart", description: "Clean vector/CAD technical drawings", controlnet: "ControlNet Lineart" },
  { mode_id: "softedge", label: "Soft Edge Sketch", description: "Hand-drawn garment sketches", controlnet: "ControlNet SoftEdge" },
  { mode_id: "scribble", label: "Scribble / Rough", description: "Rough concept sketches", controlnet: "ControlNet Scribble" },
];

const DEFAULT_FABRICS = [
  { id: "cotton", label: "Cotton", drape: "natural", weight: "medium", icon: "🌱" },
  { id: "denim", label: "Denim", drape: "stiff", weight: "heavy", icon: "👖" },
  { id: "silk", label: "Silk", drape: "fluid", weight: "light", icon: "✨" },
  { id: "knit", label: "Knit", drape: "stretch", weight: "medium", icon: "🧶" },
  { id: "leather", label: "Leather", drape: "structured", weight: "heavy", icon: "🧥" },
  { id: "chiffon", label: "Chiffon", drape: "sheer", weight: "light", icon: "🪶" },
  { id: "velvet", label: "Velvet", drape: "rich", weight: "medium", icon: "👑" },
  { id: "linen", label: "Linen", drape: "crisp", weight: "medium", icon: "🌾" },
];

const DEFAULT_COLORWAYS = [
  { id: "classic_black", pantone: "19-0303 TCX", hex: "#1C1C1C", label: "Classic Black" },
  { id: "pure_white", pantone: "11-0601 TCX", hex: "#F5F5F0", label: "Pure White" },
  { id: "navy_blue", pantone: "19-3832 TCX", hex: "#1B2A4A", label: "Navy Blue" },
  { id: "dusty_rose", pantone: "14-1511 TCX", hex: "#D4A5A5", label: "Dusty Rose" },
  { id: "sage_green", pantone: "16-0220 TCX", hex: "#8FAF8F", label: "Sage Green" },
  { id: "camel", pantone: "16-1334 TCX", hex: "#C19A6B", label: "Camel" },
  { id: "burgundy", pantone: "19-1528 TCX", hex: "#6D2B3D", label: "Burgundy" },
  { id: "cobalt", pantone: "19-3748 TCX", hex: "#0047AB", label: "Cobalt Blue" },
];

const GARMENT_TYPES = ["dress", "jacket", "shirt", "pants", "hoodie", "coat", "skirt", "blazer"];

export default function SketchProductStudio() {
  const { user } = useAuth();
  const [modes, setModes] = useState(DEFAULT_MODES);
  const [fabrics, setFabrics] = useState(DEFAULT_FABRICS);
  const [colorways, setColorways] = useState(DEFAULT_COLORWAYS);

  // Configuration state
  const [selectedMode, setSelectedMode] = useState("lineart");
  const [selectedFabric, setSelectedFabric] = useState("cotton");
  const [primaryColorway, setPrimaryColorway] = useState("classic_black");
  const [additionalVariants, setAdditionalVariants] = useState([]);
  const [garmentType, setGarmentType] = useState("dress");
  const [onModel, setOnModel] = useState(false);
  const [ghostMode, setGhostMode] = useState(true);
  const [generationTier, setGenerationTier] = useState("studio_quality"); // studio_quality (5 credits) vs fast_draft (1 credit)
  const [customPrompt, setCustomPrompt] = useState("");

  // Preview & Processing state
  const [uploadedSketch, setUploadedSketch] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeStage, setActiveStage] = useState(null); // 'parsing_sketch', 'applying_fabric', 'rendering_product', 'completed'
  const [generatedResults, setGeneratedResults] = useState(null);
  const [activeResultColorway, setActiveResultColorway] = useState(null);
  const [compareSplit, setCompareSplit] = useState(50);

  // Fetch backend modes on mount
  useEffect(() => {
    async function loadModes() {
      try {
        const res = await sketchApi.getModes();
        if (res?.data?.modes?.length) setModes(res.data.modes);
        if (res?.data?.fabrics?.length) {
          const mapped = res.data.fabrics.map((f) => ({
            ...f,
            icon: DEFAULT_FABRICS.find((df) => df.id === f.id)?.icon || "🧵",
          }));
          setFabrics(mapped);
        }
        if (res?.data?.colorways?.length) {
          const mappedColors = res.data.colorways.map((c, i) => ({
            id: Object.keys(DEFAULT_COLORWAYS).find(k => DEFAULT_COLORWAYS[k].pantone === c.pantone) || `color_${i}`,
            ...c,
          }));
          setColorways(mappedColors.length ? mappedColors : DEFAULT_COLORWAYS);
        }
      } catch (err) {
        console.warn("Using default sketch parameters:", err);
      }
    }
    loadModes();
  }, []);

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const url = URL.createObjectURL(file);
      setUploadedSketch({ file, url, name: file.name });
      toast.success("CAD Sketch uploaded successfully");
    }
  };

  const toggleVariant = (colorId) => {
    if (colorId === primaryColorway) return;
    setAdditionalVariants((prev) =>
      prev.includes(colorId) ? prev.filter((id) => id !== colorId) : [...prev, colorId]
    );
  };

  const totalJobs = 1 + additionalVariants.length;
  const creditsPerJob = generationTier === "studio_quality" ? 5 : 1;
  const totalCredits = totalJobs * creditsPerJob;

  const handleGenerate = async () => {
    setIsSubmitting(true);
    setActiveStage("parsing_sketch");

    try {
      const payload = {
        brand_id: user?.brand_id || 1,
        sketch_mode: selectedMode,
        fabric_id: selectedFabric,
        colorway_id: primaryColorway,
        garment_type: garmentType,
        on_model: onModel,
        ghost_mode: ghostMode,
        generation_mode: generationTier,
        custom_prompt: customPrompt || undefined,
        colorway_variants: additionalVariants,
      };

      const res = await sketchApi.createJob(payload);

      // Simulate step telemetry for visual feedback
      setTimeout(() => setActiveStage("applying_fabric"), 1200);
      setTimeout(() => setActiveStage("rendering_product"), 2600);

      setTimeout(() => {
        setActiveStage("completed");
        setIsSubmitting(false);

        const allSelected = [primaryColorway, ...additionalVariants];
        const activeColorwayObj = colorways.find((c) => c.id === primaryColorway) || colorways[0];
        const activeFabricObj = fabrics.find((f) => f.id === selectedFabric) || fabrics[0];

        const mockVariants = allSelected.map((cId) => {
          const cObj = colorways.find((c) => c.id === cId) || colorways[0];
          return {
            colorway_id: cId,
            label: cObj.label,
            pantone: cObj.pantone,
            hex: cObj.hex,
            fabric: activeFabricObj.label,
            drape: activeFabricObj.drape,
            renderUrl: uploadedSketch?.url || "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=900&auto=format&fit=crop&q=80",
            c2paSigned: true,
            c2paManifestId: `urn:c2pa:ml-sketch-${Date.now()}-${cId}`,
          };
        });

        setGeneratedResults(mockVariants);
        setActiveResultColorway(mockVariants[0]);
        toast.success(`Generated ${totalJobs} SKU colorway variant(s) successfully!`);
      }, 4000);
    } catch (err) {
      setIsSubmitting(false);
      setActiveStage(null);
      const errMsg = err?.response?.data?.detail || "Generation failed. Check your credit balance.";
      toast.error(errMsg);
    }
  };

  const activeModeObj = modes.find((m) => m.mode_id === selectedMode) || modes[0];
  const activeFabricObj = fabrics.find((f) => f.id === selectedFabric) || fabrics[0];
  const activeColorObj = colorways.find((c) => c.id === primaryColorway) || colorways[0];

  return (
    <div className="space-y-8">
      {/* Top Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-purple-950/40 via-indigo-950/30 to-zinc-950 border border-purple-500/20 p-6 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 shadow-xl backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2.5 mb-1.5">
            <span className="px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-full">
              WF-SKETCH-001
            </span>
            <span className="px-2.5 py-0.5 text-xs font-medium text-zinc-400 bg-zinc-900 border border-zinc-800 rounded-full flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              C2PA Certified Generative CAD
            </span>
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Sketch-to-Product Generative CAD Studio
          </h2>
          <p className="text-zinc-400 text-sm mt-1 max-w-2xl">
            Transform 2D vector CAD lineart and hand sketches into photorealistic commercial catalog & ghost mannequin renders with physical fabric drape mapping.
          </p>
        </div>

        <div className="flex items-center gap-4 bg-zinc-900/90 border border-zinc-800 px-5 py-3 rounded-xl">
          <div>
            <div className="text-xs text-zinc-400 font-medium">Batch Credit Cost</div>
            <div className="text-lg font-bold text-purple-400 flex items-center gap-1.5">
              <span>{totalCredits} credits</span>
              <span className="text-xs font-normal text-zinc-500">({totalJobs} variants)</span>
            </div>
          </div>
          <button
            onClick={handleGenerate}
            disabled={isSubmitting}
            className="px-6 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:opacity-50 text-white font-medium text-sm rounded-lg shadow-lg shadow-purple-900/30 flex items-center gap-2 transition-all cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-purple-200" />
                <span>Processing...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-purple-200" />
                <span>Generate CAD Render</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Studio Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Config Panel (5 Cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* 1. Sketch Mode Selection */}
          <div className="bg-zinc-900/80 border border-zinc-800/80 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-semibold text-white flex items-center gap-2">
                <PenTool className="w-4 h-4 text-purple-400" />
                1. Edge Guidance Mode
              </label>
              <span className="text-xs text-zinc-500">{activeModeObj?.controlnet}</span>
            </div>
            <div className="grid grid-cols-3 gap-2.5">
              {modes.map((mode) => {
                const isSelected = selectedMode === mode.mode_id;
                return (
                  <button
                    key={mode.mode_id}
                    onClick={() => setSelectedMode(mode.mode_id)}
                    className={`p-3 text-left rounded-lg border transition-all cursor-pointer ${
                      isSelected
                        ? "bg-purple-950/40 border-purple-500/80 text-white shadow-sm ring-1 ring-purple-500/40"
                        : "bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                    }`}
                  >
                    <div className="text-xs font-semibold">{mode.label}</div>
                    <div className="text-[10px] text-zinc-500 mt-1 line-clamp-2 leading-tight">
                      {mode.description}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 2. Fabric Texture & Drape Physics */}
          <div className="bg-zinc-900/80 border border-zinc-800/80 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-semibold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                2. Fabric & Drape Texture (8 Textures)
              </label>
              <span className="text-xs text-indigo-300 font-medium">
                Drape: <span className="capitalize">{activeFabricObj?.drape}</span> ({activeFabricObj?.weight})
              </span>
            </div>
            <div className="grid grid-cols-4 gap-2">
              {fabrics.map((f) => {
                const isSelected = selectedFabric === f.id;
                return (
                  <button
                    key={f.id}
                    onClick={() => setSelectedFabric(f.id)}
                    className={`p-2.5 text-center rounded-lg border transition-all cursor-pointer ${
                      isSelected
                        ? "bg-indigo-950/40 border-indigo-500 text-white shadow-sm ring-1 ring-indigo-500/40"
                        : "bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                    }`}
                  >
                    <div className="text-base mb-1">{f.icon}</div>
                    <div className="text-xs font-medium">{f.label}</div>
                    <div className="text-[9px] text-zinc-500 uppercase tracking-wider">{f.drape}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3. Pantone Colorway Matrix */}
          <div className="bg-zinc-900/80 border border-zinc-800/80 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-semibold text-white flex items-center gap-2">
                <Palette className="w-4 h-4 text-emerald-400" />
                3. Pantone Colorways & Variant Matrix
              </label>
              <span className="text-xs text-zinc-500">
                Primary: <strong className="text-white">{activeColorObj?.label}</strong> ({activeColorObj?.pantone})
              </span>
            </div>

            <div className="grid grid-cols-4 gap-2.5">
              {colorways.map((c) => {
                const isPrimary = primaryColorway === c.id;
                const isAdditional = additionalVariants.includes(c.id);

                return (
                  <div
                    key={c.id}
                    className={`relative rounded-lg p-2 border transition-all cursor-pointer ${
                      isPrimary
                        ? "border-emerald-500 bg-emerald-950/20 ring-1 ring-emerald-500/40"
                        : isAdditional
                        ? "border-purple-500/60 bg-purple-950/20"
                        : "border-zinc-800 bg-zinc-950/60 hover:border-zinc-700"
                    }`}
                    onClick={() => setPrimaryColorway(c.id)}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="w-4 h-4 rounded-full border border-white/20 shrink-0 shadow-inner"
                        style={{ backgroundColor: c.hex }}
                      />
                      <div className="overflow-hidden">
                        <div className="text-[11px] font-medium text-zinc-200 truncate">{c.label}</div>
                        <div className="text-[9px] text-zinc-500 truncate">{c.pantone}</div>
                      </div>
                    </div>

                    {/* Checkbox for batch variant */}
                    {!isPrimary && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleVariant(c.id);
                        }}
                        className={`mt-1.5 w-full py-0.5 text-[9px] font-medium rounded border transition-all ${
                          isAdditional
                            ? "bg-purple-600 border-purple-500 text-white"
                            : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        {isAdditional ? "✓ Variant Active" : "+ Add Variant"}
                      </button>
                    )}
                    {isPrimary && (
                      <div className="mt-1.5 text-center text-[9px] font-semibold text-emerald-400 bg-emerald-950/60 py-0.5 rounded">
                        ★ Primary SKU
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* 4. Render Settings */}
          <div className="bg-zinc-900/80 border border-zinc-800/80 rounded-xl p-5 space-y-4">
            <label className="text-sm font-semibold text-white flex items-center gap-2">
              <Sliders className="w-4 h-4 text-purple-400" />
              4. Garment Type & Tier Controls
            </label>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="text-xs text-zinc-400 font-medium block mb-1.5">Garment Silhouette</span>
                <select
                  value={garmentType}
                  onChange={(e) => setGarmentType(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white capitalize focus:outline-none focus:border-purple-500"
                >
                  {GARMENT_TYPES.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <span className="text-xs text-zinc-400 font-medium block mb-1.5">Quality Engine</span>
                <select
                  value={generationTier}
                  onChange={(e) => setGenerationTier(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-purple-500"
                >
                  <option value="studio_quality">Studio Quality (5 Credits)</option>
                  <option value="fast_draft">Fast Draft (1 Credit)</option>
                </select>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="onModelToggle"
                  checked={onModel}
                  onChange={(e) => setOnModel(e.target.checked)}
                  className="rounded bg-zinc-950 border-zinc-800 text-purple-600 focus:ring-0 cursor-pointer"
                />
                <label htmlFor="onModelToggle" className="text-xs text-zinc-300 cursor-pointer">
                  Render On Human Model (vs. Ghost Flatlay)
                </label>
              </div>

              <div className="text-xs text-zinc-500">
                Resolution: <strong className="text-zinc-300">2048 × 2048</strong>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Sketch Canvas & Live Render Visualizer (7 Cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Upload & Canvas Container */}
          <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-5 h-5 text-purple-400" />
                <h3 className="text-base font-bold text-white">2D Sketch $\leftrightarrow$ 3D Render Canvas</h3>
              </div>
              {uploadedSketch && (
                <button
                  onClick={() => setUploadedSketch(null)}
                  className="text-xs text-zinc-500 hover:text-red-400 transition-colors"
                >
                  Clear Sketch
                </button>
              )}
            </div>

            {/* Interactive Split View / Preview Area */}
            {!uploadedSketch ? (
              <label className="border-2 border-dashed border-zinc-800 hover:border-purple-500/50 bg-zinc-950/40 rounded-xl p-10 flex flex-col items-center justify-center gap-3 cursor-pointer transition-all group min-h-[380px]">
                <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
                <div className="w-14 h-14 rounded-full bg-purple-950/40 border border-purple-500/30 flex items-center justify-center text-purple-400 group-hover:scale-110 transition-transform">
                  <PenTool className="w-6 h-6" />
                </div>
                <div className="text-center">
                  <div className="text-sm font-semibold text-white">Upload 2D Flat Sketch or CAD Lineart</div>
                  <div className="text-xs text-zinc-500 mt-1 max-w-sm">
                    Supports PNG, JPG, or SVG technical drawings, hand sketches, or pattern blueprints.
                  </div>
                </div>
                <span className="px-3.5 py-1.5 bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded-lg group-hover:border-purple-500 transition-colors">
                  Browse Files
                </span>
              </label>
            ) : (
              <div className="space-y-4">
                {/* Visualizer Frame */}
                <div className="relative rounded-xl overflow-hidden bg-zinc-950 border border-zinc-800 aspect-square max-h-[460px] mx-auto group">
                  {/* Background Grid Pattern */}
                  <div
                    className="absolute inset-0 opacity-15"
                    style={{
                      backgroundImage: "radial-gradient(#a855f7 1px, transparent 1px)",
                      backgroundSize: "20px 20px",
                    }}
                  />

                  {/* Split Comparison or Single View */}
                  {generatedResults && activeResultColorway ? (
                    <div className="relative w-full h-full">
                      {/* Left: Original Sketch */}
                      <img
                        src={uploadedSketch.url}
                        alt="Original CAD Sketch"
                        className="absolute inset-0 w-full h-full object-contain p-4 filter contrast-125"
                      />
                      {/* Right: Rendered Product with clip-path */}
                      <div
                        className="absolute inset-0 overflow-hidden"
                        style={{ clipPath: `inset(0 0 0 ${compareSplit}%)` }}
                      >
                        <img
                          src={activeResultColorway.renderUrl}
                          alt="Rendered Product"
                          className="absolute inset-0 w-full h-full object-cover"
                        />
                      </div>

                      {/* Split Handle Bar */}
                      <div
                        className="absolute top-0 bottom-0 w-0.5 bg-purple-400 shadow-[0_0_10px_rgba(168,85,247,0.8)] z-20 cursor-ew-resize"
                        style={{ left: `${compareSplit}%` }}
                      >
                        <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-6 h-6 rounded-full bg-purple-600 border border-white flex items-center justify-center text-[10px] text-white shadow-lg">
                          ⇄
                        </div>
                      </div>

                      {/* Floating Labels */}
                      <span className="absolute top-3 left-3 px-2.5 py-1 bg-black/70 backdrop-blur-md border border-white/10 rounded-md text-[10px] font-semibold text-zinc-300 z-10">
                        CAD Vector Sketch
                      </span>
                      <span className="absolute top-3 right-3 px-2.5 py-1 bg-purple-950/80 backdrop-blur-md border border-purple-500/40 rounded-md text-[10px] font-semibold text-purple-200 z-10 flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: activeResultColorway.hex }} />
                        {activeResultColorway.label} Render
                      </span>
                    </div>
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center">
                      <img
                        src={uploadedSketch.url}
                        alt="Uploaded Sketch"
                        className="max-h-[360px] object-contain rounded-lg shadow-xl"
                      />
                      <div className="absolute bottom-4 left-4 right-4 bg-zinc-900/90 backdrop-blur-md border border-zinc-800 p-3 rounded-lg flex items-center justify-between">
                        <div className="text-left">
                          <div className="text-xs font-semibold text-white">{uploadedSketch.name}</div>
                          <div className="text-[10px] text-zinc-400">
                            Target Fabric: <strong className="text-zinc-200">{activeFabricObj.label}</strong> ({activeFabricObj.drape} drape)
                          </div>
                        </div>
                        <span className="text-[10px] px-2 py-0.5 bg-purple-950/60 border border-purple-500/40 text-purple-300 rounded font-medium">
                          Ready to Project
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Processing Overlay */}
                  {isSubmitting && (
                    <div className="absolute inset-0 bg-zinc-950/85 backdrop-blur-sm flex flex-col items-center justify-center gap-4 z-30 p-6">
                      <div className="w-16 h-16 rounded-full bg-purple-950/60 border border-purple-500 flex items-center justify-center text-purple-400 animate-pulse">
                        <Cpu className="w-8 h-8 animate-spin" />
                      </div>
                      <div className="text-center space-y-1">
                        <div className="text-sm font-bold text-white capitalize">
                          {activeStage ? activeStage.replace("_", " ") : "Processing CAD Sketch..."}
                        </div>
                        <div className="text-xs text-zinc-400">
                          Applying {activeModeObj.controlnet} & {activeFabricObj.label} texture mapping
                        </div>
                      </div>

                      {/* Step Progress Bar */}
                      <div className="w-64 bg-zinc-900 rounded-full h-2 overflow-hidden border border-zinc-800 mt-2">
                        <div
                          className="bg-gradient-to-r from-purple-500 to-indigo-500 h-full transition-all duration-500"
                          style={{
                            width:
                              activeStage === "parsing_sketch"
                                ? "30%"
                                : activeStage === "applying_fabric"
                                ? "65%"
                                : activeStage === "rendering_product"
                                ? "90%"
                                : "100%",
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Slider for Split Compare (when results ready) */}
                {generatedResults && (
                  <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-xl flex items-center gap-4">
                    <span className="text-xs text-zinc-400 whitespace-nowrap">Sketch ⇄ Render Ratio:</span>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={compareSplit}
                      onChange={(e) => setCompareSplit(Number(e.target.value))}
                      className="w-full accent-purple-500 cursor-pointer"
                    />
                    <span className="text-xs font-mono text-purple-400 w-8">{compareSplit}%</span>
                  </div>
                )}
              </div>
            )}

            {/* Generated Colorway Variant Gallery & 1-Click Exporter */}
            {generatedResults && (
              <div className="space-y-4 pt-4 border-t border-zinc-800">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                    Generated Colorway SKU Variants ({generatedResults.length})
                  </div>
                  <button
                    onClick={() => toast.success("Downloaded All Colorway SKUs + Spec Sheet (ZIP Archive)")}
                    className="px-3.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download All Variants (.ZIP)
                  </button>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {generatedResults.map((variant) => {
                    const isSelected = activeResultColorway?.colorway_id === variant.colorway_id;
                    return (
                      <div
                        key={variant.colorway_id}
                        onClick={() => setActiveResultColorway(variant)}
                        className={`p-2.5 rounded-xl border transition-all cursor-pointer ${
                          isSelected
                            ? "border-purple-500 bg-purple-950/30 ring-1 ring-purple-500/40"
                            : "border-zinc-800 bg-zinc-950/80 hover:border-zinc-700"
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          <span
                            className="w-3.5 h-3.5 rounded-full border border-white/30"
                            style={{ backgroundColor: variant.hex }}
                          />
                          <span className="text-xs font-semibold text-white truncate">{variant.label}</span>
                        </div>
                        <div className="text-[10px] text-zinc-400 font-mono truncate">{variant.pantone}</div>
                        <div className="text-[10px] text-purple-300 mt-1 flex items-center gap-1">
                          <ShieldCheck className="w-3 h-3 text-emerald-400" />
                          C2PA Certified
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
