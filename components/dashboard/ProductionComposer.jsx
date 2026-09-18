"use client";

import React, { useState } from "react";
import { Sparkles, ShoppingBag, User, Camera, Image as ImageIcon, ChevronRight, X, Check, Sliders, Layers, Compass, Zap } from "lucide-react";
import { MOCK_ELISKA_CHARACTER } from "@/lib/characterSchema";

const SAMPLE_PRODUCTS = [
  { id: "prod_1", name: "Silk Bias Dress", code: "SKU-SLK-402", category: "Dresses", thumbLabel: "Silk Slip Dress" },
  { id: "prod_2", name: "Tailored Wool Blazer", code: "SKU-WOL-809", category: "Outerwear", thumbLabel: "Wool Blazer" },
  { id: "prod_3", name: "Cashmere Turtleneck", code: "SKU-CSH-104", category: "Knitwear", thumbLabel: "Cashmere Sweater" },
  { id: "prod_4", name: "Structured Leather Trench", code: "SKU-LTH-991", category: "Coats", thumbLabel: "Leather Trench" },
];

const SAMPLE_CHARACTERS = [
  { ...MOCK_ELISKA_CHARACTER, display_name: "ELISKA", height: "178 cm", stature: "Tall", code: "EE-F-002" },
  { id: "EE-F-003", display_name: "AMARA", height: "180 cm", stature: "Tall", code: "EE-F-003", body_archetype: "Editorial Runway", status: "APPROVED" },
  { id: "EE-F-004", display_name: "FREJA", height: "176 cm", stature: "Slim", code: "EE-F-004", body_archetype: "Commercial Chic", status: "APPROVED" },
  { id: "EE-F-005", display_name: "MAYA", height: "179 cm", stature: "Tall", code: "EE-F-005", body_archetype: "High-Fashion Slim", status: "APPROVED" },
];

const SAMPLE_BACKGROUNDS = [
  { id: "bg_1", name: "Studio Grey", category: "Studio", desc: "Minimal neutral studio backdrop" },
  { id: "bg_2", name: "Paris Haussmann Balcony", category: "Editorial", desc: "Classic Parisian architectural vista" },
  { id: "bg_3", name: "Brutalist Concrete Gallery", category: "Architectural", desc: "Contemporary dramatic shadow environment" },
  { id: "bg_4", name: "Sunlit Marble Loft", category: "Daylight", desc: "Soft warm natural lighting interior" },
  { id: "bg_5", name: "High-Key Cyclorama White", category: "Commercial", desc: "Pure seamless e-commerce white" },
];

const SAMPLE_DIRECTIONS = [
  { id: "dir_1", name: "Luxury Editorial", desc: "Vogue-style high dynamic contrast, subtle motion & sharp focal depth" },
  { id: "dir_2", name: "Minimalist E-Commerce", desc: "Clean, even illumination with focus on garment fabric weave" },
  { id: "dir_3", name: "Dramatic Chiaroscuro", desc: "Deep cinematic shadows with rich directional key light" },
  { id: "dir_4", name: "Soft Daylight Natural", desc: "Organic sunbeams, natural skin textures and airy mood" },
];

export default function ProductionComposer({ onGenerate }) {
  // Step selections
  const [selectedProduct, setSelectedProduct] = useState(SAMPLE_PRODUCTS[0]);
  const [selectedCharacter, setSelectedCharacter] = useState(SAMPLE_CHARACTERS[0]);
  const [selectedAngles, setSelectedAngles] = useState(["Front", "L30", "R30", "L45"]);
  const [selectedBackground, setSelectedBackground] = useState(SAMPLE_BACKGROUNDS[0]);
  const [selectedDirection, setSelectedDirection] = useState(SAMPLE_DIRECTIONS[0]);
  const [qualityMode, setQualityMode] = useState("studio_quality"); // "fast_draft" | "studio_quality"

  // Active drawer toggle: "product" | "character" | "angle" | "background" | "direction"
  const [activeDrawer, setActiveDrawer] = useState(null);

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
        background: selectedBackground,
        direction: selectedDirection,
        quality: qualityMode,
      });
    }
  };

  const costPerImage = qualityMode === "studio_quality" ? 5 : 2;
  const totalCredits = selectedAngles.length * costPerImage;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header (Shahida Spec) */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-widest block font-bold">
            MODE LENS WORKFLOW
          </span>
          <h1 className="text-3xl font-extrabold text-white tracking-tight mt-0.5">
            CREATE PRODUCTION
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Visual studio composer for multi-angle AI fashion production.
          </p>
        </div>

        <div className="bg-zinc-950 border border-zinc-800 px-4 py-2.5 rounded-xl flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <div>
            <span className="text-[10px] text-zinc-500 font-mono block uppercase">Project</span>
            <strong className="text-xs font-bold text-white tracking-wide">Spring 2027 Campaign</strong>
          </div>
        </div>
      </div>

      {/* Visual Composition Object Stack (Shahida Spec Steps 1 - 5) */}
      <div className="space-y-3.5">
        {/* Step 1: PRODUCT */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 flex items-center justify-between backdrop-blur-md hover:border-zinc-700/80 transition-all">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-bold text-xs flex items-center justify-center font-mono">
              1
            </div>
            <div>
              <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block font-semibold">
                PRODUCT
              </span>
              <h3 className="text-base font-extrabold text-white mt-0.5 flex items-center gap-2">
                <span>[ {selectedProduct.name} ]</span>
              </h3>
              <span className="text-[11px] text-zinc-400 font-mono">{selectedProduct.code} • {selectedProduct.category}</span>
            </div>
          </div>
          <button
            onClick={() => setActiveDrawer("product")}
            className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 hover:border-cyan-500/50 hover:bg-cyan-500/10 text-xs font-bold text-zinc-200 hover:text-cyan-400 px-4 py-2.5 rounded-xl transition-all shadow-sm"
          >
            <ShoppingBag className="w-4 h-4 text-cyan-400" />
            <span>Change &gt;</span>
          </button>
        </div>

        {/* Step 2: CHARACTER */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 flex items-center justify-between backdrop-blur-md hover:border-zinc-700/80 transition-all">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 font-bold text-xs flex items-center justify-center font-mono">
              2
            </div>
            <div>
              <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block font-semibold">
                CHARACTER
              </span>
              <h3 className="text-base font-extrabold text-white mt-0.5 flex items-center gap-2">
                <span>[ {selectedCharacter.display_name} ]</span>
                <span className="text-xs font-normal text-zinc-400 font-mono">
                  {selectedCharacter.height} / {selectedCharacter.stature}
                </span>
              </h3>
              <span className="text-[11px] text-indigo-400 font-mono">
                {selectedCharacter.code || "EE-F-002"} • High-Fashion Runway Slim
              </span>
            </div>
          </div>
          <button
            onClick={() => setActiveDrawer("character")}
            className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 hover:border-indigo-500/50 hover:bg-indigo-500/10 text-xs font-bold text-zinc-200 hover:text-indigo-400 px-4 py-2.5 rounded-xl transition-all shadow-sm"
          >
            <User className="w-4 h-4 text-indigo-400" />
            <span>Change &gt;</span>
          </button>
        </div>

        {/* Step 3: POSE / ANGLE */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 backdrop-blur-md hover:border-zinc-700/80 transition-all">
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3 mb-4">
            <div className="flex items-center gap-4">
              <div className="w-8 h-8 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400 font-bold text-xs flex items-center justify-center font-mono">
                3
              </div>
              <div>
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block font-semibold">
                  POSE / ANGLE
                </span>
                <span className="text-xs text-zinc-400">Selected {selectedAngles.length} Angle Slots</span>
              </div>
            </div>

            <button
              onClick={() => setActiveDrawer("angle")}
              className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 hover:border-purple-500/50 hover:bg-purple-500/10 text-xs font-bold text-zinc-200 hover:text-purple-400 px-4 py-2.5 rounded-xl transition-all shadow-sm"
            >
              <Camera className="w-4 h-4 text-purple-400" />
              <span>Add Angle &gt;</span>
            </button>
          </div>

          {/* Active Visual Chips */}
          <div className="flex flex-wrap items-center gap-2.5 pl-12">
            {selectedAngles.map((ang) => (
              <div
                key={ang}
                className="px-4 py-2 bg-zinc-950 border border-purple-500/40 text-purple-300 font-mono text-xs font-bold rounded-xl flex items-center gap-2 shadow-sm"
              >
                <span>[ {ang} ]</span>
                <button
                  onClick={() => toggleAngle(ang)}
                  className="hover:text-red-400 transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Step 4: BACKGROUND */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 flex items-center justify-between backdrop-blur-md hover:border-zinc-700/80 transition-all">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold text-xs flex items-center justify-center font-mono">
              4
            </div>
            <div>
              <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block font-semibold">
                BACKGROUND
              </span>
              <h3 className="text-base font-extrabold text-white mt-0.5">
                [ {selectedBackground.name} ]
              </h3>
              <span className="text-[11px] text-zinc-400">{selectedBackground.desc}</span>
            </div>
          </div>
          <button
            onClick={() => setActiveDrawer("background")}
            className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 hover:border-emerald-500/50 hover:bg-emerald-500/10 text-xs font-bold text-zinc-200 hover:text-emerald-400 px-4 py-2.5 rounded-xl transition-all shadow-sm"
          >
            <ImageIcon className="w-4 h-4 text-emerald-400" />
            <span>Change &gt;</span>
          </button>
        </div>

        {/* Step 5: CREATIVE DIRECTION */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 flex items-center justify-between backdrop-blur-md hover:border-zinc-700/80 transition-all">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 font-bold text-xs flex items-center justify-center font-mono">
              5
            </div>
            <div>
              <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block font-semibold">
                CREATIVE DIRECTION
              </span>
              <h3 className="text-base font-extrabold text-amber-300 mt-0.5">
                {selectedDirection.name}
              </h3>
              <span className="text-[11px] text-zinc-400">{selectedDirection.desc}</span>
            </div>
          </div>
          <button
            onClick={() => setActiveDrawer("direction")}
            className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 hover:border-amber-500/50 hover:bg-amber-500/10 text-xs font-bold text-zinc-200 hover:text-amber-400 px-4 py-2.5 rounded-xl transition-all shadow-sm"
          >
            <Compass className="w-4 h-4 text-amber-400" />
            <span>Optional &gt;</span>
          </button>
        </div>
      </div>

      {/* OUTPUT & GENERATION SUMMARY (Shahida Spec) */}
      <div className="bg-gradient-to-r from-zinc-900 via-zinc-900 to-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-2xl space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800/80 pb-5">
          <div>
            <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-widest block font-bold">
              OUTPUT SPECIFICATION
            </span>
            <div className="flex items-baseline gap-3 mt-1">
              <h2 className="text-2xl font-extrabold text-white tracking-tight">
                {selectedAngles.length} Images
              </h2>
              <span className="px-3 py-1 bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 text-xs font-bold rounded-full font-mono">
                {qualityMode === "studio_quality" ? "Studio Quality" : "Fast Draft"}
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-1">
              Estimated Credits: <strong className="text-white font-mono">{totalCredits} Credits</strong> ({costPerImage} cr/img)
            </p>
          </div>

          <div className="flex items-center gap-2 bg-zinc-950 p-1.5 rounded-xl border border-zinc-800">
            <button
              onClick={() => setQualityMode("fast_draft")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                qualityMode === "fast_draft"
                  ? "bg-zinc-800 text-white border border-zinc-700"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Draft (2 cr)
            </button>
            <button
              onClick={() => setQualityMode("studio_quality")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                qualityMode === "studio_quality"
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Studio Quality (5 cr)
            </button>
          </div>
        </div>

        {/* Generate Primary Button */}
        <button
          onClick={handleTriggerGenerate}
          className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-extrabold text-base py-4 rounded-xl transition-all shadow-xl shadow-cyan-500/20 flex items-center justify-center gap-3 tracking-wide"
        >
          <Sparkles className="w-5 h-5" />
          <span>GENERATE PHOTOSHOOT PRODUCTION</span>
        </button>
      </div>

      {/* VISUAL DRAWERS & SELECTOR MODALS */}

      {/* Product Selector Drawer */}
      {activeDrawer === "product" && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex justify-end">
          <div className="w-full max-w-md bg-zinc-900 border-l border-zinc-800 h-full p-6 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right">
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <ShoppingBag className="w-5 h-5 text-cyan-400" />
                  <span>Select Product</span>
                </h3>
                <button
                  onClick={() => setActiveDrawer(null)}
                  className="text-zinc-400 hover:text-white p-1"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-3 overflow-y-auto max-h-[70vh]">
                {SAMPLE_PRODUCTS.map((prod) => {
                  const isSelected = selectedProduct.id === prod.id;
                  return (
                    <div
                      key={prod.id}
                      onClick={() => {
                        setSelectedProduct(prod);
                        setActiveDrawer(null);
                      }}
                      className={`p-4 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                        isSelected
                          ? "bg-cyan-500/10 border-cyan-500/50 text-white shadow-lg"
                          : "bg-zinc-950 border-zinc-800 hover:border-zinc-700 text-zinc-300"
                      }`}
                    >
                      <div>
                        <span className="text-[10px] font-mono text-zinc-500 uppercase">{prod.category}</span>
                        <h4 className="text-sm font-bold mt-0.5">{prod.name}</h4>
                        <span className="text-xs font-mono text-zinc-400">{prod.code}</span>
                      </div>
                      {isSelected && <Check className="w-5 h-5 text-cyan-400" />}
                    </div>
                  );
                })}
              </div>
            </div>

            <button
              onClick={() => setActiveDrawer(null)}
              className="w-full bg-zinc-800 hover:bg-zinc-700 text-white font-bold text-xs py-3 rounded-xl transition-all"
            >
              Close Drawer
            </button>
          </div>
        </div>
      )}

      {/* Character Selector Drawer */}
      {activeDrawer === "character" && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex justify-end">
          <div className="w-full max-w-md bg-zinc-900 border-l border-zinc-800 h-full p-6 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right">
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <User className="w-5 h-5 text-indigo-400" />
                  <span>Select Model Character</span>
                </h3>
                <button
                  onClick={() => setActiveDrawer(null)}
                  className="text-zinc-400 hover:text-white p-1"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-3 overflow-y-auto max-h-[70vh]">
                {SAMPLE_CHARACTERS.map((char) => {
                  const isSelected = selectedCharacter.display_name === char.display_name;
                  return (
                    <div
                      key={char.display_name}
                      onClick={() => {
                        setSelectedCharacter(char);
                        setActiveDrawer(null);
                      }}
                      className={`p-4 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                        isSelected
                          ? "bg-indigo-500/10 border-indigo-500/50 text-white shadow-lg"
                          : "bg-zinc-950 border-zinc-800 hover:border-zinc-700 text-zinc-300"
                      }`}
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-extrabold">{char.display_name}</h4>
                          <span className="text-[10px] font-mono px-2 py-0.5 bg-indigo-500/10 text-indigo-400 rounded-full border border-indigo-500/30">
                            {char.code || "EE-F-002"}
                          </span>
                        </div>
                        <span className="text-xs text-zinc-400 mt-1 block">
                          {char.height} • {char.stature} • {char.body_archetype || "High-Fashion Runway Slim"}
                        </span>
                      </div>
                      {isSelected && <Check className="w-5 h-5 text-indigo-400" />}
                    </div>
                  );
                })}
              </div>
            </div>

            <button
              onClick={() => setActiveDrawer(null)}
              className="w-full bg-zinc-800 hover:bg-zinc-700 text-white font-bold text-xs py-3 rounded-xl transition-all"
            >
              Close Drawer
            </button>
          </div>
        </div>
      )}

      {/* Angle Selector Drawer */}
      {activeDrawer === "angle" && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex justify-end">
          <div className="w-full max-w-md bg-zinc-900 border-l border-zinc-800 h-full p-6 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right">
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Camera className="w-5 h-5 text-purple-400" />
                  <span>Select Camera Angles</span>
                </h3>
                <button
                  onClick={() => setActiveDrawer(null)}
                  className="text-zinc-400 hover:text-white p-1"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <p className="text-xs text-zinc-400">
                Click to toggle angle slots for this production run.
              </p>

              <div className="grid grid-cols-2 gap-3">
                {["Front", "L30", "R30", "L45", "R45", "L90", "R90", "Back"].map((ang) => {
                  const active = selectedAngles.includes(ang);
                  return (
                    <button
                      key={ang}
                      onClick={() => toggleAngle(ang)}
                      className={`p-3.5 text-xs font-mono font-bold rounded-xl border transition-all flex items-center justify-between ${
                        active
                          ? "bg-purple-500/20 text-purple-300 border-purple-500/50 shadow-md"
                          : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:border-zinc-700"
                      }`}
                    >
                      <span>[ {ang} ]</span>
                      {active && <Check className="w-4 h-4 text-purple-400" />}
                    </button>
                  );
                })}
              </div>
            </div>

            <button
              onClick={() => setActiveDrawer(null)}
              className="w-full bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs py-3 rounded-xl transition-all shadow-lg"
            >
              Done Selecting Angles
            </button>
          </div>
        </div>
      )}

      {/* Background Selector Drawer */}
      {activeDrawer === "background" && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex justify-end">
          <div className="w-full max-w-md bg-zinc-900 border-l border-zinc-800 h-full p-6 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right">
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <ImageIcon className="w-5 h-5 text-emerald-400" />
                  <span>Select Background</span>
                </h3>
                <button
                  onClick={() => setActiveDrawer(null)}
                  className="text-zinc-400 hover:text-white p-1"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-3 overflow-y-auto max-h-[70vh]">
                {SAMPLE_BACKGROUNDS.map((bg) => {
                  const isSelected = selectedBackground.id === bg.id;
                  return (
                    <div
                      key={bg.id}
                      onClick={() => {
                        setSelectedBackground(bg);
                        setActiveDrawer(null);
                      }}
                      className={`p-4 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                        isSelected
                          ? "bg-emerald-500/10 border-emerald-500/50 text-white shadow-lg"
                          : "bg-zinc-950 border-zinc-800 hover:border-zinc-700 text-zinc-300"
                      }`}
                    >
                      <div>
                        <span className="text-[10px] font-mono text-zinc-500 uppercase">{bg.category}</span>
                        <h4 className="text-sm font-bold mt-0.5">{bg.name}</h4>
                        <span className="text-xs text-zinc-400">{bg.desc}</span>
                      </div>
                      {isSelected && <Check className="w-5 h-5 text-emerald-400" />}
                    </div>
                  );
                })}
              </div>
            </div>

            <button
              onClick={() => setActiveDrawer(null)}
              className="w-full bg-zinc-800 hover:bg-zinc-700 text-white font-bold text-xs py-3 rounded-xl transition-all"
            >
              Close Drawer
            </button>
          </div>
        </div>
      )}

      {/* Creative Direction Selector Drawer */}
      {activeDrawer === "direction" && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex justify-end">
          <div className="w-full max-w-md bg-zinc-900 border-l border-zinc-800 h-full p-6 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right">
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Compass className="w-5 h-5 text-amber-400" />
                  <span>Creative Direction</span>
                </h3>
                <button
                  onClick={() => setActiveDrawer(null)}
                  className="text-zinc-400 hover:text-white p-1"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-3 overflow-y-auto max-h-[70vh]">
                {SAMPLE_DIRECTIONS.map((dir) => {
                  const isSelected = selectedDirection.id === dir.id;
                  return (
                    <div
                      key={dir.id}
                      onClick={() => {
                        setSelectedDirection(dir);
                        setActiveDrawer(null);
                      }}
                      className={`p-4 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                        isSelected
                          ? "bg-amber-500/10 border-amber-500/50 text-white shadow-lg"
                          : "bg-zinc-950 border-zinc-800 hover:border-zinc-700 text-zinc-300"
                      }`}
                    >
                      <div>
                        <h4 className="text-sm font-bold text-amber-300">{dir.name}</h4>
                        <span className="text-xs text-zinc-400 mt-1 block">{dir.desc}</span>
                      </div>
                      {isSelected && <Check className="w-5 h-5 text-amber-400" />}
                    </div>
                  );
                })}
              </div>
            </div>

            <button
              onClick={() => setActiveDrawer(null)}
              className="w-full bg-zinc-800 hover:bg-zinc-700 text-white font-bold text-xs py-3 rounded-xl transition-all"
            >
              Close Drawer
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

