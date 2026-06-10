"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { FolderKanban, Image as ImageIcon, Plus, Users, ShieldAlert, Sparkles, ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { toast } from "react-hot-toast";

export default function DashboardOverview() {
  const { user } = useAuth();
  const [brands, setBrands] = useState([]);
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const brandData = await api.get("/api/v1/brands");
        setBrands(brandData);
        
        // Fetch all assets accessible to the user
        const assetData = await api.get("/api/v1/assets");
        setAssets(assetData);
      } catch (error) {
        console.error("Failed to load dashboard statistics", error);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="animate-spin text-purple-500" size={24} />
      </div>
    );
  }

  // Calculate quick stats
  const totalBrands = brands.length;
  const totalAssets = assets.length;

  return (
    <div className="space-y-8 max-w-6xl">
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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Brand Card */}
        <motion.div
          whileHover={{ y: -4 }}
          className="bg-zinc-900/40 border border-zinc-850 rounded-2xl p-6 flex items-center justify-between shadow-md hover:bg-zinc-900/60 transition-all"
        >
          <div className="space-y-1">
            <span className="text-zinc-500 text-xs font-semibold tracking-wider uppercase block">
              Active Brands
            </span>
            <span className="text-3xl font-extrabold text-zinc-100">{totalBrands}</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-purple-950/40 border border-purple-800/20 flex items-center justify-center text-purple-400 shadow-inner">
            <FolderKanban size={20} />
          </div>
        </motion.div>

        {/* Asset Card */}
        <motion.div
          whileHover={{ y: -4 }}
          className="bg-zinc-900/40 border border-zinc-850 rounded-2xl p-6 flex items-center justify-between shadow-md hover:bg-zinc-900/60 transition-all"
        >
          <div className="space-y-1">
            <span className="text-zinc-500 text-xs font-semibold tracking-wider uppercase block">
              Uploaded Assets
            </span>
            <span className="text-3xl font-extrabold text-zinc-100">{totalAssets}</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-indigo-950/40 border border-indigo-800/20 flex items-center justify-center text-indigo-400 shadow-inner">
            <ImageIcon size={20} />
          </div>
        </motion.div>

        {/* Access Rights Card */}
        <motion.div
          whileHover={{ y: -4 }}
          className="bg-zinc-900/40 border border-zinc-850 rounded-2xl p-6 flex items-center justify-between shadow-md hover:bg-zinc-900/60 transition-all"
        >
          <div className="space-y-1">
            <span className="text-zinc-500 text-xs font-semibold tracking-wider uppercase block">
              User Profile Role
            </span>
            <span className="text-xl font-bold text-zinc-100 uppercase tracking-wide">
              {user?.role || "user"}
            </span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-amber-950/40 border border-amber-800/20 flex items-center justify-center text-amber-400 shadow-inner">
            <Users size={20} />
          </div>
        </motion.div>
      </div>

      {/* Guide & Activities */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 pt-4">
        {/* Left Side: Getting Started */}
        <div className="lg:col-span-2 space-y-6">
          <h3 className="text-lg font-bold text-zinc-200 tracking-wide flex items-center gap-2">
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
                  Go to the Brands section to register your fashion label. You'll automatically be registered as the Owner.
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

        {/* Right Side: Quick Action Quickboard */}
        <div className="space-y-6">
          <h3 className="text-lg font-bold text-zinc-200 tracking-wide">
            Your Active Brands
          </h3>
          <div className="bg-zinc-900/30 border border-zinc-850 rounded-2xl p-5 space-y-4 max-h-[300px] overflow-y-auto">
            {brands.length === 0 ? (
              <div className="text-center py-6 text-zinc-500 text-xs">
                No active brands. Create one to get started!
              </div>
            ) : (
              <div className="space-y-2.5">
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
      </div>
    </div>
  );
}
