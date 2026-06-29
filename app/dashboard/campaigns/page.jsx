"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Megaphone, Plus, Trash2, Link2, Unlink, Sparkles, Image as ImageIcon, Loader2, ArrowRight, FolderKanban, Check, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

const defaultThemesToSeed = [
  {
    name: "European Summer",
    description: "Sun-drenched Mediterranean vibes with warm lighting.",
    theme_json: {
      lighting: "Bright Golden Hour, Soft Shadows (Warm)",
      location: "Coastline Cliff, Sun-drenched Stone Courtyard",
      prompt: "Warm golden sunrays, outdoor luxury, crisp blue sky background."
    }
  },
  {
    name: "Cyberpunk Studio",
    description: "Futuristic neon tones with high contrast.",
    theme_json: {
      lighting: "High-contrast Magenta & Cyan Neon, Volumetric Fog",
      location: "Sleek Industrial Studio Setup, Glossy Dark Platform",
      prompt: "Vivid neon lighting, dark cyberpunk aesthetic, futuristic vibe."
    }
  },
  {
    name: "Mediterranean Escape",
    description: "White sand dunes and light airy coastal aesthetics.",
    theme_json: {
      lighting: "Bright Mid-day Sun, Diffused White Highlights",
      location: "Greek Coastal Balcony, Aegean Sea backdrop",
      prompt: "Airy bright lighting, clean minimalist composition, pastel tones."
    }
  },
  {
    name: "Studio Light Portrait",
    description: "Clean professional studio headshots.",
    theme_json: {
      lighting: "Soft Key Light, White Diffuser Backdrop",
      location: "Professional Minimalist Portrait Studio",
      prompt: "Studio lighting, editorial clean portrait shot, high fashion lens."
    }
  }
];

export default function CampaignsPage() {
  const { user } = useAuth();
  
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Campaign details modal / view
  const [activeCampaign, setActiveCampaign] = useState(null);
  const [linkedAssets, setLinkedAssets] = useState([]);
  const [linkedWorkflows, setLinkedWorkflows] = useState([]);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [selectedThemeId, setSelectedThemeId] = useState("");

  // Dynamic Themes state
  const [themes, setThemes] = useState([]);
  const [loadingThemes, setLoadingThemes] = useState(false);

  // New Theme Creation Form States
  const [isCreateThemeOpen, setIsCreateThemeOpen] = useState(false);
  const [newThemeName, setNewThemeName] = useState("");
  const [newThemeDesc, setNewThemeDesc] = useState("");
  const [newThemeLighting, setNewThemeLighting] = useState("");
  const [newThemeLocation, setNewThemeLocation] = useState("");
  const [newThemePrompt, setNewThemePrompt] = useState("");
  const [isCreatingTheme, setIsCreatingTheme] = useState(false);

  // Fetch campaign themes
  const fetchThemes = async (brandId) => {
    setLoadingThemes(true);
    try {
      let url = "/api/v1/themes";
      if (brandId) {
        url += `?brand_id=${brandId}`;
      }
      let data = await api.get(url);
      if (data.length === 0) {
        // Seed default global themes
        const seeded = [];
        for (const t of defaultThemesToSeed) {
          try {
            const newTheme = await api.post("/api/v1/themes", t);
            seeded.push(newTheme);
          } catch (e) {
            console.error("Failed to seed default theme:", t.name, e);
          }
        }
        if (seeded.length > 0) {
          setThemes(seeded);
        }
      } else {
        setThemes(data);
      }
    } catch (error) {
      console.error("Failed to load themes:", error);
      toast.error("Failed to load campaign themes");
    } finally {
      setLoadingThemes(false);
    }
  };

  // Fetch themes whenever brand changes
  useEffect(() => {
    if (selectedBrandId) {
      fetchThemes(selectedBrandId);
    } else {
      fetchThemes("");
    }
  }, [selectedBrandId]);

  // Sync theme selection from localStorage
  useEffect(() => {
    if (activeCampaign) {
      const saved = localStorage.getItem(`campaign_theme_${activeCampaign.id}`) || "";
      setSelectedThemeId(saved);
    }
  }, [activeCampaign]);

  const handleSelectTheme = (themeId) => {
    setSelectedThemeId(themeId);
    if (activeCampaign) {
      if (themeId) {
        localStorage.setItem(`campaign_theme_${activeCampaign.id}`, themeId);
        toast.success("Aesthetics Theme applied successfully!");
      } else {
        localStorage.removeItem(`campaign_theme_${activeCampaign.id}`);
        toast.success("Aesthetics Theme cleared.");
      }
    }
  };

  const handleCreateTheme = async (e) => {
    e.preventDefault();
    if (!newThemeName.trim()) {
      toast.error("Theme name is required");
      return;
    }
    if (!activeCampaign) {
      toast.error("No active campaign selected");
      return;
    }

    setIsCreatingTheme(true);
    try {
      const payload = {
        name: newThemeName.trim(),
        description: newThemeDesc.trim() || null,
        brand_id: activeCampaign.brand_id,
        theme_json: {
          lighting: newThemeLighting.trim(),
          location: newThemeLocation.trim(),
          prompt: newThemePrompt.trim()
        }
      };

      const newTheme = await api.post("/api/v1/themes", payload);
      toast.success("Custom Aesthetics Theme created successfully!");
      setNewThemeName("");
      setNewThemeDesc("");
      setNewThemeLighting("");
      setNewThemeLocation("");
      setNewThemePrompt("");
      setIsCreateThemeOpen(false);
      
      // Refresh themes list for the active brand
      await fetchThemes(selectedBrandId || activeCampaign.brand_id.toString());
      
      // Auto-select the newly created theme
      handleSelectTheme(newTheme.id.toString());
    } catch (error) {
      toast.error(error.message || "Failed to create custom theme");
    } finally {
      setIsCreatingTheme(false);
    }
  };

  const handleDeleteTheme = async (themeId) => {
    if (!confirm("Are you sure you want to delete this custom theme?")) return;
    try {
      await api.delete(`/api/v1/themes/${themeId}`);
      toast.success("Theme deleted successfully");
      
      // If deleted theme was active, clear it
      if (selectedThemeId === themeId.toString()) {
        handleSelectTheme("");
      }
      
      // Refresh themes list
      await fetchThemes(selectedBrandId || activeCampaign?.brand_id.toString());
    } catch (error) {
      toast.error(error.message || "Failed to delete theme");
    }
  };

  // Link Dialog states
  const [isLinkAssetOpen, setIsLinkAssetOpen] = useState(false);
  const [isLinkWorkflowOpen, setIsLinkWorkflowOpen] = useState(false);
  const [availableAssets, setAvailableAssets] = useState([]);
  const [availableWorkflows, setAvailableWorkflows] = useState([]);
  const [linkingAssetId, setLinkingAssetId] = useState("");
  const [linkingWorkflowId, setLinkingWorkflowId] = useState("");

  // Create Campaign Modal
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDesc, setCreateDesc] = useState("");
  const [createBrandId, setCreateBrandId] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Fetch initial brands and campaigns
  const initData = async () => {
    try {
      const brandData = await api.get("/api/v1/brands");
      setBrands(brandData);
      if (brandData.length > 0) {
        setSelectedBrandId(brandData[0].id.toString());
        setCreateBrandId(brandData[0].id.toString());
      }
      
      const campaignData = await api.get(`/api/v1/campaigns?limit=${itemsPerPage}&offset=${(currentPage - 1) * itemsPerPage}`);
      setCampaigns(campaignData);
    } catch (error) {
      toast.error(error.message || "Failed to load initial campaigns data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    initData();
  }, []);

  // Reset page when brand selection changes
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedBrandId]);

  // Fetch campaigns again when selected brand changes
  const fetchCampaigns = async () => {
    try {
      let url = `/api/v1/campaigns?limit=${itemsPerPage}&offset=${(currentPage - 1) * itemsPerPage}`;
      if (selectedBrandId) {
        url += `&brand_id=${selectedBrandId}`;
      }
      const data = await api.get(url);
      setCampaigns(data);
    } catch (error) {
      toast.error(error.message || "Failed to filter campaigns");
    }
  };

  useEffect(() => {
    if (!loading) {
      fetchCampaigns();
    }
  }, [selectedBrandId, currentPage]);

  // Load campaign details (assets and workflows)
  const loadCampaignDetails = async (campaign) => {
    setActiveCampaign(campaign);
    setLoadingDetails(true);
    try {
      const assets = await api.get(`/api/v1/campaigns/${campaign.id}/assets`);
      setLinkedAssets(assets);
      const workflows = await api.get(`/api/v1/campaigns/${campaign.id}/workflows`);
      setLinkedWorkflows(workflows);
    } catch (error) {
      toast.error(error.message || "Failed to load campaign links");
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleCreateCampaign = async (e) => {
    e.preventDefault();
    if (!createName.trim() || !createBrandId) {
      toast.error("Name and Brand are required");
      return;
    }

    setIsCreating(true);
    try {
      await api.post("/api/v1/campaigns", {
        brand_id: parseInt(createBrandId),
        name: createName,
        description: createDesc
      });
      toast.success("Campaign created successfully!");
      setCreateName("");
      setCreateDesc("");
      setIsCreateOpen(false);
      fetchCampaigns();
    } catch (error) {
      toast.error(error.message || "Failed to create campaign");
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteCampaign = async (campaignId) => {
    if (!confirm("Are you sure you want to delete this campaign?")) return;
    try {
      await api.delete(`/api/v1/campaigns/${campaignId}`);
      toast.success("Campaign deleted successfully");
      if (activeCampaign?.id === campaignId) {
        setActiveCampaign(null);
      }
      fetchCampaigns();
    } catch (error) {
      toast.error(error.message || "Failed to delete campaign");
    }
  };

  // Open Link Asset Modal
  const openLinkAsset = async () => {
    if (!activeCampaign) return;
    setIsLinkAssetOpen(true);
    try {
      // Get all brand assets
      const allAssets = await api.get(`/api/v1/assets?brand_id=${activeCampaign.brand_id}`);
      // Filter out assets that are already linked
      const filtered = allAssets.filter(
        (asset) => !linkedAssets.some((la) => la.id === asset.id)
      );
      setAvailableAssets(filtered);
      if (filtered.length > 0) {
        setLinkingAssetId(filtered[0].id.toString());
      } else {
        setLinkingAssetId("");
      }
    } catch (error) {
      toast.error("Failed to load available assets");
    }
  };

  const handleLinkAsset = async (e) => {
    e.preventDefault();
    if (!linkingAssetId) return;
    try {
      await api.post(`/api/v1/campaigns/${activeCampaign.id}/assets/${linkingAssetId}`);
      toast.success("Asset linked successfully!");
      setIsLinkAssetOpen(false);
      loadCampaignDetails(activeCampaign);
    } catch (error) {
      toast.error(error.message || "Failed to link asset");
    }
  };

  const handleUnlinkAsset = async (assetId) => {
    try {
      await api.delete(`/api/v1/campaigns/${activeCampaign.id}/assets/${assetId}`);
      toast.success("Asset unlinked successfully");
      loadCampaignDetails(activeCampaign);
    } catch (error) {
      toast.error(error.message || "Failed to unlink asset");
    }
  };

  // Open Link Workflow Modal
  const openLinkWorkflow = async () => {
    if (!activeCampaign) return;
    setIsLinkWorkflowOpen(true);
    try {
      const templates = await api.get("/api/v1/jobs/workflow-templates");
      const filtered = templates.filter(
        (t) => !linkedWorkflows.some((lw) => lw.id === t.id)
      );
      setAvailableWorkflows(filtered);
      if (filtered.length > 0) {
        setLinkingWorkflowId(filtered[0].id.toString());
      } else {
        setLinkingWorkflowId("");
      }
    } catch (error) {
      toast.error("Failed to load workflow templates");
    }
  };

  const handleLinkWorkflow = async (e) => {
    e.preventDefault();
    if (!linkingWorkflowId) return;
    try {
      await api.post(`/api/v1/campaigns/${activeCampaign.id}/workflows/${linkingWorkflowId}`);
      toast.success("Workflow linked successfully!");
      setIsLinkWorkflowOpen(false);
      loadCampaignDetails(activeCampaign);
    } catch (error) {
      toast.error(error.message || "Failed to link workflow");
    }
  };

  const handleUnlinkWorkflow = async (workflowId) => {
    try {
      await api.delete(`/api/v1/campaigns/${activeCampaign.id}/workflows/${workflowId}`);
      toast.success("Workflow unlinked successfully");
      loadCampaignDetails(activeCampaign);
    } catch (error) {
      toast.error(error.message || "Failed to unlink workflow");
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
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="space-y-1">
          <h2 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100 flex items-center gap-2">
            <Megaphone className="text-purple-400" size={22} />
            Marketing Campaigns
          </h2>
          <p className="text-xs text-zinc-400">
            Organize catalog assets and workflows for targeted seasonal and media campaigns
          </p>
        </div>
        <button
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20"
        >
          <Plus size={14} />
          Create Campaign
        </button>
      </div>

      {/* Filters & Brand Selector */}
      <div className="bg-zinc-900/20 border border-zinc-900 p-4 rounded-xl flex items-center gap-3">
        <span className="text-xs text-zinc-400 font-medium uppercase tracking-wider">Filter Brand:</span>
        <select
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          className="bg-zinc-950 border border-zinc-850 text-zinc-200 text-xs px-3 py-2 rounded-lg outline-none cursor-pointer focus:border-purple-500 transition-all"
        >
          <option value="">All Brands</option>
          {brands.map((b) => (
            <option key={b.id} value={b.id}>{b.name}</option>
          ))}
        </select>
      </div>

      {/* Main campaigns workspace grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left side: Campaigns list */}
        <div className="lg:col-span-1 space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500">
            Campaigns ({campaigns.length})
          </h3>
          {campaigns.length === 0 ? (
            <div className="text-center py-10 bg-zinc-900/10 border border-zinc-900 rounded-2xl text-zinc-500 text-xs">
              No campaigns found for the filter.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
                {campaigns.map((c) => {
                  const brand = brands.find((b) => b.id === c.brand_id);
                  const isActive = activeCampaign?.id === c.id;
                  return (
                    <div
                      key={c.id}
                      onClick={() => loadCampaignDetails(c)}
                      className={`p-4 border rounded-xl transition-all cursor-pointer text-left relative overflow-hidden group ${
                        isActive
                          ? "bg-purple-950/20 border-purple-500/60 shadow-lg shadow-purple-950/10"
                          : "bg-zinc-900/30 border-zinc-850 hover:bg-zinc-900/50"
                      }`}
                    >
                      <div className="space-y-1.5">
                        <div className="flex justify-between items-start">
                          <span className="text-[9px] font-bold text-purple-400 bg-purple-950/50 border border-purple-800/20 px-2 py-0.5 rounded-full uppercase tracking-wider">
                            {brand ? brand.name : `Brand ID: ${c.brand_id}`}
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteCampaign(c.id);
                            }}
                            className="text-zinc-500 hover:text-rose-400 p-1 rounded-md opacity-0 group-hover:opacity-100 transition-all cursor-pointer"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                        <h4 className="text-xs font-bold text-zinc-200 group-hover:text-white truncate">
                          {c.name}
                        </h4>
                        <p className="text-[11px] text-zinc-500 line-clamp-2 leading-relaxed">
                          {c.description || "No description provided."}
                        </p>
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
                  &larr; Prev
                </button>
                <span className="text-zinc-400 text-[10px] uppercase font-bold tracking-wider">
                  Page {currentPage}
                </span>
                <button
                  type="button"
                  disabled={campaigns.length < itemsPerPage}
                  onClick={() => setCurrentPage((p) => p + 1)}
                  className="bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-900 disabled:text-zinc-500 disabled:opacity-40 text-white px-4 py-1.5 rounded-xl text-xs transition-all cursor-pointer flex items-center gap-1 font-semibold shadow-md shadow-purple-950/20"
                >
                  Next &rarr;
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right side: Detailed Workspace details */}
        <div className="lg:col-span-2 space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500">
            Workspace Detail View
          </h3>
          {!activeCampaign ? (
            <div className="flex flex-col items-center justify-center py-20 bg-zinc-900/10 border border-dashed border-zinc-850 rounded-2xl text-zinc-500 text-xs gap-3">
              <Megaphone size={32} className="text-zinc-700" />
              Select a campaign to inspect its assets and workflows.
            </div>
          ) : (
            <div className="bg-zinc-900/20 border border-zinc-855 rounded-2xl p-6 space-y-8">
              {/* Campaign Meta */}
              <div className="flex justify-between items-start gap-4">
                <div className="space-y-1">
                  <h3 className="text-base font-bold text-zinc-100">{activeCampaign.name}</h3>
                  <p className="text-xs text-zinc-400 leading-relaxed max-w-xl">
                    {activeCampaign.description || "No description."}
                  </p>
                </div>
                <div className="shrink-0 flex flex-col items-end gap-1.5">
                  <span className="text-[10px] bg-zinc-900 text-zinc-400 border border-zinc-800 px-3 py-1 rounded-full uppercase font-medium">
                    ID: {activeCampaign.id}
                  </span>
                </div>
              </div>

              {/* Campaign Theme Selector */}
              <div className="space-y-4 border-t border-zinc-850/60 pt-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h4 className="text-sm font-bold text-zinc-200 flex items-center gap-1.5">
                      <Sparkles size={16} className="text-purple-400" />
                      Campaign Aesthetics Theme
                    </h4>
                    <p className="text-[10px] text-zinc-500">Apply visual preset styling guidelines to this campaign&apos;s assets.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsCreateThemeOpen(true)}
                    className="flex items-center gap-1 bg-zinc-800 hover:bg-zinc-750 text-zinc-200 text-[10px] px-2.5 py-1.5 rounded-lg transition-all cursor-pointer font-semibold"
                  >
                    <Plus size={11} />
                    New Theme
                  </button>
                </div>

                {loadingThemes ? (
                  <div className="flex py-6 justify-center">
                    <Loader2 className="animate-spin text-purple-500" size={20} />
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {themes.map((theme) => {
                      const isSelected = selectedThemeId === theme.id.toString();
                      return (
                        <button
                          type="button"
                          key={theme.id}
                          onClick={() => handleSelectTheme(isSelected ? "" : theme.id.toString())}
                          className={`text-left p-3.5 rounded-xl border flex flex-col justify-between gap-1.5 transition-all cursor-pointer relative overflow-hidden group/theme ${
                            isSelected
                              ? "bg-purple-950/20 border-purple-500/40 shadow-inner"
                              : "bg-zinc-950/40 border-zinc-900 hover:border-zinc-850 hover:bg-zinc-900/10"
                          }`}
                        >
                          <div className="flex justify-between items-start w-full">
                            <div className="min-w-0 flex-1">
                              <span className={`text-[10px] font-bold tracking-wide transition-colors ${isSelected ? "text-purple-400" : "text-zinc-300"}`}>
                                {theme.name}
                              </span>
                              <p className="text-[9px] text-zinc-500 leading-normal mt-0.5">
                                {theme.description}
                              </p>
                            </div>
                            {theme.brand_id && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteTheme(theme.id);
                                }}
                                className="text-zinc-500 hover:text-rose-400 p-1 rounded-md opacity-0 group-hover/theme:opacity-100 transition-all cursor-pointer ml-1.5 shrink-0"
                                title="Delete Custom Theme"
                              >
                                <Trash2 size={11} />
                              </button>
                            )}
                          </div>
                          {isSelected && (
                            <div className="text-[8px] bg-purple-900/40 border border-purple-800/35 text-purple-300 px-1.5 py-0.5 rounded font-medium mt-1 uppercase tracking-wider self-start">
                              Active Preset
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}

                {selectedThemeId && (
                  <div className="bg-zinc-950/60 border border-zinc-900 rounded-xl p-4 space-y-3 leading-relaxed text-[11px] text-zinc-400">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-[9px] font-semibold text-zinc-500 block uppercase tracking-wider">Lighting Style</span>
                        <span className="text-zinc-300 font-medium">
                          {themes.find(t => t.id.toString() === selectedThemeId)?.theme_json?.lighting || "None"}
                        </span>
                      </div>
                      <div>
                        <span className="text-[9px] font-semibold text-zinc-500 block uppercase tracking-wider">Location Backdrop</span>
                        <span className="text-zinc-300 font-medium">
                          {themes.find(t => t.id.toString() === selectedThemeId)?.theme_json?.location || "None"}
                        </span>
                      </div>
                    </div>
                    <div>
                      <span className="text-[9px] font-semibold text-zinc-500 block uppercase tracking-wider">Prompt Preset Instructions</span>
                      <p className="text-zinc-300 font-mono text-[9px] bg-zinc-950/80 border border-zinc-900 p-2.5 rounded-lg mt-1 whitespace-pre-wrap leading-normal">
                        {themes.find(t => t.id.toString() === selectedThemeId)?.theme_json?.prompt || "None"}
                      </p>
                    </div>
                    <div className="pt-1 flex justify-end">
                      <Link
                        href={`/dashboard/jobs?brand_id=${activeCampaign.brand_id}&theme_id=${selectedThemeId}`}
                        className="inline-flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white text-[10px] font-bold px-3 py-1.5 rounded-lg transition-all"
                      >
                        <Sparkles size={11} />
                        Run AI Generator with Theme
                      </Link>
                    </div>
                  </div>
                )}

              {/* Linked Assets Grid */}
              <div className="space-y-4 border-t border-zinc-850/60 pt-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h4 className="text-sm font-bold text-zinc-200 flex items-center gap-1.5">
                      <ImageIcon size={16} className="text-indigo-400" />
                      Linked Assets ({linkedAssets.length})
                    </h4>
                    <p className="text-[10px] text-zinc-500">Catalog images linked to this media setup.</p>
                  </div>
                  <button
                    onClick={openLinkAsset}
                    className="flex items-center gap-1 bg-zinc-800 hover:bg-zinc-750 text-zinc-200 text-xs px-3 py-1.5 rounded-lg transition-all cursor-pointer font-medium"
                  >
                    <Link2 size={12} />
                    Link Asset
                  </button>
                </div>

                {loadingDetails ? (
                  <div className="flex py-6 justify-center">
                    <Loader2 className="animate-spin text-indigo-500" size={20} />
                  </div>
                ) : linkedAssets.length === 0 ? (
                  <div className="text-center py-8 bg-zinc-950/40 border border-zinc-900 rounded-xl text-zinc-500 text-xs">
                    No assets linked yet. Link some catalog photos.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[300px] overflow-y-auto pr-1">
                    {linkedAssets.map((asset) => (
                      <div
                        key={asset.id}
                        className="bg-zinc-950/50 border border-zinc-900 p-3 rounded-xl flex items-center justify-between gap-3 hover:border-zinc-800 transition-all group"
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="w-8 h-8 rounded-lg bg-indigo-950/40 border border-indigo-900/20 flex items-center justify-center text-indigo-400 shrink-0 text-xs uppercase font-bold">
                            {asset.asset_type.charAt(0)}
                          </div>
                          <div className="flex flex-col min-w-0">
                            <span className="text-xs font-semibold text-zinc-200 truncate">{asset.name || asset.filename}</span>
                            <span className="text-[10px] text-zinc-500 truncate">{asset.storage_path}</span>
                          </div>
                        </div>
                        <button
                          onClick={() => handleUnlinkAsset(asset.id)}
                          title="Unlink asset"
                          className="text-zinc-500 hover:text-rose-400 p-1.5 rounded-md hover:bg-rose-950/10 transition-all cursor-pointer"
                        >
                          <Unlink size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Linked Workflows List */}
              <div className="space-y-4 border-t border-zinc-850/60 pt-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h4 className="text-sm font-bold text-zinc-200 flex items-center gap-1.5">
                      <Sparkles size={16} className="text-purple-400" />
                      Linked Generation Workflows ({linkedWorkflows.length})
                    </h4>
                    <p className="text-[10px] text-zinc-500">Execution templates active for this campaign.</p>
                  </div>
                  <button
                    onClick={openLinkWorkflow}
                    className="flex items-center gap-1 bg-zinc-800 hover:bg-zinc-750 text-zinc-200 text-xs px-3 py-1.5 rounded-lg transition-all cursor-pointer font-medium"
                  >
                    <Link2 size={12} />
                    Link Workflow
                  </button>
                </div>

                {loadingDetails ? (
                  <div className="flex py-6 justify-center">
                    <Loader2 className="animate-spin text-purple-500" size={20} />
                  </div>
                ) : linkedWorkflows.length === 0 ? (
                  <div className="text-center py-8 bg-zinc-950/40 border border-zinc-900 rounded-xl text-zinc-500 text-xs">
                    No workflow templates linked to this campaign.
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                    {linkedWorkflows.map((wf) => (
                      <div
                        key={wf.id}
                        className="bg-zinc-950/50 border border-zinc-900 p-4 rounded-xl flex items-center justify-between gap-4 hover:border-zinc-800 transition-all"
                      >
                        <div className="space-y-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-zinc-200">{wf.name}</span>
                            <span className="text-[9px] bg-zinc-900 text-zinc-500 border border-zinc-800 px-2 py-0.5 rounded uppercase font-bold">
                              ID: {wf.id}
                            </span>
                          </div>
                          <p className="text-[10px] text-zinc-500 leading-relaxed truncate">{wf.description}</p>
                        </div>
                        <button
                          onClick={() => handleUnlinkWorkflow(wf.id)}
                          title="Unlink workflow"
                          className="text-zinc-500 hover:text-rose-400 p-1.5 rounded-md hover:bg-rose-950/10 transition-all cursor-pointer shrink-0"
                        >
                          <Unlink size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal: Create Campaign */}
      <AnimatePresence>
        {isCreateOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsCreateOpen(false)}
              className="fixed inset-0 bg-black"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 relative z-10 shadow-2xl space-y-4"
            >
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Megaphone className="text-purple-400" size={18} />
                  Create Campaign
                </h3>
                <button onClick={() => setIsCreateOpen(false)} className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg">
                  <X size={16} />
                </button>
              </div>
              <form onSubmit={handleCreateCampaign} className="space-y-4">
                {/* Brand */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">Select Brand</label>
                  <select
                    value={createBrandId}
                    onChange={(e) => setCreateBrandId(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                  >
                    {brands.map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>
                {/* Name */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">Campaign Name</label>
                  <input
                    type="text"
                    required
                    value={createName}
                    onChange={(e) => setCreateName(e.target.value)}
                    placeholder="e.g. Summer Shoot 2026"
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none"
                  />
                </div>
                {/* Description */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">Description</label>
                  <textarea
                    value={createDesc}
                    onChange={(e) => setCreateDesc(e.target.value)}
                    placeholder="Describe target channel and requirements..."
                    rows={3}
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none resize-none"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button type="button" onClick={() => setIsCreateOpen(false)} className="bg-zinc-800 hover:bg-zinc-755 text-zinc-300 text-xs px-4 py-2.5 rounded-xl cursor-pointer">
                    Cancel
                  </button>
                  <button type="submit" disabled={isCreating} className="bg-purple-600 hover:bg-purple-500 text-white text-xs px-4 py-2.5 rounded-xl cursor-pointer flex items-center gap-1 shadow-md shadow-purple-950/20">
                    {isCreating ? <Loader2 className="animate-spin" size={14} /> : "Create"}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal: Link Asset */}
      <AnimatePresence>
        {isLinkAssetOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsLinkAssetOpen(false)}
              className="fixed inset-0 bg-black"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 relative z-10 shadow-2xl space-y-4"
            >
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Link2 className="text-indigo-400" size={18} />
                  Link Brand Asset
                </h3>
                <button onClick={() => setIsLinkAssetOpen(false)} className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg">
                  <X size={16} />
                </button>
              </div>
              {availableAssets.length === 0 ? (
                <div className="space-y-4 text-center py-6">
                  <p className="text-xs text-zinc-400">All available brand assets are already linked to this campaign.</p>
                  <button type="button" onClick={() => setIsLinkAssetOpen(false)} className="bg-zinc-800 text-zinc-200 text-xs px-4 py-2 rounded-lg cursor-pointer">
                    Dismiss
                  </button>
                </div>
              ) : (
                <form onSubmit={handleLinkAsset} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">Select Catalog Asset</label>
                    <select
                      value={linkingAssetId}
                      onChange={(e) => setLinkingAssetId(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                    >
                      {availableAssets.map((a) => (
                        <option key={a.id} value={a.id}>{a.name || a.filename} (ID: {a.id})</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button type="button" onClick={() => setIsLinkAssetOpen(false)} className="bg-zinc-800 text-zinc-300 text-xs px-4 py-2.5 rounded-xl cursor-pointer">
                      Cancel
                    </button>
                    <button type="submit" className="bg-purple-600 hover:bg-purple-500 text-white text-xs px-4 py-2.5 rounded-xl cursor-pointer">
                      Link Asset
                    </button>
                  </div>
                </form>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal: Link Workflow */}
      <AnimatePresence>
        {isLinkWorkflowOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsLinkWorkflowOpen(false)}
              className="fixed inset-0 bg-black"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 relative z-10 shadow-2xl space-y-4"
            >
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Link2 className="text-purple-400" size={18} />
                  Link Workflow Template
                </h3>
                <button onClick={() => setIsLinkWorkflowOpen(false)} className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg">
                  <X size={16} />
                </button>
              </div>
              {availableWorkflows.length === 0 ? (
                <div className="space-y-4 text-center py-6">
                  <p className="text-xs text-zinc-400">All workflow templates are already linked to this campaign.</p>
                  <button type="button" onClick={() => setIsLinkWorkflowOpen(false)} className="bg-zinc-800 text-zinc-200 text-xs px-4 py-2 rounded-lg cursor-pointer">
                    Dismiss
                  </button>
                </div>
              ) : (
                <form onSubmit={handleLinkWorkflow} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">Select Template</label>
                    <select
                      value={linkingWorkflowId}
                      onChange={(e) => setLinkingWorkflowId(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none cursor-pointer"
                    >
                      {availableWorkflows.map((t) => (
                        <option key={t.id} value={t.id}>{t.name} (ID: {t.id})</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button type="button" onClick={() => setIsLinkWorkflowOpen(false)} className="bg-zinc-800 text-zinc-300 text-xs px-4 py-2.5 rounded-xl cursor-pointer">
                      Cancel
                    </button>
                    <button type="submit" className="bg-purple-600 hover:bg-purple-500 text-white text-xs px-4 py-2.5 rounded-xl cursor-pointer">
                      Link Workflow
                    </button>
                  </div>
                </form>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal: Create Theme */}
      <AnimatePresence>
        {isCreateThemeOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsCreateThemeOpen(false)}
              className="fixed inset-0 bg-black"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 relative z-10 shadow-2xl space-y-4"
            >
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Sparkles className="text-purple-400" size={18} />
                  Create Aesthetics Theme
                </h3>
                <button onClick={() => setIsCreateThemeOpen(false)} className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg">
                  <X size={16} />
                </button>
              </div>
              <form onSubmit={handleCreateTheme} className="space-y-4">
                {/* Theme Name */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">Theme Name</label>
                  <input
                    type="text"
                    required
                    value={newThemeName}
                    onChange={(e) => setNewThemeName(e.target.value)}
                    placeholder="e.g. Classic Editorial"
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none"
                  />
                </div>
                {/* Theme Description */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">Description</label>
                  <input
                    type="text"
                    value={newThemeDesc}
                    onChange={(e) => setNewThemeDesc(e.target.value)}
                    placeholder="e.g. Sleek high contrast catalog studio styling"
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none"
                  />
                </div>
                {/* Lighting Style */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">Lighting Style</label>
                  <input
                    type="text"
                    value={newThemeLighting}
                    onChange={(e) => setNewThemeLighting(e.target.value)}
                    placeholder="e.g. Soft Key Light, Warm Backlights"
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none"
                  />
                </div>
                {/* Location Backdrop */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">Location Backdrop</label>
                  <input
                    type="text"
                    value={newThemeLocation}
                    onChange={(e) => setNewThemeLocation(e.target.value)}
                    placeholder="e.g. Minimalist Studio, Sand Dune"
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none"
                  />
                </div>
                {/* Prompt Preset Instructions */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">Prompt Preset Instructions</label>
                  <textarea
                    value={newThemePrompt}
                    onChange={(e) => setNewThemePrompt(e.target.value)}
                    placeholder="Describe how the prompt should style this theme..."
                    rows={3}
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none resize-none"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button type="button" onClick={() => setIsCreateThemeOpen(false)} className="bg-zinc-800 hover:bg-zinc-755 text-zinc-300 text-xs px-4 py-2.5 rounded-xl cursor-pointer">
                    Cancel
                  </button>
                  <button type="submit" disabled={isCreatingTheme} className="bg-purple-600 hover:bg-purple-500 text-white text-xs px-4 py-2.5 rounded-xl cursor-pointer flex items-center gap-1 shadow-md shadow-purple-950/20">
                    {isCreatingTheme ? <Loader2 className="animate-spin" size={14} /> : "Create"}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
