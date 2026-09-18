"use client";

import React, { useState } from "react";
import { Image as ImageIcon, Camera, CheckCircle2, Clock, Eye, AlertCircle } from "lucide-react";
import { QA_STATUS } from "@/lib/characterSchema";

export default function CharacterAngleGallery({ character }) {
  const [activeCategory, setActiveCategory] = useState("full_body"); // "identity" | "half_body" | "full_body"

  if (!character || !character.angle_references) return null;

  const currentAngles = character.angle_references[activeCategory] || [];

  return (
    <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl mt-6">
      {/* Header & Sub-Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4 mb-6">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Camera className="w-5 h-5 text-cyan-400" />
            <span>Canonical Reference Asset Board</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Dynamic angle slots. Development previews active — awaiting final V1.0 Lock.
          </p>
        </div>

        {/* Category Tabs */}
        <div className="flex items-center gap-2 bg-zinc-950 p-1.5 rounded-xl border border-zinc-800">
          <button
            onClick={() => setActiveCategory("identity")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              activeCategory === "identity"
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Identity (Golden)
          </button>
          <button
            onClick={() => setActiveCategory("half_body")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              activeCategory === "half_body"
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Half-Body
          </button>
          <button
            onClick={() => setActiveCategory("full_body")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              activeCategory === "full_body"
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Full-Body
          </button>
        </div>
      </div>

      {/* Dynamic Grid Rendering (Non-hardcoded) */}
      {currentAngles.length === 0 ? (
        <div className="p-8 text-center border border-dashed border-zinc-800 rounded-xl text-zinc-500 text-xs">
          No canonical reference angles registered for this category yet.
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
          {currentAngles.map((item) => {
            const qaCfg = QA_STATUS[item.status] || QA_STATUS.IN_REVIEW;

            return (
              <div
                key={item.id}
                className="group relative bg-zinc-950 border border-zinc-800/80 rounded-xl overflow-hidden hover:border-cyan-500/40 transition-all shadow-md"
              >
                {/* Angle Badge Header */}
                <div className="px-3 py-2 bg-zinc-900/80 border-b border-zinc-800/60 flex items-center justify-between">
                  <span className="text-xs font-bold text-white tracking-wider">{item.angle}</span>
                  <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${qaCfg.color}`}>
                    {item.status}
                  </span>
                </div>

                {/* Preview Image Slot */}
                <div className="aspect-[3/4] bg-zinc-900 relative flex items-center justify-center overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-t from-zinc-950/80 via-transparent to-transparent z-10 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-3">
                    <span className="text-[10px] text-zinc-300 font-mono truncate">{item.framing}</span>
                  </div>

                  {/* Development Placeholder Visual */}
                  <div className="flex flex-col items-center gap-2 text-zinc-600 group-hover:text-cyan-400/80 transition-colors">
                    <ImageIcon className="w-8 h-8 stroke-[1.5]" />
                    <span className="text-[10px] font-mono text-zinc-500">{item.angle} SLOT</span>
                  </div>
                </div>

                {/* Footer Framing Details */}
                <div className="px-3 py-2 bg-zinc-950 text-[10px] text-zinc-400 flex items-center justify-between border-t border-zinc-900">
                  <span>Framing: {item.framing}</span>
                  <Eye className="w-3 h-3 text-zinc-500 group-hover:text-cyan-400 transition-colors" />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
