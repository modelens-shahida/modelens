"use client";
import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Sparkles, Lock, Image, Loader2, CheckCircle2 } from "lucide-react";
import toast from "react-hot-toast";

const PIPELINE_MODELS = [
  {
    id: "dalle3",
    name: "Standard DALL-E 3",
    description: "OpenAI DALL-E 3 image generation. Full creative control over scene and style.",
    badge: null,
    color: "border-zinc-700",
  },
  {
    id: "rosanne-v1",
    name: "Rosanne ComfyUI Pipeline",
    description: "Production-grade ComfyUI pipeline with Rosanne character identity pre-configured.",
    badge: "Identity Locked",
    color: "border-purple-600",
  },
];

export default function GenerationPage() {
  const { user } = useAuth();
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [selectedPipeline, setSelectedPipeline] = useState("dalle3");
  const [scenePrompt, setScenePrompt] = useState("");
  const [poseAssets, setPoseAssets] = useState([]);
  const [selectedPoseAssetId, setSelectedPoseAssetId] = useState("");
  const [selectedPoseAsset, setSelectedPoseAsset] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submittedJob, setSubmittedJob] = useState(null);

  useEffect(() => {
    api.get("/api/v1/brands").then(data => {
      setBrands(data || []);
      if (data?.length > 0) setSelectedBrandId(data[0].id.toString());
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

  const handleSubmit = async () => {
    if (!scenePrompt.trim()) {
      toast.error("Please enter a scene description");
      return;
    }
    setSubmitting(true);
    try {
      const payload = selectedPipeline === "rosanne-v1"
        ? {
            workflow_template_id: "rosanne-v1",
            brand_id: parseInt(selectedBrandId),
            inputs: {
              scene_description: scenePrompt,
              pose_filename: selectedPoseAsset?.filename || "",
            },
          }
        : {
            brand_id: parseInt(selectedBrandId),
            inputs: {
              prompt: scenePrompt,
            },
          };

      const result = await api.post("/api/v1/jobs/workflow", payload);
      setSubmittedJob(result);
      toast.success(`Job queued! ID: #${result.id || result.job_id}`);
      setScenePrompt("");
      setSelectedPoseAssetId("");
      setSelectedPoseAsset(null);
    } catch (e) {
      toast.error(e.message || "Failed to submit generation job");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Sparkles className="w-7 h-7 text-purple-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">AI Generation</h1>
            <p className="text-zinc-400 text-sm">Select pipeline and configure your generation</p>
          </div>
        </div>

        {/* Brand Selector */}
        <div className="mb-6">
          <label className="text-xs text-zinc-400 mb-1 block">Brand Workspace</label>
          <select
            value={selectedBrandId}
            onChange={(e) => setSelectedBrandId(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-zinc-200 outline-none"
          >
            {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </div>

        {/* Pipeline Model Selector */}
        <div className="mb-6">
          <label className="text-xs text-zinc-400 mb-3 block">Select Pipeline Model</label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {PIPELINE_MODELS.map(model => (
              <div
                key={model.id}
                onClick={() => setSelectedPipeline(model.id)}
                className={`relative cursor-pointer border-2 rounded-2xl p-5 transition ${
                  selectedPipeline === model.id
                    ? model.color + " bg-purple-950/20"
                    : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"
                }`}
              >
                {model.badge && (
                  <span className="flex items-center gap-1 text-xs bg-purple-900/50 border border-purple-700 text-purple-300 px-2 py-0.5 rounded-full mb-2 w-fit">
                    <Lock className="w-3 h-3" /> {model.badge}
                  </span>
                )}
                <h3 className="text-sm font-semibold text-white mb-1">{model.name}</h3>
                <p className="text-xs text-zinc-400">{model.description}</p>
                {selectedPipeline === model.id && (
                  <CheckCircle2 className="absolute top-4 right-4 w-4 h-4 text-purple-400" />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Input Controls */}
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 space-y-5">
          {/* Scene Prompt */}
          <div>
            <label className="text-xs text-zinc-400 mb-1 block">
              Scene Description {selectedPipeline === "rosanne-v1" && <span className="text-purple-400">(Node 14)</span>}
            </label>
            <textarea
              value={scenePrompt}
              onChange={(e) => setScenePrompt(e.target.value)}
              placeholder={selectedPipeline === "rosanne-v1"
                ? "Describe the scene... e.g. 'Walking through a sunlit Parisian street in summer dress'"
                : "Describe the image you want to generate..."}
              rows={4}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-200 outline-none focus:border-purple-500 transition resize-none"
            />
          </div>

          {/* Pose Reference - Only for Rosanne */}
          {selectedPipeline === "rosanne-v1" && (
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">
                Pose Reference Asset <span className="text-purple-400">(Node 22)</span>
                <span className="text-zinc-600 ml-1">(optional)</span>
              </label>
              <select
                value={selectedPoseAssetId}
                onChange={(e) => handlePoseAssetSelect(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-zinc-200 outline-none mb-3"
              >
                <option value="">No pose reference</option>
                {poseAssets.map(a => (
                  <option key={a.id} value={a.id}>{a.name || a.filename}</option>
                ))}
              </select>

              {/* Pose Preview */}
              {selectedPoseAsset && (
                <div className="flex items-center gap-3 bg-zinc-800 rounded-xl p-3">
                  {selectedPoseAsset.thumbnail_url ? (
                    <img
                      src={selectedPoseAsset.thumbnail_url}
                      alt="Pose reference"
                      className="w-16 h-16 rounded-lg object-cover border border-zinc-700"
                    />
                  ) : (
                    <div className="w-16 h-16 rounded-lg bg-zinc-700 flex items-center justify-center">
                      <Image className="w-6 h-6 text-zinc-500" />
                    </div>
                  )}
                  <div>
                    <p className="text-xs font-medium text-white">{selectedPoseAsset.name || selectedPoseAsset.filename}</p>
                    <p className="text-xs text-zinc-500">Pose reference selected</p>
                  </div>
                </div>
              )}

              {/* Identity Locked Notice */}
              <div className="mt-3 bg-purple-950/30 border border-purple-800/40 rounded-xl px-4 py-3">
                <div className="flex items-center gap-2">
                  <Lock className="w-3 h-3 text-purple-400" />
                  <p className="text-xs text-purple-300">
                    Rosanne's identity parameters are pre-configured and locked. Only scene and pose inputs are customizable.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Submit Button */}
          <button
            onClick={handleSubmit}
            disabled={submitting || !scenePrompt.trim()}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 py-3 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {submitting ? "Submitting..." : selectedPipeline === "rosanne-v1" ? "Run Rosanne Pipeline" : "Generate Image"}
          </button>
        </div>

        {/* Success State */}
        {submittedJob && (
          <div className="mt-4 bg-green-950/30 border border-green-800/40 rounded-2xl px-5 py-4 flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-green-400" />
            <div>
              <p className="text-sm font-semibold text-green-300">Generation Job Queued!</p>
              <p className="text-xs text-zinc-400">Job #{submittedJob.id || submittedJob.job_id} is processing. Check AI Generator for status.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
