"use client";

import React from "react";
import { CHARACTER_STATUS } from "@/lib/characterSchema";
import { User, ShieldCheck, Ruler, Activity, Layers, Lock, Sparkles } from "lucide-react";

export default function CharacterProfileCard({ character }) {
  if (!character) return null;

  const statusConfig = CHARACTER_STATUS[character.status] || CHARACTER_STATUS.VALIDATION;

  return (
    <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl">
      {/* Header Row */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800/80 pb-5">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-xl bg-gradient-to-tr from-cyan-500/20 via-indigo-500/20 to-purple-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold text-xl shadow-inner">
            {character.internal_code?.substring(0, 4) || "CHAR"}
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white tracking-tight">{character.display_name}</h1>
              <span className={`px-3 py-0.5 text-xs font-semibold rounded-full border ${statusConfig.color}`}>
                {statusConfig.label}
              </span>
            </div>
            <div className="flex items-center gap-4 text-xs text-zinc-400 mt-1">
              <span className="flex items-center gap-1 font-mono text-zinc-300">
                <span className="text-zinc-500">ID:</span> {character.id}
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                <span>Version: <strong className="text-white">v{character.version}</strong></span>
              </span>
              <span>•</span>
              <span className="flex items-center gap-1 text-zinc-400">
                <User className="w-3.5 h-3.5 text-cyan-400" />
                <span>{character.gender_presentation}</span>
              </span>
            </div>
          </div>
        </div>

        {/* Lock / Validation Indicator */}
        <div className="flex items-center gap-3 self-start md:self-auto">
          {character.is_locked_production ? (
            <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium">
              <Lock className="w-3.5 h-3.5" />
              <span>Production V1.0 Locked</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-medium">
              <Sparkles className="w-3.5 h-3.5 animate-pulse" />
              <span>Angle Gate Active (Validation)</span>
            </div>
          )}
        </div>
      </div>

      {/* Structured Body Scale & Demographic Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5">
        <div className="bg-zinc-950/60 border border-zinc-800/60 rounded-xl p-3.5">
          <div className="flex items-center gap-2 text-xs text-zinc-400 mb-1">
            <Ruler className="w-3.5 h-3.5 text-cyan-400" />
            <span>Canonical Height</span>
          </div>
          <p className="text-sm font-semibold text-white">
            {character.body_metrics?.canonical_height_cm} cm
          </p>
          <span className="text-[10px] text-zinc-500">Stature: {character.body_metrics?.stature_class}</span>
        </div>

        <div className="bg-zinc-950/60 border border-zinc-800/60 rounded-xl p-3.5">
          <div className="flex items-center gap-2 text-xs text-zinc-400 mb-1">
            <Activity className="w-3.5 h-3.5 text-purple-400" />
            <span>Body Archetype</span>
          </div>
          <p className="text-sm font-semibold text-white truncate">
            {character.body_metrics?.body_archetype}
          </p>
          <span className="text-[10px] text-zinc-500">BWH: {character.body_metrics?.bust_waist_hip}</span>
        </div>

        <div className="bg-zinc-950/60 border border-zinc-800/60 rounded-xl p-3.5">
          <div className="flex items-center gap-2 text-xs text-zinc-400 mb-1">
            <User className="w-3.5 h-3.5 text-emerald-400" />
            <span>Age Range</span>
          </div>
          <p className="text-sm font-semibold text-white">
            {character.age_range}
          </p>
          <span className="text-[10px] text-zinc-500">Anchor: {character.ethnicity_anchor}</span>
        </div>

        <div className="bg-zinc-950/60 border border-zinc-800/60 rounded-xl p-3.5">
          <div className="flex items-center gap-2 text-xs text-zinc-400 mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
            <span>Profile Status</span>
          </div>
          <p className="text-xs font-semibold text-cyan-400 truncate mt-0.5">
            {character.body_metrics?.body_profile_status}
          </p>
          <span className="text-[10px] text-zinc-500">Shoe EU: {character.body_metrics?.shoe_size_eu}</span>
        </div>
      </div>
    </div>
  );
}
