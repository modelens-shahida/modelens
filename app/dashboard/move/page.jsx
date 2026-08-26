"use client";
import React, { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { Film, Plus, Loader2, Play, Download, Clock, CheckCircle2, XCircle, Video, Music, Image } from "lucide-react";
import toast from "react-hot-toast";
import TaxonomyResolverPreview from "@/components/dashboard/TaxonomyResolverPreview";

const ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:5", "3:4"];
const MOTION_PRESETS = ["SUBTLE_FASHION", "RUNWAY_WALK", "ORBIT", "PUSH_IN", "PAN", "HANDHELD"];
const RESOLUTIONS = ["720p", "1080p"];

const STATUS_COLORS = {
  queued: "text-amber-400 bg-amber-900/30 border-amber-700",
  generating: "text-blue-400 bg-blue-900/30 border-blue-700",
  completed: "text-emerald-400 bg-emerald-900/30 border-emerald-700",
  failed: "text-red-400 bg-red-900/30 border-red-700",
  processing: "text-purple-400 bg-purple-900/30 border-purple-700",
  ready_to_render: "text-indigo-400 bg-indigo-900/30 border-indigo-700",
};

export default function MoveStudioPage() {
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [activeClip, setActiveClip] = useState(null);
  const [loading, setLoading] = useState(false);

  // Create project modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newMasterPrompt, setNewMasterPrompt] = useState("");
  const [newAspectRatio, setNewAspectRatio] = useState("16:9");
  const [creating, setCreating] = useState(false);

  // Storyboard form
  const [showStoryboard, setShowStoryboard] = useState(false);
  const [sbPrompt, setSbPrompt] = useState("");
  const [sbNumClips, setSbNumClips] = useState(3);
  const [sbMotionPreset, setSbMotionPreset] = useState("SUBTLE_FASHION");
  const [sbDuration, setSbDuration] = useState(4);
  const [generatingStoryboard, setGeneratingStoryboard] = useState(false);

  // Render panel
  const [renderResolution, setRenderResolution] = useState("1080p");
  const [renderAudioUrl, setRenderAudioUrl] = useState("");
  const [renderLogoUrl, setRenderLogoUrl] = useState("");
  const [rendering, setRendering] = useState(false);
  const [activeRender, setActiveRender] = useState(null);

  // Clip generation
  const [generatingClip, setGeneratingClip] = useState(null);

  const pollRef = useRef(null);

  useEffect(() => {
    api.get("/api/v1/brands").then(data => {
      setBrands(data || []);
      if (data?.length > 0) setSelectedBrandId(data[0].id.toString());
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedBrandId) fetchProjects();
  }, [selectedBrandId]);

  const fetchProjects = async () => {
    try {
      const data = await api.get(`/api/v1/video-projects?brand_id=${selectedBrandId}`);
      setProjects(data?.projects || data || []);
    } catch {}
  };

  const fetchProject = async (projectId) => {
    setLoading(true);
    try {
      const data = await api.get(`/api/v1/video-projects/${projectId}`);
      setActiveProject(data);
      if (data.renders?.length > 0) setActiveRender(data.renders[0]);
    } catch {
      toast.error("Failed to load project");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) { toast.error("Enter a project name"); return; }
    setCreating(true);
    try {
      const data = await api.post("/api/v1/video-projects", {
        brand_id: parseInt(selectedBrandId),
        name: newProjectName,
        master_prompt: newMasterPrompt,
        aspect_ratio: newAspectRatio,
      });
      toast.success("Project created!");
      setShowCreateModal(false);
      setNewProjectName("");
      setNewMasterPrompt("");
      await fetchProjects();
      await fetchProject(data.project_id || data.id);
    } catch {
      toast.error("Failed to create project");
    } finally {
      setCreating(false);
    }
  };

  const handleCreateStoryboard = async () => {
    if (!activeProject) return;
    setGeneratingStoryboard(true);
    try {
      await api.post(`/api/v1/video-projects/${activeProject.project_id}/storyboard`, {
        master_prompt: sbPrompt || activeProject.master_prompt,
        motion_preset: sbMotionPreset,
        duration: sbDuration,
        num_clips: sbNumClips,
      });
      toast.success(`${sbNumClips} storyboard clips created!`);
      setShowStoryboard(false);
      await fetchProject(activeProject.project_id);
    } catch {
      toast.error("Failed to create storyboard");
    } finally {
      setGeneratingStoryboard(false);
    }
  };

  const handleGenerateClip = async (clipId) => {
    if (!activeProject) return;
    setGeneratingClip(clipId);
    try {
      await api.post(`/api/v1/video-projects/${activeProject.project_id}/generate`, { provider: "AUTO" });
      toast.success("Generation started!");
      setTimeout(() => fetchProject(activeProject.project_id), 2000);
    } catch {
      toast.error("Failed to start generation");
    } finally {
      setGeneratingClip(null);
    }
  };

  const handleRender = async () => {
    if (!activeProject) return;
    setRendering(true);
    try {
      const data = await api.post(`/api/v1/video-projects/${activeProject.project_id}/render`, {
        resolution: renderResolution,
        audio_url: renderAudioUrl || null,
        logo_url: renderLogoUrl || null,
      });
      toast.success("Render started!");
      setActiveRender({ id: data.render_id, status: "queued" });
      startRenderPolling(data.render_id);
    } catch {
      toast.error("Failed to start render");
    } finally {
      setRendering(false);
    }
  };

  const startRenderPolling = (renderId) => {
    pollRef.current = setInterval(async () => {
      try {
        const data = await api.get(`/api/v1/video-projects/${activeProject.project_id}`);
        const render = data.renders?.find(r => r.id === renderId);
        if (render) {
          setActiveRender(render);
          if (render.status === "completed" || render.status === "failed") {
            clearInterval(pollRef.current);
            if (render.status === "completed") toast.success("Render complete!");
          }
        }
      } catch {}
    }, 3000);
  };

  useEffect(() => () => clearInterval(pollRef.current), []);

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
      <div className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Film className="w-6 h-6 text-purple-400" />
          <h1 className="text-xl font-bold">Move Studio</h1>
          <span className="text-xs bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded-full">AI Video</span>
        </div>
        <select value={selectedBrandId} onChange={(e) => setSelectedBrandId(e.target.value)} className="bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-200 outline-none">
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      <div className="flex h-[calc(100vh-65px)]">
        {/* Left: Project Browser */}
        <div className="w-64 border-r border-zinc-800 flex flex-col">
          <div className="p-4 border-b border-zinc-800">
            <button onClick={() => setShowCreateModal(true)} className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 py-2 rounded-xl text-xs font-medium transition">
              <Plus className="w-3.5 h-3.5" /> New Project
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {projects.length === 0 ? (
              <p className="text-xs text-zinc-500 text-center py-8">No projects yet</p>
            ) : (
              projects.map(p => (
                <div key={p.project_id || p.id} onClick={() => fetchProject(p.project_id || p.id)} className={`p-3 rounded-xl cursor-pointer mb-2 transition ${activeProject?.project_id === (p.project_id || p.id) ? "bg-purple-900/30 border border-purple-700" : "hover:bg-zinc-900 border border-transparent"}`}>
                  <p className="text-xs font-medium text-white truncate">{p.name}</p>
                  <p className="text-xs text-zinc-500">{p.aspect_ratio}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full border mt-1 inline-block ${STATUS_COLORS[p.status] || STATUS_COLORS.queued}`}>{p.status}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Center: Timeline */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {activeProject ? (
            <>
              <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-white">{activeProject.name}</h2>
                  <p className="text-xs text-zinc-500">{activeProject.master_prompt}</p>
                </div>
                <button onClick={() => setShowStoryboard(!showStoryboard)} className="flex items-center gap-2 text-xs border border-zinc-700 hover:border-purple-500 px-3 py-2 rounded-xl transition">
                  <Film className="w-3.5 h-3.5" /> Create Storyboard
                </button>
              </div>

              {/* Storyboard Form */}
              {showStoryboard && (
                <div className="p-4 border-b border-zinc-800 bg-zinc-900/50">
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <textarea value={sbPrompt} onChange={(e) => setSbPrompt(e.target.value)} placeholder="Scene prompt (or use master prompt)..." rows={2} className="col-span-2 bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white outline-none resize-none" />
                    <div>
                      <label className="text-xs text-zinc-400 mb-1 block">Clips: {sbNumClips}</label>
                      <input type="range" min="1" max="5" value={sbNumClips} onChange={(e) => setSbNumClips(parseInt(e.target.value))} className="w-full accent-purple-500" />
                    </div>
                    <div>
                      <label className="text-xs text-zinc-400 mb-1 block">Duration: {sbDuration}s</label>
                      <input type="range" min="2" max="10" value={sbDuration} onChange={(e) => setSbDuration(parseInt(e.target.value))} className="w-full accent-purple-500" />
                    </div>
                    <select value={sbMotionPreset} onChange={(e) => setSbMotionPreset(e.target.value)} className="bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white outline-none">
                      {MOTION_PRESETS.map(m => <option key={m}>{m}</option>)}
                    </select>
                  </div>

                  {/* Move Studio Live Resolver Preview */}
                  <div className="mb-3">
                    <TaxonomyResolverPreview
                      taxonomyIds={{
                        pose: `MOT-${sbMotionPreset}-001`,
                        camera: "CAM-MOV-DOLLY-001",
                        environment: "ENV-STU-0001",
                      }}
                      workflowId="WF-MOVE-001"
                      generationMode="studio_quality"
                    />
                  </div>

                  <button onClick={handleCreateStoryboard} disabled={generatingStoryboard} className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-4 py-2 rounded-xl text-xs font-medium transition">
                    {generatingStoryboard ? "Creating..." : `Generate ${sbNumClips} Clips`}
                  </button>
                </div>
              )}

              {/* Clips Timeline */}
              <div className="flex-1 overflow-y-auto p-4">
                {loading ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
                  </div>
                ) : activeProject.clips?.length === 0 ? (
                  <div className="text-center py-16 text-zinc-500">
                    <Film className="w-12 h-12 mx-auto mb-3 text-zinc-700" />
                    <p className="text-sm">No clips yet. Create a storyboard to get started.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {activeProject.clips?.map((clip, idx) => (
                      <div key={clip.id} onClick={() => setActiveClip(activeClip?.id === clip.id ? null : clip)} className={`border rounded-2xl p-4 cursor-pointer transition ${activeClip?.id === clip.id ? "border-purple-600 bg-purple-950/20" : "border-zinc-800 hover:border-zinc-700 bg-zinc-900/40"}`}>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-zinc-500">#{idx + 1}</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_COLORS[clip.status] || STATUS_COLORS.queued}`}>{clip.status}</span>
                            <span className="text-xs text-zinc-400">{clip.motion_preset}</span>
                            <span className="text-xs text-zinc-500">{clip.duration}s</span>
                          </div>
                          {clip.status === "queued" && (
                            <button onClick={(e) => { e.stopPropagation(); handleGenerateClip(clip.id); }} disabled={generatingClip === clip.id} className="text-xs bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-3 py-1.5 rounded-lg transition flex items-center gap-1">
                              {generatingClip === clip.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                              Generate
                            </button>
                          )}
                        </div>
                        {clip.prompt && <p className="text-xs text-zinc-400 truncate">{clip.prompt}</p>}
                        {clip.clip_url && (
                          <video src={clip.clip_url} className="w-full h-32 object-cover rounded-xl mt-2 border border-zinc-700" controls />
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Generate All Button */}
              <div className="p-4 border-t border-zinc-800">
                <button onClick={() => handleGenerateClip(null)} disabled={!activeProject.clips?.some(c => c.status === "queued")} className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 py-2.5 rounded-xl text-sm font-medium transition flex items-center justify-center gap-2">
                  <Play className="w-4 h-4" /> Generate All Clips
                </button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <Film className="w-16 h-16 text-zinc-700 mx-auto mb-3" />
                <p className="text-zinc-500">Select or create a project</p>
              </div>
            </div>
          )}
        </div>

        {/* Right: Render Panel */}
        {activeProject && (
          <div className="w-72 border-l border-zinc-800 flex flex-col">
            <div className="p-4 border-b border-zinc-800">
              <h2 className="text-xs font-semibold text-zinc-300 uppercase mb-4">Render Settings</h2>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-zinc-400 mb-1 block">Resolution</label>
                  <div className="flex gap-2">
                    {RESOLUTIONS.map(r => (
                      <button key={r} onClick={() => setRenderResolution(r)} className={`flex-1 text-xs py-2 rounded-xl transition ${renderResolution === r ? "bg-purple-600 text-white" : "border border-zinc-700 text-zinc-300"}`}>{r}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs text-zinc-400 mb-1 block flex items-center gap-1"><Music className="w-3 h-3" /> Audio URL</label>
                  <input type="text" value={renderAudioUrl} onChange={(e) => setRenderAudioUrl(e.target.value)} placeholder="https://..." className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white outline-none" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 mb-1 block flex items-center gap-1"><Image className="w-3 h-3" /> Logo/Watermark URL</label>
                  <input type="text" value={renderLogoUrl} onChange={(e) => setRenderLogoUrl(e.target.value)} placeholder="https://..." className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white outline-none" />
                </div>
                <button onClick={handleRender} disabled={rendering || !activeProject.clips?.some(c => c.status === "completed")} className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 py-2.5 rounded-xl text-xs font-medium transition flex items-center justify-center gap-2">
                  {rendering ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Video className="w-3.5 h-3.5" />}
                  {rendering ? "Rendering..." : "Render Video"}
                </button>
              </div>
            </div>

            {/* Render Status & Preview */}
            <div className="flex-1 overflow-y-auto p-4">
              {activeRender ? (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_COLORS[activeRender.status] || STATUS_COLORS.queued}`}>{activeRender.status}</span>
                    {activeRender.status === "queued" || activeRender.status === "processing" ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
                    ) : null}
                  </div>
                  {activeRender.status === "completed" && activeRender.output_url ? (
                    <div>
                      <video src={activeRender.output_url} controls className="w-full rounded-xl border border-zinc-700 mb-3" />
                      <a href={activeRender.output_url} download className="flex items-center justify-center gap-2 text-xs bg-zinc-800 hover:bg-zinc-700 py-2 rounded-xl transition">
                        <Download className="w-3.5 h-3.5" /> Download MP4
                      </a>
                    </div>
                  ) : activeRender.status === "completed" ? (
                    <div className="text-center py-6">
                      <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
                      <p className="text-xs text-emerald-400">Render complete!</p>
                    </div>
                  ) : activeRender.status === "failed" ? (
                    <div className="text-center py-6">
                      <XCircle className="w-10 h-10 text-red-400 mx-auto mb-2" />
                      <p className="text-xs text-red-400">Render failed</p>
                    </div>
                  ) : (
                    <div className="text-center py-6">
                      <Clock className="w-10 h-10 text-amber-400 mx-auto mb-2 animate-pulse" />
                      <p className="text-xs text-zinc-400">Rendering in progress...</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-zinc-600">
                  <Video className="w-10 h-10 mx-auto mb-2" />
                  <p className="text-xs">No renders yet</p>
                </div>
              )}

              {/* Previous Renders */}
              {activeProject.renders?.length > 0 && (
                <div className="mt-4">
                  <h3 className="text-xs font-semibold text-zinc-400 mb-2">Previous Renders</h3>
                  {activeProject.renders.map(r => (
                    <div key={r.id} onClick={() => setActiveRender(r)} className="flex items-center justify-between p-2 rounded-xl hover:bg-zinc-900 cursor-pointer mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_COLORS[r.status] || STATUS_COLORS.queued}`}>{r.status}</span>
                      <span className="text-xs text-zinc-500">{r.duration_seconds ? `${r.duration_seconds}s` : ""}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold text-white mb-4">New Video Project</h2>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Project Name *</label>
                <input type="text" value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)} placeholder="e.g. Summer Collection Campaign" className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-white outline-none" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Master Prompt</label>
                <textarea value={newMasterPrompt} onChange={(e) => setNewMasterPrompt(e.target.value)} placeholder="Overall scene description..." rows={3} className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-white outline-none resize-none" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Aspect Ratio</label>
                <div className="flex gap-2 flex-wrap">
                  {ASPECT_RATIOS.map(r => (
                    <button key={r} onClick={() => setNewAspectRatio(r)} className={`text-xs px-3 py-1.5 rounded-lg transition ${newAspectRatio === r ? "bg-purple-600 text-white" : "border border-zinc-700 text-zinc-300"}`}>{r}</button>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={handleCreateProject} disabled={creating} className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 py-2.5 rounded-xl text-sm font-medium transition">
                {creating ? "Creating..." : "Create Project"}
              </button>
              <button onClick={() => setShowCreateModal(false)} className="flex-1 border border-zinc-700 py-2.5 rounded-xl text-sm text-zinc-300 hover:text-white transition">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
