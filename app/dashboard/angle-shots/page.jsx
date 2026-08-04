"use client";

import React, { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { 
  Camera, Search, Filter, Loader2, CheckCircle2, AlertTriangle, 
  ArrowRight, Clock, Plus, Trash2, RotateCcw, Upload, FileText, Check, ShieldAlert
} from "lucide-react";
import toast from "react-hot-toast";

const PRESET_FAMILIES = ["CATALOG_STANDING", "EDITORIAL_STANDING", "MOTION", "SEATED", "LEANING", "CROPPED_DETAIL", "GARMENT_INTERACTION", "ACCESSORY", "KIDS_BABY"];
const FRAMINGS = ["FULL_BODY", "THREE_QUARTERS", "CLOSE_UP", "UPPER_BODY"];
const TIERS = ["CORE", "EXPANSION"];

export default function AngleShotsPage() {
  const [presets, setPresets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterFamily, setFilterFamily] = useState("");
  const [filterFraming, setFilterFraming] = useState("");
  const [filterTier, setFilterTier] = useState("");

  const [selectedPreset, setSelectedPreset] = useState(null);
  const [presetHistory, setPresetHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [activeTab, setActiveTab] = useState("upload"); // upload, validate, history

  // Custom Pose Upload state
  const [uploadName, setUploadName] = useState("");
  const [uploadCategory, setUploadCategory] = useState("CATALOG_STANDING");
  const [uploadFraming, setUploadFraming] = useState("FULL_BODY");
  const [uploadPose, setUploadPose] = useState("standing");
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadPreview, setUploadPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadJobStatus, setUploadJobStatus] = useState(null);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

  // Schema validation console state
  const [jsonInput, setJsonInput] = useState(
    JSON.stringify({
      preset_id: "ML-POSE-CAT-999",
      version: "1.0.0",
      family: "CATALOG_STANDING",
      display_name: "Interactive Test Pose",
      body_yaw_deg: 45,
      framing: "FULL_BODY",
      qa_rule_codes: ["RULE_HEAD_VISIBLE", "RULE_FEET_VISIBLE"],
      status: "ACTIVE",
      tier: "CORE",
      risk_level: "LOW"
    }, null, 2)
  );
  const [validationResult, setValidationResult] = useState(null);
  const [validating, setValidating] = useState(false);

  // Fetch presets
  const fetchPresets = async (showLoading = false) => {
    try {
      if (showLoading) {
        setLoading(true);
      }
      const data = await api.get("/api/v1/angle-shots");
      setPresets(data);
    } catch (err) {
      toast.error(err.message || "Failed to fetch presets");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPresets(false);
    }, 0);
    return () => {
      clearTimeout(timer);
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Fetch selected preset history
  useEffect(() => {
    if (selectedPreset) {
      const timer = setTimeout(() => {
        setLoadingHistory(true);
      }, 0);

      api.get(`/api/v1/angle-shots/${selectedPreset.id}/history`)
        .then((data) => {
          setPresetHistory(data);
        })
        .catch((err) => {
          toast.error("Failed to load version history");
        })
        .finally(() => {
          setLoadingHistory(false);
        });

      return () => clearTimeout(timer);
    } else {
      const timer = setTimeout(() => {
        setPresetHistory([]);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [selectedPreset]);

  // Handle file select
  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUploadFile(file);
      const reader = new FileReader();
      reader.onload = (event) => setUploadPreview(event.target.result);
      reader.readAsDataURL(file);
    }
  };

  // Upload and extract pose
  const handleUploadCustomPose = async (e) => {
    e.preventDefault();
    if (!uploadName || !uploadFile) {
      toast.error("Please provide a name and reference image");
      return;
    }

    try {
      setUploading(true);
      setUploadJobStatus(null);
      
      const formData = new FormData();
      formData.append("name", uploadName);
      formData.append("category", uploadCategory);
      formData.append("framing", uploadFraming);
      formData.append("pose", uploadPose);
      formData.append("reference_image", uploadFile);

      // Create preset with upload
      const result = await api.post("/api/v1/angle-shots", formData);
      toast.success("Reference image uploaded. Starting custom pose extraction...");
      setUploadJobStatus(result);

      // Reset form fields
      setUploadName("");
      setUploadFile(null);
      setUploadPreview(null);
      
      // Start polling for celery task progression
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const check = await api.get(`/api/v1/angle-shots/${result.id}`);
          setUploadJobStatus(check);
          if (check.status === "active") {
            toast.success(`Pose extraction complete for "${check.name}"!`);
            clearInterval(pollRef.current);
            setUploading(false);
            fetchPresets();
          } else if (check.status === "failed") {
            toast.error("Pose extraction pipeline failed.");
            clearInterval(pollRef.current);
            setUploading(false);
          }
        } catch (pollErr) {
          clearInterval(pollRef.current);
          setUploading(false);
        }
      }, 3000);

    } catch (err) {
      toast.error(err.message || "Failed to upload custom pose");
      setUploading(false);
    }
  };

  // Validate JSON against schema
  const handleValidateSchema = async () => {
    try {
      setValidating(true);
      setValidationResult(null);
      let parsed = {};
      try {
        parsed = JSON.parse(jsonInput);
      } catch (jsonErr) {
        setValidationResult({
          valid: false,
          error: "Invalid JSON format: please verify your brackets and syntax."
        });
        setValidating(false);
        return;
      }

      const res = await api.post("/api/v1/angle-shots/validate", parsed);
      setValidationResult({
        valid: res.valid,
        message: res.message
      });
      toast.success("Validation completed!");
    } catch (err) {
      setValidationResult({
        valid: false,
        error: err.message || "Schema validation failed."
      });
      toast.error("JSON schema validation failed.");
    } finally {
      setValidating(false);
    }
  };

  // Restore previous version
  const handleRestoreVersion = async (versionNumber) => {
    if (!selectedPreset) return;
    try {
      const result = await api.post(`/api/v1/angle-shots/${selectedPreset.id}/restore/${versionNumber}`);
      toast.success(`Preset successfully restored to version ${versionNumber}!`);
      
      // Refresh presets list and select state
      const updatedList = await api.get("/api/v1/angle-shots");
      setPresets(updatedList);
      const match = updatedList.find(p => p.id === selectedPreset.id);
      setSelectedPreset(match);
    } catch (err) {
      toast.error(err.message || "Failed to restore version snapshot");
    }
  };

  // Delete preset
  const handleDeletePreset = async (presetId) => {
    if (!confirm("Are you sure you want to archive/delete this preset configuration?")) return;
    try {
      await api.delete(`/api/v1/angle-shots/${presetId}`);
      toast.success("Preset successfully archived.");
      if (selectedPreset?.id === presetId) {
        setSelectedPreset(null);
      }
      fetchPresets();
    } catch (err) {
      toast.error(err.message || "Failed to delete preset");
    }
  };

  // Filter logic
  const filteredPresets = presets.filter((p) => {
    const matchesSearch = p.name?.toLowerCase().includes(search.toLowerCase()) || 
                          p.code?.toLowerCase().includes(search.toLowerCase()) ||
                          p.pose?.toLowerCase().includes(search.toLowerCase());
    const matchesFamily = !filterFamily || p.category === filterFamily;
    const matchesFraming = !filterFraming || p.framing === filterFraming;
    const matchesTier = !filterTier || 
                        (filterTier === "CORE" && !p.is_premium) || 
                        (filterTier === "EXPANSION" && p.is_premium);
    return matchesSearch && matchesFamily && matchesFraming && matchesTier;
  });

  return (
    <div className="space-y-6 text-zinc-100 p-2">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-zinc-900/50 border border-zinc-800/80 p-6 rounded-2xl backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Camera className="text-purple-500 w-6 h-6" />
            <h1 className="text-2xl font-bold tracking-tight text-white">Angle Shot Preset Library</h1>
          </div>
          <p className="text-sm text-zinc-400 max-w-2xl">
            Administrative preset configuration manager. Enforce standardized pose models, crop rules, aspects, limb structures, and track revision rollbacks.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchPresets} 
            className="flex items-center gap-1.5 text-xs text-zinc-300 hover:text-white bg-zinc-850 hover:bg-zinc-800 border border-zinc-700/80 px-4 py-2.5 rounded-xl transition-all"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Main Grid View */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left Side: Filter and Library List (2/3 width) */}
        <div className="xl:col-span-2 space-y-4">
          <div className="flex flex-col md:flex-row gap-3 bg-zinc-900/30 border border-zinc-850 p-4 rounded-xl backdrop-blur-sm">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 w-4 h-4 text-zinc-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search presets by name, code or pose..."
                className="w-full pl-9 pr-4 py-2 bg-zinc-950 border border-zinc-800 rounded-xl focus:border-purple-500 focus:outline-none text-sm text-zinc-200 transition-colors placeholder-zinc-650"
              />
            </div>
            {/* Filters */}
            <div className="flex flex-wrap gap-2">
              <select
                value={filterFamily}
                onChange={(e) => setFilterFamily(e.target.value)}
                className="bg-zinc-950 border border-zinc-800 px-3 py-2 rounded-xl text-xs text-zinc-300 focus:border-purple-500 focus:outline-none"
              >
                <option value="">All Families</option>
                {PRESET_FAMILIES.map(f => <option key={f} value={f}>{f.replace("_", " ")}</option>)}
              </select>
              <select
                value={filterFraming}
                onChange={(e) => setFilterFraming(e.target.value)}
                className="bg-zinc-950 border border-zinc-800 px-3 py-2 rounded-xl text-xs text-zinc-300 focus:border-purple-500 focus:outline-none"
              >
                <option value="">All Framings</option>
                {FRAMINGS.map(f => <option key={f} value={f}>{f.replace("_", " ")}</option>)}
              </select>
              <select
                value={filterTier}
                onChange={(e) => setFilterTier(e.target.value)}
                className="bg-zinc-950 border border-zinc-800 px-3 py-2 rounded-xl text-xs text-zinc-300 focus:border-purple-500 focus:outline-none"
              >
                <option value="">All Tiers</option>
                {TIERS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>

          {/* Cards Grid */}
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 bg-zinc-900/10 border border-zinc-850 rounded-2xl">
              <Loader2 className="animate-spin text-purple-500 w-10 h-10 mb-4" />
              <p className="text-sm text-zinc-400">Loading preset configurations...</p>
            </div>
          ) : filteredPresets.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 bg-zinc-900/10 border border-zinc-850 rounded-2xl">
              <Camera className="text-zinc-700 w-12 h-12 mb-3" />
              <p className="text-sm text-zinc-400">No preset configurations match your criteria.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredPresets.map((preset) => {
                const isSelected = selectedPreset?.id === preset.id;
                const isCustom = preset.is_custom;
                const isPremium = preset.is_premium;

                return (
                  <div
                    key={preset.id}
                    onClick={() => setSelectedPreset(preset)}
                    className={`relative p-5 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between h-48 backdrop-blur-md ${
                      isSelected
                        ? "bg-purple-950/20 border-purple-500/80 shadow-md shadow-purple-950/10"
                        : "bg-zinc-900/30 border-zinc-800 hover:bg-zinc-900/50 hover:border-zinc-750"
                    }`}
                  >
                    <div>
                      {/* Tags */}
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] tracking-wide font-mono font-bold text-purple-400 uppercase bg-purple-950/40 border border-purple-800/40 px-2 py-0.5 rounded-full">
                          {preset.code || `ML-POSE-CUSTOM-${preset.id}`}
                        </span>
                        <div className="flex gap-1.5">
                          {isPremium ? (
                            <span className="text-[9px] font-bold text-amber-400 bg-amber-950/40 border border-amber-800/40 px-2 py-0.5 rounded-full">
                              EXPANSION
                            </span>
                          ) : (
                            <span className="text-[9px] font-bold text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded-full">
                              CORE
                            </span>
                          )}
                          {isCustom && (
                            <span className="text-[9px] font-bold text-indigo-400 bg-indigo-950/40 border border-indigo-800/40 px-2 py-0.5 rounded-full">
                              CUSTOM
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Title */}
                      <h3 className="text-base font-bold text-white mb-1 line-clamp-1">{preset.name}</h3>
                      <p className="text-xs text-zinc-400 line-clamp-2 mb-3">
                        {preset.description || `Category: ${preset.category || "Unassigned"}. Framing: ${preset.framing || "Standard"}. Pose: ${preset.pose || "Neutral"}.`}
                      </p>
                    </div>

                    {/* Bottom stats row */}
                    <div className="flex justify-between items-center text-[11px] text-zinc-500 border-t border-zinc-800/50 pt-3">
                      <span>Framing: <strong className="text-zinc-300">{preset.framing}</strong></span>
                      <span>Pose: <strong className="text-zinc-300">{preset.pose}</strong></span>
                      <span>v{preset.version}</span>
                    </div>

                    {/* Archive button */}
                    {isCustom && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeletePreset(preset.id);
                        }}
                        className="absolute bottom-4 right-4 p-1.5 text-zinc-500 hover:text-rose-400 rounded-lg hover:bg-rose-950/20 transition-all"
                        title="Archive Preset"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Side: Interactive Controls / Selected Details (1/3 width) */}
        <div className="space-y-6">
          {/* Selected Preset Details Panel */}
          {selectedPreset && (
            <div className="bg-zinc-900/40 border border-zinc-800 p-6 rounded-2xl backdrop-blur-md space-y-4">
              <div className="flex justify-between items-start border-b border-zinc-800/80 pb-4">
                <div>
                  <span className="text-[10px] font-mono text-purple-400 bg-purple-950/40 border border-purple-800/40 px-2.5 py-0.5 rounded-full">
                    {selectedPreset.code || `ML-POSE-CUSTOM-${selectedPreset.id}`}
                  </span>
                  <h2 className="text-lg font-bold text-white mt-2">{selectedPreset.name}</h2>
                </div>
                <button
                  onClick={() => setSelectedPreset(null)}
                  className="text-xs text-zinc-500 hover:text-zinc-300"
                >
                  Clear Selection
                </button>
              </div>

              {/* Specs Grid */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-zinc-950 border border-zinc-850 p-2.5 rounded-xl">
                  <span className="text-zinc-500 block mb-0.5">Family</span>
                  <strong className="text-zinc-200 block truncate">{selectedPreset.category}</strong>
                </div>
                <div className="bg-zinc-950 border border-zinc-850 p-2.5 rounded-xl">
                  <span className="text-zinc-500 block mb-0.5">Framing</span>
                  <strong className="text-zinc-200 block truncate">{selectedPreset.framing}</strong>
                </div>
                <div className="bg-zinc-950 border border-zinc-850 p-2.5 rounded-xl">
                  <span className="text-zinc-500 block mb-0.5">Pose Concept</span>
                  <strong className="text-zinc-200 block truncate">{selectedPreset.pose}</strong>
                </div>
                <div className="bg-zinc-950 border border-zinc-850 p-2.5 rounded-xl">
                  <span className="text-zinc-500 block mb-0.5">Focal Length</span>
                  <strong className="text-zinc-200 block truncate">
                    {selectedPreset.focal_length_mm ? `${selectedPreset.focal_length_mm} mm` : "N/A"}
                  </strong>
                </div>
              </div>

              {/* Extra Quality Rules from JSONB */}
              {selectedPreset.quality_rules && (
                <div className="bg-zinc-950/50 border border-zinc-850/80 p-4 rounded-xl space-y-3">
                  <h4 className="text-xs font-bold text-purple-400 border-b border-zinc-850 pb-1.5 uppercase tracking-wide">
                    Quality Rules & Limbs Structure
                  </h4>
                  <div className="space-y-1.5 text-[11px]">
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Body Yaw Angle:</span>
                      <span className="text-zinc-300 font-mono">{selectedPreset.quality_rules.body_yaw_deg}°</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Risk Level:</span>
                      <span className={`font-bold uppercase ${
                        selectedPreset.quality_rules.risk_level === "HIGH" ? "text-rose-400" : "text-emerald-400"
                      }`}>
                        {selectedPreset.quality_rules.risk_level || "LOW"}
                      </span>
                    </div>
                    {selectedPreset.quality_rules.qa_rule_codes && (
                      <div className="pt-1.5">
                        <span className="text-zinc-500 block mb-1">Enforced QA Codes:</span>
                        <div className="flex flex-wrap gap-1">
                          {(Array.isArray(selectedPreset.quality_rules.qa_rule_codes) 
                            ? selectedPreset.quality_rules.qa_rule_codes 
                            : selectedPreset.quality_rules.qa_rule_codes.split(";")
                          ).map((code, idx) => (
                            <span key={idx} className="bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded font-mono text-[9px] text-zinc-400">
                              {code.trim()}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Action Tabs Panel */}
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl backdrop-blur-md overflow-hidden flex flex-col h-[460px]">
            {/* Tabs Header */}
            <div className="flex border-b border-zinc-800 bg-zinc-950/40">
              <button
                onClick={() => setActiveTab("upload")}
                className={`flex-1 py-3 text-xs font-bold transition-all border-b-2 flex items-center justify-center gap-1.5 ${
                  activeTab === "upload"
                    ? "border-purple-500 text-white bg-zinc-900/20"
                    : "border-transparent text-zinc-500 hover:text-zinc-300"
                }`}
              >
                <Upload size={13} /> Custom Upload
              </button>
              <button
                onClick={() => setActiveTab("validate")}
                className={`flex-1 py-3 text-xs font-bold transition-all border-b-2 flex items-center justify-center gap-1.5 ${
                  activeTab === "validate"
                    ? "border-purple-500 text-white bg-zinc-900/20"
                    : "border-transparent text-zinc-500 hover:text-zinc-300"
                }`}
              >
                <FileText size={13} /> Schema Validator
              </button>
              <button
                onClick={() => setActiveTab("history")}
                className={`flex-1 py-3 text-xs font-bold transition-all border-b-2 flex items-center justify-center gap-1.5 ${
                  activeTab === "history"
                    ? "border-purple-500 text-white bg-zinc-900/20"
                    : "border-transparent text-zinc-500 hover:text-zinc-300"
                }`}
                disabled={!selectedPreset}
              >
                <RotateCcw size={13} /> History {selectedPreset && `(${selectedPreset.version})`}
              </button>
            </div>

            {/* Tab 1: Custom Pose Upload */}
            {activeTab === "upload" && (
              <form onSubmit={handleUploadCustomPose} className="p-6 flex flex-col justify-between flex-1 overflow-y-auto space-y-4">
                <div className="space-y-4">
                  <div>
                    <label className="text-[11px] font-bold text-zinc-400 block mb-1 uppercase">Preset Display Name</label>
                    <input
                      type="text"
                      required
                      value={uploadName}
                      onChange={(e) => setUploadName(e.target.value)}
                      placeholder="e.g. Dynamic Relaxed Sitting"
                      className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-xl focus:border-purple-500 focus:outline-none"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[11px] font-bold text-zinc-400 block mb-1 uppercase">Category</label>
                      <select
                        value={uploadCategory}
                        onChange={(e) => setUploadCategory(e.target.value)}
                        className="w-full px-3 py-2 text-xs bg-zinc-950 border border-zinc-800 rounded-xl focus:outline-none"
                      >
                        {PRESET_FAMILIES.map(f => <option key={f} value={f}>{f.replace("_", " ")}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-[11px] font-bold text-zinc-400 block mb-1 uppercase">Framing</label>
                      <select
                        value={uploadFraming}
                        onChange={(e) => setUploadFraming(e.target.value)}
                        className="w-full px-3 py-2 text-xs bg-zinc-950 border border-zinc-800 rounded-xl focus:outline-none"
                      >
                        {FRAMINGS.map(f => <option key={f} value={f}>{f.replace("_", " ")}</option>)}
                      </select>
                    </div>
                  </div>

                  {/* Drag and Drop Reference File */}
                  <div>
                    <label className="text-[11px] font-bold text-zinc-400 block mb-1.5 uppercase">Reference Image Pose</label>
                    <input
                      type="file"
                      accept="image/*"
                      ref={fileInputRef}
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                    <div
                      onClick={() => fileInputRef.current?.click()}
                      className="border border-dashed border-zinc-800 hover:border-purple-500/50 bg-zinc-950 p-4 rounded-xl text-center cursor-pointer transition-all flex flex-col items-center justify-center min-h-28"
                    >
                      {uploadPreview ? (
                        <img src={uploadPreview} alt="Preview" className="w-16 h-16 object-cover rounded-lg border border-zinc-800" />
                      ) : (
                        <>
                          <Upload className="text-zinc-650 w-6 h-6 mb-2" />
                          <span className="text-xs text-zinc-400">Click to select reference image file</span>
                          <span className="text-[10px] text-zinc-600 mt-1">PNG, JPG, WEBP formats</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Polling / Job Status Indicator */}
                  {uploadJobStatus && (
                    <div className="bg-zinc-950/80 border border-zinc-850 p-3.5 rounded-xl space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-zinc-400 uppercase tracking-wide">Extraction Task:</span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                          uploadJobStatus.status === "active" ? "text-emerald-400 bg-emerald-950/20" :
                          uploadJobStatus.status === "failed" ? "text-rose-400 bg-rose-950/20" :
                          "text-amber-400 bg-amber-950/20 animate-pulse"
                        }`}>
                          {uploadJobStatus.status}
                        </span>
                      </div>
                      <div className="text-[10px] text-zinc-500">
                        {uploadJobStatus.status === "active" ? "Thumbnail and pose map generated!" :
                         uploadJobStatus.status === "failed" ? "Custom pose extraction pipeline crashed." :
                         "Analyzing image landmarks and generating pose map..."}
                      </div>
                    </div>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={uploading || !uploadFile || !uploadName}
                  className="w-full py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-500 font-bold rounded-xl text-xs flex items-center justify-center gap-1.5 transition-all text-white mt-auto"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="animate-spin w-4 h-4" /> Extracting landmarks...
                    </>
                  ) : (
                    <>
                      Create Custom Preset
                    </>
                  )}
                </button>
              </form>
            )}

            {/* Tab 2: JSON Schema Validator */}
            {activeTab === "validate" && (
              <div className="p-6 flex flex-col justify-between flex-1 overflow-y-auto space-y-4">
                <div className="space-y-3 flex-1 flex flex-col">
                  <label className="text-[11px] font-bold text-zinc-400 block uppercase">Raw Configuration Input (JSON)</label>
                  <textarea
                    value={jsonInput}
                    onChange={(e) => setJsonInput(e.target.value)}
                    rows={12}
                    className="w-full flex-1 p-3 bg-zinc-950 border border-zinc-850 rounded-xl font-mono text-[10px] text-zinc-300 focus:border-purple-500 focus:outline-none resize-none leading-relaxed"
                  />

                  {/* Validation results console log */}
                  {validationResult && (
                    <div className={`p-4 border rounded-xl flex items-start gap-3 backdrop-blur-md ${
                      validationResult.valid 
                        ? "bg-emerald-950/10 border-emerald-800/40 text-emerald-300"
                        : "bg-rose-950/10 border-rose-800/40 text-rose-300"
                    }`}>
                      {validationResult.valid ? (
                        <>
                          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                          <div>
                            <strong className="text-xs block text-emerald-200">Schema Validation Passed</strong>
                            <span className="text-[10px] leading-relaxed block mt-0.5">{validationResult.message}</span>
                          </div>
                        </>
                      ) : (
                        <>
                          <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0" />
                          <div>
                            <strong className="text-xs block text-rose-200">Schema Validation Failed</strong>
                            <span className="text-[10px] font-mono leading-relaxed block mt-0.5">{validationResult.error}</span>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>

                <button
                  onClick={handleValidateSchema}
                  disabled={validating || !jsonInput}
                  className="w-full py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-500 font-bold rounded-xl text-xs flex items-center justify-center gap-1.5 transition-all text-white"
                >
                  {validating ? <Loader2 className="animate-spin w-4 h-4" /> : "Validate Schema Config"}
                </button>
              </div>
            )}

            {/* Tab 3: Version History Drawer */}
            {activeTab === "history" && selectedPreset && (
              <div className="p-6 flex flex-col justify-between flex-1 overflow-y-auto space-y-4">
                {loadingHistory ? (
                  <div className="flex flex-col items-center justify-center py-20 flex-1">
                    <Loader2 className="animate-spin text-purple-500 w-8 h-8 mb-2" />
                    <p className="text-[10px] text-zinc-500">Loading version logs...</p>
                  </div>
                ) : presetHistory.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-20 flex-1">
                    <Clock className="text-zinc-700 w-10 h-10 mb-2" />
                    <p className="text-[10px] text-zinc-500">No version snapshot logs found.</p>
                  </div>
                ) : (
                  <div className="space-y-4 flex-1 overflow-y-auto pr-1">
                    <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wide mb-2">Version Log snapshots</h3>
                    <div className="space-y-3">
                      {presetHistory.map((ver) => {
                        const isCurrent = ver.version === selectedPreset.version;
                        return (
                          <div
                            key={ver.id}
                            className={`p-4 rounded-xl border flex flex-col justify-between gap-3 transition-all ${
                              isCurrent 
                                ? "bg-purple-950/15 border-purple-500/40"
                                : "bg-zinc-950/60 border-zinc-850"
                            }`}
                          >
                            <div className="flex justify-between items-center">
                              <span className="text-[11px] font-bold text-white">Version v{ver.version}</span>
                              {isCurrent ? (
                                <span className="inline-flex items-center gap-1 text-[9px] text-purple-400 uppercase font-bold bg-purple-950/30 border border-purple-800/30 px-2 py-0.5 rounded-full">
                                  <Check size={8} /> Active
                                </span>
                              ) : (
                                <button
                                  onClick={() => handleRestoreVersion(ver.version)}
                                  className="text-[10px] font-bold text-zinc-400 hover:text-white flex items-center gap-1 bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 px-2.5 py-1 rounded transition-all"
                                >
                                  <RotateCcw size={10} /> Restore
                                </button>
                              )}
                            </div>
                            <p className="text-[10px] text-zinc-400 italic">
                              &quot;{ver.change_note || "No edit comments provided."}&quot;
                            </p>
                            <div className="text-[9px] text-zinc-600 text-right">
                              Logged on: {new Date(ver.created_at).toLocaleDateString()}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
