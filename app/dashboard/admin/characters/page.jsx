"use client";

import React, { useState } from "react";
import AutoFilenameGenerator from "@/components/dashboard/AutoFilenameGenerator";
import CharacterReferenceSetManager from "@/components/dashboard/CharacterReferenceSetManager";
import { 
  User, 
  CheckCircle2, 
  AlertCircle, 
  Layers, 
  Sparkles, 
  ShieldCheck, 
  Camera, 
  FileText, 
  Activity, 
  Sliders, 
  Eye, 
  Award 
} from "lucide-react";
import { motion } from "framer-motion";

const ELISKA_CANONICAL_SLOTS = [
  { group: "Horizontal Face Set (11 Angles)", total: 11, filled: 11, items: [
    { code: "YAW-000", label: "Front 0°", status: "APPROVED" },
    { code: "YAW-L15", label: "Left 15°", status: "APPROVED" },
    { code: "YAW-R15", label: "Right 15°", status: "APPROVED" },
    { code: "YAW-L30", label: "Left 30°", status: "APPROVED" },
    { code: "YAW-R30", label: "Right 30°", status: "APPROVED" },
    { code: "YAW-L45", label: "Left 45°", status: "APPROVED" },
    { code: "YAW-R45", label: "Right 45°", status: "APPROVED" },
    { code: "YAW-L60", label: "Left 60°", status: "APPROVED" },
    { code: "YAW-R60", label: "Right 60°", status: "APPROVED" },
    { code: "YAW-L90", label: "Profile L90°", status: "APPROVED" },
    { code: "YAW-R90", label: "Profile R90°", status: "APPROVED" },
  ]},
  { group: "Vertical Pitch Set (6 Angles)", total: 6, filled: 6, items: [
    { code: "YAW-000_UP30", label: "Front Up 30°", status: "APPROVED" },
    { code: "YAW-000_DN30", label: "Front Down 30°", status: "APPROVED" },
    { code: "YAW-L30_UP30", label: "L30 Up 30°", status: "APPROVED" },
    { code: "YAW-L30_DN30", label: "L30 Down 30°", status: "APPROVED" },
    { code: "YAW-R30_UP30", label: "R30 Up 30°", status: "APPROVED" },
    { code: "YAW-R30_DN30", label: "R30 Down 30°", status: "APPROVED" },
  ]},
  { group: "Half-Body Framing", total: 5, filled: 5, items: [
    { code: "HALF_000", label: "Front Medium", status: "APPROVED" },
    { code: "HALF_L30", label: "L30 Medium", status: "APPROVED" },
    { code: "HALF_R30", label: "R30 Medium", status: "APPROVED" },
    { code: "HALF_L45", label: "L45 Medium", status: "APPROVED" },
    { code: "HALF_R45", label: "R45 Medium", status: "APPROVED" },
  ]},
  { group: "Full-Body Baseline", total: 7, filled: 3, items: [
    { code: "FULL_000", label: "Front Standing 175cm", status: "APPROVED" },
    { code: "FULL_L30", label: "L30 Walking", status: "APPROVED" },
    { code: "FULL_R30", label: "R30 Contrapposto", status: "APPROVED" },
    { code: "FULL_L45", label: "L45 Turn", status: "PENDING" },
    { code: "FULL_R45", label: "R45 Turn", status: "PENDING" },
    { code: "FULL_L90", label: "Profile L90", status: "PENDING" },
    { code: "FULL_R90", label: "Profile R90", status: "PENDING" },
  ]},
];

const GOLDEN_GATES = [
  { id: "GC-01", name: "Permanent Marker Verification", desc: "Right-jaw mark present on visible views only", status: "PASS" },
  { id: "GC-02", name: "Anti-Plastic Skin Microtexture", desc: "Pore & fine grain retention across specular highlights", status: "PASS" },
  { id: "GC-03", name: "5'9\" / 175cm Height Proportions", desc: "Standardized head-to-body & torso-to-leg ratios", status: "PASS" },
  { id: "GC-04", name: "Multi-Angle Geometry Stability", desc: "Facial identity embedding drift < 5% across 11 angles", status: "PASS" },
  { id: "GC-05", name: "Two-Reference Pairing Enforced", desc: "Primary canonical medium + close crop conditioning", status: "PASS" },
  { id: "GC-06", name: "LoRA Training Dataset Frozen", desc: "Immutable manifest with 100% training-cleared rights", status: "READY" },
];

export default function GoldenCharacterHubPage() {
  const [activeTab, setActiveTab] = useState("coverage"); // "coverage" | "references" | "generator"

  const totalSlots = ELISKA_CANONICAL_SLOTS.reduce((acc, g) => acc + g.total, 0);
  const filledSlots = ELISKA_CANONICAL_SLOTS.reduce((acc, g) => acc + g.filled, 0);
  const coveragePercent = Math.round((filledSlots / totalSlots) * 100);

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Top Header Card */}
        <div className="p-6 rounded-3xl bg-gradient-to-r from-zinc-950 via-indigo-950/40 to-zinc-950 border border-zinc-800 shadow-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-pink-500 p-0.5 shadow-lg shadow-indigo-500/20">
              <div className="w-full h-full bg-zinc-950 rounded-[14px] flex items-center justify-center text-indigo-400">
                <User className="w-8 h-8" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-bold text-white">Eliska Novak</h1>
                <span className="px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 font-mono text-xs font-bold">
                  EE-F-002
                </span>
                <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Golden Character Candidate
                </span>
              </div>
              <p className="text-zinc-400 text-xs mt-1">
                Height: 175 cm (5&apos;9&quot;) · Origin: Synthetic Original · Permanent Marker: Right-Jaw Beauty Mark (`SKM-ELISKA-001`)
              </p>
            </div>
          </div>

          {/* Character Build Coverage Meter */}
          <div className="flex items-center gap-4 bg-zinc-900/80 border border-zinc-800 px-5 py-3 rounded-2xl">
            <div className="text-right">
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 block">
                Canonical Coverage
              </span>
              <span className="text-xl font-bold text-indigo-300">{coveragePercent}% Complete</span>
              <span className="text-[10px] text-zinc-500 block">({filledSlots}/{totalSlots} Canonical Slots)</span>
            </div>
            <div className="w-12 h-12 rounded-full border-4 border-indigo-500/30 border-t-indigo-500 flex items-center justify-center font-bold text-xs">
              {coveragePercent}%
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 border-b border-zinc-800 pb-3">
          <button
            onClick={() => setActiveTab("coverage")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
              activeTab === "coverage"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
                : "bg-zinc-900 text-zinc-400 hover:text-white"
            }`}
          >
            <Camera className="w-4 h-4" />
            Canonical View Slots & Gates
          </button>
          <button
            onClick={() => setActiveTab("references")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
              activeTab === "references"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
                : "bg-zinc-900 text-zinc-400 hover:text-white"
            }`}
          >
            <Layers className="w-4 h-4" />
            Reference Sets (`REFSET-*`)
          </button>
          <button
            onClick={() => setActiveTab("generator")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
              activeTab === "generator"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
                : "bg-zinc-900 text-zinc-400 hover:text-white"
            }`}
          >
            <FileText className="w-4 h-4" />
            Auto-Filename Generator
          </button>
        </div>

        {/* Tab 1: Coverage & Golden Gates */}
        {activeTab === "coverage" && (
          <div className="space-y-6">
            {/* Golden Validation Gates */}
            <div className="p-6 rounded-2xl bg-zinc-950 border border-zinc-800 space-y-4">
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                <Award className="w-4 h-4 text-amber-400" />
                Golden Character Validation Gates (Sections 01–21)
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {GOLDEN_GATES.map((g) => (
                  <div key={g.id} className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-indigo-300 font-bold">{g.id}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                        {g.status}
                      </span>
                    </div>
                    <p className="text-xs font-medium text-white">{g.name}</p>
                    <p className="text-[11px] text-zinc-400">{g.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Canonical Slots Matrix */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                <Sliders className="w-4 h-4 text-indigo-400" />
                Canonical Angle & Framing Matrix
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {ELISKA_CANONICAL_SLOTS.map((group, idx) => (
                  <div key={idx} className="p-5 rounded-2xl bg-zinc-950 border border-zinc-800 space-y-3">
                    <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
                      <h4 className="text-xs font-bold text-white font-mono uppercase tracking-wide">
                        {group.group}
                      </h4>
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-indigo-300 border border-zinc-800 font-bold">
                        {group.filled} / {group.total}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {group.items.map((slot) => (
                        <div
                          key={slot.code}
                          className={`p-2.5 rounded-xl border text-xs font-mono transition ${
                            slot.status === "APPROVED"
                              ? "bg-zinc-900/80 border-emerald-800/60 text-zinc-200"
                              : "bg-zinc-950 border-dashed border-zinc-800 text-zinc-500"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-bold text-white text-[11px]">{slot.code}</span>
                            {slot.status === "APPROVED" ? (
                              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <AlertCircle className="w-3 h-3 text-amber-500" />
                            )}
                          </div>
                          <span className="text-[10px] text-zinc-400 block truncate">{slot.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Reference Sets */}
        {activeTab === "references" && (
          <div>
            <CharacterReferenceSetManager characterId="EE-F-002" />
          </div>
        )}

        {/* Tab 3: Filename Generator */}
        {activeTab === "generator" && (
          <div>
            <AutoFilenameGenerator />
          </div>
        )}
      </div>
    </div>
  );
}
