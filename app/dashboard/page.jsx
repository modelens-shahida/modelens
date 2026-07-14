"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { FolderKanban, Image as ImageIcon, Plus, Users, Sparkles, ArrowRight, Loader2, Coins, Clock, Activity, CheckCircle2, AlertTriangle } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { toast } from "react-hot-toast";

export default function DashboardOverview() {
  const { user } = useAuth();
  const [brands, setBrands] = useState([]);
  const [assets, setAssets] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [ssoWelcome, setSsoWelcome] = useState(null);
  const [creditInfo, setCreditInfo] = useState(null);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  useEffect(() => {
    api.get("/api/v1/credits/balance").then((data) => {
      setCreditInfo(data);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const stored = sessionStorage.getItem("sso_welcome");
    if (stored) {
      try {
        setSsoWelcome(JSON.parse(stored));
      } catch (e) {
        console.error("Failed to parse SSO welcome", e);
      }
    }
  }, []);

  useEffect(() => {
    async function fetchStats() {
      try {
        // Fetch brands
        const brandData = await api.get("/api/v1/brands");
        setBrands(brandData);
        
        // Fetch assets
        const assetData = await api.get("/api/v1/assets");
        setAssets(assetData);

        // Fetch recent AI generation jobs
        const jobData = await api.get("/api/v1/jobs?limit=5&offset=0");
        setRecentJobs(jobData);
      } catch (error) {
        console.error("Failed to load dashboard statistics", error);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  const getStatusBadge = (status) => {
    switch (status) {
      case "pending":
        return (
          <span className="inline-flex items-center gap-1 text-[9px] uppercase font-bold text-amber-400 bg-amber-950/20 border border-amber-900/30 px-2 py-0.5 rounded-full">
            <Clock size={8} /> Pending
          </span>
        );
      case "processing":
        return (
          <span className="inline-flex items-center gap-1 text-[9px] uppercase font-bold text-purple-400 bg-purple-950/20 border border-purple-800/30 px-2 py-0.5 rounded-full">
            <Loader2 size={8} className="animate-spin text-purple-400" /> Processing
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 text-[9px] uppercase font-bold text-emerald-400 bg-emerald-950/20 border border-emerald-800/30 px-2 py-0.5 rounded-full">
            <CheckCircle2 size={8} /> Completed
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 text-[9px] uppercase font-bold text-rose-400 bg-rose-950/20 border border-rose-800/30 px-2 py-0.5 rounded-full">
            <AlertTriangle size={8} /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[9px] uppercase font-bold text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded-full">
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

  const totalBrands = brands.length;
  const totalAssets = assets.length;

  return (
    <div className="space-y-8 max-w-6xl">
      {/* Low Credit Warning Banner */}
      {creditInfo?.low_credits && !bannerDismissed && (
        <div className="mx-6 mt-4 flex items-center justify-between gap-4 bg-amber-950/40 border border-amber-700/50 backdrop-blur-sm rounded-2xl px-5 py-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-amber-300">Low Credit Balance</p>
              <p className="text-xs text-amber-400/80">
                You have <span className="font-bold text-amber-300">{creditInfo.balance}</span> credits remaining (threshold: {creditInfo.low_credit_threshold}). Top up to continue generating content.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <Link href="/dashboard/billing" className="text-xs bg-amber-500 hover:bg-amber-400 text-black font-semibold px-4 py-1.5 rounded-full transition">
              Top Up
            </Link>
            <button onClick={() => setBannerDismissed(true)} className="text-amber-500 hover:text-amber-300 transition text-lg font-bold">
              ×
            </button>
          </div>
        </div>
      )}

      {/* SSO Welcome Alert Banner */}
      {ssoWelcome && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-purple-950/20 border border-purple-900/40 rounded-2xl p-5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 shadow-lg shadow-purple-950/10"
        >
          <div className="flex gap-3">
            <span className="p-2 bg-purple-900/30 rounded-xl text-purple-400 max-fit">
              <Sparkles size={20} />
            </span>
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-zinc-100">Auto-Enrollment Successful!</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                You've been automatically provisioned as a member of the **{ssoWelcome.brandName}** workspace.
              </p>
            </div>
          </div>
          <div className="flex gap-3 w-full sm:w-auto">
            <Link
              href={`/dashboard/brands/${ssoWelcome.brandId}`}
              onClick={() => sessionStorage.removeItem("sso_welcome")}
              className="flex-1 sm:flex-initial bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold py-2.5 px-4 rounded-xl transition-all text-center cursor-pointer"
            >
              Go to Workspace
            </Link>
            <button
              onClick={() => {
                sessionStorage.removeItem("sso_welcome");
                setSsoWelcome(null);
              }}
              className="bg-zinc-900/60 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 text-xs font-semibold py-2.5 px-4 rounded-xl transition-all cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        </motion.div>
      )}

      {/* Welcome Hero Banner */}
      <div className="bg-gradient-to-r from-zinc-900 via-zinc-900 to-purple-950/20 border border-zinc-850/80 rounded-2xl p-6 md:p-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 shadow-xl relative overflow-hidden">
        <div className="absolute inset-0 bg-grid-white/[0.02] pointer-events-none" />
        <div className="space-y-2 relative z-10">
          <div className="flex items-center gap-2 text-purple-400 text-xs font-semibold uppercase tracking-wider">
            <Sparkles size={14} />
            AI Catalog Generation Suite
          </div>
          <h2 className="text-2xl md:text-3xl font-extrabold text-white">
            Welcome, {user?.full_name || "Fashion Designer"}
          </h2>
          <p className="text-sm text-zinc-400 max-w-lg leading-relaxed">
            Manage your fashion catalog assets, define brand taxonomies, and generate high-converting product shots in seconds.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto relative z-10">
          <Link
            href="/dashboard/brands"
            className="flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold px-5 py-3 rounded-xl transition-all cursor-pointer shadow-lg shadow-purple-950/20"
          >
            <Plus size={16} />
            Manage Brands
          </Link>
          <Link
            href="/dashboard/assets"
            className="flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-white text-sm font-semibold px-5 py-3 rounded-xl transition-all cursor-pointer"
          >
            Explore Assets
            <ArrowRight size={16} />
          </Link>
        </div>
      </div>

      {/* Grid of Key Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Brand Card */}
        <motion.div
          whileHover={{ y: -4 }}
          className="bg-zinc-900/30 border border-zinc-850 rounded-2xl p-5 flex items-center justify-between shadow-md hover:bg-zinc-900/50 transition-all"
        >
          <div className="space-y-1">
            <span className="text-zinc-500 text-[10px] font-semibold tracking-wider uppercase block">
              Active Brands
            </span>
            <span className="text-2xl font-extrabold text-zinc-100">{totalBrands}</span>
          </div>
          <div className="w-10 h-10 rounded-xl bg-purple-950/40 border border-purple-800/20 flex items-center justify-center text-purple-400 shadow-inner">
            <FolderKanban size={18} />
          </div>
        </motion.div>

        {/* Asset Card */}
        <motion.div
          whileHover={{ y: -4 }}
          className="bg-zinc-900/30 border border-zinc-850 rounded-2xl p-5 flex items-center justify-between shadow-md hover:bg-zinc-900/50 transition-all"
        >
          <div className="space-y-1">
            <span className="text-zinc-500 text-[10px] font-semibold tracking-wider uppercase block">
              Catalog Assets
            </span>
            <span className="text-2xl font-extrabold text-zinc-100">{totalAssets}</span>
          </div>
          <div className="w-10 h-10 rounded-xl bg-indigo-950/40 border border-indigo-800/20 flex items-center justify-center text-indigo-400 shadow-inner">
            <ImageIcon size={18} />
          </div>
        </motion.div>

        {/* Credits Card */}
        <motion.div
          whileHover={{ y: -4 }}
          className="bg-zinc-900/30 border border-zinc-850 rounded-2xl p-5 flex items-center justify-between shadow-md hover:bg-zinc-900/50 transition-all"
        >
          <div className="space-y-1">
            <span className="text-zinc-500 text-[10px] font-semibold tracking-wider uppercase block">
              AI GPU Credits
            </span>
            <span className="text-2xl font-extrabold text-zinc-100">{user?.credits ?? 0}</span>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-950/40 border border-emerald-800/20 flex items-center justify-center text-emerald-400 shadow-inner">
            <Coins size={18} />
          </div>
        </motion.div>

        {/* Access Rights Card */}
        <motion.div
          whileHover={{ y: -4 }}
          className="bg-zinc-900/30 border border-zinc-850 rounded-2xl p-5 flex items-center justify-between shadow-md hover:bg-zinc-900/50 transition-all"
        >
          <div className="space-y-1">
            <span className="text-zinc-500 text-[10px] font-semibold tracking-wider uppercase block">
              User Profile Role
            </span>
            <span className="text-sm font-bold text-zinc-200 uppercase tracking-wide">
              {user?.role || "user"}
            </span>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-950/40 border border-amber-800/20 flex items-center justify-center text-amber-400 shadow-inner">
            <Users size={18} />
          </div>
        </motion.div>
      </div>

      {/* Guide & Activities */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 pt-4">
        {/* Left Side: Getting Started & Recent Activity */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* Recent AI Generation Jobs */}
          <div className="space-y-4">
            <h3 className="text-base font-bold text-zinc-200 tracking-wide flex items-center gap-2">
              <Activity size={18} className="text-purple-400" />
              Recent AI Generation Runs
            </h3>
            
            {recentJobs.length === 0 ? (
              <div className="text-center py-12 bg-zinc-900/10 border border-zinc-900 rounded-2xl text-zinc-500 text-xs">
                No active jobs executed yet. Head to the AI Generator to run catalog designs.
              </div>
            ) : (
              <div className="border border-zinc-900 rounded-2xl overflow-hidden bg-zinc-950/40">
                <div className="divide-y divide-zinc-900">
                  {recentJobs.map((job) => (
                    <div key={job.id} className="p-4 flex items-center justify-between gap-4 hover:bg-zinc-900/20 transition-all">
                      <div className="space-y-1 text-left min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-zinc-200">Job #{job.id}</span>
                          <span className="text-[10px] text-zinc-500 font-medium">Generation</span>
                        </div>
                        <p className="text-[10px] text-zinc-400 truncate max-w-xs md:max-w-md">
                          Asset S3 Path: {job.inputs?.urls?.[0] || "No source inputs"}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-[10px] text-zinc-500">
                          {new Date(job.created_at).toLocaleDateString()}
                        </span>
                        {getStatusBadge(job.status)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Getting Started Guide */}
          <div className="space-y-4">
            <h3 className="text-base font-bold text-zinc-200 tracking-wide">
              Getting Started with ModeLens
            </h3>
            <div className="space-y-4">
              {/* Step 1 */}
              <div className="flex gap-4 p-4 bg-zinc-900/20 border border-zinc-900 rounded-xl">
                <div className="w-8 h-8 rounded-lg bg-purple-900/20 text-purple-400 font-bold flex items-center justify-center shrink-0 border border-purple-800/10">
                  1
                </div>
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-zinc-100">Create or Choose a Brand</h4>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    Go to the Brands section to register your fashion label. You&apos;ll automatically be registered as the Owner.
                  </p>
                </div>
              </div>

              {/* Step 2 */}
              <div className="flex gap-4 p-4 bg-zinc-900/20 border border-zinc-900 rounded-xl">
                <div className="w-8 h-8 rounded-lg bg-indigo-900/20 text-indigo-400 font-bold flex items-center justify-center shrink-0 border border-indigo-800/10">
                  2
                </div>
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-zinc-100">Upload Product Images</h4>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    Add raw campaign files or model shots in Assets, and associate them with your brand to catalog them.
                  </p>
                </div>
              </div>

              {/* Step 3 */}
              <div className="flex gap-4 p-4 bg-zinc-900/20 border border-zinc-900 rounded-xl">
                <div className="w-8 h-8 rounded-lg bg-emerald-900/20 text-emerald-400 font-bold flex items-center justify-center shrink-0 border border-emerald-800/10">
                  3
                </div>
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-zinc-100">Enforce Taxonomy & Generate</h4>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    Assign camera filters, lighting presets, location properties and mood settings to generate stunning images.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Active Brands & Recent Assets */}
        <div className="space-y-8">
          
          {/* Active Brands list */}
          <div className="space-y-4">
            <h3 className="text-base font-bold text-zinc-200 tracking-wide">
              Your Active Brands
            </h3>
            <div className="bg-zinc-900/30 border border-zinc-850 rounded-2xl p-4 space-y-4 max-h-[260px] overflow-y-auto">
              {brands.length === 0 ? (
                <div className="text-center py-6 text-zinc-500 text-xs">
                  No active brands. Create one to get started!
                </div>
              ) : (
                <div className="space-y-2">
                  {brands.map((b) => (
                    <Link
                      key={b.id}
                      href={`/dashboard/brands/${b.id}`}
                      className="flex justify-between items-center p-3 rounded-xl bg-zinc-950/60 border border-zinc-900 hover:border-zinc-800 hover:bg-zinc-900/40 transition-all group"
                    >
                      <span className="text-xs font-semibold text-zinc-300 group-hover:text-white transition-colors">
                        {b.name}
                      </span>
                      <span className="text-[10px] text-zinc-500 group-hover:text-purple-400 flex items-center gap-1">
                        Details <ArrowRight size={10} />
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Recent Catalog Assets */}
          <div className="space-y-4">
            <h3 className="text-base font-bold text-zinc-200 tracking-wide">
              Recent Catalog Assets
            </h3>
            {assets.length === 0 ? (
              <div className="text-center py-10 bg-zinc-900/10 border border-zinc-900 rounded-2xl text-zinc-500 text-xs">
                No catalog assets uploaded yet.
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {assets.slice(0, 6).map((asset) => (
                  <Link 
                    key={asset.id} 
                    href="/dashboard/assets"
                    className="aspect-square rounded-xl border border-zinc-900 hover:border-purple-500/50 overflow-hidden relative group transition-all"
                  >
                    <img
                      src={asset.storage_path}
                      alt={asset.name}
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'flex';
                      }}
                      className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
                    />
                    {/* Fallback Icon */}
                    <div className="hidden absolute inset-0 bg-zinc-950 items-center justify-center text-zinc-700">
                      <ImageIcon size={16} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
