"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Wrench, Plus, Loader2, Clock, CheckCircle2, AlertTriangle, Play, X, FileText, ArrowRight, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

export default function FixRequestsPage() {
  const { user } = useAuth();

  // Core Data States
  const [brands, setBrands] = useState([]);
  const [selectedBrand, setSelectedBrand] = useState("");
  const [members, setMembers] = useState([]);
  const [fixRequests, setFixRequests] = useState([]);
  const [assets, setAssets] = useState([]);
  const [assetsMap, setAssetsMap] = useState({});

  // UI / UX States
  const [loading, setLoading] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const limit = 10;

  // Modal States
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState(null);

  // Form States - Create
  const [createAssetId, setCreateAssetId] = useState("");
  const [createNotes, setCreateNotes] = useState("");
  const [createJobId, setCreateJobId] = useState("");
  const [isSubmittingCreate, setIsSubmittingCreate] = useState(false);

  // Form States - Review
  const [reviewStatus, setReviewStatus] = useState("in_progress");
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewUpdatedAssetId, setReviewUpdatedAssetId] = useState("");
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  // Load brands on mount
  useEffect(() => {
    async function initPage() {
      try {
        setLoading(true);
        const data = await api.get("/api/v1/brands");
        setBrands(data);
        if (data.length > 0) {
          setSelectedBrand(data[0].id.toString());
        }
      } catch (error) {
        toast.error("Failed to load brands.");
        console.error(error);
      } finally {
        setLoading(false);
      }
    }
    initPage();
  }, []);

  // Fetch brand members, assets, and fix requests when selected brand changes
  useEffect(() => {
    if (!selectedBrand) return;
    setPage(1);
    fetchWorkspaceData();
  }, [selectedBrand]);

  // Refetch fix requests when page or filter changes
  useEffect(() => {
    if (!selectedBrand) return;
    fetchFixRequests();
  }, [page, statusFilter]);

  const fetchWorkspaceData = async () => {
    try {
      setLoadingList(true);
      const brandId = parseInt(selectedBrand);

      // Fetch members to determine RBAC
      const membersData = await api.get(`/api/v1/brands/${brandId}/members`);
      setMembers(membersData);

      // Fetch assets list for selection forms & lookup mapping
      const assetsData = await api.get(`/api/v1/assets?brand_id=${brandId}&limit=100`);
      setAssets(assetsData);

      const mapping = {};
      assetsData.forEach((a) => {
        mapping[a.id] = a;
      });
      setAssetsMap(mapping);

      await fetchFixRequests();
    } catch (error) {
      toast.error("Failed to load brand workspace data.");
      console.error(error);
    } finally {
      setLoadingList(false);
    }
  };

  const fetchFixRequests = async () => {
    try {
      setLoadingList(true);
      const brandId = parseInt(selectedBrand);
      const offset = (page - 1) * limit;

      const data = await api.get(
        `/api/v1/fix-requests?brand_id=${brandId}&limit=${limit}&offset=${offset}`
      );
      setFixRequests(data || []);
    } catch (error) {
      toast.error("Failed to load fix requests.");
      console.error(error);
    } finally {
      setLoadingList(false);
    }
  };

  // Resolve user role in active brand
  const activeBrandObj = brands.find((b) => b.id.toString() === selectedBrand);
  const userIsOwner = activeBrandObj?.owner_id === user?.id;
  const userMembership = members.find((m) => m.user_id === user?.id);
  const userRole = userIsOwner ? "owner" : userMembership?.role || "viewer";

  // Check Permissions
  const canCreate = ["owner", "admin", "editor"].includes(userRole);
  const canReview = ["owner", "admin"].includes(userRole);

  // Filter requests locally by review_status if needed
  const filteredRequests = fixRequests.filter((req) => {
    if (statusFilter === "all") return true;
    return req.review_status === statusFilter;
  });

  const getStatusConfig = (status) => {
    switch (status) {
      case "pending":
        return {
          label: "Pending",
          colorClass: "text-amber-400 bg-amber-950/20 border-amber-900/30",
          icon: Clock,
        };
      case "in_progress":
        return {
          label: "In Progress",
          colorClass: "text-purple-400 bg-purple-950/20 border-purple-800/30",
          icon: Play,
        };
      case "completed":
        return {
          label: "Completed",
          colorClass: "text-emerald-400 bg-emerald-950/20 border-emerald-800/30",
          icon: CheckCircle2,
        };
      case "rejected":
        return {
          label: "Rejected",
          colorClass: "text-rose-400 bg-rose-950/20 border-rose-800/30",
          icon: AlertTriangle,
        };
      default:
        return {
          label: "Unknown",
          colorClass: "text-zinc-400 bg-zinc-800 border-zinc-700",
          icon: Clock,
        };
    }
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    if (!createAssetId) {
      toast.error("Please select an original asset.");
      return;
    }
    if (!createNotes.trim()) {
      toast.error("Please provide requester notes.");
      return;
    }

    setIsSubmittingCreate(true);
    try {
      const payload = {
        original_asset_id: parseInt(createAssetId),
        requester_notes: createNotes.trim(),
        job_id: createJobId ? parseInt(createJobId) : null,
      };

      await api.post("/api/v1/fix-requests", payload);
      toast.success("Fix request submitted successfully!");
      setIsCreateOpen(false);

      // Reset Form
      setCreateAssetId("");
      setCreateNotes("");
      setCreateJobId("");

      fetchFixRequests();
    } catch (error) {
      toast.error(error.message || "Failed to submit request.");
    } finally {
      setIsSubmittingCreate(false);
    }
  };

  const openReviewModal = (req) => {
    setSelectedRequest(req);
    setReviewStatus(req.review_status === "pending" ? "in_progress" : req.review_status);
    setReviewNotes(req.reviewer_notes || "");
    setReviewUpdatedAssetId(req.updated_asset_id ? req.updated_asset_id.toString() : "");
    setIsReviewOpen(true);
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    setIsSubmittingReview(true);
    try {
      const payload = {
        review_status: reviewStatus,
        reviewer_notes: reviewNotes.trim() || null,
        updated_asset_id: reviewUpdatedAssetId ? parseInt(reviewUpdatedAssetId) : null,
      };

      await api.patch(`/api/v1/fix-requests/${selectedRequest.id}`, payload);
      toast.success("Fix request updated successfully!");
      setIsReviewOpen(false);
      fetchFixRequests();
    } catch (error) {
      toast.error(error.message || "Failed to update fix request.");
    } finally {
      setIsSubmittingReview(false);
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
    <div className="space-y-6 max-w-6xl pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100 flex items-center gap-2">
            <Wrench size={22} className="text-purple-400" />
            Fix & Adjustment Requests
          </h2>
          <p className="text-xs text-zinc-400">
            Submit catalog cropping corrections, background adjustment commands, or approve updates.
          </p>
        </div>

        {/* Brand Selector dropdown */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-500 font-medium">Workspace:</span>
            <select
              value={selectedBrand}
              onChange={(e) => setSelectedBrand(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-semibold px-3 py-2 rounded-xl focus:outline-none focus:border-purple-600 cursor-pointer"
            >
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>

          {canCreate && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20"
            >
              <Plus size={14} />
              New Request
            </button>
          )}
        </div>
      </div>

      {/* Zero State for Brands */}
      {brands.length === 0 ? (
        <div className="text-center py-16 bg-zinc-900/10 border border-zinc-900 rounded-2xl space-y-4 max-w-md mx-auto">
          <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-500 mx-auto">
            <Wrench size={22} />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-zinc-200">No Brand Workspaces</h3>
            <p className="text-xs text-zinc-400 px-6">
              Create a brand first before submitting adjustment or catalog fix requests.
            </p>
          </div>
        </div>
      ) : (
        <>
          {/* Filter Bar & Quick Stats */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-zinc-900/30 border border-zinc-850/60 p-4 rounded-2xl">
            <div className="flex flex-wrap items-center gap-2">
              {["all", "pending", "in_progress", "completed", "rejected"].map((filter) => (
                <button
                  key={filter}
                  onClick={() => setStatusFilter(filter)}
                  className={`text-xs font-semibold px-3.5 py-2 rounded-xl border transition-all cursor-pointer capitalize ${
                    statusFilter === filter
                      ? "bg-purple-600/15 border-purple-500/30 text-purple-400"
                      : "bg-zinc-950/40 border-zinc-850/40 text-zinc-400 hover:bg-zinc-900/40 hover:text-zinc-200"
                  }`}
                >
                  {filter.replace("_", " ")}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 text-zinc-500 text-xs font-semibold">
              <span className="text-[10px] uppercase tracking-wider bg-zinc-850 text-zinc-300 px-2.5 py-0.5 rounded-full">
                Your Workspace Role: {userRole}
              </span>
              <button
                onClick={fetchFixRequests}
                className="p-2 hover:bg-zinc-900 rounded-xl text-zinc-400 hover:text-zinc-200 transition-colors"
                title="Refresh timeline"
              >
                <RefreshCw size={12} />
              </button>
            </div>
          </div>

          {/* List Loader / Table */}
          {loadingList ? (
            <div className="flex justify-center py-20">
              <Loader2 className="animate-spin text-purple-500" size={24} />
            </div>
          ) : filteredRequests.length === 0 ? (
            <div className="text-center py-20 bg-zinc-950/40 border border-zinc-900 rounded-2xl">
              <p className="text-zinc-400 text-sm">No adjustments match the active filters.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredRequests.map((req) => {
                const origAsset = assetsMap[req.original_asset_id];
                const updatedAsset = assetsMap[req.updated_asset_id];
                const statusConfig = getStatusConfig(req.review_status);
                const StatusIcon = statusConfig.icon;

                return (
                  <motion.div
                    key={req.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-zinc-950/60 border border-zinc-900 hover:border-zinc-850 rounded-2xl p-5 transition-all shadow-md flex flex-col md:flex-row justify-between items-start md:items-center gap-6"
                  >
                    {/* Media Assets Comparison */}
                    <div className="flex items-center gap-4 min-w-0 flex-1">
                      {/* Original Asset Thumbnail preview */}
                      <div className="w-16 h-16 rounded-xl bg-zinc-900 border border-zinc-800 flex-shrink-0 flex items-center justify-center overflow-hidden relative">
                        {origAsset?.storage_path ? (
                          <img
                            src={origAsset.storage_path}
                            alt="Original Asset"
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <FileText size={18} className="text-zinc-600" />
                        )}
                        <span className="absolute bottom-0 inset-x-0 text-center bg-black/60 text-[8px] text-zinc-400 py-0.5 uppercase tracking-wide font-bold">
                          Orig
                        </span>
                      </div>

                      {/* Direction arrow if completed */}
                      {req.review_status === "completed" && updatedAsset && (
                        <div className="text-purple-400">
                          <ArrowRight size={14} />
                        </div>
                      )}

                      {/* Updated Asset Thumbnail preview */}
                      {req.review_status === "completed" && updatedAsset && (
                        <div className="w-16 h-16 rounded-xl bg-zinc-900 border border-zinc-800 flex-shrink-0 flex items-center justify-center overflow-hidden relative">
                          <img
                            src={updatedAsset.storage_path}
                            alt="Updated Asset"
                            className="w-full h-full object-cover"
                          />
                          <span className="absolute bottom-0 inset-x-0 text-center bg-black/60 text-[8px] text-emerald-400 py-0.5 uppercase tracking-wide font-bold">
                            Fixed
                          </span>
                        </div>
                      )}

                      {/* Notes & details */}
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-semibold text-zinc-300">
                            Request #{req.id}
                          </span>
                          <span className="text-[10px] text-zinc-500">
                            {new Date(req.created_at).toLocaleString()}
                          </span>
                          {req.job_id && (
                            <span className="text-[9px] bg-zinc-900 text-zinc-400 px-2 py-0.5 rounded border border-zinc-800">
                              Job ID: {req.job_id}
                            </span>
                          )}
                        </div>

                        <p className="text-xs text-zinc-200 line-clamp-2">
                          <span className="font-semibold text-zinc-400">Notes: </span>
                          {req.requester_notes}
                        </p>

                        {req.reviewer_notes && (
                          <p className="text-xs text-purple-400 line-clamp-2">
                            <span className="font-semibold text-purple-500">Review: </span>
                            {req.reviewer_notes}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Badge Status & Review Action */}
                    <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-end border-t md:border-t-0 border-zinc-900 pt-3 md:pt-0">
                      <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide border px-2.5 py-1 rounded-full ${statusConfig.colorClass}`}>
                        <StatusIcon size={10} />
                        {statusConfig.label}
                      </span>

                      {canReview && (req.review_status === "pending" || req.review_status === "in_progress") && (
                        <button
                          onClick={() => openReviewModal(req)}
                          className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-200 text-xs font-semibold px-3 py-1.5 rounded-xl transition-all cursor-pointer"
                        >
                          Review
                        </button>
                      )}
                    </div>
                  </motion.div>
                );
              })}

              {/* Pagination controls */}
              <div className="flex items-center justify-between border-t border-zinc-900 pt-4">
                <button
                  disabled={page === 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="inline-flex items-center gap-1 bg-zinc-950 border border-zinc-900 disabled:opacity-40 text-zinc-300 text-xs font-semibold px-3 py-2 rounded-xl hover:bg-zinc-900 transition-all cursor-pointer"
                >
                  <ChevronLeft size={14} /> Previous
                </button>

                <span className="text-xs text-zinc-500 font-semibold">Page {page}</span>

                <button
                  disabled={filteredRequests.length < limit}
                  onClick={() => setPage((p) => p + 1)}
                  className="inline-flex items-center gap-1 bg-zinc-950 border border-zinc-900 disabled:opacity-40 text-zinc-300 text-xs font-semibold px-3 py-2 rounded-xl hover:bg-zinc-900 transition-all cursor-pointer"
                >
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* CREATE MODAL */}
      <AnimatePresence>
        {isCreateOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsCreateOpen(false)}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            />

            {/* Content */}
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-zinc-950 border border-zinc-850/80 rounded-2xl w-full max-w-lg p-6 overflow-hidden relative z-10 shadow-2xl"
            >
              <button
                onClick={() => setIsCreateOpen(false)}
                className="absolute top-4 right-4 text-zinc-400 hover:text-white transition-colors"
              >
                <X size={18} />
              </button>

              <h3 className="text-md font-bold text-zinc-200 mb-4">Submit Fix / Adjustment Request</h3>

              <form onSubmit={handleCreateSubmit} className="space-y-4">
                {/* Select Asset */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-400 block">
                    Original Asset to Fix *
                  </label>
                  <select
                    value={createAssetId}
                    onChange={(e) => setCreateAssetId(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-semibold p-3 rounded-xl focus:outline-none focus:border-purple-600 cursor-pointer"
                  >
                    <option value="">-- Choose Asset --</option>
                    {assets.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({a.filename})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Job ID */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-400 block">
                    Associated AI Job ID (Optional)
                  </label>
                  <input
                    type="number"
                    value={createJobId}
                    onChange={(e) => setCreateJobId(e.target.value)}
                    placeholder="e.g. 104"
                    className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-semibold p-3 rounded-xl focus:outline-none focus:border-purple-600"
                  />
                </div>

                {/* Notes */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-400 block">
                    Adjustment Instructions *
                  </label>
                  <textarea
                    rows={4}
                    value={createNotes}
                    onChange={(e) => setCreateNotes(e.target.value)}
                    placeholder="Describe what needs to be adjusted (e.g. cropping borders, background artifacts correction, etc.)"
                    className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-semibold p-3 rounded-xl focus:outline-none focus:border-purple-600 resize-none"
                    maxLength={2000}
                  />
                </div>

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={isSubmittingCreate}
                  className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-semibold py-3.5 rounded-xl transition-all cursor-pointer"
                >
                  {isSubmittingCreate ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    "Submit Request"
                  )}
                </button>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* REVIEW MODAL */}
      <AnimatePresence>
        {isReviewOpen && selectedRequest && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsReviewOpen(false)}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            />

            {/* Content */}
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-zinc-950 border border-zinc-850/80 rounded-2xl w-full max-w-lg p-6 overflow-hidden relative z-10 shadow-2xl"
            >
              <button
                onClick={() => setIsReviewOpen(false)}
                className="absolute top-4 right-4 text-zinc-400 hover:text-white transition-colors"
              >
                <X size={18} />
              </button>

              <h3 className="text-md font-bold text-zinc-200 mb-4">Review Fix Request #{selectedRequest.id}</h3>

              <div className="bg-zinc-900/40 border border-zinc-900 p-3 rounded-xl mb-4 text-xs space-y-1 text-zinc-300">
                <p>
                  <span className="font-semibold text-zinc-500">Original Asset:</span>{" "}
                  {assetsMap[selectedRequest.original_asset_id]?.name || `ID ${selectedRequest.original_asset_id}`}
                </p>
                <p>
                  <span className="font-semibold text-zinc-500">Requester Notes:</span>{" "}
                  {selectedRequest.requester_notes}
                </p>
              </div>

              <form onSubmit={handleReviewSubmit} className="space-y-4">
                {/* Status Selection */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-400 block">
                    Review Status *
                  </label>
                  <select
                    value={reviewStatus}
                    onChange={(e) => setReviewStatus(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-semibold p-3 rounded-xl focus:outline-none focus:border-purple-600 cursor-pointer"
                  >
                    <option value="in_progress">In Progress</option>
                    <option value="completed">Completed</option>
                    <option value="rejected">Rejected</option>
                  </select>
                </div>

                {/* Updated Asset Selection (only if status is completed) */}
                {reviewStatus === "completed" && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-zinc-400 block">
                      Resolved Asset Link
                    </label>
                    <select
                      value={reviewUpdatedAssetId}
                      onChange={(e) => setReviewUpdatedAssetId(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-semibold p-3 rounded-xl focus:outline-none focus:border-purple-600 cursor-pointer"
                    >
                      <option value="">-- Select Updated Asset --</option>
                      {assets.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name} ({a.filename})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Review Notes */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-400 block">
                    Reviewer Notes (Optional)
                  </label>
                  <textarea
                    rows={3}
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    placeholder="Provide details about the review decision or resolution details..."
                    className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-semibold p-3 rounded-xl focus:outline-none focus:border-purple-600 resize-none"
                  />
                </div>

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={isSubmittingReview}
                  className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-semibold py-3.5 rounded-xl transition-all cursor-pointer"
                >
                  {isSubmittingReview ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    "Save Review"
                  )}
                </button>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
