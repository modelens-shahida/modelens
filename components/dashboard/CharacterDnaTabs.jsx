"use client";

import React, { useState } from "react";
import { Dna, Sliders, Eye, Sparkles, User, Palette, MapPin } from "lucide-react";

export default function CharacterDnaTabs({ character }) {
  const [activeTab, setActiveTab] = useState("dna"); // "dna" | "controls"

  if (!character) return null;

  const { dna } = character;

  return (
    <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl mt-6">
      {/* Top Tab Navigation */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4 mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab("dna")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              activeTab === "dna"
                ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
            }`}
          >
            <Dna className="w-4 h-4 text-cyan-400" />
            <span>Permanent Character DNA</span>
          </button>

          <button
            onClick={() => setActiveTab("controls")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              activeTab === "controls"
                ? "bg-purple-500/10 text-purple-400 border border-purple-500/30 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
            }`}
          >
            <Sliders className="w-4 h-4 text-purple-400" />
            <span>Production Controls (Job Overrides)</span>
          </button>
        </div>

        <div className="text-xs text-zinc-500 hidden sm:block">
          {activeTab === "dna" ? (
            <span className="text-cyan-400/80 font-mono">Immutable Definition</span>
          ) : (
            <span className="text-purple-400/80 font-mono">Job Level Settings</span>
          )}
        </div>
      </div>

      {/* Tab Content: Permanent Character DNA */}
      {activeTab === "dna" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Identity Facial Features */}
            <div className="bg-zinc-950/60 border border-zinc-800/70 rounded-xl p-4">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4 text-cyan-400" />
                <span>Identity & Facial Structure</span>
              </h3>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-zinc-500">Face Shape:</span>
                  <p className="font-medium text-white">{dna?.identity_dna?.face_shape}</p>
                </div>
                <div>
                  <span className="text-zinc-500">Eye Color & Shape:</span>
                  <p className="font-medium text-white">{dna?.identity_dna?.eye_color} ({dna?.identity_dna?.eye_shape})</p>
                </div>
                <div>
                  <span className="text-zinc-500">Nose Bridge:</span>
                  <p className="font-medium text-white">{dna?.identity_dna?.nose_bridge}</p>
                </div>
                <div>
                  <span className="text-zinc-500">Jawline & Cheekbones:</span>
                  <p className="font-medium text-white">{dna?.identity_dna?.jawline}</p>
                </div>
              </div>
            </div>

            {/* Skin & Hair Profile */}
            <div className="bg-zinc-950/60 border border-zinc-800/70 rounded-xl p-4">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <Palette className="w-4 h-4 text-purple-400" />
                <span>Base Skin & Hair Profile</span>
              </h3>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-zinc-500">Base Skin Tone:</span>
                  <p className="font-medium text-white">{dna?.skin_and_hair?.base_skin_tone}</p>
                </div>
                <div>
                  <span className="text-zinc-500">Skin Texture:</span>
                  <p className="font-medium text-white">{dna?.skin_and_hair?.skin_texture_profile}</p>
                </div>
                <div>
                  <span className="text-zinc-500">Base Hair Color:</span>
                  <p className="font-medium text-white">{dna?.skin_and_hair?.base_hair_color}</p>
                </div>
                <div>
                  <span className="text-zinc-500">Default Hair Style:</span>
                  <p className="font-medium text-white">{dna?.skin_and_hair?.hair_style_default}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Body Structure & Facial Landmarks */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-zinc-950/60 border border-zinc-800/70 rounded-xl p-4">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <User className="w-4 h-4 text-emerald-400" />
                <span>Body DNA & Posture Anchor</span>
              </h3>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div>
                  <span className="text-zinc-500">Shoulder Width:</span>
                  <p className="font-medium text-white">{dna?.body_dna?.shoulder_width}</p>
                </div>
                <div>
                  <span className="text-zinc-500">Torso Ratio:</span>
                  <p className="font-medium text-white">{dna?.body_dna?.torso_ratio}</p>
                </div>
                <div>
                  <span className="text-zinc-500">Posture Anchor:</span>
                  <p className="font-medium text-white">{dna?.body_dna?.posture_anchor}</p>
                </div>
              </div>
            </div>

            <div className="bg-zinc-950/60 border border-zinc-800/70 rounded-xl p-4">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-amber-400" />
                <span>Identity Landmarks & Distinguishing Marks</span>
              </h3>
              <div className="space-y-2 text-xs">
                <p className="text-zinc-300">
                  <span className="text-zinc-500 font-medium">Cheek Landmark:</span> {dna?.landmarks?.left_cheek_mole}
                </p>
                <p className="text-zinc-300">
                  <span className="text-zinc-500 font-medium">Collarbone Landmark:</span> {dna?.landmarks?.right_collarbone}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab Content: Production Controls (Explicitly Separated) */}
      {activeTab === "controls" && (
        <div className="bg-zinc-950/60 border border-purple-500/20 rounded-xl p-5 text-xs">
          <div className="flex items-center gap-2 text-purple-400 font-medium mb-3">
            <Sparkles className="w-4 h-4" />
            <span>Ephemeral Generation Parameters (Separated from Character DNA)</span>
          </div>
          <p className="text-zinc-400 mb-4">
            These attributes belong to individual studio generation jobs and do not mutate the permanent identity definition of <strong className="text-white">{character.display_name}</strong>.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-zinc-300">
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg">
              <span className="text-zinc-500">Pose & Action</span>
              <p className="font-medium text-white mt-1">Catalog Standing L30</p>
            </div>
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg">
              <span className="text-zinc-500">Expression</span>
              <p className="font-medium text-white mt-1">Soft Editorial Neutral</p>
            </div>
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg">
              <span className="text-zinc-500">Garment / Outfit</span>
              <p className="font-medium text-white mt-1">Preset #402 Active</p>
            </div>
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg">
              <span className="text-zinc-500">Lighting & Camera</span>
              <p className="font-medium text-white mt-1">Soft Studio 85mm</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
