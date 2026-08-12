"use client";

import React, { useState } from "react";
import {
  Zap,
  Gem,
  Clock,
  Coins,
  CheckCircle2,
  Rocket,
  Sparkles,
  ArrowRight,
  Info,
  Star,
} from "lucide-react";

/**
 * GenerationModeSelector Component
 * Whitelabeled Generation Mode Selection Cards ("Fast Draft" vs "Studio Quality").
 * Replaces technical provider model names (Gemini, FASHN, etc.) with commercial tier branding.
 *
 * @param {Object} props
 * @param {string} props.selectedMode - Currently active mode ('fast_draft' | 'studio_quality')
 * @param {function} props.onSelectMode - Callback triggered on selection change
 */
export default function GenerationModeSelector({
  selectedMode = "studio_quality",
  onSelectMode,
}) {
  const [currentMode, setCurrentMode] = useState(selectedMode);

  const handleSelect = (mode) => {
    setCurrentMode(mode);
    if (onSelectMode) {
      onSelectMode(mode);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto py-6 px-4">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <h2 className="text-2xl font-bold text-zinc-100">
            Select Generation Mode
          </h2>
          <div className="group relative cursor-pointer">
            <Info className="w-5 h-5 text-zinc-600 hover:text-zinc-400 transition" />
            <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-white text-xs rounded-lg shadow-lg z-20 pointer-events-none">
              Choose Fast Draft for quick concept exploration or Studio Quality for commercial final assets.
            </div>
          </div>
        </div>
        <p className="text-sm text-zinc-500 mt-1">
          Choose the mode that best fits your workflow and quality needs.
        </p>
      </div>

      {/* Grid of Mode Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: Fast Draft (Mode 1) */}
        <div
          onClick={() => handleSelect("fast_draft")}
          className={`relative rounded-2xl p-6 transition-all duration-200 cursor-pointer border-2 flex flex-col justify-between ${
            currentMode === "fast_draft"
               ? "border-purple-500 bg-purple-950/20 shadow-md ring-2 ring-purple-500/20"
               : "border-zinc-850 bg-zinc-900/40 hover:border-purple-700/50 hover:shadow-sm"
          }`}
        >
          <div>
            {/* Top Badge */}
            <div className="flex items-center justify-between mb-4">
              <span className="bg-purple-600 text-white text-[11px] font-extrabold px-3 py-1 rounded-lg uppercase tracking-wider">
                MODE 1
              </span>
            </div>

            {/* Icon & Title */}
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-full bg-purple-900/30 text-purple-400 flex items-center justify-center flex-shrink-0">
                <Zap className="w-7 h-7 fill-purple-600/20 text-purple-400" />
              </div>
              <div>
                <h3 className="text-2xl font-bold text-purple-400">Fast Draft</h3>
                <p className="text-sm text-zinc-400 mt-0.5 font-normal">
                  Best for quick previews and early concept testing.
                </p>
              </div>
            </div>

            {/* Metrics Row */}
            <div className="grid grid-cols-2 gap-4 py-4 px-4 bg-zinc-900/60 rounded-xl border border-zinc-800 mb-5">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-purple-900/30 text-purple-400 flex items-center justify-center">
                  <Clock className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-base font-bold text-zinc-100">~15 sec</div>
                  <div className="text-xs text-zinc-500 font-medium">Estimated time</div>
                </div>
              </div>
              <div className="flex items-center gap-3 border-l border-zinc-850 pl-4">
                <div className="w-9 h-9 rounded-full bg-purple-900/30 text-purple-400 flex items-center justify-center">
                  <Coins className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-base font-bold text-zinc-100">Lower</div>
                  <div className="text-xs text-zinc-500 font-medium">credit use</div>
                </div>
              </div>
            </div>

            {/* Divider */}
            <hr className="border-zinc-800 mb-4" />

            {/* Use For List */}
            <div className="mb-6">
              <h4 className="text-sm font-bold text-purple-400 mb-3">Use for:</h4>
              <ul className="space-y-2.5">
                {[
                  "Rapid design exploration",
                  "Composition testing",
                  "Early visual direction",
                  "Lower-credit generations",
                ].map((item, idx) => (
                  <li key={idx} className="flex items-center gap-2.5 text-sm text-zinc-300">
                    <CheckCircle2 className="w-4 h-4 text-purple-400 fill-purple-600/10 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Action Button */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleSelect("fast_draft");
            }}
            className={`w-full py-3.5 px-4 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all ${
              currentMode === "fast_draft"
                ? "bg-purple-600 text-white shadow-md hover:bg-purple-700"
                : "border-2 border-purple-600 text-purple-400 bg-zinc-900/40 hover:bg-purple-950/20"
            }`}
          >
            <Rocket className="w-4 h-4" />
            <span>Select Fast Draft</span>
            <ArrowRight className="w-4 h-4 ml-auto" />
          </button>
        </div>

        {/* Card 2: Studio Quality (Mode 2) */}
        <div
          onClick={() => handleSelect("studio_quality")}
          className={`relative rounded-2xl p-6 transition-all duration-200 cursor-pointer border-2 flex flex-col justify-between ${
            currentMode === "studio_quality"
              ? "border-amber-500 bg-amber-950/20 shadow-md ring-2 ring-amber-500/20"
              : "border-zinc-850 bg-zinc-900/40 hover:border-amber-400 hover:shadow-sm"
          }`}
        >
          <div>
            {/* Top Row Badges */}
            <div className="flex items-center justify-between mb-4">
              <span className="bg-amber-600 text-white text-[11px] font-extrabold px-3 py-1 rounded-lg uppercase tracking-wider">
                MODE 2
              </span>
              <span className="inline-flex items-center gap-1.5 bg-amber-500/10 text-amber-400 border border-amber-500/30 px-3 py-1 rounded-full text-xs font-semibold">
                <Star className="w-3.5 h-3.5 fill-amber-500 text-amber-500" />
                Recommended for final images
              </span>
            </div>

            {/* Icon & Title */}
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-full bg-amber-500/10 text-amber-400 flex items-center justify-center flex-shrink-0">
                <Gem className="w-7 h-7 text-amber-400" />
              </div>
              <div>
                <h3 className="text-2xl font-bold text-amber-400">Studio Quality</h3>
                <p className="text-sm text-zinc-400 mt-0.5 font-normal">
                  Maximum detail and garment accuracy.
                </p>
              </div>
            </div>

            {/* Metrics Row */}
            <div className="grid grid-cols-2 gap-4 py-4 px-4 bg-zinc-900/60 rounded-xl border border-zinc-800 mb-5">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-amber-500/10 text-amber-400 flex items-center justify-center">
                  <Clock className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-base font-bold text-zinc-100">~45 sec</div>
                  <div className="text-xs text-zinc-500 font-medium">Estimated time</div>
                </div>
              </div>
              <div className="flex items-center gap-3 border-l border-zinc-850 pl-4">
                <div className="w-9 h-9 rounded-full bg-amber-500/10 text-amber-400 flex items-center justify-center">
                  <Coins className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-base font-bold text-zinc-100">Higher</div>
                  <div className="text-xs text-zinc-500 font-medium">credit use</div>
                </div>
              </div>
            </div>

            {/* Divider */}
            <hr className="border-zinc-800 mb-4" />

            {/* Use For List */}
            <div className="mb-6">
              <h4 className="text-sm font-bold text-amber-700 mb-3">Use for:</h4>
              <ul className="space-y-2.5">
                {[
                  "Stronger fabric realism",
                  "Improved construction accuracy",
                  "Better print and pattern preservation",
                  "Refined on-model and campaign imagery",
                  "Final commercial review",
                ].map((item, idx) => (
                  <li key={idx} className="flex items-center gap-2.5 text-sm text-zinc-300">
                    <CheckCircle2 className="w-4 h-4 text-amber-600 fill-amber-600/10 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Action Button */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleSelect("studio_quality");
            }}
            className={`w-full py-3.5 px-4 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all ${
              currentMode === "studio_quality"
                ? "bg-amber-600 text-white shadow-md hover:bg-amber-700"
                : "border-2 border-amber-600 text-amber-700 bg-zinc-900/40 hover:bg-amber-950/20"
            }`}
          >
            <Sparkles className="w-4 h-4" />
            <span>Select Studio Quality</span>
            <ArrowRight className="w-4 h-4 ml-auto" />
          </button>
        </div>
      </div>
    </div>
  );
}
