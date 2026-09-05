"use client";
import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Plus, Loader2, CheckCircle2, Clock, XCircle, AlertCircle, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import toast from "react-hot-toast";
import QADiagnosticCard from "@/components/dashboard/QADiagnosticCard";
import CanvasRetouchModal from "@/components/dashboard/CanvasRetouchModal";
import QADiagnosticInspector from "@/components/dashboard/QADiagnosticInspector";

const STATUS_CONFIG = {
  pending: { label: "Pending", color: "bg-amber-900/40 text-amber-400 border-amber-700", icon: Clock },
  in_progress: { label: "In Progress", color: "bg-blue-900/40 text-blue-400 border-blue-700", icon: RefreshCw },
  completed: { label: "Completed", color: "bg-emerald-900/40 text-emerald-400 border-emerald-700", icon: CheckCircle2 },
  rejected: { label: "Rejected", color: "bg-red-900/40 text-red-400 border-red-700", icon: XCircle },
};

const STATUS_TABS = ["all", "pending", "in_progress", "completed", "rejected"];

export default function FixRequestsPage() {
  const { user } = useAuth();
  const [brands, setBrands] = useState([]);
  const [selectedBrand, setSelectedBrand] = useState("");
  const [requests, setRequests] = useState([]);
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("all");
  const [activeMainTab, setActiveMainTab] = useState("inspector");
  const [userRole, setUserRole] = useState("viewer");

  // New Request Modal
  const [showNewModal, setShowNewModal] = useState(false);
  const [newForm, setNewForm] = useState({ original_asset_id: "", requester_notes: "" });
  const [submitting, setSubmitting] = useState(false);

  // Review Modal
  const [reviewRequest, setReviewRequest] = useState(null);
  const [reviewForm, setReviewForm] = useState({ status: "", reviewer_notes: "", updated_asset_id: "" });
  const [reviewing, setReviewing] = useState(false);
  const [showRetouchModal, setShowRetouchModal] = useState(false);

  const fetchRequests = async () => {
    setLoading(true);
    try {
      const data = await api.get(`/api/v1/fix-requests?brand_id=${selectedBrand}&limit=50`);
      setRequests(data?.requests || data || []);
    } catch {
      toast.error("Failed to load fix requests");
    } finally {
      setLoading(false);
    }
  };
  const fetchAssets = async () => {
    try {
      const data = await api.get(`/api/v1/assets?brand_id=${selectedBrand}&limit=100`);
      setAssets(data || []);
    } catch {}
  };
  const fetchUserRole = async () => {
    try {
      const members = await api.get(`/api/v1/brands/${selectedBrand}/members`);
      const me = members.find(m => m.user_id === user?.id);
      setUserRole(me?.role || "viewer");
    } catch {}
  };

  useEffect(() => {
    api.get("/api/v1/brands").then(data => {
      setBrands(data || []);
      if (data?.length > 0) setSelectedBrand(data[0].id.toString());
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedBrand) return;
    fetchRequests();
    fetchAssets();
    fetchUserRole();
  }, [selectedBrand]);




  const handleSubmitRequest = async () => {
    if (!newForm.original_asset_id || !newForm.requester_notes.trim()) {
      toast.error("Please select an asset and add notes");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/api/v1/fix-requests", {
        brand_id: parseInt(selectedBrand),
        original_asset_id: parseInt(newForm.original_asset_id),
        requester_notes: newForm.requester_notes,
      });
      toast.success("Fix request submitted!");
      setShowNewModal(false);
      setNewForm({ original_asset_id: "", requester_notes: "" });
      fetchRequests();
    } catch (e) {
      toast.error(e.message || "Failed to submit request");
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenReview = (req) => {
    setReviewRequest(req);
    setReviewForm({ status: req.status, reviewer_notes: req.reviewer_notes || "", updated_asset_id: req.updated_asset_id || "" });
  };

  const handleSubmitReview = async () => {
    setReviewing(true);
    try {
      await api.patch(`/api/v1/fix-requests/${reviewRequest.id}`, {
        status: reviewForm.status,
        reviewer_notes: reviewForm.reviewer_notes,
        ...(reviewForm.updated_asset_id && { updated_asset_id: parseInt(reviewForm.updated_asset_id) }),
      });
      toast.success("Review updated!");
      setReviewRequest(null);
      fetchRequests();
    } catch (e) {
      toast.error("Failed to update review");
    } finally {
      setReviewing(false);
    }
  };

  const canReview = userRole === "owner" || userRole === "admin";

  const filteredRequests = requests.filter(r =>
    activeTab === "all" || r.status === activeTab
  );

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <AlertCircle className="w-6 h-6 text-purple-400" /> Fix Requests
            </h1>
            <p className="text-zinc-400 text-sm mt-1">Asset retouch and correction requests</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={selectedBrand}
              onChange={(e) => setSelectedBrand(e.target.value)}
              className="bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-200 outline-none"
            >
              {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <button
              onClick={() => setShowNewModal(true)}
              className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-xl text-sm font-medium transition"
            >
              <Plus className="w-4 h-4" /> New Fix Request
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-3 mb-6">
          <button
            onClick={() => setActiveMainTab("inspector")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              activeMainTab === "inspector"
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-transparent"
            }`}
          >
            <ShieldCheck size={14} className="text-emerald-400" />
            AI QA Diagnostic & Inpainting Studio (WF-QA-001)
          </button>
          <button
            onClick={() => setActiveMainTab("requests")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              activeMainTab === "requests"
                ? "bg-purple-600/15 text-purple-300 border border-purple-500/30 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-transparent"
            }`}
          >
            <AlertCircle size={14} className="text-purple-400" />
            Fix Requests & Inpainting Queue
          </button>
        </div>

        {activeMainTab === "inspector" ? (
          <QADiagnosticInspector brandId={selectedBrand || brands[0]?.id || 1} />
        ) : (
          <>
            {/* Status Tabs */}
            <div className="flex gap-2 mb-6 overflow-x-auto">
              {STATUS_TABS.map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 rounded-xl text-xs font-medium whitespace-nowrap transition ${
                    activeTab === tab
                      ? "bg-purple-600 text-white"
                      : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
                  }`}
                >
                  {tab === "all" ? "All" : tab.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase())}
                  {tab !== "all" && (
                    <span className="ml-1.5 text-xs opacity-70">
                      ({requests.filter(r => r.status === tab).length})
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Requests List */}
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
              </div>
            ) : filteredRequests.length === 0 ? (
              <div className="text-zinc-500 text-sm text-center py-16 border border-zinc-800 rounded-2xl">
                No fix requests found.
              </div>
            ) : (
              <div className="space-y-4">
                {filteredRequests.map(req => {
                  const statusCfg = STATUS_CONFIG[req.status] || STATUS_CONFIG.pending;
                  const StatusIcon = statusCfg.icon;
                  return (
                    <div
                      key={req.id}
                      className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5 hover:border-zinc-700 transition cursor-pointer"
                      onClick={() => canReview && handleOpenReview(req)}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${statusCfg.color}`}>
                              <StatusIcon className="w-3 h-3" />
                              {statusCfg.label}
                            </span>
                            <span className="text-xs text-zinc-500">#{req.id}</span>
                            <span className="text-xs text-zinc-500">{new Date(req.created_at).toLocaleDateString()}</span>
                          </div>
                          <p className="text-sm text-zinc-300 mb-2">{req.requester_notes}</p>
                          {req.reviewer_notes && (
                            <div className="bg-zinc-800/50 rounded-xl px-3 py-2 mt-2">
                              <p className="text-xs text-zinc-400">
                                <span className="text-zinc-500">Reviewer: </span>{req.reviewer_notes}
                              </p>
                            </div>
                          )}
                        </div>
                        {req.asset_thumbnail_url && (
                          <img src={req.asset_thumbnail_url} alt="asset" className="w-16 h-16 rounded-xl object-cover border border-zinc-700 shrink-0" />
                        )}
                      </div>
                      {canReview && (
                        <p className="text-xs text-purple-400 mt-3">Click to review →</p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {/* New Fix Request Modal */}
      {showNewModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold text-white mb-4">New Fix Request</h2>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Select Asset *</label>
                <select
                  value={newForm.original_asset_id}
                  onChange={(e) => setNewForm(p => ({...p, original_asset_id: e.target.value}))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2.5 text-sm text-zinc-200 outline-none"
                >
                  <option value="">Select an asset...</option>
                  {assets.map(a => <option key={a.id} value={a.id}>{a.name || a.filename}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Requester Notes *</label>
                <textarea
                  value={newForm.requester_notes}
                  onChange={(e) => setNewForm(p => ({...p, requester_notes: e.target.value}))}
                  placeholder="Describe the corrections or retouches needed..."
                  rows={4}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2.5 text-sm text-zinc-200 outline-none resize-none"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={handleSubmitRequest} disabled={submitting} className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 py-2.5 rounded-xl text-sm font-medium transition">
                {submitting ? "Submitting..." : "Submit Request"}
              </button>
              <button onClick={() => setShowNewModal(false)} className="flex-1 border border-zinc-700 py-2.5 rounded-xl text-sm text-zinc-300 hover:text-white transition">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Review Modal */}
      {reviewRequest && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold text-white mb-4">Review Fix Request #{reviewRequest.id}</h2>
            <p className="text-xs text-zinc-400 mb-4 bg-zinc-800 rounded-xl px-3 py-2">{reviewRequest.requester_notes}</p>
            <div className="space-y-4">
              {reviewRequest?.original_asset_id && (
                <div className="mb-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-zinc-300">QA Diagnostics & Retouch</span>
                    <button
                      type="button"
                      onClick={() => setShowRetouchModal(true)}
                      className="px-2.5 py-1 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition flex items-center gap-1 shadow-md shadow-purple-600/20"
                    >
                      <Sparkles className="w-3.5 h-3.5" /> Launch Canvas Retouch
                    </button>
                  </div>
                  <QADiagnosticCard assetId={reviewRequest.original_asset_id} />
                </div>
              )}

              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Update Status</label>
                <select
                  value={reviewForm.status}
                  onChange={(e) => setReviewForm(p => ({...p, status: e.target.value}))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2.5 text-sm text-zinc-200 outline-none"
                >
                  <option value="pending">Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Reviewer Notes</label>
                <textarea
                  value={reviewForm.reviewer_notes}
                  onChange={(e) => setReviewForm(p => ({...p, reviewer_notes: e.target.value}))}
                  placeholder="Add review notes..."
                  rows={3}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2.5 text-sm text-zinc-200 outline-none resize-none"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Updated Asset (optional)</label>
                <select
                  value={reviewForm.updated_asset_id}
                  onChange={(e) => setReviewForm(p => ({...p, updated_asset_id: e.target.value}))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2.5 text-sm text-zinc-200 outline-none"
                >
                  <option value="">No replacement asset</option>
                  {assets.map(a => <option key={a.id} value={a.id}>{a.name || a.filename}</option>)}
                </select>
              </div>
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={handleSubmitReview} disabled={reviewing} className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 py-2.5 rounded-xl text-sm font-medium transition">
                {reviewing ? "Updating..." : "Update Review"}
              </button>
              <button onClick={() => setReviewRequest(null)} className="flex-1 border border-zinc-700 py-2.5 rounded-xl text-sm text-zinc-300 hover:text-white transition">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Canvas Retouch Modal */}
      {showRetouchModal && reviewRequest?.original_asset_id && (
        <CanvasRetouchModal
          isOpen={showRetouchModal}
          onClose={() => setShowRetouchModal(false)}
          asset={{ id: reviewRequest.original_asset_id, storage_uri: reviewRequest.asset_thumbnail_url }}
          initialDefectCode="ART-HAND-001"
          onSuccess={() => {
            fetchRequests();
          }}
        />
      )}
    </div>
  );
}
