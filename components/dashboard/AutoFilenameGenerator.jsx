"use client";

import React, { useState } from "react";
import { FileText, Copy, CheckCircle2, Sparkles, Tag, ShieldCheck } from "lucide-react";
import toast from "react-hot-toast";

const CHARACTERS = [
  { id: "EE-F-002", name: "Eliska Novak (EE-F-002)" },
  { id: "AR-F-001", name: "Aria Chen (AR-F-001)" },
  { id: "MK-M-001", name: "Marcus Vance (MK-M-001)" },
];

const FRAMINGS = [
  { value: "GM", label: "Golden Master (GM)" },
  { value: "FACE", label: "Face Geometry (FACE)" },
  { value: "VERT", label: "Vertical Pitch (VERT)" },
  { value: "HALF", label: "Half Body (HALF)" },
  { value: "FULL", label: "Full Body (FULL)" },
  { value: "SKIN", label: "Skin Texture (SKIN)" },
  { value: "HAIR", label: "Hair Identity (HAIR)" },
  { value: "EXP", label: "Expression (EXP)" },
  { value: "POSE", label: "Pose Baseline (POSE)" },
];

const VIEWS = [
  { value: "YAW-000", label: "Front (YAW-000)" },
  { value: "YAW-L15", label: "Left 15° (YAW-L15)" },
  { value: "YAW-R15", label: "Right 15° (YAW-R15)" },
  { value: "YAW-L30", label: "Left 30° (YAW-L30)" },
  { value: "YAW-R30", label: "Right 30° (YAW-R30)" },
  { value: "YAW-L45", label: "Left 45° (YAW-L45)" },
  { value: "YAW-R45", label: "Right 45° (YAW-R45)" },
  { value: "YAW-L60", label: "Left 60° (YAW-L60)" },
  { value: "YAW-R60", label: "Right 60° (YAW-R60)" },
  { value: "YAW-L90", label: "Profile Left (YAW-L90)" },
  { value: "YAW-R90", label: "Profile Right (YAW-R90)" },
  { value: "YAW-000_PITCH-UP30", label: "Front Pitch Up 30°" },
  { value: "YAW-000_PITCH-DN30", label: "Front Pitch Down 30°" },
  { value: "YAW-L30_PITCH-UP30", label: "Left 30° Pitch Up 30°" },
  { value: "YAW-L30_PITCH-DN30", label: "Left 30° Pitch Down 30°" },
  { value: "YAW-R30_PITCH-UP30", label: "Right 30° Pitch Up 30°" },
  { value: "YAW-R30_PITCH-DN30", label: "Right 30° Pitch Down 30°" },
  { value: "BEAUTY", label: "Beauty Macro (BEAUTY)" },
];

const EXPRESSIONS = [
  { value: "NEUTRAL", label: "Neutral Baseline" },
  { value: "MICROSMILE", label: "Micro Smile" },
  { value: "SOFTSMILE", label: "Soft Smile" },
  { value: "SMILE", label: "Natural Smile" },
  { value: "SERIOUS", label: "Editorial Serious" },
  { value: "CONFIDENT", label: "Confident Stance" },
];

export default function AutoFilenameGenerator({ className = "" }) {
  const [character, setCharacter] = useState("EE-F-002");
  const [framing, setFraming] = useState("FACE");
  const [view, setView] = useState("YAW-L30");
  const [expression, setExpression] = useState("NEUTRAL");
  const [version, setVersion] = useState("v01");
  const [candidate, setCandidate] = useState("C01");
  const [extension, setExtension] = useState("png");
  const [copied, setCopied] = useState(false);

  const generatedFilename = `${character}_${framing}_${view}_${expression}_${version}_${candidate}.${extension}`;

  const copyFilename = () => {
    navigator.clipboard.writeText(generatedFilename);
    setCopied(true);
    toast.success("Standard filename copied to clipboard!");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`p-5 rounded-2xl bg-zinc-950 border border-zinc-800 text-zinc-100 shadow-xl ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <FileText className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">Auto-Filename Generator (Section 16 Standard)</h4>
            <p className="text-xs text-zinc-400">Generates canonical, zero-padded asset filenames with no ambiguity</p>
          </div>
        </div>

        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-emerald-400 font-bold">
          REGISTRY COMPLIANT
        </span>
      </div>

      {/* Selectors Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4 text-xs">
        <div>
          <label className="text-[11px] text-zinc-400 block mb-1 font-medium">Character</label>
          <select
            value={character}
            onChange={(e) => setCharacter(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-white focus:border-emerald-500 outline-none"
          >
            {CHARACTERS.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-[11px] text-zinc-400 block mb-1 font-medium">Framing / Domain</label>
          <select
            value={framing}
            onChange={(e) => setFraming(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-white focus:border-emerald-500 outline-none"
          >
            {FRAMINGS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-[11px] text-zinc-400 block mb-1 font-medium">View / Angle</label>
          <select
            value={view}
            onChange={(e) => setView(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-white focus:border-emerald-500 outline-none font-mono"
          >
            {VIEWS.map((v) => (
              <option key={v.value} value={v.value}>
                {v.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-[11px] text-zinc-400 block mb-1 font-medium">Expression</label>
          <select
            value={expression}
            onChange={(e) => setExpression(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-white focus:border-emerald-500 outline-none"
          >
            {EXPRESSIONS.map((ex) => (
              <option key={ex.value} value={ex.value}>
                {ex.label}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-1.5">
          <div>
            <label className="text-[11px] text-zinc-400 block mb-1 font-medium">Version</label>
            <select
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              className="w-full px-2 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-white font-mono focus:border-emerald-500 outline-none"
            >
              <option value="v01">v01</option>
              <option value="v02">v02</option>
              <option value="v03">v03</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] text-zinc-400 block mb-1 font-medium">Candidate</label>
            <select
              value={candidate}
              onChange={(e) => setCandidate(e.target.value)}
              className="w-full px-2 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-white font-mono focus:border-emerald-500 outline-none"
            >
              <option value="C01">C01</option>
              <option value="C02">C02</option>
              <option value="C03">C03</option>
              <option value="C04">C04</option>
            </select>
          </div>
        </div>

        <div>
          <label className="text-[11px] text-zinc-400 block mb-1 font-medium">Extension</label>
          <select
            value={extension}
            onChange={(e) => setExtension(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-white font-mono focus:border-emerald-500 outline-none"
          >
            <option value="png">.png</option>
            <option value="jpg">.jpg</option>
            <option value="webp">.webp</option>
          </select>
        </div>
      </div>

      {/* Generated Filename Box with 1-Click Copy */}
      <div className="p-3 rounded-xl bg-zinc-900 border border-emerald-500/30 flex items-center justify-between gap-3">
        <div className="font-mono text-xs text-emerald-300 font-bold tracking-tight truncate select-all">
          {generatedFilename}
        </div>

        <button
          onClick={copyFilename}
          className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition flex items-center gap-1.5 shrink-0 shadow-lg shadow-emerald-500/20"
        >
          {copied ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? "Copied" : "Copy Filename"}
        </button>
      </div>
    </div>
  );
}
