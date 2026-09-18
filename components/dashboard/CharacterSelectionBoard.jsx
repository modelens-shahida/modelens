"use client";

import React from "react";
import { User, Check, Sparkles, Layers, ArrowRight } from "lucide-react";
import { CHARACTER_STATUS } from "@/lib/characterSchema";

export default function CharacterSelectionBoard({
  characters = [],
  selectedCharacterId,
  onSelectCharacter,
  activeStudioName = "Studio",
}) {
  return (
    <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 backdrop-blur-md shadow-xl mb-6">
      <div className="flex items-center justify-between mb-4 border-b border-zinc-800 pb-3">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <User className="w-4 h-4 text-cyan-400" />
            <span>Select Model Character ({activeStudioName})</span>
          </h3>
          <p className="text-[11px] text-zinc-400 mt-0.5">
            Universal character registry. Referencing canonical ID across all studios.
          </p>
        </div>
        <span className="text-xs font-mono text-zinc-500">{characters.length} Models Available</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
        {characters.map((char) => {
          const isSelected = selectedCharacterId === char.id;
          const statusCfg = CHARACTER_STATUS[char.status] || CHARACTER_STATUS.VALIDATION;

          return (
            <div
              key={char.id}
              onClick={() => onSelectCharacter && onSelectCharacter(char.id)}
              className={`group cursor-pointer border rounded-xl p-3.5 transition-all flex items-center justify-between ${
                isSelected
                  ? "bg-cyan-500/10 border-cyan-500/60 shadow-lg shadow-cyan-500/5 ring-1 ring-cyan-500/30"
                  : "bg-zinc-950/70 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/50"
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center font-mono font-bold text-xs ${
                    isSelected
                      ? "bg-cyan-500 text-black shadow-md shadow-cyan-500/20"
                      : "bg-zinc-800 text-zinc-300 group-hover:bg-zinc-700"
                  }`}
                >
                  {char.internal_code?.substring(0, 4) || "CHAR"}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold text-white group-hover:text-cyan-400 transition-colors">
                      {char.display_name}
                    </h4>
                    <span className={`px-2 py-0.5 text-[9px] font-semibold rounded-full border ${statusCfg.color}`}>
                      v{char.version}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500 mt-0.5">
                    <span className="font-mono">ID: {char.id}</span>
                    <span>•</span>
                    <span>{char.gender_presentation}</span>
                  </div>
                </div>
              </div>

              <div>
                {isSelected ? (
                  <div className="w-6 h-6 rounded-full bg-cyan-500 text-black flex items-center justify-center shadow-md shadow-cyan-500/30">
                    <Check className="w-3.5 h-3.5 stroke-[3]" />
                  </div>
                ) : (
                  <div className="w-6 h-6 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-600 group-hover:text-zinc-300 flex items-center justify-center">
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
