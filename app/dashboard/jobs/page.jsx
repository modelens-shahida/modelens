"use client";

import React, { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Sparkles, Loader2, Play, CheckCircle2, AlertTriangle, ArrowRight, Clock, ExternalLink, RefreshCw, Layers } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "react-hot-toast";

export default function JobsPage() {
  const { user } = useAuth();
  
  // Data loading states
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [brandAssets, setBrandAssets] = useState([]);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [callbackUrl, setCallbackUrl] = useState("");
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Active polling jobs tracker
  const [activePollIds, setActivePollIds] = useState(new Set());
  const pollIntervalRef = useRef({});

  // Initialize page data
  const initPage = async () => {
    try {
      const brandData = await api.get("/api/v1/brands");
      setBrands(brandData);
      if (brandData.length > 0) {
        setSelectedBrandId(brandData[0].id.toString());
      }

      const templateData = await api.get("/api/v1/jobs/workflow-templates");
      setTemplates(templateData);
      if (templateData.length > 0) {
        setSelectedTemplateId(templateData[0].id.toString());
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

  // Fetch brand assets when brand selection changes
  useEffect(() => {
    async function fetchAssets() {
      if (!selectedBrandId) {
        setBrandAssets([]);
        setSelectedAssetId("");
        return;
      }
      try {
        const assets = await api.get(`/api/v1/assets?brand_id=${selectedBrandId}`);
        setBrandAssets(assets);
        if (assets.length > 0) {
          setSelectedAssetId(assets[0].id.toString());
        } else {
          setSelectedAssetId("");
        }
      } catch (error) {
        console.error("Failed to load assets", error);
      }
    }
    fetchAssets();
    
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

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!selectedBrandId || !selectedTemplateId) {
      toast.error("Brand and Workflow Template are required");
      return;
    }

    setIsSubmitting(true);
    try {
      // Resolve asset storage path if an asset is selected
      const selectedAsset = brandAssets.find((a) => a.id.toString() === selectedAssetId);
      const inputs = selectedAsset 
        ? { urls: [selectedAsset.storage_path] }
        : { urls: [] };

      const payload = {
        brand_id: parseInt(selectedBrandId),
        workflow_template_id: parseInt(selectedTemplateId),
        inputs,
        callback_url: callbackUrl.trim() || null
      };

      const newJob = await api.post("/api/v1/jobs/generate", payload);
      toast.success("AI Generation Job scheduled successfully!");
      setCallbackUrl("");
      
      // Update list
      setJobs((prev) => [newJob, ...prev]);
      // Start polling
      setActivePollIds((prev) => {
        const next = new Set(prev);
        next.add(newJob.id);
        return next;
      });
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
            Run isolated on-model image generation workflows using catalog assets and active templates
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
          <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
            <Layers size={14} className="text-purple-400" />
            Generation Parameters
          </h3>

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
                  {brandAssets.map((a) => (
                    <option key={a.id} value={a.id}>{a.name || a.filename} (ID: {a.id})</option>
                  ))}
                </select>
              )}
            </div>

            {/* Optional webhook URL */}
            <div className="space-y-1.5">
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
              <p className="text-[9px] text-zinc-500">
                ModeLens will POST a JSON payload with execution state details when this job completes or fails.
              </p>
            </div>

            {/* Generate Trigger */}
            <button
              type="submit"
              disabled={isSubmitting || brandAssets.length === 0}
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
                            <span className="text-[10px] text-zinc-500">Generation</span>
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
                        <div className="bg-zinc-950/40 border border-zinc-900/80 p-3 rounded-xl space-y-1">
                          <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-wide">Input Parameters</span>
                          {job.inputs?.urls && job.inputs.urls.length > 0 ? (
                            <div className="truncate">
                              <span className="text-zinc-500">S3 Source:</span>{" "}
                              <span className="text-[10px] font-mono text-zinc-300">{job.inputs.urls[0]}</span>
                            </div>
                          ) : (
                            <div className="text-[10px] text-zinc-500">No source assets input</div>
                          )}
                          {job.callback_url && (
                            <div className="truncate text-[10px]">
                              <span className="text-zinc-500">Webhook:</span>{" "}
                              <span className="text-[9px] font-mono text-zinc-400">{job.callback_url}</span>
                            </div>
                          )}
                        </div>

                        {/* Outputs Info */}
                        <div className="bg-zinc-950/40 border border-zinc-900/80 p-3 rounded-xl space-y-1">
                          <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-wide">Output Assets</span>
                          {job.status === "completed" ? (
                            <div className="space-y-1">
                              {job.outputs?.urls && job.outputs.urls.map((url, index) => (
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
                              {job.asset_id && (
                                <div className="text-[10px] text-zinc-500">
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
                              Awaiting generated output file path...
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
