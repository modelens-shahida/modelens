"use client";

import React, { useState } from "react";
import { CheckCircle2, RotateCcw, Edit, AlertOctagon, Download, ShieldCheck, ChevronDown, ChevronUp, Image as ImageIcon, Sparkles, Layers } from "lucide-react";
import { MOCK_ELISKA_CHARACTER } from "@/lib/characterSchema";

export default function ReviewComparisonWorkspace({
  resultAsset = {
    id: "AST-2027-001",
    angle: "L30",
    framing: "Full-Body",
    character: MOCK_ELISKA_CHARACTER,
    productName: "Silk Bias Cut Slip Dress",
    originalUrl: "/api/placeholder/450/600",
    resultUrl: "/api/placeholder/450/600",
    qaScore: {
      identity: "96.2% PASS",
      garment: "98.1% PASS",
      hands: "99.0% PASS",
      feet: "97.4% PASS",
      artifacts: "CLEAN",
    },
  },
}) {
  const [showQaDetails, setShowQaDetails] = useState(true);
  const [approvalState, setApprovalState] = useState("PENDING"); // "PENDING" | "APPROVED" | "REJECTED"

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header & Meta Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">Editorial Asset Review & QA Workspace</h1>
            <span
              className={`px-3 py-0.5 text-xs font-mono font-bold rounded-full border ${
                approvalState === "APPROVED"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/30"
              }`}
            >
              {approvalState}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1 font-mono">
            Asset ID: {resultAsset.id} • Angle: {resultAsset.angle} ({resultAsset.framing})
          </p>
        </div>

        {/* Action Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setApprovalState("APPROVED")}
            className="flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs px-4 py-2 rounded-xl transition-all shadow-md shadow-emerald-500/20"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>APPROVE</span>
          </button>

          <button className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 px-3.5 py-2 rounded-xl transition-all">
            <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />
            <span>REGENERATE</span>
          </button>

          <button className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 px-3.5 py-2 rounded-xl transition-all">
            <Edit className="w-3.5 h-3.5 text-purple-400" />
            <span>EDIT CANVAS</span>
          </button>

          <button className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs text-rose-400 px-3.5 py-2 rounded-xl transition-all">
            <AlertOctagon className="w-3.5 h-3.5" />
            <span>REPORT ISSUE</span>
          </button>

          <button className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 px-3.5 py-2 rounded-xl transition-all">
            <Download className="w-3.5 h-3.5" />
            <span>EXPORT</span>
          </button>
        </div>
      </div>

      {/* Split-Screen Review Workspace (Original vs Generated Result) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Original Product Panel */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 backdrop-blur-md shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
              Original Garment Input
            </span>
            <span className="text-[11px] text-zinc-500">{resultAsset.productName}</span>
          </div>

          <div className="aspect-[3/4] bg-zinc-950 rounded-xl border border-zinc-800/80 flex items-center justify-center relative overflow-hidden group">
            <div className="text-center space-y-2 text-zinc-600">
              <ImageIcon className="w-12 h-12 mx-auto stroke-[1]" />
              <span className="text-xs font-mono text-zinc-500 block">ORIGINAL FLAT LAY INPUT</span>
            </div>
          </div>
        </div>

        {/* Generated Result Panel */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 backdrop-blur-md shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <span className="text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              <span>AI Generated Editorial Result</span>
            </span>
            <span className="text-[11px] text-zinc-400">Model: {resultAsset.character.display_name}</span>
          </div>

          <div className="aspect-[3/4] bg-zinc-950 rounded-xl border border-cyan-500/30 flex items-center justify-center relative overflow-hidden group shadow-inner">
            <div className="text-center space-y-2 text-cyan-400/80">
              <ImageIcon className="w-12 h-12 mx-auto stroke-[1.5]" />
              <span className="text-xs font-mono block text-cyan-400">GENERATED RESULT ({resultAsset.angle})</span>
            </div>
          </div>
        </div>
      </div>

      {/* Expandable Technical QA Details Breakdown */}
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl overflow-hidden backdrop-blur-md">
        <button
          onClick={() => setShowQaDetails(!showQaDetails)}
          className="w-full px-6 py-4 text-xs font-bold text-white flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
            <span>Automated QA & High-Precision Quality Metrics</span>
          </div>
          <div className="flex items-center gap-2 text-zinc-400">
            <span>{showQaDetails ? "Collapse Details" : "Expand Details"}</span>
            {showQaDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {showQaDetails && (
          <div className="p-6 border-t border-zinc-800 grid grid-cols-2 md:grid-cols-5 gap-4 text-xs">
            <div className="bg-zinc-950 border border-zinc-800/80 p-3.5 rounded-xl">
              <span className="text-zinc-500 block text-[10px] uppercase">Identity Similarity</span>
              <p className="font-bold text-emerald-400 mt-1">{resultAsset.qaScore.identity}</p>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 p-3.5 rounded-xl">
              <span className="text-zinc-500 block text-[10px] uppercase">Garment Fidelity</span>
              <p className="font-bold text-emerald-400 mt-1">{resultAsset.qaScore.garment}</p>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 p-3.5 rounded-xl">
              <span className="text-zinc-500 block text-[10px] uppercase">Hands Anatomy</span>
              <p className="font-bold text-emerald-400 mt-1">{resultAsset.qaScore.hands}</p>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 p-3.5 rounded-xl">
              <span className="text-zinc-500 block text-[10px] uppercase">Feet Grounding</span>
              <p className="font-bold text-emerald-400 mt-1">{resultAsset.qaScore.feet}</p>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 p-3.5 rounded-xl">
              <span className="text-zinc-500 block text-[10px] uppercase">Artifact Audit</span>
              <p className="font-bold text-cyan-400 mt-1">{resultAsset.qaScore.artifacts}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
