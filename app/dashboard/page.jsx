"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Sparkles, Plus, AlertCircle, ArrowRight, Loader2, CheckCircle2, Clock, ShieldAlert, Image as ImageIcon, Camera, PenTool, Grid, Video, Layers, FolderKanban } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import StudioQuickLaunchCard from "@/components/dashboard/StudioQuickLaunchCard";

export default function DashboardOverview() {
  const { user } = useAuth();
  const [brands, setBrands] = useState([]);
  const [assets, setAssets] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchDashboardData() {
      try {
        setLoading(true);
        const [brandData, assetData, jobData] = await Promise.all([
          api.get("/api/v1/brands").catch(() => []),
          api.get("/api/v1/assets").catch(() => []),
          api.get("/api/v1/jobs?limit=6").catch(() => []),
        ]);
        setBrands(brandData || []);
        setAssets(assetData || []);
        setRecentJobs(jobData || []);
      } catch (error) {
        console.warn("Using default luxury dashboard state", error);
      } finally {
        setLoading(false);
      }
    }
    fetchDashboardData();
  }, []);

  const userName = user?.full_name || user?.email?.split("@")[0] || "Shahida";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 space-y-8">
      {/* Top Welcome Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
        <div>
          <span className="text-xs font-mono font-bold text-cyan-400 uppercase tracking-widest block mb-1">
            MODE LENS FASHION PRODUCTION OS
          </span>
          <h1 className="text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <span>Good morning, {userName}</span>
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Manage your AI model characters, photoshoot productions, creative direction, and quality control.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/create"
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs px-5 py-3 rounded-xl transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            <span>+ CREATE PRODUCTION</span>
          </Link>
        </div>
      </div>

      {/* Studios Section (Shahida Directive: Ghost, Sketch, Catalog, Move) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <span>Production Studios</span>
          </h2>
          <span className="text-xs text-zinc-500 font-mono">4 Specialized Workflows</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StudioQuickLaunchCard
            id="ghost"
            title="GHOST STUDIO"
            subtitle="Flat Lay & Mannequin"
            description="Transform flat lay garment photos into high-fashion model imagery."
            href="/dashboard/ghost"
            iconName="ghost"
            accentColor="cyan"
            badge="P1 Core"
          />
          <StudioQuickLaunchCard
            id="sketch"
            title="SKETCH STUDIO"
            subtitle="CAD Visualization"
            description="Generative CAD rendering from technical sketches to volumetric models."
            href="/dashboard/sketch"
            iconName="sketch"
            accentColor="purple"
            badge="Generative"
          />
          <StudioQuickLaunchCard
            id="catalog"
            title="CATALOG STUDIO"
            subtitle="E-Commerce Batch"
            description="High-volume batch production across multiple marketplace formats."
            href="/dashboard/catalog"
            iconName="catalog"
            accentColor="emerald"
            badge="Batch"
          />
          <StudioQuickLaunchCard
            id="move"
            title="MOVE STUDIO"
            subtitle="AI Fashion Video"
            description="Animate static fashion models into runway motion and video clips."
            href="/dashboard/move"
            iconName="move"
            accentColor="amber"
            badge="Motion"
          />
        </div>
      </div>

      {/* Production Status Metrics Bar */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 backdrop-blur-md shadow-xl">
        <div className="flex items-center justify-between mb-4 border-b border-zinc-800 pb-3">
          <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
            Production Status Overview
          </span>
          <span className="text-xs font-mono text-cyan-400">Live Real-Time Execution</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
            <span className="text-xs text-zinc-400 block">Active Projects</span>
            <p className="text-2xl font-extrabold text-white mt-1">8</p>
            <span className="text-[10px] text-zinc-500">Across 3 active campaigns</span>
          </div>

          <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
            <span className="text-xs text-zinc-400 block">Generating Jobs</span>
            <p className="text-2xl font-extrabold text-amber-400 mt-1 flex items-center gap-2">
              <span>24</span>
              <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
            </p>
            <span className="text-[10px] text-zinc-500">Parallel rendering active</span>
          </div>

          <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
            <span className="text-xs text-zinc-400 block">Ready for Review</span>
            <p className="text-2xl font-extrabold text-cyan-400 mt-1">16</p>
            <span className="text-[10px] text-zinc-500">Pending approval in QA</span>
          </div>

          <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
            <span className="text-xs text-zinc-400 block">Completed Production</span>
            <p className="text-2xl font-extrabold text-emerald-400 mt-1">142</p>
            <span className="text-[10px] text-zinc-500">Exported to library</span>
          </div>
        </div>
      </div>

      {/* Needs Attention Queue */}
      <div className="bg-zinc-900/90 border border-amber-500/20 rounded-2xl p-5 backdrop-blur-md shadow-xl">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase tracking-wider">
            <AlertCircle className="w-4 h-4" />
            <span>Needs Attention (3 Alerts)</span>
          </div>
          <Link href="/dashboard/fix-requests" className="text-xs text-zinc-400 hover:text-white transition-colors">
            View All QA Queues &rarr;
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="bg-zinc-950 border border-amber-500/30 p-3.5 rounded-xl flex items-center justify-between text-xs">
            <div>
              <span className="font-bold text-white block">4 Images Waiting for QA</span>
              <span className="text-[10px] text-zinc-400">Spring 2027 Runway Campaign</span>
            </div>
            <Link href="/dashboard/results/AST-2027-001" className="px-2.5 py-1 bg-amber-500/10 text-amber-400 border border-amber-500/30 rounded-lg text-[10px] font-bold">
              Review
            </Link>
          </div>

          <div className="bg-zinc-950 border border-rose-500/30 p-3.5 rounded-xl flex items-center justify-between text-xs">
            <div>
              <span className="font-bold text-white block">2 Failed Generations</span>
              <span className="text-[10px] text-zinc-400">Silk Bias Dress / High Mesh</span>
            </div>
            <Link href="/dashboard/jobs" className="px-2.5 py-1 bg-rose-500/10 text-rose-400 border border-rose-500/30 rounded-lg text-[10px] font-bold">
              Inspect
            </Link>
          </div>

          <div className="bg-zinc-950 border border-cyan-500/30 p-3.5 rounded-xl flex items-center justify-between text-xs">
            <div>
              <span className="font-bold text-white block">1 Batch Requires Review</span>
              <span className="text-[10px] text-zinc-400">E-Commerce Catalog Batch #402</span>
            </div>
            <Link href="/dashboard/catalog" className="px-2.5 py-1 bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 rounded-lg text-[10px] font-bold">
              Open Batch
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Productions & Visual Fashion Editorial Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <h2 className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
            <ImageIcon className="w-4 h-4 text-cyan-400" />
            <span>Recent Productions & Visual Results</span>
          </h2>
          <Link href="/dashboard/results/latest" className="text-xs text-cyan-400 hover:text-cyan-300 font-medium">
            Browse All Media &rarr;
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { id: 1, name: "Spring 2027 Runway Campaign", model: "ELISKA NOVAK (EE-F-002)", status: "12/16 Complete", quality: "Studio Quality 4K" },
            { id: 2, name: "Silk Bias Dress E-Com Batch", model: "SORA KIM (EE-F-003)", status: "Ready for Review", quality: "Catalog Batch" },
            { id: 3, name: "Velvet Evening Editorial", model: "ELISKA NOVAK (EE-F-002)", status: "Completed", quality: "Studio Quality 4K" },
            { id: 4, name: "Minimalist Resort 2027", model: "AMARA OKONJO (EE-F-004)", status: "Generating (75%)", quality: "Studio Quality 4K" },
          ].map((prod) => (
            <Link
              key={prod.id}
              href="/dashboard/results/AST-2027-001"
              className="group bg-zinc-900 border border-zinc-800 hover:border-cyan-500/50 rounded-2xl overflow-hidden transition-all shadow-md flex flex-col justify-between"
            >
              <div className="aspect-[4/3] bg-zinc-950 flex items-center justify-center relative overflow-hidden">
                <div className="text-center space-y-1 text-zinc-600 group-hover:text-cyan-400 transition-colors p-4">
                  <ImageIcon className="w-10 h-10 mx-auto stroke-[1]" />
                  <span className="text-[10px] font-mono text-zinc-500 block truncate">{prod.name}</span>
                </div>
              </div>

              <div className="p-4 border-t border-zinc-800/80">
                <h3 className="text-xs font-bold text-white group-hover:text-cyan-400 transition-colors truncate">
                  {prod.name}
                </h3>
                <p className="text-[11px] text-zinc-400 mt-0.5 truncate">{prod.model}</p>
                <div className="flex items-center justify-between text-[10px] font-mono mt-2 pt-2 border-t border-zinc-900">
                  <span className="text-cyan-400">{prod.status}</span>
                  <span className="text-zinc-500">{prod.quality}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
