"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Film, Sparkles, Video, Play, Compass, RotateCw, Wind } from "lucide-react";
import MotionPresetSelector from "@/components/dashboard/MotionPresetSelector";

export default function MoveStudioPage() {
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");

  useEffect(() => {
    api.get("/api/v1/brands")
      .then((data) => {
        setBrands(data || []);
        if (data?.length > 0) {
          setSelectedBrandId(data[0].id.toString());
        }
      })
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-black text-white p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <Film className="w-6 h-6 text-purple-400" />
              <span>Move Studio (Motion Video Generation)</span>
            </h1>
            <span className="px-2.5 py-0.5 bg-purple-500/10 border border-purple-500/30 text-purple-400 text-xs font-mono font-bold rounded-full">
              MOT-WF-001
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Generate high-fashion AI motion clips, runway pacing walks, and fabric drape dynamics.
          </p>
        </div>

        {/* Brand Selector */}
        <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 px-3 py-2 rounded-xl">
          <span className="text-xs text-zinc-500 font-medium">Active Brand:</span>
          <select
            value={selectedBrandId}
            onChange={(e) => setSelectedBrandId(e.target.value)}
            className="bg-transparent text-xs text-white font-medium focus:outline-none cursor-pointer"
          >
            {brands.map((b) => (
              <option key={b.id} value={b.id} className="bg-zinc-900 text-white">
                {b.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Motion Video Selector & Job Dispatch Studio */}
      <MotionPresetSelector brandId={selectedBrandId} />
    </div>
  );
}
