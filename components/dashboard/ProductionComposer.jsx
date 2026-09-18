"use client";

import React, { useState } from "react";
import { Sparkles, ShoppingBag, User, Move, Image as ImageIcon, ChevronRight, X, Check, Sliders, Camera, Sun, Eye } from "lucide-react";
import { MOCK_ELISKA_CHARACTER } from "@/lib/characterSchema";

export default function ProductionComposer({ onGenerate }) {
  // Step selections
  const [selectedProduct, setSelectedProduct] = useState({ id: 1, name: "Silk Bias Cut Slip Dress", code: "SKU-SLK-402", thumb: "/api/placeholder/100/100" });
  const [selectedCharacter, setSelectedCharacter] = useState(MOCK_ELISKA_CHARACTER);
  const [selectedAngles, setSelectedAngles] = useState(["FRONT", "L30", "R30", "L45"]);
  const [selectedPose, setSelectedPose] = useState("Catalog Standing L30");
  const [selectedBackground, setSelectedBackground] = useState({ id: "bg_grey", name: "Studio Grey Minimal", category: "Studio" });
  const [creativeStyle, setCreativeStyle] = useState("Luxury Editorial Minimal");
  const [qualityMode, setQualityMode] = useState("studio_quality"); // "fast_draft" | "studio_quality"

  // Drawer modal toggles
  const [activeDrawer, setActiveDrawer] = useState(null); // "product" | "character" | "angle" | "background"
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Advanced settings
  const [cameraFocal, setCameraFocal] = useState("85mm Prime");
  const [lightingPreset, setLightingPreset] = useState("Soft High-Key Studio");
  const [expression, setExpression] = useState("Editorial Neutral");

  const toggleAngle = (angle) => {
    if (selectedAngles.includes(angle)) {
      if (selectedAngles.length > 1) {
        setSelectedAngles(selectedAngles.filter((a) => a !== angle));
      }
    } else {
      setSelectedAngles([...selectedAngles, angle]);
    }
  };

  const handleTriggerGenerate = () => {
    if (onGenerate) {
      onGenerate({
        product: selectedProduct,
        character: selectedCharacter,
        angles: selectedAngles,
        pose: selectedPose,
        background: selectedBackground,
        style: creativeStyle,
        quality: qualityMode,
      });
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Sparkles className="w-7 h-7 text-cyan-400" />
            <span>Create AI Photoshoot Production</span>
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Compose high-fashion assets visually. Non-cluttered studio orchestration.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-xl text-zinc-400">
          <span>Project:</span>
          <strong className="text-white">Spring 2027 Campaign</strong>
        </div>
      </div>

      {/* Visual Composition Steps */}
      <div className="space-y-4">
        {/* Step 1: Product Selection */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 flex items-center justify-between backdrop-blur-md">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-bold text-xs flex items-center justify-center font-mono">
              1
            </div>
            <div>
              <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block">Target Product</span>
              <h3 className="text-sm font-bold text-white mt-0.5">{selectedProduct.name}</h3>
              <span className="text-[11px] text-zinc-400 font-mono">{selectedProduct.code}</span>
            </div>
          </div>
          <button
            onClick={() => setActiveDrawer("product")}
            className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 px-4 py-2 rounded-xl transition-all"
          >
            <ShoppingBag className="w-3.5 h-3.5 text-cyan-400" />
            <span>Change Product</span>
            <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
          </button>
        </div>

        {/* Step 2: Character Selection */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 flex items-center justify-between backdrop-blur-md">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-bold text-xs flex items-center justify-center font-mono">
              2
            </div>
            <div>
              <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block">Model Character</span>
              <div className="flex items-center gap-2 mt-0.5">
                <h3 className="text-sm font-bold text-white">{selectedCharacter.display_name}</h3>
                <span className="px-2 py-0.5 bg-cyan-500/10 text-cyan-400 text-[10px] font-semibold rounded-full border border-cyan-500/30 font-mono">
                  {selectedCharacter.id} (v{selectedCharacter.version})
                </span>
              </div>
              <span className="text-[11px] text-zinc-400">
                {selectedCharacter.body_metrics?.canonical_height_cm} cm • {selectedCharacter.body_metrics?.stature_class}
              </span>
            </div>
          </div>
          <button
            onClick={() => setActiveDrawer("character")}
            className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 px-4 py-2 rounded-xl transition-all"
          >
            <User className="w-3.5 h-3.5 text-cyan-400" />
            <span>Change Model</span>
            <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
          </button>
        </div>

        {/* Step 3: Pose & Angle Selector */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 backdrop-blur-md">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <div className="w-8 h-8 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-bold text-xs flex items-center justify-center font-mono">
                3
              </div>
              <div>
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block">Pose & Angle Slots</span>
                <h3 className="text-sm font-bold text-white mt-0.5">{selectedPose}</h3>
              </div>
            </div>
          </div>

          {/* Angle Chips */}
          <div className="flex flex-wrap items-center gap-2.5 pt-2 pl-12">
            {["FRONT", "L30", "R30", "L45", "R45", "L90", "R90"].map((angle) => {
              const active = selectedAngles.includes(angle);
              return (
                <button
                  key={angle}
                  onClick={() => toggleAngle(angle)}
                  className={`px-3.5 py-1.5 text-xs font-mono font-semibold rounded-xl border transition-all flex items-center gap-1.5 ${
                    active
                      ? "bg-cyan-500/20 text-cyan-400 border-cyan-500/50 shadow-sm"
                      : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:border-zinc-700"
                  }`}
                >
                  {active && <Check className="w-3 h-3 text-cyan-400" />}
                  <span>{angle}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Step 4: Background Selection */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 flex items-center justify-between backdrop-blur-md">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-bold text-xs flex items-center justify-center font-mono">
              4
            </div>
            <div>
              <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block">Environment & Scene</span>
              <h3 className="text-sm font-bold text-white mt-0.5">{selectedBackground.name}</h3>
              <span className="text-[11px] text-zinc-400">{selectedBackground.category} Category</span>
            </div>
          </div>
          <button
            onClick={() => setActiveDrawer("background")}
            className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 px-4 py-2 rounded-xl transition-all"
          >
            <ImageIcon className="w-3.5 h-3.5 text-cyan-400" />
            <span>Change Background</span>
            <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
          </button>
        </div>
      </div>

      {/* Advanced Controls Accordion */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl overflow-hidden backdrop-blur-md">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full px-5 py-3.5 text-xs font-semibold text-zinc-400 hover:text-white flex items-center justify-between transition-colors"
        >
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-purple-400" />
            <span>Advanced Controls (Camera, Lighting, Expression, Gaze)</span>
          </div>
          <span>{showAdvanced ? "Hide Advanced ▲" : "Show Advanced ▼"}</span>
        </button>

        {showAdvanced && (
          <div className="p-5 border-t border-zinc-800 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block text-zinc-500 mb-1">Camera & Lens</label>
              <select
                value={cameraFocal}
                onChange={(e) => setCameraFocal(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-white"
              >
                <option value="85mm Prime">85mm Prime Editorial</option>
                <option value="50mm Standard">50mm Standard Studio</option>
                <option value="105mm Macro">105mm Macro Detail</option>
              </select>
            </div>

            <div>
              <label className="block text-zinc-500 mb-1">Lighting Preset</label>
              <select
                value={lightingPreset}
                onChange={(e) => setLightingPreset(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-white"
              >
                <option value="Soft High-Key Studio">Soft High-Key Studio</option>
                <option value="Moody Dramatic Chiaroscuro">Moody Dramatic Chiaroscuro</option>
                <option value="Golden Hour Warm Exterior">Golden Hour Warm Exterior</option>
              </select>
            </div>

            <div>
              <label className="block text-zinc-500 mb-1">Model Expression</label>
              <select
                value={expression}
                onChange={(e) => setExpression(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-white"
              >
                <option value="Editorial Neutral">Editorial Neutral</option>
                <option value="Soft Confident Smile">Soft Confident Smile</option>
                <option value="High-Fashion Intense Gaze">High-Fashion Intense Gaze</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Output & Generation Bar */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-6">
          <div>
            <span className="text-[10px] font-mono text-zinc-500 uppercase">Quality Option</span>
            <div className="flex items-center gap-2 mt-1">
              <button
                onClick={() => setQualityMode("fast_draft")}
                className={`px-3 py-1 text-xs font-semibold rounded-lg border transition-all ${
                  qualityMode === "fast_draft"
                    ? "bg-zinc-800 text-white border-zinc-700"
                    : "text-zinc-500 border-transparent hover:text-zinc-300"
                }`}
              >
                Fast Draft (2 cr/img)
              </button>
              <button
                onClick={() => setQualityMode("studio_quality")}
                className={`px-3 py-1 text-xs font-semibold rounded-lg border transition-all ${
                  qualityMode === "studio_quality"
                    ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
                    : "text-zinc-500 border-transparent hover:text-zinc-300"
                }`}
              >
                Studio Quality (5 cr/img)
              </button>
            </div>
          </div>

          <div className="border-l border-zinc-800 pl-6 hidden md:block">
            <span className="text-[10px] font-mono text-zinc-500 uppercase">Total Output</span>
            <p className="text-sm font-bold text-white mt-0.5">
              {selectedAngles.length} Images ({selectedAngles.length * (qualityMode === "studio_quality" ? 5 : 2)} Credits)
            </p>
          </div>
        </div>

        <button
          onClick={handleTriggerGenerate}
          className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-sm px-6 py-3 rounded-xl transition-all shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2"
        >
          <Sparkles className="w-4 h-4" />
          <span>GENERATE PHOTOSHOOT</span>
        </button>
      </div>
    </div>
  );
}
