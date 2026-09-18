"use client";

import React from "react";
import Link from "next/link";
import { Camera, PenTool, Grid, Video, ArrowUpRight, Sparkles } from "lucide-react";

export default function StudioQuickLaunchCard({
  id,
  title,
  subtitle,
  description,
  href,
  iconName,
  accentColor = "cyan",
  badge,
}) {
  const getIcon = () => {
    switch (iconName) {
      case "ghost":
        return <Camera className="w-6 h-6 text-cyan-400" />;
      case "sketch":
        return <PenTool className="w-6 h-6 text-purple-400" />;
      case "catalog":
        return <Grid className="w-6 h-6 text-emerald-400" />;
      case "move":
        return <Video className="w-6 h-6 text-amber-400" />;
      default:
        return <Sparkles className="w-6 h-6 text-cyan-400" />;
    }
  };

  const borderHover = {
    cyan: "hover:border-cyan-500/50 hover:shadow-cyan-500/10",
    purple: "hover:border-purple-500/50 hover:shadow-purple-500/10",
    emerald: "hover:border-emerald-500/50 hover:shadow-emerald-500/10",
    amber: "hover:border-amber-500/50 hover:shadow-amber-500/10",
  }[accentColor] || "hover:border-cyan-500/50";

  return (
    <Link
      href={href}
      className={`group relative bg-zinc-950/80 border border-zinc-800/80 rounded-2xl p-5 transition-all duration-300 backdrop-blur-md shadow-xl flex flex-col justify-between ${borderHover}`}
    >
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl group-hover:scale-105 transition-transform">
            {getIcon()}
          </div>

          <div className="flex items-center gap-2">
            {badge && (
              <span className="px-2.5 py-0.5 text-[10px] font-mono font-bold rounded-full bg-zinc-800 border border-zinc-700 text-zinc-300">
                {badge}
              </span>
            )}
            <div className="w-8 h-8 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-500 group-hover:text-white group-hover:bg-zinc-800 transition-colors">
              <ArrowUpRight className="w-4 h-4" />
            </div>
          </div>
        </div>

        <h3 className="text-base font-bold text-white group-hover:text-cyan-400 transition-colors tracking-tight">
          {title}
        </h3>
        <p className="text-xs font-medium text-zinc-400 mt-0.5">{subtitle}</p>
        <p className="text-[11px] text-zinc-500 mt-2 line-clamp-2 leading-relaxed">{description}</p>
      </div>

      <div className="mt-4 pt-3 border-t border-zinc-900/80 flex items-center justify-between text-[10px] font-mono text-zinc-500 group-hover:text-zinc-400">
        <span>LAUNCH STUDIO</span>
        <span>MODIFIED TODAY</span>
      </div>
    </Link>
  );
}
