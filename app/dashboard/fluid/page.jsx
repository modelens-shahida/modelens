"use client";
import React, { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { Layers, Plus, ChevronRight, Download, RefreshCw, Loader2, Image, Wand2, UserCheck, Crop, ArrowUp, X } from "lucide-react";
import toast from "react-hot-toast";
import Link from "next/link";
import TaxonomyResolverPreview from "@/components/dashboard/TaxonomyResolverPreview";
import { ShieldCheck } from "lucide-react";

const ASPECT_RATIOS = ["1:1", "3:4", "4:5", "9:16", "16:9", "21:9"];
const RESOLUTIONS = ["1K", "2K", "4K"];
const UPSCALE_RESOLUTIONS = ["4K", "8K", "14K"];
const OPERATIONS = ["apply-product", "edit", "model-swap", "reframe", "upscale"];

export default function FluidStudioPage() {
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [activeLayer, setActiveLayer] = useState(null);
  const [brandModels, setBrandModels] = useState([]);
  const [brands, setBrands] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeOp, setActiveOp] = useState(null);
  const [tab, setTab] = useState("editor"); // "editor" | "models"

  // Session creation form
  const [newSessionName, setNewSessionName] = useState("");
  const [newScenePrompt, setNewScenePrompt] = useState("");
  const [newAspectRatio, setNewAspectRatio] = useState("4:5");
  const [newResolution, setNewResolution] = useState("2K");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [creating, setCreating] = useState(false);

  // Operation forms
  const [opProductId, setOpProductId] = useState("");
  const [opInstructions, setOpInstructions] = useState("");
  const [opPrompt, setOpPrompt] = useState("");
  const [opMaskFile, setOpMaskFile] = useState(null);
  const [opModelPrompt, setOpModelPrompt] = useState("");
  const [opAspectRatio, setOpAspectRatio] = useState("4:5");
  const [opUpscale, setOpUpscale] = useState("4K");
  const [opSubmitting, setOpSubmitting] = useState(false);

  // Brand model creation
  const [newModelName, setNewModelName] = useState("");
  const [newModelGender, setNewModelGender] = useState("Female");
  const [fullBodyFile, setFullBodyFile] = useState(null);
  const [portraitFile, setPortraitFile] = useState(null);
  const [creatingModel, setCreatingModel] = useState(false);

  const maskInputRef = useRef(null);

  const fetchSessions = async () => {
    try {
      const data = await api.get("/api/v1/editorial-sessions");
      setSessions(data?.sessions || data || []);
    } catch {}
  };

  const fetchBrandModels = async () => {
    try {
      const data = await api.get("/api/v1/brand-models");
      setBrandModels(data?.models || data || []);
    } catch {}
  };

  const fetchBrands = async () => {
    try {
      const data = await api.get("/api/v1/brands");
      setBrands(data || []);
    } catch {}
  };

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    fetchSessions();
    fetchBrandModels();
    fetchBrands();
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  const fetchSession = async (sessionId) => {
    setLoading(true);
    try {
      const data = await api.get(`/api/v1/editorial-sessions/${sessionId}`);
      setActiveSession(data);
      if (data.layers?.length > 0) {
        setActiveLayer(data.layers[data.layers.length - 1]);
      }
    } catch {
      toast.error("Failed to load session");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSession = async () => {
    if (!newSessionName.trim()) { toast.error("Please enter a session name"); return; }
    setCreating(true);
    try {
      const data = await api.post("/api/v1/editorial-sessions", {
        name: newSessionName,
        scene_prompt: newScenePrompt,
        aspect_ratio: newAspectRatio,
        resolution: newResolution,
      });
      toast.success("Session created!");
      setShowCreateForm(false);
      setNewSessionName("");
      setNewScenePrompt("");
      await fetchSessions();
      await fetchSession(data.session_id);
    } catch (e) {
      toast.error("Failed to create session");
    } finally {
      setCreating(false);
    }
  };

  const handleOperation = async (operation) => {
    if (!activeLayer) { toast.error("Select a layer first"); return; }
    setOpSubmitting(true);
    try {
      let payload = {};
      if (operation === "apply-product") {
        payload = { product_id: opProductId, instructions: opInstructions };
      } else if (operation === "edit") {
        payload = { prompt: opPrompt };
        if (opMaskFile) payload.mask_asset_id = opMaskFile.name;
      } else if (operation === "model-swap") {
        payload = { identity_prompt: opModelPrompt };
      } else if (operation === "reframe") {
        payload = { aspect_ratio: opAspectRatio };
      } else if (operation === "upscale") {
        payload = { resolution: opUpscale };
      }

      await api.post(
        `/api/v1/editorial-sessions/${activeSession.session_id}/layers/${activeLayer.layer_id}/${operation}`,
        payload
      );
      toast.success("Operation queued!");
      await fetchSession(activeSession.session_id);
      setActiveOp(null);
    } catch (e) {
      toast.error(e.message || "Operation failed");
    } finally {
      setOpSubmitting(false);
    }
  };

  const handleCreateBrandModel = async () => {
    if (!newModelName.trim()) { toast.error("Please enter a model name"); return; }
    if (!fullBodyFile || !portraitFile) {
      toast.error("Please upload both full-body and portrait reference files");
      return;
    }
    setCreatingModel(true);
    try {
      const brandId = brands[0]?.id || "1";

      // 1. Upload Full Body Image as Asset
      const formData1 = new FormData();
      formData1.append("brand_id", brandId);
      formData1.append("name", `${newModelName}_full`);
      formData1.append("asset_type", "model_pose");
      formData1.append("file", fullBodyFile);
      const res1 = await api.post("/api/v1/assets", formData1);

      // 2. Upload Portrait Image as Asset
      const formData2 = new FormData();
      formData2.append("brand_id", brandId);
      formData2.append("name", `${newModelName}_portrait`);
      formData2.append("asset_type", "model_portrait");
      formData2.append("file", portraitFile);
      const res2 = await api.post("/api/v1/assets", formData2);

      // 3. Create Brand Model Entry
      await api.post("/api/v1/brand-models", {
        name: newModelName,
        gender: newModelGender,
        full_body_reference_asset_id: String(res1.id),
        portrait_reference_asset_id: String(res2.id),
        rights_confirmed: true
      });

      toast.success("Brand model created!");
      setNewModelName("");
      setFullBodyFile(null);
      setPortraitFile(null);
      fetchBrandModels();
    } catch (e) {
      toast.error("Failed to create brand model");
    } finally {
      setCreatingModel(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
      <div className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Layers className="w-6 h-6 text-purple-400" />
          <h1 className="text-xl font-bold">Fluid Studio</h1>
          <span className="text-xs bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded-full">Non-destructive</span>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setTab("editor")} className={`text-xs px-3 py-1.5 rounded-lg transition ${tab === "editor" ? "bg-purple-600 text-white" : "text-zinc-400 hover:text-white"}`}>Editor</button>
          <button onClick={() => setTab("models")} className={`text-xs px-3 py-1.5 rounded-lg transition ${tab === "models" ? "bg-purple-600 text-white" : "text-zinc-400 hover:text-white"}`}>Brand Models</button>
        </div>
      </div>

      {tab === "editor" ? (
        <div className="flex h-[calc(100vh-65px)]">
          {/* Left: Session List */}
          <div className="w-64 border-r border-zinc-800 flex flex-col">
            <div className="p-4 border-b border-zinc-800">
              <button onClick={() => setShowCreateForm(!showCreateForm)} className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 py-2 rounded-xl text-xs font-medium transition">
                <Plus className="w-3.5 h-3.5" /> New Session
              </button>
            </div>

            {/* Create Form */}
            {showCreateForm && (
              <div className="p-4 border-b border-zinc-800 space-y-3">
                <input type="text" value={newSessionName} onChange={(e) => setNewSessionName(e.target.value)} placeholder="Session name" className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white outline-none" />
                <textarea value={newScenePrompt} onChange={(e) => setNewScenePrompt(e.target.value)} placeholder="Scene prompt..." rows={2} className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white outline-none resize-none" />
                <div className="grid grid-cols-2 gap-2">
                  <select value={newAspectRatio} onChange={(e) => setNewAspectRatio(e.target.value)} className="bg-zinc-900 border border-zinc-700 rounded-lg px-2 py-1.5 text-xs text-white outline-none">
                    {ASPECT_RATIOS.map(r => <option key={r}>{r}</option>)}
                  </select>
                  <select value={newResolution} onChange={(e) => setNewResolution(e.target.value)} className="bg-zinc-900 border border-zinc-700 rounded-lg px-2 py-1.5 text-xs text-white outline-none">
                    {RESOLUTIONS.map(r => <option key={r}>{r}</option>)}
                  </select>
                </div>
                <div className="pt-2">
                  <TaxonomyResolverPreview
                    taxonomyIds={{
                      environment: "ENV-STU-0001",
                      camera: "CAM-LENS-50MM-001",
                    }}
                    workflowId="WF-FLUID-001"
                    generationMode="studio_quality"
                  />
                </div>
                <button onClick={handleCreateSession} disabled={creating} className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 py-1.5 rounded-lg text-xs font-medium transition">
                  {creating ? "Creating..." : "Create"}
                </button>
              </div>
            )}

            {/* Sessions List */}
            <div className="flex-1 overflow-y-auto p-2">
              {sessions.length === 0 ? (
                <p className="text-xs text-zinc-500 text-center py-8">No sessions yet</p>
              ) : (
                sessions.map(session => (
                  <div key={session.session_id} onClick={() => fetchSession(session.session_id)} className={`p-3 rounded-xl cursor-pointer mb-2 transition ${activeSession?.session_id === session.session_id ? "bg-purple-900/30 border border-purple-700" : "hover:bg-zinc-900 border border-transparent"}`}>
                    <p className="text-xs font-medium text-white truncate">{session.name}</p>
                    <p className="text-xs text-zinc-500">{new Date(session.created_at).toLocaleDateString()}</p>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Middle: Canvas */}
          <div className="flex-1 flex flex-col">
            {activeSession ? (
              <>
                <div className="flex-1 flex items-center justify-center bg-zinc-950 p-6">
                  {loading ? (
                    <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
                  ) : activeLayer?.image_url ? (
                    <img src={activeLayer.image_url} alt="Layer output" className="max-h-full max-w-full object-contain rounded-xl border border-zinc-800" />
                  ) : (
                    <div className="text-center">
                      <Layers className="w-16 h-16 text-zinc-700 mx-auto mb-3" />
                      <p className="text-zinc-500 text-sm">Select or generate a layer</p>
                    </div>
                  )}
                </div>

                {/* Operations Toolbar */}
                <div className="border-t border-zinc-800 p-4">
                  <div className="flex gap-2 justify-center flex-wrap">
                    {[
                      { op: "apply-product", icon: <Image className="w-3.5 h-3.5" />, label: "Apply Product" },
                      { op: "edit", icon: <Wand2 className="w-3.5 h-3.5" />, label: "Edit" },
                      { op: "model-swap", icon: <UserCheck className="w-3.5 h-3.5" />, label: "Model Swap" },
                      { op: "reframe", icon: <Crop className="w-3.5 h-3.5" />, label: "Reframe" },
                      { op: "upscale", icon: <ArrowUp className="w-3.5 h-3.5" />, label: "Upscale" },
                    ].map(({ op, icon, label }) => (
                      <button key={op} onClick={() => setActiveOp(activeOp === op ? null : op)} className={`flex items-center gap-1.5 text-xs px-3 py-2 rounded-xl transition ${activeOp === op ? "bg-purple-600 text-white" : "border border-zinc-700 hover:border-purple-500 text-zinc-300"}`}>
                        {icon} {label}
                      </button>
                    ))}
                  </div>

                  {/* Operation Panels */}
                  {activeOp && (
                    <div className="mt-4 bg-zinc-900 border border-zinc-700 rounded-xl p-4">
                      {activeOp === "apply-product" && (
                        <div className="space-y-3">
                          <input type="text" value={opProductId} onChange={(e) => setOpProductId(e.target.value)} placeholder="Product ID" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white outline-none" />
                          <textarea value={opInstructions} onChange={(e) => setOpInstructions(e.target.value)} placeholder="Placement instructions..." rows={2} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white outline-none resize-none" />
                        </div>
                      )}
                      {activeOp === "edit" && (
                        <div className="space-y-3">
                          <textarea value={opPrompt} onChange={(e) => setOpPrompt(e.target.value)} placeholder="Correction prompt..." rows={2} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white outline-none resize-none" />
                          <div>
                            <label className="text-xs text-zinc-400 mb-1 block">Mask (optional)</label>
                            <input type="file" accept="image/*" ref={maskInputRef} onChange={(e) => setOpMaskFile(e.target.files[0])} className="text-xs text-zinc-400" />
                          </div>
                        </div>
                      )}
                      {activeOp === "model-swap" && (
                        <textarea value={opModelPrompt} onChange={(e) => setOpModelPrompt(e.target.value)} placeholder="Model identity prompt..." rows={2} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white outline-none resize-none" />
                      )}
                      {activeOp === "reframe" && (
                        <div className="flex gap-2 flex-wrap">
                          {ASPECT_RATIOS.map(r => (
                            <button key={r} onClick={() => setOpAspectRatio(r)} className={`text-xs px-3 py-1.5 rounded-lg transition ${opAspectRatio === r ? "bg-purple-600 text-white" : "border border-zinc-700 text-zinc-300"}`}>{r}</button>
                          ))}
                        </div>
                      )}
                      {activeOp === "upscale" && (
                        <div className="flex gap-2">
                          {UPSCALE_RESOLUTIONS.map(r => (
                            <button key={r} onClick={() => setOpUpscale(r)} className={`text-xs px-3 py-1.5 rounded-lg transition ${opUpscale === r ? "bg-purple-600 text-white" : "border border-zinc-700 text-zinc-300"}`}>{r}</button>
                          ))}
                        </div>
                      )}
                      <button onClick={() => handleOperation(activeOp)} disabled={opSubmitting} className="mt-3 w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 py-2 rounded-xl text-xs font-medium transition flex items-center justify-center gap-2">
                        {opSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                        {opSubmitting ? "Processing..." : `Apply ${activeOp.replace("-", " ")}`}
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <Layers className="w-16 h-16 text-zinc-700 mx-auto mb-3" />
                  <p className="text-zinc-500">Select or create a session</p>
                </div>
              </div>
            )}
          </div>

          {/* Right: Layer History */}
          {activeSession && (
            <div className="w-64 border-l border-zinc-800 flex flex-col">
              <div className="p-4 border-b border-zinc-800">
                <h2 className="text-xs font-semibold text-zinc-300 uppercase">Layer History</h2>
              </div>
              <div className="flex-1 overflow-y-auto p-2">
                {activeSession.layers?.length === 0 ? (
                  <p className="text-xs text-zinc-500 text-center py-8">No layers yet</p>
                ) : (
                  activeSession.layers?.map((layer, idx) => (
                    <div key={layer.layer_id} onClick={() => setActiveLayer(layer)} className={`p-3 rounded-xl cursor-pointer mb-2 transition ${activeLayer?.layer_id === layer.layer_id ? "bg-purple-900/30 border border-purple-700" : "hover:bg-zinc-900 border border-transparent"}`}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-purple-400">#{idx + 1}</span>
                        <span className="text-xs font-medium text-white capitalize">{layer.operation?.replace("-", " ") || "Base"}</span>
                      </div>
                      {layer.image_url && <img src={layer.image_url} alt="" className="w-full h-20 object-cover rounded-lg border border-zinc-700" />}
                      {layer.prompt && <p className="text-xs text-zinc-500 mt-1 truncate">{layer.prompt}</p>}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Brand Models Tab */
        <div className="p-6 max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-white">Brand Models Registry</h2>
          </div>

          {/* Create Model Form */}
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 mb-6">
            <h3 className="text-sm font-semibold text-white mb-4">Add New Model</h3>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Model Name *</label>
                <input type="text" value={newModelName} onChange={(e) => setNewModelName(e.target.value)} placeholder="e.g. Maya" className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-white outline-none" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Gender</label>
                <select value={newModelGender} onChange={(e) => setNewModelGender(e.target.value)} className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-white outline-none">
                  <option value="Female">Female</option>
                  <option value="Male">Male</option>
                  <option value="Non-binary">Non-binary</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Full Body Reference</label>
                <input type="file" accept="image/*" onChange={(e) => setFullBodyFile(e.target.files[0])} className="text-xs text-zinc-400" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Portrait Reference</label>
                <input type="file" accept="image/*" onChange={(e) => setPortraitFile(e.target.files[0])} className="text-xs text-zinc-400" />
              </div>
            </div>
            <button onClick={handleCreateBrandModel} disabled={creatingModel} className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-6 py-2.5 rounded-xl text-sm font-medium transition">
              {creatingModel ? "Creating..." : "Add Brand Model"}
            </button>
          </div>

          {/* Models Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {brandModels.length === 0 ? (
              <div className="col-span-3 text-center py-12 text-zinc-500 text-sm border border-dashed border-zinc-800 rounded-2xl">
                No brand models yet. Add your first model above.
              </div>
            ) : (
              brandModels.map(model => (
                <div key={model.model_id} className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-4">
                  {model.full_body_url && <img src={model.full_body_url} alt={model.name} className="w-full h-40 object-cover rounded-xl border border-zinc-700 mb-3" />}
                  <h3 className="text-sm font-semibold text-white">{model.name}</h3>
                  <p className="text-xs text-zinc-500 capitalize">{model.gender}</p>
                  <span className="text-xs bg-emerald-900/40 text-emerald-400 px-2 py-0.5 rounded-full mt-2 inline-block">Active</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
