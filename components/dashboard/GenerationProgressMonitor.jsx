"use client";

import React from "react";
import { Loader2, CheckCircle2, Clock, Sparkles, Layers, Image as ImageIcon, ArrowLeft } from "lucide-react";

export default function GenerationProgressMonitor({
  jobId = "JOB-SPRING-2027-001",
  projectName = "Spring 2027 Runway Campaign",
  characterName = "ELISKA NOVAK (EE-F-002)",
  productName = "Silk Bias Cut Slip Dress",
  progressPercent = 75,
  completedCount = 12,
  totalCount = 16,
  onComplete,
}) {
  const tiles = [
    { id: 1, angle: "FRONT", status: "COMPLETED", duration: "4.2s" },
    { id: 2, angle: "L30", status: "COMPLETED", duration: "3.9s" },
    { id: 3, angle: "R30", status: "COMPLETED", duration: "4.1s" },
    { id: 4, angle: "L45", status: "GENERATING", duration: "In Progress..." },
    { id: 5, angle: "R45", status: "QUEUED", duration: "Waiting..." },
    { id: 6, angle: "L90", status: "QUEUED", duration: "Waiting..." },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Top Header & Job ID */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white tracking-tight">{projectName}</h1>
              <span className="px-3 py-0.5 bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-mono font-semibold rounded-full flex items-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>GENERATING</span>
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-1 font-mono">Job ID: {jobId}</p>
          </div>

          <div className="text-right">
            <span className="text-[10px] font-mono text-zinc-500 uppercase">Progress Status</span>
            <p className="text-lg font-bold text-cyan-400 mt-0.5">
              {completedCount} / {totalCount} Complete ({progressPercent}%)
            </p>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-5 space-y-2">
          <div className="w-full h-3 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800 p-0.5">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-indigo-500 rounded-full transition-all duration-500 shadow-sm"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[11px] text-zinc-500">
            <span>Asynchronous execution active — you may safely leave this page.</span>
            <span>Estimated time remaining: 12 seconds</span>
          </div>
        </div>
      </div>

      {/* Active Job Parameters Summary */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        <div>
          <span className="text-zinc-500">Model Character</span>
          <p className="font-semibold text-white mt-0.5">{characterName}</p>
        </div>
        <div>
          <span className="text-zinc-500">Target Product</span>
          <p className="font-semibold text-white mt-0.5">{productName}</p>
        </div>
        <div>
          <span className="text-zinc-500">Background</span>
          <p className="font-semibold text-white mt-0.5">Studio Grey Minimal</p>
        </div>
        <div>
          <span className="text-zinc-500">Quality Preset</span>
          <p className="font-semibold text-cyan-400 mt-0.5">Studio Quality (4K)</p>
        </div>
      </div>

      {/* Streaming Result Tiles */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl">
        <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <span>Real-Time Streaming Generation Tiles</span>
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
          {tiles.map((tile) => (
            <div
              key={tile.id}
              className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden shadow-md flex flex-col justify-between"
            >
              <div className="px-2.5 py-1.5 bg-zinc-900/80 border-b border-zinc-800 text-[10px] font-mono font-bold text-white flex items-center justify-between">
                <span>{tile.angle}</span>
                {tile.status === "COMPLETED" && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
                {tile.status === "GENERATING" && <Loader2 className="w-3 h-3 text-amber-400 animate-spin" />}
                {tile.status === "QUEUED" && <Clock className="w-3 h-3 text-zinc-600" />}
              </div>

              <div className="aspect-[3/4] bg-zinc-900 flex items-center justify-center p-3 relative">
                {tile.status === "COMPLETED" && (
                  <div className="text-center space-y-1">
                    <ImageIcon className="w-8 h-8 text-emerald-400 mx-auto" />
                    <span className="text-[9px] font-mono text-emerald-400 block">READY FOR QA</span>
                  </div>
                )}
                {tile.status === "GENERATING" && (
                  <div className="text-center space-y-1">
                    <Sparkles className="w-8 h-8 text-amber-400 animate-pulse mx-auto" />
                    <span className="text-[9px] font-mono text-amber-400 block">RENDERING...</span>
                  </div>
                )}
                {tile.status === "QUEUED" && (
                  <div className="text-center space-y-1 opacity-50">
                    <Clock className="w-8 h-8 text-zinc-600 mx-auto" />
                    <span className="text-[9px] font-mono text-zinc-600 block">QUEUED</span>
                  </div>
                )}
              </div>

              <div className="px-2.5 py-1.5 bg-zinc-950 text-[9px] font-mono text-zinc-500 border-t border-zinc-900">
                {tile.duration}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
