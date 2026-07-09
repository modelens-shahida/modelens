"use client";

import React, { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Sparkles, Loader2, Play, CheckCircle2, AlertTriangle, ArrowRight, Clock, ExternalLink, RefreshCw, Layers, Video, ImageIcon, Film, Sliders } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "react-hot-toast";
import { useWebSocket } from "@/lib/useWebSocket";

function JobsPageContent() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  
  // Data loading states
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [brandAssets, setBrandAssets] = useState([]);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [characters, setCharacters] = useState([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState("");

  // Real-time WebSocket for job updates
  const { token } = useAuth();
  useWebSocket({
    token,
    brandId: selectedBrandId,
    onEvent: (event) => {
      if (event.type === "job.completed" || event.type === "job.failed") {
        fetchJobsList();
      }
    },
  });
  const [prompts, setPrompts] = useState([]);
  const [selectedPromptId, setSelectedPromptId] = useState("");
  
  // Dynamic Themes loading state
  const [themes, setThemes] = useState([]);
  const [selectedThemeId, setSelectedThemeId] = useState("");
  
  const [callbackUrl, setCallbackUrl] = useState("");
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // New states for pipeline generation workflows
  const [generationMode, setGenerationMode] = useState("pipeline"); // "pipeline" | "template"
  const [workflowType, setWorkflowType] = useState("flat_lay_to_model");
  const [selectedMotionType, setSelectedMotionType] = useState("runway_walk");
  const [selectedDurationSeconds, setSelectedDurationSeconds] = useState("5");
  const [backgroundStyle, setBackgroundStyle] = useState("studio");
  const [customBackgroundPrompt, setCustomBackgroundPrompt] = useState("");
  const [characterVersions, setCharacterVersions] = useState([]);
  const [selectedVersionId, setSelectedVersionId] = useState("");

  // Active polling jobs tracker
  const [activePollIds, setActivePollIds] = useState(new Set());
  const pollIntervalRef = useRef({});

  // Initialize page data
  const initPage = async () => {
    try {
      const brandData = await api.get("/api/v1/brands");
      setBrands(brandData);
      
      let initialBrandId = "";
      if (brandData.length > 0) {
        initialBrandId = brandData[0].id.toString();
      }

      // Check query parameter for brand_id
      const queryBrandId = searchParams.get("brand_id");
      if (queryBrandId && brandData.some(b => b.id.toString() === queryBrandId)) {
        initialBrandId = queryBrandId;
      }
      setSelectedBrandId(initialBrandId);

      const templateData = await api.get("/api/v1/jobs/workflow-templates");
      setTemplates(templateData);
      if (templateData.length > 0) {
        setSelectedTemplateId(templateData[0].id.toString());
      }

      // Load prompts globally
      const promptData = await api.get("/api/v1/prompts");
      setPrompts(promptData);
      if (promptData.length > 0) {
        setSelectedPromptId(promptData[0].id.toString());
      }

      // Initial job list fetch
      const jobData = await api.get(`/api/v1/jobs?limit=${itemsPerPage}&offset=${(currentPage - 1) * itemsPerPage}`);
      setJobs(jobData);

      // Track active jobs that need polling
      const activeIds = jobData
        .filter((j) => j.status === "pending" || j.status === "processing")
        .map((j) => j.id);
      setActivePollIds(new Set(activeIds));
    } catch (error) {
      toast.error(error.message || "Failed to load generator options");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    initPage();
    return () => {
      // Clear all active intervals on unmount
      Object.values(pollIntervalRef.current).forEach(clearInterval);
    };
  }, []);

  // Fetch jobs list
  const fetchJobsList = async () => {
    try {
      let url = `/api/v1/jobs?limit=${itemsPerPage}&offset=${(currentPage - 1) * itemsPerPage}`;
      if (selectedBrandId) {
        url += `&brand_id=${selectedBrandId}`;
      }
      const data = await api.get(url);
      setJobs(data);
      
      // Update our polling set
      const activeIds = data
        .filter((j) => j.status === "pending" || j.status === "processing")
        .map((j) => j.id);
      setActivePollIds((prev) => {
        const next = new Set(prev);
        activeIds.forEach((id) => next.add(id));
        return next;
      });
    } catch (error) {
      console.error("Failed to reload job history", error);
    }
  };

  // Reset page when brand changes
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedBrandId]);

  // Fetch brand assets, characters, and themes when brand selection changes
  useEffect(() => {
    async function fetchBrandData() {
      if (!selectedBrandId) {
        setBrandAssets([]);
        setSelectedAssetId("");
        setCharacters([]);
        setSelectedCharacterId("");
        setThemes([]);
        setSelectedThemeId("");
        return;
      }
      try {
        // Fetch Assets
        const assets = await api.get(`/api/v1/assets?brand_id=${selectedBrandId}`);
        setBrandAssets(assets);
        if (assets.length > 0) {
          setSelectedAssetId(assets[0].id.toString());
        } else {
          setSelectedAssetId("");
        }

        // Fetch Characters
        const charData = await api.get(`/api/v1/characters?brand_id=${selectedBrandId}`);
        setCharacters(charData);
        if (charData.length > 0) {
          setSelectedCharacterId(charData[0].id.toString());
        } else {
          setSelectedCharacterId("");
        }

        // Fetch Themes
        const themeData = await api.get(`/api/v1/themes?brand_id=${selectedBrandId}`);
        setThemes(themeData);

        // Pre-select theme if theme_id query param matches
        const queryThemeId = searchParams.get("theme_id");
        if (queryThemeId && themeData.some(t => t.id.toString() === queryThemeId)) {
          setSelectedThemeId(queryThemeId);
        } else {
          setSelectedThemeId("");
        }
      } catch (error) {
        console.error("Failed to load brand data", error);
      }
    }
    fetchBrandData();
    
    // Also update current active jobs filter
    if (!loading) {
      fetchJobsList();
    }
  }, [selectedBrandId, currentPage]);

  // Poll single job status
  const pollJobStatus = async (jobId) => {
    try {
      const updatedJob = await api.get(`/api/v1/jobs/${jobId}`);
      
      // Update jobs list in state
      setJobs((prevJobs) =>
        prevJobs.map((j) => (j.id === jobId ? updatedJob : j))
      );

      // If completed or failed, remove from active polling list and clear interval
      if (updatedJob.status === "completed" || updatedJob.status === "failed") {
        if (updatedJob.status === "completed") {
          toast.success(`Job #${jobId} completed successfully!`);
        } else {
          toast.error(`Job #${jobId} failed: ${updatedJob.error_message || "Unknown error"}`);
        }

        setActivePollIds((prev) => {
          const next = new Set(prev);
          next.delete(jobId);
          return next;
        });

        if (pollIntervalRef.current[jobId]) {
          clearInterval(pollIntervalRef.current[jobId]);
          delete pollIntervalRef.current[jobId];
        }
      }
    } catch (error) {
      console.error(`Failed to poll status for Job #${jobId}`, error);
    }
  };

  // Manage setInterval loops for active poll IDs
  useEffect(() => {
    activePollIds.forEach((jobId) => {
      // Set up polling interval if it doesn't exist yet
      if (!pollIntervalRef.current[jobId]) {
        // Poll immediately once, then set interval
        pollJobStatus(jobId);
        pollIntervalRef.current[jobId] = setInterval(() => {
          pollJobStatus(jobId);
        }, 2500);
      }
    });

    // Clear any intervals for jobs that are no longer active
    Object.keys(pollIntervalRef.current).forEach((key) => {
      const jobId = parseInt(key);
      if (!activePollIds.has(jobId)) {
        clearInterval(pollIntervalRef.current[jobId]);
        delete pollIntervalRef.current[jobId];
      }
    });
  }, [activePollIds]);

  // Fetch character versions when character changes
  useEffect(() => {
    async function fetchVersions() {
      if (!selectedCharacterId) {
        setCharacterVersions([]);
        setSelectedVersionId("");
        return;
      }
      try {
        const versions = await api.get(`/api/v1/characters/${selectedCharacterId}/versions`);
        setCharacterVersions(versions);
        if (versions.length > 0) {
          // Default to latest version
          const sorted = [...versions].sort((a, b) => b.version_number - a.version_number);
          setSelectedVersionId(sorted[0].id.toString());
        } else {
          setSelectedVersionId("");
        }
      } catch (error) {
        console.error("Failed to load character versions", error);
      }
    }
    fetchVersions();
  }, [selectedCharacterId]);

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!selectedBrandId) {
      toast.error("Brand is required");
      return;
    }

    setIsSubmitting(true);
    try {
      if (generationMode === "template") {
        if (!selectedTemplateId) {
          toast.error("Workflow Template is required");
          setIsSubmitting(false);
          return;
        }

        const selectedAsset = brandAssets.find((a) => a.id.toString() === selectedAssetId);
        const selectedChar = characters.find((c) => c.id.toString() === selectedCharacterId);
        const selectedPrompt = prompts.find((p) => p.id.toString() === selectedPromptId);
        const selectedTheme = themes.find((t) => t.id.toString() === selectedThemeId);

        const inputs = {
          urls: selectedAsset ? [selectedAsset.storage_path] : [],
          character_id: selectedChar ? selectedChar.id : null,
          character_name: selectedChar ? selectedChar.name : null,
          character_description: selectedChar ? selectedChar.description : null,
          prompt_id: selectedPrompt ? selectedPrompt.id : null,
          prompt_name: selectedPrompt ? selectedPrompt.name : null,
          prompt_text: selectedPrompt ? selectedPrompt.prompt_text : null,
          theme_id: selectedTheme ? selectedTheme.id : null,
          theme_name: selectedTheme ? selectedTheme.name : null,
          theme_json: selectedTheme ? selectedTheme.theme_json : null,
        };

        const payload = {
          brand_id: parseInt(selectedBrandId),
          workflow_template_id: parseInt(selectedTemplateId),
          inputs,
          callback_url: callbackUrl.trim() || null
        };

        const newJob = await api.post("/api/v1/jobs/generate", payload);
        toast.success("AI Generation Job scheduled successfully!");
        setCallbackUrl("");
        setJobs((prev) => [newJob, ...prev]);
        setActivePollIds((prev) => {
          const next = new Set(prev);
          next.add(newJob.id);
          return next;
        });
      } else {
        // Pipeline Mode
        if (!selectedAssetId) {
          toast.error("Source Catalog Asset is required");
          setIsSubmitting(false);
          return;
        }

        const inputs = {
          source_asset_id: parseInt(selectedAssetId),
        };

        if (workflowType === "video_generation") {
          inputs.motion_type = selectedMotionType || "runway_walk";
          inputs.duration_seconds = parseInt(selectedDurationSeconds) || 5;
        } else {
          inputs.character_id = selectedCharacterId ? parseInt(selectedCharacterId) : null;
          inputs.character_version_id = selectedVersionId ? parseInt(selectedVersionId) : null;
          inputs.background_style = backgroundStyle || "studio";
          if (backgroundStyle === "custom") {
            inputs.custom_background_prompt = customBackgroundPrompt.trim() || null;
          }
        }

        const payload = {
          brand_id: parseInt(selectedBrandId),
          workflow_type: workflowType,
          inputs,
          callback_url: callbackUrl.trim() || null
        };

        const newJob = await api.post("/api/v1/jobs/workflow", payload);
        toast.success("AI Generation Workflow scheduled successfully!");
        setCallbackUrl("");
        setJobs((prev) => [newJob, ...prev]);
        setActivePollIds((prev) => {
          const next = new Set(prev);
          next.add(newJob.id);
          return next;
        });
      }
    } catch (error) {
      toast.error(error.message || "Failed to trigger AI generation");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Helper to format status badges
  const getStatusBadge = (status) => {
    switch (status) {
      case "pending":
        return (
          <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold text-amber-400 bg-amber-950/30 border border-amber-800/30 px-2 py-0.5 rounded-full animate-pulse">
            <Clock size={10} /> Pending
          </span>
        );
      case "processing":
        return (
          <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold text-purple-400 bg-purple-950/30 border border-purple-800/30 px-2 py-0.5 rounded-full">
            <Loader2 size={10} className="animate-spin text-purple-400" /> Processing
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold text-emerald-400 bg-emerald-950/30 border border-emerald-800/30 px-2 py-0.5 rounded-full">
            <CheckCircle2 size={10} /> Completed
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold text-rose-400 bg-rose-950/30 border border-rose-800/30 px-2 py-0.5 rounded-full">
            <AlertTriangle size={10} /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold text-zinc-400 bg-zinc-850 border border-zinc-800 px-2 py-0.5 rounded-full">
            Unknown
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="animate-spin text-purple-500" size={24} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header section */}
      <div className="flex justify-between items-center">
        <div className="space-y-1">
          <h2 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100 flex items-center gap-2">
            <Sparkles className="text-purple-400" size={22} />
            AI Catalog Generator
          </h2>
          <p className="text-xs text-zinc-400">
            Generate stunning fashion assets using manual pipeline workflows or configured templates
          </p>
        </div>
        <button
          onClick={fetchJobsList}
          title="Reload job history"
          className="flex items-center justify-center bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-300 hover:text-white p-2 rounded-xl transition-all cursor-pointer shadow-md"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Main split work-desk */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Form Configurator */}
        <div className="lg:col-span-5 bg-zinc-900/20 border border-zinc-900 rounded-2xl p-6 space-y-6">
          {/* Generation Mode Tabs */}
          <div className="flex bg-zinc-950/80 border border-zinc-900 p-1 rounded-xl gap-1">
            <button
              type="button"
              onClick={() => setGenerationMode("pipeline")}
              className={`flex-1 py-2 px-3 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                generationMode === "pipeline"
                  ? "bg-purple-600 text-white shadow-md shadow-purple-950/30"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Sparkles size={13} /> Pipeline Workflows
            </button>
            <button
              type="button"
              onClick={() => setGenerationMode("template")}
              className={`flex-1 py-2 px-3 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                generationMode === "template"
                  ? "bg-purple-600 text-white shadow-md shadow-purple-950/30"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Layers size={13} /> AI Templates
            </button>
          </div>

          <form onSubmit={handleGenerate} className="space-y-5">
            {/* Pick Brand */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                Target Brand Label
              </label>
              <select
                value={selectedBrandId}
                onChange={(e) => setSelectedBrandId(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
              >
                {brands.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
            </div>

            {/* Pick Input Asset */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                Source Catalog Asset
              </label>
              {brandAssets.length === 0 ? (
                <div className="p-3 bg-zinc-950/40 border border-zinc-900/60 rounded-xl text-center text-[10px] text-zinc-500">
                  No assets available for this brand. Upload photos in Assets tab first.
                </div>
              ) : (
                <select
                  value={selectedAssetId}
                  onChange={(e) => setSelectedAssetId(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                >
                  <option value="">-- Select Source Asset --</option>
                  {brandAssets.map((a) => (
                    <option key={a.id} value={a.id}>{a.name || a.filename} (ID: {a.id})</option>
                  ))}
                </select>
              )}
            </div>

            {/* Source Catalog Preview */}
            {selectedAssetId && brandAssets.find(a => a.id.toString() === selectedAssetId) && (
              <div className="flex gap-3 items-center bg-zinc-950/60 border border-zinc-900 p-3 rounded-xl">
                <img
                  src={brandAssets.find(a => a.id.toString() === selectedAssetId)?.storage_path}
                  alt="Source preview"
                  className="w-12 h-12 object-cover rounded-lg border border-zinc-800"
                />
                <div className="truncate">
                  <span className="text-[9px] text-zinc-500 font-bold block uppercase tracking-wider">Catalog Preview</span>
                  <span className="text-zinc-300 font-medium truncate block text-xs max-w-[180px]">
                    {brandAssets.find(a => a.id.toString() === selectedAssetId)?.name || brandAssets.find(a => a.id.toString() === selectedAssetId)?.filename}
                  </span>
                </div>
              </div>
            )}

            {/* Pipeline Configuration Form */}
            {generationMode === "pipeline" ? (
              <div className="space-y-4 pt-1 border-t border-zinc-900">
                {/* Custom Card Selector for Pipeline Workflows */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    Workflow Pipeline
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { id: "flat_lay_to_model", label: "Flat-Lay to Model", desc: "Flatlays into model shots", icon: ImageIcon },
                      { id: "mannequin_to_model", label: "Mannequin to Model", desc: "Mannequins to model shots", icon: ImageIcon },
                      { id: "video_generation", label: "Video Generation", desc: "Animate into motion video", icon: Video },
                      { id: "on_model_replacement", label: "On-Model Swap", desc: "Swap model/outfit on catalog", icon: Sparkles },
                      { id: "background_replacement", label: "Background Swap", desc: "Change photo background", icon: Layers }
                    ].map((opt) => {
                      const IconComponent = opt.icon;
                      const active = workflowType === opt.id;
                      return (
                        <button
                          key={opt.id}
                          type="button"
                          onClick={() => setWorkflowType(opt.id)}
                          className={`text-left p-3 rounded-xl border transition-all cursor-pointer flex flex-col justify-between h-20 outline-none ${
                            active
                              ? "bg-purple-950/20 border-purple-500 shadow-md shadow-purple-950/10 text-zinc-100"
                              : "bg-zinc-950/40 border-zinc-900 hover:border-zinc-800 text-zinc-400 hover:text-zinc-300"
                          }`}
                        >
                          <div className="flex justify-between items-start w-full">
                            <IconComponent size={14} className={active ? "text-purple-400" : "text-zinc-500"} />
                            {active && <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />}
                          </div>
                          <div>
                            <div className="text-[10px] font-bold tracking-wide">{opt.label}</div>
                            <div className="text-[8px] text-zinc-500 leading-snug line-clamp-1">{opt.desc}</div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Conditional Fields based on pipeline choice */}
                {workflowType === "video_generation" ? (
                  <div className="space-y-4">
                    {/* Motion Type */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider flex items-center gap-1">
                        <Film size={12} className="text-purple-400" />
                        Motion Preset
                      </label>
                      <select
                        value={selectedMotionType}
                        onChange={(e) => setSelectedMotionType(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                      >
                        <option value="runway_walk">Runway Walk (Standard)</option>
                        <option value="turn_and_pose">Turn & Pose</option>
                        <option value="close_up_spin">Close Up Spin</option>
                        <option value="slow_pan">Slow Pan</option>
                      </select>
                    </div>

                    {/* Duration */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider flex items-center gap-1">
                        <Sliders size={12} className="text-purple-400" />
                        Duration (Seconds)
                      </label>
                      <input
                        type="number"
                        min={3}
                        max={15}
                        value={selectedDurationSeconds}
                        onChange={(e) => setSelectedDurationSeconds(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Character Identity */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                        AI Character Model
                      </label>
                      {characters.length === 0 ? (
                        <div className="p-3 bg-zinc-950/40 border border-zinc-900/60 rounded-xl text-center text-[10px] text-zinc-500">
                          No custom models defined. Create characters under the AI Characters tab first.
                        </div>
                      ) : (
                        <select
                          value={selectedCharacterId}
                          onChange={(e) => setSelectedCharacterId(e.target.value)}
                          className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                        >
                          <option value="">-- No Character (Use Default) --</option>
                          {characters.map((c) => (
                            <option key={c.id} value={c.id}>{c.name} (ID: {c.id})</option>
                          ))}
                        </select>
                      )}
                    </div>

                    {/* Character Versions Dropdown */}
                    {selectedCharacterId && (
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                          Model Version / Outfit Config
                        </label>
                        {characterVersions.length === 0 ? (
                          <div className="p-3 bg-zinc-950/40 border border-zinc-900/60 rounded-xl text-center text-[10px] text-zinc-500">
                            No version profiles defined for this character. Standard configuration will be applied.
                          </div>
                        ) : (
                          <select
                            value={selectedVersionId}
                            onChange={(e) => setSelectedVersionId(e.target.value)}
                            className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                          >
                            {characterVersions.map((v) => (
                              <option key={v.id} value={v.id}>
                                Version {v.version_number} — {v.prompt_trigger ? (v.prompt_trigger.slice(0, 30) + "...") : "Default Preset"}
                              </option>
                            ))}
                          </select>
                        )}
                      </div>
                    )}

                    {/* Background style */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                        Background Aesthetic Style
                      </label>
                      <select
                        value={backgroundStyle}
                        onChange={(e) => setBackgroundStyle(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                      >
                        <option value="studio">Minimalist Studio (White/Gray Backdrop)</option>
                        <option value="outdoor">Bright Outdoor / Sunny Street</option>
                        <option value="urban">Industrial Urban / Concrete Backdrop</option>
                        <option value="nature">Garden / Soft Floral Backdrop</option>
                        <option value="runway">Bright Fashion Runway / Catwalk</option>
                        <option value="custom">-- Custom Prompt Backdrop --</option>
                      </select>
                    </div>

                    {/* Custom Backdrop prompt input */}
                    {backgroundStyle === "custom" && (
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                          Custom Backdrop prompt
                        </label>
                        <input
                          type="text"
                          value={customBackgroundPrompt}
                          onChange={(e) => setCustomBackgroundPrompt(e.target.value)}
                          placeholder="e.g. on a cozy café terrace, warm evening light, highly detailed"
                          className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none"
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              // Template Configuration Form
              <div className="space-y-4 pt-1 border-t border-zinc-900">
                {/* Pick Template */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    Workflow AI Template
                  </label>
                  <select
                    value={selectedTemplateId}
                    onChange={(e) => setSelectedTemplateId(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                  >
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name} (ID: {t.id})</option>
                    ))}
                  </select>
                </div>

                {/* Pick Character Profile */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    AI Character Model
                  </label>
                  {characters.length === 0 ? (
                    <div className="p-3 bg-zinc-950/40 border border-zinc-900/60 rounded-xl text-center text-[10px] text-zinc-500">
                      No custom models defined. Create characters under the AI Characters tab first.
                    </div>
                  ) : (
                    <select
                      value={selectedCharacterId}
                      onChange={(e) => setSelectedCharacterId(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                    >
                      <option value="">-- No Character (Use Default) --</option>
                      {characters.map((c) => (
                        <option key={c.id} value={c.id}>{c.name} (ID: {c.id})</option>
                      ))}
                    </select>
                  )}
                </div>

                {/* Pick Campaign Theme */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    Campaign Aesthetics Theme
                  </label>
                  {themes.length === 0 ? (
                    <div className="p-3 bg-zinc-950/40 border border-zinc-900/60 rounded-xl text-center text-[10px] text-zinc-500">
                      No campaign themes found. Create themes under Marketing Campaigns page first.
                    </div>
                  ) : (
                    <>
                      <select
                        value={selectedThemeId}
                        onChange={(e) => setSelectedThemeId(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                      >
                        <option value="">-- No Theme (Use Default) --</option>
                        {themes.map((t) => (
                          <option key={t.id} value={t.id}>{t.name} (ID: {t.id})</option>
                        ))}
                      </select>
                      {selectedThemeId && themes.find(t => t.id.toString() === selectedThemeId) && (
                        <div className="bg-zinc-950/60 border border-zinc-850/30 rounded-xl p-3.5 space-y-2 text-[10px] text-zinc-400 mt-2">
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <span className="text-[8px] font-semibold text-zinc-500 block uppercase tracking-wider">Lighting</span>
                              <span className="text-zinc-300 font-medium truncate block">
                                {themes.find(t => t.id.toString() === selectedThemeId)?.theme_json?.lighting || "None"}
                              </span>
                            </div>
                            <div>
                              <span className="text-[8px] font-semibold text-zinc-500 block uppercase tracking-wider">Backdrop</span>
                              <span className="text-zinc-300 font-medium truncate block">
                                {themes.find(t => t.id.toString() === selectedThemeId)?.theme_json?.location || "None"}
                              </span>
                            </div>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* Pick Prompt Template */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    AI Prompt Template
                  </label>
                  {prompts.length === 0 ? (
                    <div className="p-3 bg-zinc-950/40 border border-zinc-900/60 rounded-xl text-center text-[10px] text-zinc-500">
                      No prompts seeded. Create templates under the AI Prompts tab first.
                    </div>
                  ) : (
                    <select
                      value={selectedPromptId}
                      onChange={(e) => setSelectedPromptId(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                    >
                      <option value="">-- No Prompt (Use Default) --</option>
                      {prompts.map((p) => (
                        <option key={p.id} value={p.id}>{p.name} (ID: {p.id})</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
            )}

            {/* Optional webhook URL */}
            <div className="space-y-1.5 pt-1">
              <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                Webhook Callback URL (Optional)
              </label>
              <input
                type="url"
                value={callbackUrl}
                onChange={(e) => setCallbackUrl(e.target.value)}
                placeholder="https://my-domain.com/webhooks/modelens"
                className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none"
              />
              <p className="text-[9px] text-zinc-500 leading-normal">
                ModeLens will POST a JSON payload with execution state details when this job completes or fails.
              </p>
            </div>

            {/* Generate Trigger */}
            <button
              type="submit"
              disabled={isSubmitting || !selectedAssetId}
              className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-xs font-semibold py-3 rounded-xl transition-all cursor-pointer shadow-lg shadow-purple-950/20 disabled:shadow-none"
            >
              {isSubmitting ? (
                <Loader2 className="animate-spin" size={14} />
              ) : (
                <Play size={12} fill="currentColor" />
              )}
              Queue AI Generation (1 Credit)
            </button>
          </form>
        </div>

        {/* Right Column: Execution History & Real-Time Monitoring */}
        <div className="lg:col-span-7 space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 flex items-center gap-2">
            <Clock size={14} className="text-purple-400" />
            Generation Job History ({jobs.length})
          </h3>

          {jobs.length === 0 ? (
            <div className="text-center py-20 bg-zinc-900/10 border border-zinc-900 rounded-2xl text-zinc-500 text-xs">
              No jobs found. Queue a generation to see real-time updates.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-4 max-h-[600px] overflow-y-auto pr-1">
                {jobs.map((job) => {
                  const brand = brands.find((b) => b.id === job.brand_id);
                  const isPolling = activePollIds.has(job.id);

                  return (
                    <div
                      key={job.id}
                      className={`bg-zinc-900/20 border rounded-2xl p-5 hover:bg-zinc-900/40 transition-all space-y-4 relative overflow-hidden ${
                        isPolling ? "border-purple-500/40" : "border-zinc-850"
                      }`}
                    >
                      {/* Job Top Row */}
                      <div className="flex justify-between items-start gap-3 flex-wrap">
                        <div className="space-y-1 text-left">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-zinc-200">Job #{job.id}</span>
                            <span className="text-[10px] text-zinc-500 uppercase font-semibold">
                              {job.job_type === "workflow" ? "Pipeline Pipeline" : "Template Run"}
                            </span>
                            {brand && (
                              <span className="text-[9px] bg-zinc-950 text-zinc-400 border border-zinc-850 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                                {brand.name}
                              </span>
                            )}
                          </div>
                          <p className="text-[10px] text-zinc-500">
                            Started: {new Date(job.created_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {getStatusBadge(job.status)}
                        </div>
                      </div>

                      {/* Outputs & Details Container */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-zinc-850/60 pt-4 text-xs leading-relaxed text-zinc-400">
                        {/* Inputs info */}
                        <div className="bg-zinc-950/40 border border-zinc-900/80 p-3 rounded-xl space-y-2">
                          <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-wide block">Input Parameters</span>
                          {job.inputs?.workflow_type && (
                            <div className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider">
                              Pipeline: {job.inputs.workflow_type.replace(/_/g, ' ')}
                            </div>
                          )}
                          {job.inputs?.source_asset_id ? (
                            <div className="flex gap-2 items-center">
                              {(() => {
                                const sAsset = brandAssets.find(a => a.id === job.inputs.source_asset_id);
                                if (sAsset) {
                                  return (
                                    <>
                                      <img
                                        src={sAsset.storage_path}
                                        alt="Source"
                                        className="w-10 h-10 object-cover rounded border border-zinc-850"
                                      />
                                      <div className="truncate">
                                        <span className="text-zinc-300 font-medium block truncate text-[10px]">
                                          {sAsset.name || sAsset.filename}
                                        </span>
                                        <span className="text-zinc-500 text-[9px]">ID: {sAsset.id}</span>
                                      </div>
                                    </>
                                  );
                                }
                                return (
                                  <div className="text-[10px] text-zinc-500">
                                    Asset ID: {job.inputs.source_asset_id}
                                  </div>
                                );
                              })()}
                            </div>
                          ) : job.inputs?.urls && job.inputs.urls.length > 0 ? (
                            <div className="truncate">
                              <span className="text-zinc-500">S3 Source:</span>{" "}
                              <span className="text-[10px] font-mono text-zinc-300">{job.inputs.urls[0]}</span>
                            </div>
                          ) : (
                            <div className="text-[10px] text-zinc-500">No source assets input</div>
                          )}
                          {job.inputs?.character_id && (
                            <div className="text-[10px] text-zinc-400">
                              <span className="text-zinc-500">Model ID:</span> {job.inputs.character_id}
                              {job.inputs.character_version_id && (
                                <> (v{job.inputs.character_version_id})</>
                              )}
                            </div>
                          )}
                          {job.inputs?.motion_type && (
                            <div className="text-[10px] text-zinc-400">
                              <span className="text-zinc-500">Motion:</span> {job.inputs.motion_type} ({job.inputs.duration_seconds || 5}s)
                            </div>
                          )}
                          {job.callback_url && (
                            <div className="truncate text-[10px]">
                              <span className="text-zinc-500">Webhook:</span>{" "}
                              <span className="text-[9px] font-mono text-zinc-400">{job.callback_url}</span>
                            </div>
                          )}
                        </div>

                        {/* Outputs Info */}
                        <div className="bg-zinc-950/40 border border-zinc-900/80 p-3 rounded-xl space-y-2">
                          <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-wide block">Output Assets</span>
                          {job.status === "completed" ? (
                            <div className="space-y-2">
                              {job.outputs?.video_url ? (
                                <div className="space-y-2">
                                  <div className="flex justify-between items-center gap-2">
                                    <span className="text-[10px] font-mono text-emerald-400 truncate max-w-[150px]">
                                      {job.outputs.video_url}
                                    </span>
                                    <a
                                      href={job.outputs.video_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-[10px] text-purple-400 hover:text-purple-300 font-semibold inline-flex items-center gap-1 shrink-0"
                                    >
                                      Download <ExternalLink size={10} />
                                    </a>
                                  </div>
                                  <video
                                    src={job.outputs.video_url}
                                    controls
                                    className="w-full max-h-48 object-cover rounded-xl border border-zinc-800 bg-black outline-none"
                                    poster={brandAssets.find((a) => a.id === job.inputs?.source_asset_id)?.storage_path}
                                  />
                                </div>
                              ) : job.outputs?.urls ? (
                                <div className="space-y-1">
                                  {job.outputs.urls.map((url, index) => (
                                    <div key={index} className="flex justify-between items-center gap-2">
                                      <span className="text-[10px] font-mono text-emerald-400 truncate max-w-[150px]">
                                        {url}
                                      </span>
                                      <a
                                        href={url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-[10px] text-purple-400 hover:text-purple-300 font-semibold inline-flex items-center gap-1 shrink-0"
                                      >
                                        View <ExternalLink size={10} />
                                      </a>
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                              {job.asset_id && (
                                <div className="text-[10px] text-zinc-500 border-t border-zinc-900 pt-1 mt-1">
                                  Catalog Asset ID: <span className="text-zinc-300 font-semibold">{job.asset_id}</span>
                                </div>
                              )}
                            </div>
                          ) : job.status === "failed" ? (
                            <div className="text-[10px] text-rose-400 leading-snug">
                              Error: {job.error_message || "Operation failed"}
                            </div>
                          ) : (
                            <div className="text-[10px] text-zinc-500 flex items-center gap-1.5">
                              <Loader2 className="animate-spin text-purple-500" size={12} />
                              Awaiting output files...
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Pagination Controls */}
              <div className="flex justify-between items-center bg-zinc-950 border border-zinc-900 rounded-2xl p-3 mt-4">
                <button
                  type="button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
                  className="bg-zinc-900 border border-zinc-850 hover:border-zinc-700 disabled:opacity-40 disabled:hover:border-zinc-850 text-zinc-300 px-3 py-1.5 rounded-xl text-xs transition-all cursor-pointer flex items-center gap-1 font-semibold"
                >
                  &larr; Previous
                </button>
                <span className="text-zinc-400 text-[10px] uppercase font-bold tracking-wider">
                  Page {currentPage}
                </span>
                <button
                  type="button"
                  disabled={jobs.length < itemsPerPage}
                  onClick={() => setCurrentPage((p) => p + 1)}
                  className="bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-900 disabled:text-zinc-500 disabled:opacity-40 text-white px-4 py-1.5 rounded-xl text-xs transition-all cursor-pointer flex items-center gap-1 font-semibold shadow-md shadow-purple-950/20"
                >
                  Next &rarr;
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="animate-spin text-purple-500" size={24} />
      </div>
    }>
      <JobsPageContent />
    </Suspense>
  );
}
