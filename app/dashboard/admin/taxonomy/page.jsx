"use client";
import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Search, Filter, CheckCircle2, XCircle, Clock, ChevronDown, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

const TAXONOMY_TYPES = [
  { value: "lighting", label: "Lighting" },
  { value: "pose", label: "Pose" },
  { value: "camera", label: "Camera" },
  { value: "hair", label: "Hair" },
  { value: "skin", label: "Skin" },
];

const STATUS_CONFIG = {
  approved: { icon: <CheckCircle2 className="w-3.5 h-3.5" />, color: "text-emerald-400 bg-emerald-900/30 border-emerald-800" },
  pending: { icon: <Clock className="w-3.5 h-3.5" />, color: "text-amber-400 bg-amber-900/30 border-amber-800" },
  rejected: { icon: <XCircle className="w-3.5 h-3.5" />, color: "text-red-400 bg-red-900/30 border-red-800" },
  revision_required: { icon: <Clock className="w-3.5 h-3.5" />, color: "text-orange-400 bg-orange-900/30 border-orange-800" },
};

export default function TaxonomyAdminPage() {
  const [activeType, setActiveType] = useState("lighting");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [updatingId, setUpdatingId] = useState(null);

  useEffect(() => {
    fetchTaxonomy();
  }, [activeType]);

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

  const filtered = items.filter(item => {
    const matchSearch = !search || 
      item.name?.toLowerCase().includes(search.toLowerCase()) ||
      item.taxonomy_id?.toLowerCase().includes(search.toLowerCase());
    const matchStatus = !statusFilter || item.approval_status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Taxonomy Admin</h1>
          <p className="text-zinc-400 text-sm mt-1">Manage Mode Lens production taxonomy registry</p>
        </div>

        {/* Type Tabs */}
        <div className="flex gap-2 mb-6 flex-wrap">
          {TAXONOMY_TYPES.map(t => (
            <button
              key={t.value}
              onClick={() => setActiveType(t.value)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition ${activeType === t.value ? "bg-purple-600 text-white" : "border border-zinc-700 text-zinc-400 hover:text-white"}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Search & Filter */}
        <div className="flex gap-3 mb-4 flex-wrap">
          <div className="flex-1 flex items-center gap-2 bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 min-w-48">
            <Search className="w-4 h-4 text-zinc-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or ID..."
              className="flex-1 bg-transparent text-sm text-zinc-200 outline-none placeholder-zinc-600"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-200 outline-none"
          >
            <option value="">All Status</option>
            <option value="approved">Approved</option>
            <option value="pending">Pending</option>
            <option value="revision_required">Revision Required</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        {/* Table */}
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl overflow-hidden">
          <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-zinc-800 bg-zinc-900/60">
            <div className="col-span-2 text-xs font-semibold text-zinc-400 uppercase">ID</div>
            <div className="col-span-3 text-xs font-semibold text-zinc-400 uppercase">Name</div>
            <div className="col-span-2 text-xs font-semibold text-zinc-400 uppercase">Family</div>
            <div className="col-span-2 text-xs font-semibold text-zinc-400 uppercase">Status</div>
            <div className="col-span-3 text-xs font-semibold text-zinc-400 uppercase">Actions</div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-purple-400" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-sm">No taxonomy items found</div>
          ) : (
            <div className="divide-y divide-zinc-800/50">
              {filtered.map(item => {
                const statusCfg = STATUS_CONFIG[item.approval_status] || STATUS_CONFIG.pending;
                return (
                  <div key={item.id} className="grid grid-cols-12 gap-2 px-4 py-3 hover:bg-zinc-800/30 transition items-center">
                    <div className="col-span-2">
                      <span className="text-xs font-mono text-purple-400">{item.taxonomy_id}</span>
                    </div>
                    <div className="col-span-3">
                      <p className="text-xs font-medium text-zinc-200">{item.name}</p>
                      {item.version && <p className="text-xs text-zinc-500">v{item.version}</p>}
                    </div>
                    <div className="col-span-2">
                      <span className="text-xs text-zinc-400 capitalize">{item.family}</span>
                    </div>
                    <div className="col-span-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full border flex items-center gap-1 w-fit ${statusCfg.color}`}>
                        {statusCfg.icon}
                        {item.approval_status}
                      </span>
                    </div>
                    <div className="col-span-3 flex gap-2">
                      {item.approval_status !== "approved" && (
                        <button
                          onClick={() => updateApprovalStatus(item.id, "approved")}
                          disabled={updatingId === item.id}
                          className="text-xs bg-emerald-900/30 hover:bg-emerald-900/50 border border-emerald-800 text-emerald-400 px-2 py-1 rounded-lg transition disabled:opacity-50"
                        >
                          Approve
                        </button>
                      )}
                      {item.approval_status !== "revision_required" && (
                        <button
                          onClick={() => updateApprovalStatus(item.id, "revision_required")}
                          disabled={updatingId === item.id}
                          className="text-xs bg-amber-900/30 hover:bg-amber-900/50 border border-amber-800 text-amber-400 px-2 py-1 rounded-lg transition disabled:opacity-50"
                        >
                          Revise
                        </button>
                      )}
                      {item.approval_status !== "rejected" && (
                        <button
                          onClick={() => updateApprovalStatus(item.id, "rejected")}
                          disabled={updatingId === item.id}
                          className="text-xs bg-red-900/30 hover:bg-red-900/50 border border-red-800 text-red-400 px-2 py-1 rounded-lg transition disabled:opacity-50"
                        >
                          Reject
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
