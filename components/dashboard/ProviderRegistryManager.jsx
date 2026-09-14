"use client";

import React, { useState } from "react";
import { 
  Cpu, 
  Layers, 
  ShieldCheck, 
  ArrowRightLeft, 
  Sliders, 
  Sparkles, 
  Eye, 
  CheckCircle2, 
  AlertCircle, 
  Zap, 
  Activity,
  Compass,
  RotateCw,
  UserCheck
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

// Internal Provider Routing Data
const INTERNAL_PROVIDERS = [
  {
    id: "PROV-COMFY-01",
    name: "ComfyUI GPU Cluster (H100 NVLink)",
    type: "SELF_HOSTED_GPU",
    status: "HEALTHY",
    latency: "1.2s",
    avgQaScore: 96.4,
    tier: "STUDIO_QUALITY",
    models: ["FLUX.1-Dev-ControlNet", "SDXL-Inpainting-v2", "LoRA-EE-F-002-v1"],
  },
  {
    id: "PROV-FASHN-01",
    name: "FASHN.ai Virtual Try-On API",
    type: "MANAGED_API",
    status: "HEALTHY",
    latency: "2.4s",
    avgQaScore: 95.8,
    tier: "STUDIO_QUALITY",
    models: ["product-to-model-v2", "try-on-max-2k"],
  },
  {
    id: "PROV-FAL-01",
    name: "Fal.ai Fast Generation Pipe",
    type: "SERVERLESS",
    status: "HEALTHY",
    latency: "0.6s",
    avgQaScore: 92.1,
    tier: "FAST_DRAFT",
    models: ["flux-schnell-turbo", "lightning-sdxl"],
  },
  {
    id: "PROV-OAI-01",
    name: "OpenAI DALL-E 3 / Vision Guard",
    type: "THIRD_PARTY_API",
    status: "STANDBY",
    latency: "3.1s",
    avgQaScore: 94.0,
    tier: "STUDIO_QUALITY",
    models: ["dall-e-3-hd", "gpt-4o-vision-qa"],
  },
];

const ROUTING_POLICIES = [
  {
    id: "POL-01",
    workflow: "Ghost Mannequin 3D Reconstruction (WF-GHOST-001)",
    customerTierName: "Studio Quality (96+ Fidelity)",
    primaryRoute: "PROV-COMFY-01 (ControlNet + Alpha Mask)",
    fallbackRoute: "PROV-FASHN-01 (Try-On Max)",
    fallbackThreshold: 94.0,
    status: "ACTIVE",
  },
  {
    id: "POL-02",
    workflow: "Catalog Fast Draft Preview (WF-CAT-DRAFT)",
    customerTierName: "Fast Draft (<1s Generation)",
    primaryRoute: "PROV-FAL-01 (FLUX Schnell)",
    fallbackRoute: "PROV-COMFY-01",
    fallbackThreshold: 90.0,
    status: "ACTIVE",
  },
  {
    id: "POL-03",
    workflow: "Sketch CAD Generative Render (WF-SKETCH-001)",
    customerTierName: "Studio Quality (ControlNet CAD)",
    primaryRoute: "PROV-COMFY-01",
    fallbackRoute: "PROV-OAI-01",
    fallbackThreshold: 94.0,
    status: "ACTIVE",
  },
];

const POSE_PRESETS_DECOUPLED = [
  {
    code: "POSE-GEO-001",
    name: "Frontal Eye Contact (30° Body Turn)",
    bodyYaw: "R030",
    bodyPitch: "000",
    bodyRoll: "000",
    headYaw: "000",
    headPitch: "UP05",
    headRoll: "000",
    gaze: "DIRECT_CAMERA",
    expression: "EXPR-SOFT-SMILE",
    desc: "Body angled 30° to the right for garment depth, but head & eyes turned 0° directly toward camera.",
  },
  {
    code: "POSE-GEO-002",
    name: "Editorial Profile Lookback",
    bodyYaw: "L045",
    bodyPitch: "DN05",
    bodyRoll: "000",
    headYaw: "R030",
    headPitch: "000",
    headRoll: "L05",
    gaze: "OFF_CAMERA_RIGHT",
    expression: "EXPR-EDITORIAL-SERIOUS",
    desc: "Left 45° body stance with right 30° head turn lookback and off-camera gaze anchor.",
  },
  {
    code: "POSE-GEO-003",
    name: "Contrapposto Fashion Walk",
    bodyYaw: "R015",
    bodyPitch: "000",
    bodyRoll: "R05",
    headYaw: "L015",
    headPitch: "DN10",
    headRoll: "000",
    gaze: "DIRECT_CAMERA",
    expression: "EXPR-NATURAL-CHIC",
    desc: "Natural hips tilt with 15° counter head turn maintaining direct camera eye contact.",
  },
];

export default function ProviderRegistryManager() {
  const [activeTab, setActiveTab] = useState("providers"); // "providers" | "policies" | "pose"
  
  // Decoupled Pose Geometry State
  const [selectedPose, setSelectedPose] = useState(POSE_PRESETS_DECOUPLED[0]);
  const [bodyYaw, setBodyYaw] = useState("R030");
  const [headYaw, setHeadYaw] = useState("000");
  const [headPitch, setHeadPitch] = useState("UP05");
  const [gaze, setGaze] = useState("DIRECT_CAMERA");
  const [expression, setExpression] = useState("EXPR-SOFT-SMILE");

  const applyPosePreset = (preset) => {
    setSelectedPose(preset);
    setBodyYaw(preset.bodyYaw);
    setHeadYaw(preset.headYaw);
    setHeadPitch(preset.headPitch);
    setGaze(preset.gaze);
    setExpression(preset.expression);
    toast.success(`Loaded Independent Pose Geometry: ${preset.code}`);
  };

  return (
    <div className="space-y-6">
      {/* Top Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-r from-zinc-950 via-indigo-950/30 to-zinc-950 border border-indigo-800/40">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Cpu className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              Provider Abstraction & Pose Geometry Registry
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800">
                P2 Decoupled Engine
              </span>
            </h2>
            <p className="text-xs text-zinc-400">
              Manage multi-provider routing policies (Fast Draft vs Studio Quality) and independent body/head pose parameters.
            </p>
          </div>
        </div>

        {/* Customer Abstraction Badge */}
        <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-xl text-xs">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="text-zinc-400">Customer Facing View:</span>
          <span className="font-mono text-emerald-300 font-bold">Obfuscated (Fast Draft / Studio Quality)</span>
        </div>
      </div>

      {/* Main Tab Navigation */}
      <div className="flex gap-2 border-b border-zinc-850 pb-3">
        <button
          onClick={() => setActiveTab("providers")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
            activeTab === "providers"
              ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
              : "bg-zinc-900 text-zinc-400 hover:text-white"
          }`}
        >
          <Cpu className="w-4 h-4" />
          Internal Providers Cluster
        </button>
        <button
          onClick={() => setActiveTab("policies")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
            activeTab === "policies"
              ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
              : "bg-zinc-900 text-zinc-400 hover:text-white"
          }`}
        >
          <ArrowRightLeft className="w-4 h-4" />
          Routing Policies & Fallbacks
        </button>
        <button
          onClick={() => setActiveTab("pose")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
            activeTab === "pose"
              ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
              : "bg-zinc-900 text-zinc-400 hover:text-white"
          }`}
        >
          <RotateCw className="w-4 h-4" />
          Independent Pose/Geometry Controller
        </button>
      </div>

      {/* TAB 1: Internal Providers */}
      {activeTab === "providers" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {INTERNAL_PROVIDERS.map((prov) => (
              <div key={prov.id} className="p-5 rounded-2xl bg-zinc-950 border border-zinc-850 space-y-4 hover:border-zinc-700 transition">
                <div className="flex items-center justify-between border-b border-zinc-850 pb-3">
                  <div>
                    <span className="text-[10px] font-mono font-bold text-indigo-400 block">{prov.id}</span>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      {prov.name}
                    </h3>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    {prov.status}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 font-mono text-xs">
                  <div className="bg-zinc-900 p-2.5 rounded-xl border border-zinc-850">
                    <span className="text-[9px] text-zinc-500 block uppercase">Type</span>
                    <span className="font-bold text-zinc-300 text-[11px] truncate block">{prov.type}</span>
                  </div>
                  <div className="bg-zinc-900 p-2.5 rounded-xl border border-zinc-850">
                    <span className="text-[9px] text-zinc-500 block uppercase">Latency</span>
                    <span className="font-bold text-indigo-300 text-[11px] block">{prov.latency}</span>
                  </div>
                  <div className="bg-zinc-900 p-2.5 rounded-xl border border-zinc-850">
                    <span className="text-[9px] text-zinc-500 block uppercase">Avg QA Score</span>
                    <span className="font-bold text-emerald-300 text-[11px] block">{prov.avgQaScore}</span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">Deployed Models / Workflows</span>
                  <div className="flex flex-wrap gap-1.5">
                    {prov.models.map((m, i) => (
                      <span key={i} className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: Routing Policies */}
      {activeTab === "policies" && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-850 flex items-center justify-between text-xs text-zinc-400">
            <span className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              Dynamic Auto-Fallback Engine is active. If primary route drops below threshold, request auto-reroutes in &lt;150ms.
            </span>
          </div>

          <div className="space-y-3">
            {ROUTING_POLICIES.map((pol) => (
              <div key={pol.id} className="p-5 rounded-2xl bg-zinc-950 border border-zinc-850 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-850 pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold text-indigo-400">{pol.id}</span>
                      <h4 className="text-sm font-bold text-white">{pol.workflow}</h4>
                    </div>
                    <span className="text-xs text-emerald-400 font-semibold mt-0.5 block">
                      Customer Tier Display: &quot;{pol.customerTierName}&quot;
                    </span>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-800 self-start sm:self-auto">
                    {pol.status}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-850">
                    <span className="text-[10px] text-zinc-500 font-mono block uppercase">Primary Route</span>
                    <span className="font-bold text-white font-mono mt-0.5 block truncate">{pol.primaryRoute}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-850">
                    <span className="text-[10px] text-zinc-500 font-mono block uppercase">Fallback Route</span>
                    <span className="font-bold text-zinc-300 font-mono mt-0.5 block truncate">{pol.fallbackRoute}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-850">
                    <span className="text-[10px] text-zinc-500 font-mono block uppercase">QA Fallback Gate</span>
                    <span className="font-bold text-amber-300 font-mono mt-0.5 block">&lt; {pol.fallbackThreshold} QA Score</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: Independent Pose & Geometry Controller */}
      {activeTab === "pose" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Presets List */}
          <div className="lg:col-span-1 space-y-3 bg-zinc-950 border border-zinc-850 p-4 rounded-2xl">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-850 pb-2">
              Decoupled Geometry Presets
            </h3>
            <div className="space-y-2">
              {POSE_PRESETS_DECOUPLED.map((preset) => {
                const isSelected = selectedPose.code === preset.code;
                return (
                  <button
                    key={preset.code}
                    onClick={() => applyPosePreset(preset)}
                    className={`w-full text-left p-3.5 rounded-xl border transition flex flex-col gap-1.5 cursor-pointer ${
                      isSelected
                        ? "bg-indigo-950/50 border-indigo-500 text-white shadow-md"
                        : "bg-zinc-900/50 border-zinc-850 text-zinc-300 hover:border-zinc-700"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs font-mono text-indigo-300">{preset.code}</span>
                      <span className="text-[10px] text-zinc-500 font-mono">Body: {preset.bodyYaw} | Head: {preset.headYaw}</span>
                    </div>
                    <span className="text-xs font-semibold text-white">{preset.name}</span>
                    <p className="text-[11px] text-zinc-400 leading-snug">{preset.desc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Decoupled Geometry Inspector & Simulator */}
          <div className="lg:col-span-2 bg-zinc-950 border border-zinc-850 p-6 rounded-2xl space-y-6">
            <div className="flex items-center justify-between border-b border-zinc-850 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-indigo-400" />
                  Independent Body vs Head Geometry Controls
                </h3>
                <p className="text-xs text-zinc-400">
                  Separates torso orientation (`body_yaw`) from head facing angle (`head_yaw`) and gaze vector (`gaze`).
                </p>
              </div>
              <span className="text-xs font-mono px-3 py-1 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold">
                Decoupled
              </span>
            </div>

            {/* Geometry Sliders Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Body Orientation */}
              <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-850 space-y-4">
                <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                  <Compass className="w-4 h-4 text-indigo-400" />
                  Body Stance Orientation
                </h4>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-xs font-mono text-zinc-300 mb-1">
                      <span>Body Yaw (Torso Rotation)</span>
                      <span className="text-indigo-300 font-bold">{bodyYaw}</span>
                    </div>
                    <select
                      value={bodyYaw}
                      onChange={(e) => setBodyYaw(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white font-mono outline-none"
                    >
                      <option value="000">000 (Front Standing 0°)</option>
                      <option value="R015">R015 (Right Turn 15°)</option>
                      <option value="R030">R030 (Right Turn 30° - Standard Catalog)</option>
                      <option value="R045">R045 (Right Turn 45°)</option>
                      <option value="L015">L015 (Left Turn 15°)</option>
                      <option value="L030">L030 (Left Turn 30°)</option>
                      <option value="L045">L045 (Left Turn 45°)</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Head Orientation */}
              <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-850 space-y-4">
                <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                  <UserCheck className="w-4 h-4 text-pink-400" />
                  Head & Facial Facing Angle
                </h4>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-xs font-mono text-zinc-300 mb-1">
                      <span>Head Yaw (Facing Angle)</span>
                      <span className="text-pink-300 font-bold">{headYaw}</span>
                    </div>
                    <select
                      value={headYaw}
                      onChange={(e) => setHeadYaw(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white font-mono outline-none"
                    >
                      <option value="000">000 (Front Gaze into Camera)</option>
                      <option value="R015">R015 (Right Head Turn 15°)</option>
                      <option value="R030">R030 (Right Head Turn 30°)</option>
                      <option value="L015">L015 (Left Head Turn 15°)</option>
                      <option value="L030">L030 (Left Head Turn 30°)</option>
                    </select>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs font-mono text-zinc-300 mb-1">
                      <span>Head Pitch</span>
                      <span className="text-pink-300 font-bold">{headPitch}</span>
                    </div>
                    <select
                      value={headPitch}
                      onChange={(e) => setHeadPitch(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white font-mono outline-none"
                    >
                      <option value="000">000 (Eye Level)</option>
                      <option value="UP05">UP05 (Chin Up 5°)</option>
                      <option value="DN05">DN05 (Chin Down 5°)</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            {/* Live Angle Geometry Combination Summary Card */}
            <div className="p-4 rounded-xl bg-indigo-950/40 border border-indigo-800/60 flex items-center justify-between font-mono text-xs">
              <div>
                <span className="text-zinc-400 block text-[10px] uppercase">Active Geometry Vector</span>
                <span className="text-white font-bold text-sm">
                  body_yaw={bodyYaw} + head_yaw={headYaw} + head_pitch={headPitch}
                </span>
                <p className="text-indigo-300 text-[11px] mt-0.5">
                  {bodyYaw !== headYaw
                    ? "✨ Independent Pose Active: Body is angled for garment silhouette while face maintains camera eye-contact!"
                    : "Standard Aligned Facing Vector."}
                </p>
              </div>
              <button
                onClick={() => toast.success(`Saved Pose Vector: body_yaw=${bodyYaw}, head_yaw=${headYaw}`)}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition shadow-lg shadow-indigo-600/20 shrink-0"
              >
                Apply to Generation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
