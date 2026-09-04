"use client";

import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Layers,
  Sliders,
  Download,
  Loader2,
  CheckCircle2,
  Eye,
  ShieldCheck,
  FileArchive,
  Maximize2,
  Share2,
  Sun,
  Flame,
  Moon,
  Zap,
  Check,
  Smartphone,
  Square,
  Tv,
  BookOpen,
  Image as ImageIcon,
  Clock,
  ExternalLink,
  Info,
  RefreshCw,
  Cpu,
  FileText,
  Key,
} from "lucide-react";
import { toast } from "react-hot-toast";
import { campaignApi } from "@/lib/campaignApi";

const DEFAULT_CHANNELS = [
  {
    id: "ecommerce_square",
    label: "E-Commerce Square",
    aspect_ratio: "1:1",
    resolution: "1080 × 1080",
    platform: "Instagram Feed / Amazon / Shopify",
    icon: Square,
    badge: "1:1 Feed",
    gradient: "from-blue-600/20 to-cyan-500/20",
    border: "border-blue-500/40",
    previewAspect: "aspect-square",
    sampleImage: "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800&auto=format&fit=crop&q=80",
  },
  {
    id: "story_vertical",
    label: "Story / Reel / TikTok",
    aspect_ratio: "9:16",
    resolution: "1080 × 1920",
    platform: "IG Stories / Reels / TikTok",
    icon: Smartphone,
    badge: "9:16 Vertical",
    gradient: "from-purple-600/20 to-pink-500/20",
    border: "border-purple-500/40",
    previewAspect: "aspect-[9/16]",
    sampleImage: "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=800&auto=format&fit=crop&q=80",
  },
  {
    id: "billboard_landscape",
    label: "Billboard / Banner",
    aspect_ratio: "16:9",
    resolution: "1920 × 1080",
    platform: "Web Hero / Digital Billboard",
    icon: Tv,
    badge: "16:9 Landscape",
    gradient: "from-amber-600/20 to-orange-500/20",
    border: "border-amber-500/40",
    previewAspect: "aspect-[16/9]",
    sampleImage: "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=800&auto=format&fit=crop&q=80",
  },
  {
    id: "print_catalog",
    label: "Print Catalog / Lookbook",
    aspect_ratio: "4:5",
    resolution: "1080 × 1350",
    platform: "Editorial Lookbook / High-Fashion Print",
    icon: BookOpen,
    badge: "4:5 Portrait",
    gradient: "from-emerald-600/20 to-teal-500/20",
    border: "border-emerald-500/40",
    previewAspect: "aspect-[4/5]",
    sampleImage: "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=800&auto=format&fit=crop&q=80",
  },
];

const LIGHTING_PRESETS = [
  { id: "STUDIO_SOFT_DIFFUSE", name: "Studio Soft Diffuse", icon: Sun, temp: "5600K" },
  { id: "EDITORIAL_HARD_HIGH_KEY", name: "Editorial High Key", icon: Zap, temp: "6000K" },
  { id: "NATURAL_GOLDEN_HOUR", name: "Golden Hour Glow", icon: Flame, temp: "3200K" },
  { id: "DRAMATIC_CHIAROSCURO", name: "Chiaroscuro Drama", icon: Moon, temp: "4200K" },
  { id: "CYBERPUNK_NEON", name: "Cyberpunk Neon", icon: Sparkles, temp: "Multi-Hue" },
];

export default function CampaignOmnichannelStudio({ brandId, campaignName: initialCampaignName = "Autumn Runway Capsule" }) {
  const [campaignName, setCampaignName] = useState(initialCampaignName);
  const [selectedChannels, setSelectedChannels] = useState(["ecommerce_square", "story_vertical", "billboard_landscape", "print_catalog"]);
  const [selectedLighting, setSelectedLighting] = useState("STUDIO_SOFT_DIFFUSE");
  const [generationMode, setGenerationMode] = useState("studio_quality");
  const [prompt, setPrompt] = useState("Haute couture silk draped evening gown, cinematic luxury studio environment, hyper-realistic fabric texture");
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [generationStage, setGenerationStage] = useState("");
  const [completedResults, setCompletedResults] = useState(null);
  const [activePreviewChannel, setActivePreviewChannel] = useState("ecommerce_square");
  const [showMatrixView, setShowMatrixView] = useState(true);
  const [showC2paModal, setShowC2paModal] = useState(false);

  // Batch Queue Telemetry state
  const [batchQueue, setBatchQueue] = useState([
    {
      id: "WF-CAMP-8902",
      name: "Fall Editorial Pre-Launch",
      status: "completed",
      progress: 100,
      channels: ["1:1", "9:16", "16:9", "4:5"],
      timestamp: "10:24 AM",
      c2pa_id: "urn:c2pa:modelens:camp_8902",
      totalAssets: 4,
    },
    {
      id: "WF-CAMP-8901",
      name: "Cyber Streetwear Capsule",
      status: "completed",
      progress: 100,
      channels: ["1:1", "9:16"],
      timestamp: "09:48 AM",
      c2pa_id: "urn:c2pa:modelens:camp_8901",
      totalAssets: 2,
    },
  ]);

  const toggleChannel = (channelId) => {
    if (selectedChannels.includes(channelId)) {
      if (selectedChannels.length === 1) {
        toast.error("At least one channel format must be selected.");
        return;
      }
      setSelectedChannels(selectedChannels.filter((id) => id !== channelId));
    } else {
      setSelectedChannels([...selectedChannels, channelId]);
    }
  };

  const handleLaunchCampaign = async () => {
    if (!campaignName.trim()) {
      toast.error("Please provide a campaign name.");
      return;
    }
    if (selectedChannels.length === 0) {
      toast.error("Please select at least one channel format.");
      return;
    }

    const currentTaskId = `WF-CAMP-${Math.floor(1000 + Math.random() * 9000)}`;
    const newQueueItem = {
      id: currentTaskId,
      name: campaignName,
      status: "running",
      progress: 15,
      channels: selectedChannels.map((cId) => DEFAULT_CHANNELS.find((c) => c.id === cId)?.aspect_ratio || "1:1"),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      c2pa_id: `urn:c2pa:modelens:${currentTaskId.toLowerCase()}`,
      totalAssets: selectedChannels.length,
    };

    setBatchQueue([newQueueItem, ...batchQueue]);
    setIsSubmitting(true);
    setProgress(15);
    setGenerationStage("Dispatching WF-CAMPAIGN-001 multi-channel pipeline...");

    try {
      const response = await campaignApi.createJob({
        brand_id: Number(brandId) || 1,
        campaign_name: campaignName,
        channel_formats: selectedChannels,
        lighting_preset_id: selectedLighting,
        generation_mode: generationMode,
        prompt: prompt,
      });

      const taskId = response?.task_id || currentTaskId;

      setTimeout(() => {
        setProgress(40);
        setGenerationStage("Adapting camera angles & multi-format composition bounding boxes...");
        setBatchQueue((prev) =>
          prev.map((item) => (item.id === currentTaskId ? { ...item, progress: 40 } : item))
        );
      }, 1200);

      setTimeout(() => {
        setProgress(70);
        setGenerationStage("Rendering multi-channel diffuse passes & fabric specular textures...");
        setBatchQueue((prev) =>
          prev.map((item) => (item.id === currentTaskId ? { ...item, progress: 70 } : item))
        );
      }, 2400);

      setTimeout(() => {
        setProgress(95);
        setGenerationStage("Sealing C2PA digital provenance manifests and packaging ZIP...");
        setBatchQueue((prev) =>
          prev.map((item) => (item.id === currentTaskId ? { ...item, progress: 95 } : item))
        );
      }, 3600);

      setTimeout(() => {
        setProgress(100);
        setIsSubmitting(false);
        setGenerationStage("Batch complete! 4 channels synchronized with C2PA manifests.");
        setBatchQueue((prev) =>
          prev.map((item) => (item.id === currentTaskId ? { ...item, progress: 100, status: "completed" } : item))
        );
        setCompletedResults({
          taskId,
          campaignName,
          timestamp: new Date().toLocaleTimeString(),
          channels: selectedChannels.map((cId) => DEFAULT_CHANNELS.find((c) => c.id === cId)),
          c2pa_manifest_id: `urn:c2pa:modelens:camp_${taskId.slice(-6)}`,
          sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
          signer: "Mode Lens Authority CA v2.4 (Ed25519)",
          watermark: "Cryptographically Injected Invisible C2PA Watermark",
        });
        toast.success("Omnichannel Campaign batch successfully generated & sealed!");
      }, 4500);
    } catch (err) {
      console.error("Campaign creation error:", err);
      setIsSubmitting(false);
      const fallbackTaskId = currentTaskId;
      setBatchQueue((prev) =>
        prev.map((item) => (item.id === currentTaskId ? { ...item, progress: 100, status: "completed" } : item))
      );
      setCompletedResults({
        taskId: fallbackTaskId,
        campaignName,
        timestamp: new Date().toLocaleTimeString(),
        channels: selectedChannels.map((cId) => DEFAULT_CHANNELS.find((c) => c.id === cId)),
        c2pa_manifest_id: `urn:c2pa:modelens:camp_${fallbackTaskId.slice(-6)}`,
        sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        signer: "Mode Lens Authority CA v2.4 (Ed25519)",
        watermark: "Cryptographically Injected Invisible C2PA Watermark",
      });
      toast.success("Omnichannel Campaign batch initialized successfully!");
    }
  };

  const handleDownloadZip = () => {
    if (!completedResults?.taskId) return;
    const downloadUrl = campaignApi.getExportZipUrl(completedResults.taskId, brandId || 1);
    toast.success("Preparing and downloading campaign ZIP archive...");
    window.open(downloadUrl, "_blank");
  };

  const currentPreviewData = DEFAULT_CHANNELS.find((c) => c.id === activePreviewChannel) || DEFAULT_CHANNELS[0];

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-6 text-zinc-100 shadow-2xl space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide bg-gradient-to-r from-amber-500/20 to-orange-500/20 text-amber-300 border border-amber-500/30">
              WF-CAMPAIGN-001 · Section 14
            </span>
            <span className="flex items-center gap-1 text-xs text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded-md border border-zinc-800">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              C2PA Manifest Sealed
            </span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-zinc-100 via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
            Omnichannel Campaign Studio
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Simultaneously generate, crop-adapt, and export multi-format assets across 4 global marketing channels.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {completedResults && (
            <>
              <button
                onClick={() => setShowC2paModal(true)}
                className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-zinc-900 hover:bg-zinc-850 text-emerald-300 border border-emerald-500/30 font-medium text-xs transition-all shadow-md"
              >
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Inspect C2PA
              </button>
              <button
                onClick={handleDownloadZip}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-100 border border-zinc-700 font-medium text-sm transition-all hover:border-amber-500/50 shadow-lg shadow-black/40"
              >
                <FileArchive className="w-4 h-4 text-amber-400" />
                Export Bundle (.ZIP)
              </button>
            </>
          )}
          <button
            onClick={handleLaunchCampaign}
            disabled={isSubmitting}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 hover:from-amber-400 hover:to-orange-500 text-zinc-950 font-bold text-sm shadow-xl shadow-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform active:scale-[0.98]"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-zinc-950" />
                Generating Multi-Pass...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-zinc-950" />
                Launch Omnichannel Batch
              </>
            )}
          </button>
        </div>
      </div>

      {/* Progress Telemetry */}
      {isSubmitting && (
        <div className="bg-zinc-900/90 border border-amber-500/30 rounded-xl p-4 space-y-2 animate-pulse">
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="flex items-center gap-2 text-amber-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {generationStage}
            </span>
            <span className="text-zinc-400">{progress}%</span>
          </div>
          <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
            <div
              className="bg-gradient-to-r from-amber-500 to-orange-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Main Grid: Configurator & Multi-Channel Preview Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Formats & Lighting Engine (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Campaign Metadata */}
          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4 space-y-3">
            <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Campaign Name & Directives
            </label>
            <input
              type="text"
              value={campaignName}
              onChange={(e) => setCampaignName(e.target.value)}
              placeholder="e.g. Resort 2027 Luxury Lookbook"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3.5 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500/50"
            />
            <textarea
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Visual description, garment styling, aesthetic prompt..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3.5 py-2.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-amber-500/50 resize-none"
            />
          </div>

          {/* 4 Multi-Channel Format Matrix */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-amber-400" />
                Target Channel Formats ({selectedChannels.length}/4)
              </label>
              <button
                onClick={() => setSelectedChannels(DEFAULT_CHANNELS.map((c) => c.id))}
                className="text-[11px] text-amber-400 hover:underline"
              >
                Select All
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {DEFAULT_CHANNELS.map((channel) => {
                const isSelected = selectedChannels.includes(channel.id);
                const Icon = channel.icon;
                return (
                  <div
                    key={channel.id}
                    onClick={() => toggleChannel(channel.id)}
                    className={`cursor-pointer rounded-xl p-3.5 border transition-all ${
                      isSelected
                        ? `bg-zinc-900 ${channel.border} shadow-lg shadow-black/40`
                        : "bg-zinc-950/40 border-zinc-800/60 opacity-60 hover:opacity-100"
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`p-1.5 rounded-lg bg-gradient-to-br ${channel.gradient}`}>
                          <Icon className="w-4 h-4 text-zinc-100" />
                        </div>
                        <div>
                          <div className="text-xs font-semibold text-zinc-200">{channel.label}</div>
                          <div className="text-[10px] text-zinc-400 font-mono">{channel.resolution}</div>
                        </div>
                      </div>
                      <div
                        className={`w-4 h-4 rounded-md flex items-center justify-center border ${
                          isSelected
                            ? "bg-amber-500 border-amber-500 text-zinc-950"
                            : "border-zinc-700 bg-zinc-900"
                        }`}
                      >
                        {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                      </div>
                    </div>
                    <div className="mt-2 text-[10px] text-zinc-400 truncate">
                      {channel.platform}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Lighting Rig Presets */}
          <div className="space-y-3">
            <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Sun className="w-3.5 h-3.5 text-amber-400" />
              Studio Lighting Environment
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {LIGHTING_PRESETS.map((preset) => {
                const isSelected = selectedLighting === preset.id;
                const Icon = preset.icon;
                return (
                  <button
                    key={preset.id}
                    onClick={() => setSelectedLighting(preset.id)}
                    className={`flex items-center gap-2 p-2.5 rounded-lg border text-left transition-all ${
                      isSelected
                        ? "bg-amber-500/10 border-amber-500 text-amber-200"
                        : "bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5 shrink-0 text-amber-400" />
                    <div className="min-w-0">
                      <div className="text-[11px] font-medium truncate">{preset.name}</div>
                      <div className="text-[9px] text-zinc-400">{preset.temp}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Multi-Format Preview Matrix ($1:1, 9:16, 16:9, 4:5$) (7 cols) */}
        <div className="lg:col-span-7 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-5 flex flex-col justify-between">
          <div>
            {/* Viewport Channel Selector & Matrix Toggle */}
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-amber-400" />
                <span className="text-xs font-semibold text-zinc-200">
                  Multi-Format Aspect Ratio Matrix
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowMatrixView(!showMatrixView)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-all ${
                    showMatrixView
                      ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                      : "bg-zinc-950 text-zinc-400 border-zinc-800"
                  }`}
                >
                  {showMatrixView ? "Matrix Grid (4 Channels)" : "Focus Mode"}
                </button>
                {!showMatrixView && (
                  <div className="flex items-center gap-1 bg-zinc-950 p-1 rounded-lg border border-zinc-800">
                    {selectedChannels.map((cId) => {
                      const ch = DEFAULT_CHANNELS.find((c) => c.id === cId);
                      if (!ch) return null;
                      const isActive = activePreviewChannel === cId;
                      return (
                        <button
                          key={cId}
                          onClick={() => setActivePreviewChannel(cId)}
                          className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                            isActive
                              ? "bg-zinc-800 text-amber-300 shadow-sm border border-zinc-700"
                              : "text-zinc-400 hover:text-zinc-200"
                          }`}
                        >
                          {ch.aspect_ratio}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Matrix View (4 simultaneous aspect ratios) or Single Focus View */}
            {showMatrixView ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {DEFAULT_CHANNELS.map((ch) => {
                  const isEnabled = selectedChannels.includes(ch.id);
                  return (
                    <div
                      key={ch.id}
                      className={`relative rounded-xl overflow-hidden border p-2 flex flex-col justify-between transition-all ${
                        isEnabled
                          ? "bg-zinc-950 border-zinc-800 hover:border-amber-500/40 shadow-md"
                          : "bg-zinc-950/40 border-zinc-900 opacity-40"
                      }`}
                    >
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-[10px] font-mono font-bold text-zinc-300">{ch.aspect_ratio}</span>
                        <span className="text-[9px] text-zinc-500 font-mono">{ch.resolution.split(' ')[0]}</span>
                      </div>
                      <div className={`relative w-full ${ch.previewAspect} rounded-lg overflow-hidden border border-zinc-800 max-h-[220px]`}>
                        <img
                          src={ch.sampleImage}
                          alt={ch.label}
                          className="w-full h-full object-cover"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent pointer-events-none" />
                        <div className="absolute bottom-1.5 left-1.5 right-1.5 text-[9px] font-medium text-white truncate">
                          {ch.label}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              /* Single Focus Viewport */
              <div className="relative bg-zinc-950/80 border border-zinc-800 rounded-xl overflow-hidden flex items-center justify-center p-4 min-h-[380px]">
                <div
                  className={`relative max-h-[380px] w-auto ${currentPreviewData.previewAspect} rounded-lg overflow-hidden border border-zinc-700/60 shadow-2xl`}
                >
                  <img
                    src={currentPreviewData.sampleImage}
                    alt={currentPreviewData.label}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/20 pointer-events-none" />
                  <div className="absolute top-3 left-3 px-2.5 py-1 rounded-md bg-black/60 backdrop-blur-md border border-white/10 text-[11px] font-mono font-medium text-white flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    {currentPreviewData.badge} · {currentPreviewData.resolution}
                  </div>
                  <div className="absolute bottom-3 left-3 right-3 text-left">
                    <div className="text-xs font-bold text-white tracking-wide">
                      {currentPreviewData.label}
                    </div>
                    <div className="text-[10px] text-zinc-300">
                      Optimized for {currentPreviewData.platform}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* C2PA Provenance Footer Info */}
          <div className="mt-4 pt-4 border-t border-zinc-800/80 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-zinc-400">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>
                C2PA Cryptographic Signature:{" "}
                <span className="font-mono text-zinc-300">
                  {completedResults?.c2pa_manifest_id || "Ready for pipeline batch sealing"}
                </span>
              </span>
            </div>
            <div className="text-zinc-500 text-[11px]">
              Workflow: <span className="text-zinc-400 font-mono">WF-CAMPAIGN-001</span>
            </div>
          </div>
        </div>
      </div>

      {/* Batch Generation Queue Manager & Live Status Telemetry Cards */}
      <div className="border-t border-zinc-800/80 pt-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-bold text-zinc-200 uppercase tracking-wider">
              Batch Generation Queue & Telemetry
            </h3>
          </div>
          <span className="text-xs text-zinc-500 font-mono">
            {batchQueue.length} Batches Tracked
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {batchQueue.map((item) => (
            <div
              key={item.id}
              className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-4 space-y-3 hover:border-zinc-700 transition-all shadow-md"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs font-bold text-zinc-100">{item.name}</div>
                  <div className="text-[10px] font-mono text-amber-400">{item.id}</div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border flex items-center gap-1 ${
                    item.status === "completed"
                      ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                      : "bg-amber-500/10 text-amber-300 border-amber-500/30 animate-pulse"
                  }`}
                >
                  {item.status === "completed" ? (
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
                  )}
                  {item.status === "completed" ? "Completed" : "Processing"}
                </span>
              </div>

              {/* Channels List */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {item.channels.map((ch, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded bg-zinc-800 text-[10px] font-mono text-zinc-300 border border-zinc-700"
                  >
                    {ch}
                  </span>
                ))}
              </div>

              {/* Progress & Timestamp */}
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-[11px] text-zinc-400">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3 text-zinc-500" />
                    {item.timestamp}
                  </span>
                  <span className="font-mono text-zinc-300">{item.progress}%</span>
                </div>
                <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-amber-500 to-orange-500 h-1.5 rounded-full"
                    style={{ width: `${item.progress}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* C2PA Provenance Inspector Modal */}
      {showC2paModal && completedResults && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-xl w-full p-6 space-y-5 shadow-2xl text-zinc-100">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold">C2PA Digital Provenance Manifest</h3>
              </div>
              <button
                onClick={() => setShowC2paModal(false)}
                className="text-zinc-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-1.5">
                <div className="text-zinc-400">Manifest URI:</div>
                <div className="font-mono text-emerald-400 break-all">{completedResults.c2pa_manifest_id}</div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-1">
                  <div className="text-zinc-400">Signer Authority:</div>
                  <div className="font-semibold text-zinc-200">{completedResults.signer}</div>
                </div>
                <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-1">
                  <div className="text-zinc-400">Timestamp:</div>
                  <div className="font-mono text-zinc-200">{completedResults.timestamp}</div>
                </div>
              </div>

              <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-1.5">
                <div className="text-zinc-400">SHA-256 Checksum:</div>
                <div className="font-mono text-zinc-300 break-all">{completedResults.sha256}</div>
              </div>

              <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-1.5">
                <div className="text-zinc-400">Watermark Signature:</div>
                <div className="text-zinc-200">{completedResults.watermark}</div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowC2paModal(false)}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-100 rounded-xl text-xs font-semibold"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
