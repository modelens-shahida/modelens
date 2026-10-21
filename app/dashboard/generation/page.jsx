"use client";
import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import {
  Sparkles,
  Lock,
  Image as ImageIcon,
  Loader2,
  CheckCircle2,
  Sliders,
  Zap,
  ShieldCheck,
  Camera,
  Coins,
  Layers,
  Flame,
  Info
} from "lucide-react";
import toast from "react-hot-toast";

const PIPELINE_MODELS = [
  {
    id: "rosanne-v1",
    name: "Eliska — Studio Editorial Model",
    description: "Flagship luxury fashion digital model with locked facial geometry, high-fidelity skin realism & pose directing.",
    badge: "Identity Locked",
    badgeColor: "bg-purple-900/50 border-purple-700 text-purple-300",
    color: "border-purple-600",
  },
  {
    id: "dalle3",
    name: "Creative Scene Exploration",
    description: "Open-ended scene exploration and concept moodboarding across contemporary fashion aesthetics.",
    badge: "Standard",
    badgeColor: "bg-zinc-800 border-zinc-700 text-zinc-300",
    color: "border-zinc-700",
  },
];

const LUXURY_STYLING_PRESETS = [
  { id: "beauty_quiet_luxury", name: "Quiet Luxury", desc: "Sleek low bun, luminous nude makeup, clean manicure, calm confident gaze" },
  { id: "beauty_european_editorial", name: "European Editorial", desc: "Slick-back wet sheen, defined sculpted eyes, architectural poise" },
  { id: "beauty_soft_luxury", name: "Soft Luxury", desc: "Brushed-out waves, radiant skin, soft bronzed tones, relaxed elegance" },
  { id: "beauty_classic_evening", name: "Classic Evening", desc: "Polished updo, refined eye definition, satin lip, evening glamour" },
  { id: "beauty_modern_minimal", name: "Modern Minimal", desc: "Clean natural straight hair, fresh satin finish, clean architectural poise" },
  { id: "beauty_resort_luxury", name: "Resort Luxury", desc: "Sunkissed skin, relaxed texture, golden warmth, vacation ease" },
];

const QUALITY_TIERS = [
  {
    tier: "fast_preview",
    name: "Fast Preview",
    resolution: "2K",
    credits: 1,
    desc: "Rapid turnaround for concept vetting",
    icon: Zap,
    color: "border-emerald-700/60 bg-emerald-950/20 text-emerald-400"
  },
  {
    tier: "high_fidelity",
    name: "High Fidelity",
    resolution: "2K",
    credits: 3,
    desc: "Studio-quality commercial assets with full texture",
    icon: Sparkles,
    color: "border-purple-600/70 bg-purple-950/30 text-purple-300",
    popular: true
  },
  {
    tier: "ultra_master",
    name: "Ultra Master",
    resolution: "4K",
    credits: 5,
    desc: "Maximum detail 4K editorial campaign renders",
    icon: Flame,
    color: "border-amber-600/70 bg-amber-950/20 text-amber-300"
  },
];

const POSE_PRESETS = [
  { pose_id: "POSE-ROS-001", name: "Editorial Standing", angle: "FRONT", camera: "Eye-Level" },
  { pose_id: "POSE-ROS-002", name: "Three Quarter Left", angle: "L30", camera: "Eye-Level" },
  { pose_id: "POSE-ROS-003", name: "Three Quarter Right", angle: "R30", camera: "Eye-Level" },
  { pose_id: "POSE-ROS-004", name: "Left Profile", angle: "L45", camera: "Eye-Level" },
  { pose_id: "POSE-ROS-005", name: "Right Profile", angle: "R45", camera: "Eye-Level" },
  { pose_id: "POSE-ROS-006", name: "Runway Walk", angle: "FRONT", camera: "Low-Angle" },
  { pose_id: "POSE-ROS-007", name: "Editorial Seated", angle: "FRONT", camera: "Eye-Level" },
  { pose_id: "POSE-ROS-008", name: "Over Shoulder", angle: "L30", camera: "High-Angle" },
];

const PROMPT_INSPIRATIONS = [
  "Parisian Haussmann Balcony, warm golden hour, silk slip dress",
  "Minimalist brutalist concrete gallery, dramatic directional shadows",
  "Sunlit marble loft, soft daylight, tailored cashmere blazer",
  "Haute couture runway, cinematic backstage spotlights, satin evening gown",
];

const IDENTITY_LOCKS = [
  "face_geometry",
  "eye_color",
  "skin_tone",
  "hairline",
  "identity_markers",
  "age_anchor",
];

export default function GenerationPage() {
  const { user } = useAuth();
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [selectedPipeline, setSelectedPipeline] = useState("rosanne-v1");
  const [selectedTier, setSelectedTier] = useState("high_fidelity");
  const [selectedPresetId, setSelectedPresetId] = useState("POSE-ROS-001");
  const [selectedStylePresetId, setSelectedStylePresetId] = useState("beauty_quiet_luxury");
  const [identityStrength, setIdentityStrength] = useState(0.82);
  const [scenePrompt, setScenePrompt] = useState("");
  const [poseAssets, setPoseAssets] = useState([]);
  const [selectedPoseAssetId, setSelectedPoseAssetId] = useState("");
  const [selectedPoseAsset, setSelectedPoseAsset] = useState(null);
  const [balance, setBalance] = useState(100);
  const [submitting, setSubmitting] = useState(false);
  const [submittedJob, setSubmittedJob] = useState(null);

  useEffect(() => {
    api.get("/api/v1/brands").then(data => {
      setBrands(data || []);
      if (data?.length > 0) setSelectedBrandId(data[0].id.toString());
    }).catch(() => {});

    api.get("/api/v1/credits/balance").then(data => {
      if (data && typeof data.balance === "number") {
        setBalance(data.balance);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedBrandId) return;
    api.get(`/api/v1/assets?brand_id=${selectedBrandId}&limit=50`).then(data => {
      setPoseAssets(data || []);
    }).catch(() => {});
  }, [selectedBrandId]);

  const handlePoseAssetSelect = (assetId) => {
    setSelectedPoseAssetId(assetId);
    const asset = poseAssets.find(a => a.id.toString() === assetId.toString());
    setSelectedPoseAsset(asset || null);
  };

  const selectedTierObj = QUALITY_TIERS.find(t => t.tier === selectedTier) || QUALITY_TIERS[1];
  const requiredCredits = selectedTierObj.credits;
  const hasSufficientCredits = balance >= requiredCredits;

  const handleSubmit = async () => {
    if (!scenePrompt.trim()) {
      toast.error("Please enter a scene description");
      return;
    }
    if (!hasSufficientCredits) {
      toast.error(`Insufficient credits! Required: ${requiredCredits}, Available: ${balance}`);
      return;
    }

    setSubmitting(true);
    try {
      let result;
      if (selectedPipeline === "rosanne-v1") {
        result = await api.post("/api/v1/rosanne/generate", {
          workflow_template_id: "rosanne-v1",
          brand_id: parseInt(selectedBrandId) || 1,
          quality: selectedTier === "ultra_master" ? "max" : selectedTier === "fast_preview" ? "standard" : "quality",
          identity_strength: identityStrength,
          beauty_direction: selectedStylePresetId,
          pose_preset_id: selectedPresetId,
          scene_prompt: scenePrompt,
          inputs: {
            scene_description: scenePrompt,
            pose_filename: selectedPoseAsset?.filename || "",
            beauty_direction: selectedStylePresetId,
          },
        });
      } else {
        result = await api.post("/api/v1/jobs/workflow", {
          brand_id: parseInt(selectedBrandId) || 1,
          quality_mode: selectedTier,
          inputs: {
            prompt: scenePrompt,
          },
        });
      }

      setSubmittedJob(result);
      setBalance(prev => Math.max(0, prev - requiredCredits));
      toast.success(`Job queued! ID: #${result.job_id || result.id}`);
    } catch (e) {
      toast.error(e.message || "Failed to submit generation job");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-white p-6 md:p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Top Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800/80 pb-6">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-900/30 border border-purple-700/50 text-purple-400">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                Generation Studio
                <span className="text-[10px] uppercase font-bold tracking-widest bg-purple-500/10 border border-purple-500/30 text-purple-400 px-2 py-0.5 rounded-full">
                  v2.4
                </span>
              </h1>
              <p className="text-xs text-zinc-400 mt-0.5">
                AI Fashion Photoshoot Studio with Precision Identity Locks, Direction Presets & Standardized Quality Tiers
              </p>
            </div>
          </div>

          {/* Credit Pill */}
          <div className="flex items-center gap-2 bg-zinc-900/80 border border-zinc-800 px-3.5 py-2 rounded-xl text-xs">
            <Coins className="w-4 h-4 text-amber-400" />
            <span className="text-zinc-400">Balance:</span>
            <span className="font-bold text-white">{balance}</span>
            <span className="text-zinc-500">credits</span>
          </div>
        </div>

        {/* Workspace Brand Selector */}
        <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-5">
          <label className="text-xs font-semibold text-zinc-300 mb-2 flex items-center justify-between">
            <span>Brand Workspace</span>
            <span className="text-[11px] text-zinc-500 font-normal">Multi-tenant Isolation</span>
          </label>
          <select
            value={selectedBrandId}
            onChange={(e) => setSelectedBrandId(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-700/80 rounded-xl px-4 py-2.5 text-sm text-zinc-200 outline-none focus:border-purple-500 transition"
          >
            {brands.length > 0 ? (
              brands.map(b => <option key={b.id} value={b.id}>{b.name} (ID: #{b.id})</option>)
            ) : (
              <option value="1">Default Workspace</option>
            )}
          </select>
        </div>

        {/* Pipeline Model Selector */}
        <div className="space-y-3">
          <label className="text-xs font-semibold text-zinc-300 block">
            Select Generation Engine
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {PIPELINE_MODELS.map(model => {
              const isSelected = selectedPipeline === model.id;
              return (
                <div
                  key={model.id}
                  onClick={() => setSelectedPipeline(model.id)}
                  className={`relative cursor-pointer border-2 rounded-2xl p-5 transition flex flex-col justify-between ${
                    isSelected
                      ? "border-purple-500 bg-purple-950/20 shadow-lg shadow-purple-950/40"
                      : "border-zinc-850 bg-zinc-900/40 hover:border-zinc-700"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${model.badgeColor}`}>
                        {model.badge}
                      </span>
                      {isSelected && <CheckCircle2 className="w-4 h-4 text-purple-400" />}
                    </div>
                    <h3 className="text-sm font-bold text-white mb-1">{model.name}</h3>
                    <p className="text-xs text-zinc-400 leading-relaxed">{model.description}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Quality Tiers */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-zinc-300 block">
              Standardized Quality Tier
            </label>
            <span className="text-[11px] text-zinc-500">Auto-dispatched with SLA priority</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {QUALITY_TIERS.map(tier => {
              const IconComp = tier.icon;
              const isSelected = selectedTier === tier.tier;
              return (
                <div
                  key={tier.tier}
                  onClick={() => setSelectedTier(tier.tier)}
                  className={`relative cursor-pointer border-2 rounded-2xl p-4 transition flex flex-col justify-between ${
                    isSelected
                      ? "border-purple-500 bg-purple-950/25 shadow-md shadow-purple-950/40"
                      : "border-zinc-850 bg-zinc-900/40 hover:border-zinc-700"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold text-white flex items-center gap-1.5">
                        <IconComp className="w-3.5 h-3.5 text-purple-400" />
                        {tier.name}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                        {tier.resolution}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400 mb-3">{tier.desc}</p>
                  </div>
                  <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60 text-xs">
                    <span className="text-zinc-500">Cost:</span>
                    <span className="font-bold text-purple-300">{tier.credits} {tier.credits === 1 ? "credit" : "credits"}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Rosanne Identity Locks Banner & Pose Selector */}
        {selectedPipeline === "rosanne-v1" && (
          <div className="bg-zinc-900/50 border border-purple-800/40 rounded-2xl p-6 space-y-6">
            
            {/* Identity Locks Card */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-purple-400" />
                  <span className="text-xs font-bold text-white">Studio Identity Locks (6/6 Active)</span>
                </div>
                <span className="text-[11px] text-purple-300/80">Golden Reference Rig</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {IDENTITY_LOCKS.map(lock => (
                  <div key={lock} className="flex items-center gap-1.5 bg-purple-950/30 border border-purple-800/40 px-2.5 py-1.5 rounded-lg text-[11px] text-purple-200">
                    <Lock className="w-3 h-3 text-purple-400" />
                    <span>{lock.replace("_", " ")}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Luxury Styling Direction Presets */}
            <div>
              <div className="flex items-center justify-between text-xs mb-2.5">
                <span className="text-zinc-300 font-medium flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                  Luxury Styling Direction (Smart Presets)
                </span>
                <span className="text-[11px] font-mono text-purple-300">
                  Identity Locked (0.82 Standard)
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {LUXURY_STYLING_PRESETS.map((preset) => {
                  const isActive = selectedStylePresetId === preset.id;
                  return (
                    <div
                      key={preset.id}
                      onClick={() => setSelectedStylePresetId(preset.id)}
                      className={`p-3 rounded-xl border cursor-pointer transition flex flex-col justify-between ${
                        isActive
                          ? "bg-purple-950/40 border-purple-500 text-white shadow-sm"
                          : "bg-zinc-950/60 border-zinc-800 hover:border-zinc-700 text-zinc-300"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold">{preset.name}</span>
                        {isActive && <CheckCircle2 className="w-3.5 h-3.5 text-purple-400" />}
                      </div>
                      <p className="text-[10px] text-zinc-400 line-clamp-2 leading-tight">{preset.desc}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Editorial Pose Presets Quick Select */}
            <div>
              <label className="text-xs font-semibold text-zinc-300 mb-2 flex items-center gap-1.5 block">
                <Camera className="w-3.5 h-3.5 text-purple-400" />
                Editorial Pose Presets (8 Available)
              </label>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {POSE_PRESETS.map(preset => {
                  const isPresetActive = selectedPresetId === preset.pose_id;
                  return (
                    <div
                      key={preset.pose_id}
                      onClick={() => setSelectedPresetId(preset.pose_id)}
                      className={`cursor-pointer border rounded-xl p-2.5 text-left transition ${
                        isPresetActive
                          ? "border-purple-500 bg-purple-950/40 text-white"
                          : "border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:border-zinc-700"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-bold text-purple-400">{preset.angle}</span>
                        <span className="text-[9px] text-zinc-500">{preset.camera}</span>
                      </div>
                      <p className="text-xs font-medium truncate text-zinc-200">{preset.name}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Optional Custom Pose Asset Reference */}
            <div>
              <label className="text-xs font-semibold text-zinc-300 mb-1.5 block">
                Custom Pose Conditioning Asset <span className="text-zinc-500 font-normal">(optional OpenPose image)</span>
              </label>
              <select
                value={selectedPoseAssetId}
                onChange={(e) => handlePoseAssetSelect(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700/80 rounded-xl px-4 py-2.5 text-sm text-zinc-200 outline-none"
              >
                <option value="">No custom pose file (Use preset)</option>
                {poseAssets.map(a => (
                  <option key={a.id} value={a.id}>{a.name || a.filename}</option>
                ))}
              </select>

              {selectedPoseAsset && (
                <div className="mt-3 flex items-center gap-3 bg-zinc-850/60 border border-zinc-750 rounded-xl p-3">
                  {selectedPoseAsset.thumbnail_url ? (
                    <img
                      src={selectedPoseAsset.thumbnail_url}
                      alt="Pose preview"
                      className="w-12 h-12 rounded-lg object-cover border border-zinc-700"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-lg bg-zinc-800 flex items-center justify-center">
                      <ImageIcon className="w-5 h-5 text-zinc-500" />
                    </div>
                  )}
                  <div className="text-xs">
                    <p className="font-semibold text-white">{selectedPoseAsset.name || selectedPoseAsset.filename}</p>
                    <p className="text-zinc-400 text-[11px]">Conditioning reference attached</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Scene Prompt & Quick Tags */}
        <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-zinc-300 block">
              Scene Description & Wardrobe
            </label>
            <span className="text-[11px] text-zinc-500">Structured prompt engine</span>
          </div>

          <textarea
            value={scenePrompt}
            onChange={(e) => setScenePrompt(e.target.value)}
            placeholder={
              selectedPipeline === "rosanne-v1"
                ? "Describe environment, lighting, mood, and garments (e.g., 'Rosanne standing on a sunlit Parisian marble terrace wearing an oversized cashmere trench coat, soft 35mm golden hour lighting')."
                : "Describe your creative vision..."
            }
            rows={4}
            className="w-full bg-zinc-900 border border-zinc-700/80 rounded-xl px-4 py-3 text-sm text-zinc-100 outline-none focus:border-purple-500 transition resize-none leading-relaxed"
          />

          {/* Prompt Inspirations */}
          <div>
            <span className="text-[11px] text-zinc-400 block mb-2">Quick Inspiration Presets:</span>
            <div className="flex flex-wrap gap-2">
              {PROMPT_INSPIRATIONS.map((preset, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setScenePrompt(preset)}
                  className="text-left text-[11px] bg-zinc-850 hover:bg-zinc-800 text-zinc-300 hover:text-white px-3 py-1.5 rounded-lg border border-zinc-750 transition"
                >
                  "{preset}"
                </button>
              ))}
            </div>
          </div>

          {/* Submit Action */}
          <div className="pt-2">
            <button
              onClick={handleSubmit}
              disabled={submitting || !scenePrompt.trim() || !hasSufficientCredits}
              className={`w-full py-3.5 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2 shadow-lg ${
                hasSufficientCredits
                  ? "bg-purple-600 hover:bg-purple-700 text-white shadow-purple-900/30"
                  : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
              } disabled:opacity-50`}
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Dispatching to ComfyUI Cluster...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>
                    {selectedPipeline === "rosanne-v1" ? "Run Rosanne Pipeline" : "Generate Master Image"}
                    {" "}• ({requiredCredits} {requiredCredits === 1 ? "Credit" : "Credits"})
                  </span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Job Notification Toast Card */}
        {submittedJob && (
          <div className="bg-emerald-950/30 border border-emerald-800/40 rounded-2xl p-5 flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <div className="text-xs space-y-1">
              <p className="font-bold text-emerald-300 text-sm">Generation Dispatched Successfully!</p>
              <p className="text-zinc-300">
                Job <span className="font-mono text-purple-300">#{submittedJob.job_id || submittedJob.id}</span> is actively rendering.
              </p>
              <p className="text-zinc-500 text-[11px]">
                Quality Tier: <strong className="text-zinc-300">{selectedTier}</strong> • Remaining Balance: <strong className="text-amber-400">{balance} credits</strong>
              </p>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
