"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { taxonomyResolverApi } from "@/lib/taxonomyResolverApi";
import TaxonomyResolverPreview from "@/components/dashboard/TaxonomyResolverPreview";
import { Search, Filter, CheckCircle2, XCircle, Clock, ChevronDown, Loader2, Sparkles, Cpu, Layers, Sliders } from "lucide-react";
import toast from "react-hot-toast";

const TAXONOMY_TYPES = [
  { value: "lighting", label: "Lighting (Section 09)" },
  { value: "pose", label: "Pose & Gesture (Section 07)" },
  { value: "camera", label: "Camera (Section 08)" },
  { value: "hair", label: "Hair Identity (Section 05)" },
  { value: "skin", label: "Skin Texture (Section 04)" },
  { value: "garment", label: "Garment & Product (Section 10)" },
  { value: "fabric", label: "Fabric & Material (Section 11)" },
  { value: "environment", label: "Background & Space (Section 12)" },
];

const STATUS_CONFIG = {
  approved: { icon: <CheckCircle2 className="w-3.5 h-3.5" />, color: "text-emerald-400 bg-emerald-900/30 border-emerald-800" },
  pending: { icon: <Clock className="w-3.5 h-3.5" />, color: "text-amber-400 bg-amber-900/30 border-amber-800" },
  rejected: { icon: <XCircle className="w-3.5 h-3.5" />, color: "text-red-400 bg-red-900/30 border-red-800" },
  revision_required: { icon: <Clock className="w-3.5 h-3.5" />, color: "text-orange-400 bg-orange-900/30 border-orange-800" },
};

export default function TaxonomyAdminPage() {
  const [mainTab, setMainTab] = useState("registry"); // "registry" | "resolver" | "nodemaps"
  const [activeType, setActiveType] = useState("lighting");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [updatingId, setUpdatingId] = useState(null);

  // Resolver Simulation State
  const [simulatorTaxonomyIds, setSimulatorTaxonomyIds] = useState({
    lighting: "LGT-STU-0001",
    pose: "POS-CAT-0001",
    camera: "CAM-CAT-0001",
    skin: "SKIN-NAT-0001",
  });
  const [simulatorWorkflow, setSimulatorWorkflow] = useState("WF-CATALOG-001");
  const [simulatorMode, setSimulatorMode] = useState("studio_quality");

  // Node Maps State
  const [nodeMaps, setNodeMaps] = useState([]);
  const [loadingNodes, setLoadingNodes] = useState(false);

  useEffect(() => {
    if (mainTab === "registry") {
      fetchTaxonomy();
    } else if (mainTab === "nodemaps") {
      fetchNodeMaps();
    }
  }, [mainTab, activeType]);

  const fetchTaxonomy = async () => {
    setLoading(true);
    try {
      const data = await api.get(`/api/v1/taxonomy/${activeType}`);
      setItems(data?.items || data || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchNodeMaps = async () => {
    setLoadingNodes(true);
    try {
      const data = await taxonomyResolverApi.getWorkflowNodeMaps(simulatorWorkflow);
      setNodeMaps(data?.node_mappings || []);
    } catch {
      setNodeMaps([]);
    } finally {
      setLoadingNodes(false);
    }
  };

  const updateApprovalStatus = async (itemId, newStatus) => {
    setUpdatingId(itemId);
    try {
      await api.patch(`/api/v1/taxonomy/${activeType}/${itemId}`, { approval_status: newStatus });
      toast.success(`Status updated to ${newStatus}`);
      fetchTaxonomy();
    } catch {
      toast.error("Failed to update status");
    } finally {
      setUpdatingId(null);
    }
  };

  const filtered = items.filter((item) => {
    const matchSearch =
      !search ||
      item.name?.toLowerCase().includes(search.toLowerCase()) ||
      item.taxonomy_id?.toLowerCase().includes(search.toLowerCase());
    const matchStatus = !statusFilter || item.approval_status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Top Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
              Taxonomy & Resolver Admin
              <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800">
                v1.0 Registry
              </span>
            </h1>
            <p className="text-zinc-400 text-sm mt-1">
              Authoritative taxonomy vocabulary, execution resolver simulation & ComfyUI node mappings
            </p>
          </div>
        </div>

        {/* Main Navigation Tabs */}
        <div className="flex gap-2 border-b border-zinc-800 pb-3">
          <button
            onClick={() => setMainTab("registry")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
              mainTab === "registry"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
                : "bg-zinc-900 text-zinc-400 hover:text-white"
            }`}
          >
            <Layers className="w-4 h-4" />
            Taxonomy Registry
          </button>
          <button
            onClick={() => setMainTab("resolver")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
              mainTab === "resolver"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
                : "bg-zinc-900 text-zinc-400 hover:text-white"
            }`}
          >
            <Sparkles className="w-4 h-4" />
            Resolver Simulator (Dry-Run)
          </button>
          <button
            onClick={() => setMainTab("nodemaps")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
              mainTab === "nodemaps"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
                : "bg-zinc-900 text-zinc-400 hover:text-white"
            }`}
          >
            <Cpu className="w-4 h-4" />
            ComfyUI Node Maps
          </button>
        </div>

        {/* Tab 1: Taxonomy Registry */}
        {mainTab === "registry" && (
          <div className="space-y-6">
            {/* Type Tabs */}
            <div className="flex gap-2 flex-wrap">
              {TAXONOMY_TYPES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setActiveType(t.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    activeType === t.value
                      ? "bg-zinc-800 text-white border border-zinc-700 shadow"
                      : "bg-zinc-950 text-zinc-400 hover:text-zinc-200 border border-zinc-900"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Filters */}
            <div className="flex gap-3">
              <div className="relative flex-1">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-zinc-500" />
                <input
                  type="text"
                  placeholder="Search by name or taxonomy ID..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-sm text-zinc-300 focus:outline-none focus:border-indigo-500"
              >
                <option value="">All Statuses</option>
                <option value="approved">Approved</option>
                <option value="pending">Pending</option>
                <option value="revision_required">Revision Required</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>

            {/* Table */}
            <div className="bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-16 text-zinc-500 space-y-2">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
                  <p className="text-xs">Loading taxonomy items...</p>
                </div>
              ) : filtered.length === 0 ? (
                <div className="text-center py-16 text-zinc-500 text-sm">
                  No taxonomy entries found.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-800 text-zinc-400 text-xs font-mono uppercase bg-zinc-900/40">
                      <th className="text-left py-3 px-4">Taxonomy ID</th>
                      <th className="text-left py-3 px-4">Name</th>
                      <th className="text-left py-3 px-4">Family / Subcategory</th>
                      <th className="text-left py-3 px-4">Approval Status</th>
                      <th className="text-right py-3 px-4">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60">
                    {filtered.map((item) => {
                      const cfg = STATUS_CONFIG[item.approval_status] || STATUS_CONFIG.pending;
                      return (
                        <tr key={item.id || item.taxonomy_id} className="hover:bg-zinc-900/50 transition">
                          <td className="py-3 px-4 font-mono text-xs text-indigo-300 font-bold">
                            {item.taxonomy_id}
                          </td>
                          <td className="py-3 px-4 font-medium text-white">
                            {item.display_name || item.name}
                          </td>
                          <td className="py-3 px-4 text-zinc-400 text-xs font-mono">
                            {item.family || item.subcategory || "—"}
                          </td>
                          <td className="py-3 px-4">
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${cfg.color}`}>
                              {cfg.icon}
                              <span className="capitalize">{item.approval_status?.replace("_", " ") || "Pending"}</span>
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              {item.approval_status !== "approved" && (
                                <button
                                  onClick={() => updateApprovalStatus(item.id, "approved")}
                                  disabled={updatingId === item.id}
                                  className="px-2.5 py-1 rounded-lg bg-emerald-950/80 border border-emerald-800 text-emerald-300 hover:bg-emerald-900 text-xs font-medium transition"
                                >
                                  Approve
                                </button>
                              )}
                              {item.approval_status !== "rejected" && (
                                <button
                                  onClick={() => updateApprovalStatus(item.id, "rejected")}
                                  disabled={updatingId === item.id}
                                  className="px-2.5 py-1 rounded-lg bg-red-950/80 border border-red-800 text-red-300 hover:bg-red-900 text-xs font-medium transition"
                                >
                                  Reject
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Resolver Simulator */}
        {mainTab === "resolver" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-6 rounded-2xl bg-zinc-950 border border-zinc-800 space-y-4">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <Sliders className="w-4 h-4 text-indigo-400" />
                Configure Intent Inputs
              </h3>
              <p className="text-xs text-zinc-400">
                Select taxonomy IDs to test the Resolver logic and preview parameters before execution.
              </p>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="text-[11px] text-zinc-400 block mb-1 font-medium">Target Workflow</label>
                  <select
                    value={simulatorWorkflow}
                    onChange={(e) => setSimulatorWorkflow(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-white focus:border-indigo-500 outline-none"
                  >
                    <option value="WF-CATALOG-001">WF-CATALOG-001 (Catalog Studio)</option>
                    <option value="WF-GHOST-001">WF-GHOST-001 (Ghost Studio)</option>
                    <option value="WF-SKETCH-001">WF-SKETCH-001 (Sketch Studio)</option>
                    <option value="WF-MOVE-001">WF-MOVE-001 (Move Studio)</option>
                  </select>
                </div>

                <div>
                  <label className="text-[11px] text-zinc-400 block mb-1 font-medium">Generation Mode</label>
                  <select
                    value={simulatorMode}
                    onChange={(e) => setSimulatorMode(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-white focus:border-indigo-500 outline-none"
                  >
                    <option value="studio_quality">Studio Quality (45s, Multi-Pass QA, 5 Credits)</option>
                    <option value="fast_draft">Fast Draft (15s, Rapid Preview, 2 Credits)</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2">
                  <div>
                    <label className="text-[11px] text-zinc-400 block mb-1">Lighting Taxonomy ID</label>
                    <input
                      type="text"
                      value={simulatorTaxonomyIds.lighting || ""}
                      onChange={(e) => setSimulatorTaxonomyIds({ ...simulatorTaxonomyIds, lighting: e.target.value })}
                      placeholder="LGT-STU-0001"
                      className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-800 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-zinc-400 block mb-1">Pose Taxonomy ID</label>
                    <input
                      type="text"
                      value={simulatorTaxonomyIds.pose || ""}
                      onChange={(e) => setSimulatorTaxonomyIds({ ...simulatorTaxonomyIds, pose: e.target.value })}
                      placeholder="POS-CAT-0001"
                      className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-800 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-zinc-400 block mb-1">Camera Taxonomy ID</label>
                    <input
                      type="text"
                      value={simulatorTaxonomyIds.camera || ""}
                      onChange={(e) => setSimulatorTaxonomyIds({ ...simulatorTaxonomyIds, camera: e.target.value })}
                      placeholder="CAM-CAT-0001"
                      className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-800 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-zinc-400 block mb-1">Skin Taxonomy ID</label>
                    <input
                      type="text"
                      value={simulatorTaxonomyIds.skin || ""}
                      onChange={(e) => setSimulatorTaxonomyIds({ ...simulatorTaxonomyIds, skin: e.target.value })}
                      placeholder="SKIN-NAT-0001"
                      className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-800 text-white font-mono"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Live Resolver Widget */}
            <div>
              <TaxonomyResolverPreview
                taxonomyIds={simulatorTaxonomyIds}
                workflowId={simulatorWorkflow}
                generationMode={simulatorMode}
              />
            </div>
          </div>
        )}

        {/* Tab 3: ComfyUI Node Maps */}
        {mainTab === "nodemaps" && (
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-white">ComfyUI Node Mappings</h3>
                <p className="text-xs text-zinc-400">
                  Decoupled mapping between canonical taxonomy IDs and internal ComfyUI execution graph nodes
                </p>
              </div>
              <select
                value={simulatorWorkflow}
                onChange={(e) => setSimulatorWorkflow(e.target.value)}
                className="px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-white"
              >
                <option value="WF-CATALOG-001">WF-CATALOG-001</option>
                <option value="WF-GHOST-001">WF-GHOST-001</option>
                <option value="WF-MOVE-001">WF-MOVE-001</option>
              </select>
            </div>

            {loadingNodes ? (
              <div className="flex flex-col items-center justify-center py-12 text-zinc-500 space-y-2">
                <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
                <p className="text-xs">Loading workflow node maps...</p>
              </div>
            ) : nodeMaps.length === 0 ? (
              <div className="text-center py-12 rounded-xl border border-dashed border-zinc-800 text-zinc-500 text-xs italic">
                No active node mappings registered for workflow {simulatorWorkflow}.
              </div>
            ) : (
              <div className="space-y-2 font-mono text-xs">
                {nodeMaps.map((nm, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-zinc-900/60 border border-zinc-800">
                    <div className="flex items-center gap-3">
                      <span className="px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 font-bold">
                        Node {nm.node_id}
                      </span>
                      <span className="text-zinc-300 font-semibold">{nm.field_name}</span>
                    </div>
                    <span className="text-zinc-400">{nm.taxonomy_id}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
