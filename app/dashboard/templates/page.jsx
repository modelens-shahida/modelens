"use client";

import React, { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Sparkles, Layers, Image as ImageIcon, CheckCircle, AlertCircle, Loader2, ArrowRight, Play, Eye, Download, Search } from "lucide-react";

export default function TemplatesStudio() {
  const { user } = useAuth();
  
  // Data State
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [assets, setAssets] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [generations, setGenerations] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");

  // Form State
  const [variables, setVariables] = useState({});
  const [selectedGarmentAssetId, setSelectedGarmentAssetId] = useState("");
  const [selectedPoseAssetId, setSelectedPoseAssetId] = useState("");
  const [selectedMaterialAssetId, setSelectedMaterialAssetId] = useState("");
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [provider, setProvider] = useState("AUTO");
  
  // UI State
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [previewImage, setPreviewImage] = useState(null);

  // 1. Fetch Brands on Load
  useEffect(() => {
    async function fetchBrands() {
      try {
        const data = await api.get("/api/v1/brands");
        setBrands(data);
        if (data.length > 0) {
          setSelectedBrandId(data[0].id.toString());
        }
      } catch (err) {
        console.error("Failed to load brands:", err);
        setError("Failed to load brand workspaces.");
      }
    }
    fetchBrands();
  }, []);

  // 2. Fetch Assets & Templates & Generations when Selected Brand Changes
  useEffect(() => {
    if (!selectedBrandId) return;
    
    async function fetchBrandData() {
      setLoading(true);
      setError("");
      try {
        // Fetch Assets
        const assetData = await api.get(`/api/v1/assets?brand_id=${selectedBrandId}`);
        setAssets(assetData);

        // Fetch Templates
        const templateData = await api.get(`/api/v1/templates?brand_id=${selectedBrandId}`);
        setTemplates(templateData);
        if (templateData.length > 0) {
          handleSelectTemplate(templateData[0]);
        } else {
          setSelectedTemplate(null);
        }

        // Fetch Generations
        const genData = await api.get(`/api/v1/generations?brand_id=${selectedBrandId}`);
        setGenerations(genData);

      } catch (err) {
        console.error("Failed to load brand data:", err);
        setError("Failed to load workspace data.");
      } finally {
        setLoading(false);
      }
    }

    fetchBrandData();
  }, [selectedBrandId]);

  // 3. Status Polling for Pending Generations
  useEffect(() => {
    const hasPending = generations.some(g => g.status === "QUEUED" || g.status === "PROCESSING");
    if (!hasPending) return;

    const interval = setInterval(async () => {
      try {
        const genData = await api.get(`/api/v1/generations?brand_id=${selectedBrandId}`);
        setGenerations(genData);
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [generations, selectedBrandId]);

  // Parse prompt variables helper
  const handleSelectTemplate = (template) => {
    setSelectedTemplate(template);
    
    // Parse variables dynamically from prompt
    const matches = template.prompt.match(/\{\{([^}]+)\}\}/g) || [];
    const vars = Array.from(new Set(matches.map(m => m.replace(/\{\{|\}\}/g, "").trim())));
    
    // Set default/empty values
    const initialVars = {};
    vars.forEach(v => {
      initialVars[v] = "";
    });
    setVariables(initialVars);

    // Reset reference selections
    setSelectedGarmentAssetId("");
    setSelectedPoseAssetId("");
    setSelectedMaterialAssetId("");
  };

  // Variable input change handler
  const handleVariableChange = (key, val) => {
    setVariables(prev => ({
      ...prev,
      [key]: val
    }));
  };

  // Submit Generation Request
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedTemplate) return;

    setSubmitting(true);
    setError("");
    setSuccess("");

    // Verify all dynamic variables are filled
    const missingVars = Object.keys(variables).filter(k => !variables[k].trim());
    if (missingVars.length > 0) {
      setError(`Please fill in all template variables: ${missingVars.join(", ")}`);
      setSubmitting(false);
      return;
    }

    const payload = {
      template_id: selectedTemplate.id,
      variables: variables,
      aspect_ratio: aspectRatio,
      provider: provider,
      brand_id: parseInt(selectedBrandId)
    };

    if (selectedGarmentAssetId) payload.garment_asset_id = parseInt(selectedGarmentAssetId);
    if (selectedPoseAssetId) payload.pose_asset_id = parseInt(selectedPoseAssetId);
    if (selectedMaterialAssetId) payload.material_asset_id = parseInt(selectedMaterialAssetId);

    try {
      const response = await api.post("/api/v1/generations", payload);
      setSuccess("Generation job queued successfully!");
      
      // Update generations list immediately
      const genData = await api.get(`/api/v1/generations?brand_id=${selectedBrandId}`);
      setGenerations(genData);
    } catch (err) {
      console.error("Failed to start generation:", err);
      setError(err.message || "Failed to trigger template generation.");
    } finally {
      setSubmitting(false);
    }
  };

  // Filter templates list
  const filteredTemplates = templates.filter(t => 
    t.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    t.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 space-y-8">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-900 pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Layers className="text-purple-500" /> Templates Studio
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Build high-converting product shots dynamically using customizable prompt templates.
          </p>
        </div>

        {/* Workspace selector */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Workspace:</span>
          <select
            value={selectedBrandId}
            onChange={(e) => setSelectedBrandId(e.target.value)}
            className="bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-xs text-zinc-200 focus:border-purple-500 outline-none cursor-pointer"
          >
            {brands.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="flex items-center gap-3 bg-rose-950/20 border border-rose-900/30 text-rose-400 p-4 rounded-xl text-sm">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="flex items-center gap-3 bg-emerald-950/20 border border-emerald-900/30 text-emerald-400 p-4 rounded-xl text-sm">
          <CheckCircle size={18} />
          <span>{success}</span>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Loader2 className="animate-spin text-purple-500" size={32} />
          <span className="text-xs text-zinc-400">Loading templates directory...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* LEFT COLUMN: Templates List */}
          <div className="lg:col-span-4 bg-zinc-900/25 border border-zinc-900 rounded-2xl p-5 space-y-4">
            <div className="relative">
              <Search className="absolute left-3.5 top-3 text-zinc-500" size={16} />
              <input
                type="text"
                placeholder="Search templates..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-850 rounded-xl pl-10 pr-4 py-2.5 text-xs text-zinc-200 focus:border-purple-500 outline-none placeholder:text-zinc-500"
              />
            </div>

            <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
              {filteredTemplates.length === 0 ? (
                <p className="text-xs text-zinc-500 text-center py-8">No templates found.</p>
              ) : (
                filteredTemplates.map((t) => {
                  const isSelected = selectedTemplate?.id === t.id;
                  return (
                    <div
                      key={t.id}
                      onClick={() => handleSelectTemplate(t)}
                      className={`p-4 rounded-xl border transition-all cursor-pointer text-left ${
                        isSelected
                          ? "bg-purple-600/10 border-purple-500 text-white"
                          : "bg-zinc-950 border-zinc-900 text-zinc-400 hover:border-zinc-800 hover:text-zinc-200"
                      }`}
                    >
                      <h3 className="text-sm font-semibold">{t.name}</h3>
                      <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{t.description}</p>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* RIGHT COLUMN: Configurator Form */}
          <div className="lg:col-span-8 bg-zinc-900/25 border border-zinc-900 rounded-2xl p-6">
            {selectedTemplate ? (
              <form onSubmit={handleSubmit} className="space-y-6">
                <div>
                  <h2 className="text-lg font-bold text-white">{selectedTemplate.name}</h2>
                  <p className="text-xs text-zinc-500 mt-0.5">{selectedTemplate.description}</p>
                  
                  {/* Prompt Blueprint Code Box */}
                  <div className="mt-3 bg-zinc-950 border border-zinc-900/80 rounded-xl p-3 text-[11px] font-mono text-zinc-400 leading-relaxed break-all">
                    <span className="text-zinc-600 block uppercase text-[9px] font-sans font-bold tracking-wider mb-1">Prompt Blueprint</span>
                    {selectedTemplate.prompt}
                  </div>
                </div>

                <hr className="border-zinc-900" />

                {/* Variable inputs */}
                {Object.keys(variables).length > 0 && (
                  <div className="space-y-4">
                    <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Prompt Variables</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.keys(variables).map((key) => (
                        <div key={key} className="space-y-1.5">
                          <label className="text-xs font-medium text-zinc-300 capitalize">{key.replace(/_/g, " ")}</label>
                          <input
                            type="text"
                            required
                            placeholder={`Value for ${key}`}
                            value={variables[key]}
                            onChange={(e) => handleVariableChange(key, e.target.value)}
                            className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-200 outline-none"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Reference Assets */}
                <div className="space-y-4">
                  <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Reference Layers (Optional)</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Garment */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-300">Product Garment</label>
                      <select
                        value={selectedGarmentAssetId}
                        onChange={(e) => setSelectedGarmentAssetId(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-3 py-2.5 text-xs text-zinc-200 focus:border-purple-500 outline-none cursor-pointer"
                      >
                        <option value="">-- None --</option>
                        {assets.map((a) => (
                          <option key={a.id} value={a.id}>{a.name || a.filename}</option>
                        ))}
                      </select>
                    </div>

                    {/* Pose */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-300">Reference Pose</label>
                      <select
                        value={selectedPoseAssetId}
                        onChange={(e) => setSelectedPoseAssetId(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-3 py-2.5 text-xs text-zinc-200 focus:border-purple-500 outline-none cursor-pointer"
                      >
                        <option value="">-- None --</option>
                        {assets.map((a) => (
                          <option key={a.id} value={a.id}>{a.name || a.filename}</option>
                        ))}
                      </select>
                    </div>

                    {/* Material */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-300">Texture / Material</label>
                      <select
                        value={selectedMaterialAssetId}
                        onChange={(e) => setSelectedMaterialAssetId(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-3 py-2.5 text-xs text-zinc-200 focus:border-purple-500 outline-none cursor-pointer"
                      >
                        <option value="">-- None --</option>
                        {assets.map((a) => (
                          <option key={a.id} value={a.id}>{a.name || a.filename}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Additional Settings */}
                <div className="space-y-4">
                  <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Output Settings</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Aspect Ratio */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-300">Aspect Ratio</label>
                      <select
                        value={aspectRatio}
                        onChange={(e) => setAspectRatio(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-3 py-2.5 text-xs text-zinc-200 focus:border-purple-500 outline-none cursor-pointer"
                      >
                        <option value="1:1">1:1 Square</option>
                        <option value="4:5">4:5 Portrait</option>
                        <option value="16:9">16:9 Landscape</option>
                      </select>
                    </div>

                    {/* Model Provider */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-zinc-300">AI Engine</label>
                      <select
                        value={provider}
                        onChange={(e) => setProvider(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-3 py-2.5 text-xs text-zinc-200 focus:border-purple-500 outline-none cursor-pointer"
                      >
                        <option value="AUTO">Auto-Select Model</option>
                        <option value="GEMINI">Google Gemini Multimodal</option>
                        <option value="FASHN">Fashn Tryon Engine</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Action button */}
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl py-3 text-xs font-bold transition-all shadow-md shadow-purple-950/20 disabled:bg-purple-600/50 cursor-pointer disabled:cursor-not-allowed"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="animate-spin" size={14} /> Queuing Generation Job...
                    </>
                  ) : (
                    <>
                      <Play size={12} fill="currentColor" /> Generate Studio Shot
                    </>
                  )}
                </button>
              </form>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-center text-zinc-500">
                <ImageIcon size={32} className="mb-2 text-zinc-600" />
                <p className="text-xs">Select a template template from the catalog list to configure.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* BOTTOM SECTION: Generation Jobs History */}
      <div className="bg-zinc-900/25 border border-zinc-900 rounded-2xl p-6 space-y-4">
        <h2 className="text-sm font-bold text-white uppercase tracking-wider">Recent Generations Log</h2>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-zinc-850 text-zinc-400 font-semibold">
                <th className="pb-3">Job ID</th>
                <th className="pb-3">Template</th>
                <th className="pb-3">Configuration Variables</th>
                <th className="pb-3">Engine</th>
                <th className="pb-3">Status</th>
                <th className="pb-3">Created</th>
                <th className="pb-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {generations.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-8 text-zinc-500">
                    No generations recorded yet for this workspace. Select a template above to generate one.
                  </td>
                </tr>
              ) : (
                generations.map((g) => {
                  const statusColors = {
                    QUEUED: "bg-purple-950/40 text-purple-400 border border-purple-900/30",
                    PROCESSING: "bg-blue-950/40 text-blue-400 border border-blue-900/30",
                    COMPLETED: "bg-emerald-950/40 text-emerald-400 border border-emerald-900/30",
                    FAILED: "bg-rose-950/40 text-rose-400 border border-rose-900/30",
                  };

                  return (
                    <tr key={g.id} className="border-b border-zinc-900/60 hover:bg-zinc-900/10">
                      <td className="py-4 font-mono text-[10px] text-zinc-500">#{g.id}</td>
                      <td className="py-4 text-zinc-200 font-medium">
                        {templates.find(t => t.id === g.template_id)?.name || `Template ${g.template_id}`}
                      </td>
                      <td className="py-4 text-zinc-400 max-w-xs truncate">
                        {Object.entries(g.variables || {}).map(([k, v]) => `${k}:${v}`).join(", ")}
                      </td>
                      <td className="py-4 text-zinc-400">{g.provider}</td>
                      <td className="py-4">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] uppercase font-semibold ${statusColors[g.status] || "bg-zinc-800 text-zinc-400"}`}>
                          {g.status}
                        </span>
                      </td>
                      <td className="py-4 text-zinc-500">
                        {new Date(g.created_at).toLocaleString()}
                      </td>
                      <td className="py-4 text-right">
                        {g.status === "COMPLETED" && g.output_image_path ? (
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => setPreviewImage(g.output_image_path)}
                              className="p-1.5 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-lg transition-colors cursor-pointer"
                              title="Preview Shot"
                            >
                              <Eye size={14} />
                            </button>
                            <a
                              href={g.output_image_path}
                              download
                              target="_blank"
                              rel="noreferrer"
                              className="p-1.5 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-lg transition-colors cursor-pointer"
                              title="Download Shot"
                            >
                              <Download size={14} />
                            </a>
                          </div>
                        ) : g.status === "FAILED" ? (
                          <span className="text-[10px] text-rose-500" title={g.error_message || "Unknown error"}>
                            Error details
                          </span>
                        ) : (
                          <span className="text-[10px] text-zinc-500 flex items-center justify-end gap-1">
                            <Loader2 className="animate-spin" size={10} /> Active
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Image Preview Modal */}
      {previewImage && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden max-w-2xl w-full relative">
            <button
              onClick={() => setPreviewImage(null)}
              className="absolute top-4 right-4 bg-black/60 hover:bg-black/80 text-white rounded-full p-1.5 focus:outline-none transition-colors cursor-pointer"
            >
              &times;
            </button>
            <div className="p-8 flex items-center justify-center bg-zinc-950">
              <img
                src={previewImage}
                alt="Generated Studio Output"
                className="max-h-[60vh] object-contain rounded-lg"
              />
            </div>
            <div className="p-4 bg-zinc-900 border-t border-zinc-850 flex justify-between items-center">
              <span className="text-xs text-zinc-400">Layer output successfully rendered.</span>
              <a
                href={previewImage}
                download
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer"
              >
                <Download size={12} /> Download Layer
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
