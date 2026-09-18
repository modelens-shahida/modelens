"use client";

import React, { useState } from "react";
import Link from "next/link";
import { User, ArrowLeft, Lock, ShieldCheck, CheckCircle2, Layers, Dna, Camera, Award, Sparkles, Eye, History } from "lucide-react";
import { MOCK_ELISKA_CHARACTER, CHARACTER_STATUS } from "@/lib/characterSchema";

export default function EliskaCharacterDetailPage({ params }) {
  const [activeTab, setActiveTab] = useState("overview"); // OVERVIEW | IDENTITY | BODY | ANGLES | APPEARANCE | QA | VERSIONS

  const char = {
    ...MOCK_ELISKA_CHARACTER,
    version: "1.0",
    status: "PRODUCTION",
    is_locked_production: true,
  };

  const tabs = [
    { id: "overview", label: "OVERVIEW", icon: User },
    { id: "identity", label: "IDENTITY", icon: Eye },
    { id: "body", label: "BODY", icon: Dna },
    { id: "angles", label: "ANGLES", icon: Camera },
    { id: "appearance", label: "APPEARANCE", icon: Sparkles },
    { id: "qa", label: "QA", icon: ShieldCheck },
    { id: "versions", label: "VERSIONS", icon: History },
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 space-y-6">
      {/* Navigation Breadcrumb */}
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <Link
          href="/dashboard/characters"
          className="flex items-center gap-2 text-xs font-semibold text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Character Library (Casting Board)</span>
        </Link>
        <span className="text-xs font-mono text-zinc-500">Character Package EE-F-002</span>
      </div>

      {/* Header Row (Shahida Directive) */}
      <div className="max-w-6xl mx-auto bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-extrabold text-white tracking-tight">{char.display_name}</h1>
              <span className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-mono font-bold rounded-full">
                {char.id}
              </span>
            </div>

            <div className="flex items-center gap-3 text-xs text-zinc-400 mt-2 font-mono">
              <span>Version {char.version}</span>
              <span>•</span>
              <span className="px-2.5 py-0.5 bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-[10px] font-bold rounded-full flex items-center gap-1">
                <Lock className="w-3 h-3" />
                <span>LOCKED</span>
              </span>
              <span className="px-2.5 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold rounded-full flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" />
                <span>PRODUCTION</span>
              </span>
            </div>
          </div>

          <Link
            href="/dashboard/create"
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs px-5 py-2.5 rounded-xl transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2 self-start md:self-auto"
          >
            <Sparkles className="w-4 h-4" />
            <span>SELECT FOR PRODUCTION</span>
          </Link>
        </div>

        {/* Hero Section & Details Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-6">
          {/* Large Hero Portrait (Shahida Directive) */}
          <div className="lg:col-span-4">
            <div className="bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl relative aspect-[3/4] flex items-center justify-center group">
              <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-transparent to-transparent z-10 opacity-60" />
              <div className="text-center space-y-2 text-cyan-400/80 z-20">
                <User className="w-16 h-16 stroke-[1.2] mx-auto" />
                <span className="text-xs font-mono font-bold block text-white">HERO PORTRAIT PHOTO</span>
                <span className="text-[10px] text-zinc-500 font-mono">ELISKA NOVAK V1.0</span>
              </div>
            </div>
          </div>

          {/* Tabbed Content Area */}
          <div className="lg:col-span-8 flex flex-col justify-between">
            {/* 7 Tabs (Shahida Directive: OVERVIEW, IDENTITY, BODY, ANGLES, APPEARANCE, QA, VERSIONS) */}
            <div>
              <div className="flex items-center gap-2 border-b border-zinc-800 pb-3 overflow-x-auto scrollbar-thin">
                {tabs.map((t) => {
                  const active = activeTab === t.id;
                  const Icon = t.icon;
                  return (
                    <button
                      key={t.id}
                      onClick={() => setActiveTab(t.id)}
                      className={`px-3.5 py-2 text-xs font-bold rounded-xl border transition-all flex items-center gap-1.5 whitespace-nowrap ${active
                          ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/40 shadow-sm"
                          : "text-zinc-400 border-transparent hover:text-white hover:bg-zinc-800/50"
                        }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      <span>{t.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* Tab 1: OVERVIEW (Shahida Directive Fields) */}
              {activeTab === "overview" && (
                <div className="grid grid-cols-2 gap-4 mt-5">
                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
                    <span className="text-xs text-zinc-500 block">Height</span>
                    <p className="text-lg font-bold text-white mt-0.5">178 cm</p>
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
                    <span className="text-xs text-zinc-500 block">Stature</span>
                    <p className="text-lg font-bold text-white mt-0.5">Tall</p>
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl col-span-2">
                    <span className="text-xs text-zinc-500 block">Body Archetype</span>
                    <p className="text-base font-bold text-white mt-0.5">High-Fashion Runway Slim</p>
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
                    <span className="text-xs text-zinc-500 block">Identity Status</span>
                    <p className="text-sm font-bold text-indigo-400 mt-0.5 flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5" />
                      <span>Locked</span>
                    </p>
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
                    <span className="text-xs text-zinc-500 block">Body Profile</span>
                    <p className="text-sm font-bold text-indigo-400 mt-0.5 flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5" />
                      <span>Locked</span>
                    </p>
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl col-span-2">
                    <span className="text-xs text-zinc-500 block">Production Eligibility</span>
                    <p className="text-sm font-bold text-emerald-400 mt-0.5 flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Approved (Shahida V1.0 Cleared)</span>
                    </p>
                  </div>
                </div>
              )}

              {/* Tab 2: IDENTITY */}
              {activeTab === "identity" && (
                <div className="mt-5 space-y-3 text-xs bg-zinc-950 p-4 rounded-xl border border-zinc-800">
                  <h3 className="font-bold text-cyan-400">Facial Architecture & DNA</h3>
                  <div className="grid grid-cols-2 gap-3 text-zinc-300">
                    <div><span className="text-zinc-500">Face Shape:</span> Oval Architectural</div>
                    <div><span className="text-zinc-500">Eye Color:</span> Deep Hazel-Green</div>
                    <div><span className="text-zinc-500">Nose Bridge:</span> Refined Straight</div>
                    <div><span className="text-zinc-500">Jawline:</span> Sculpted Angular</div>
                  </div>
                </div>
              )}

              {/* Tab 3: BODY */}
              {activeTab === "body" && (
                <div className="mt-5 space-y-3 text-xs bg-zinc-950 p-4 rounded-xl border border-zinc-800">
                  <h3 className="font-bold text-purple-400">Structured Body Profile</h3>
                  <div className="grid grid-cols-2 gap-3 text-zinc-300">
                    <div><span className="text-zinc-500">HEIGHT:</span> 178 cm</div>
                    <div><span className="text-zinc-500">STATURE:</span> Tall</div>
                    <div><span className="text-zinc-500">BODY ARCHETYPE:</span> High-Fashion Runway Slim</div>
                    <div><span className="text-zinc-500">PROPORTION PROFILE:</span> EE-F-002 Body V1</div>
                  </div>
                </div>
              )}

              {/* Tab 4: ANGLES */}
              {activeTab === "angles" && (
                <div className="mt-5 space-y-4">
                  <h4 className="text-xs font-bold text-white uppercase">Half Body Angle Set</h4>
                  <div className="grid grid-cols-5 gap-2 text-center text-[10px] font-mono">
                    {["L45", "L30", "FRONT", "R30", "R45"].map((ang) => (
                      <div key={ang} className="bg-zinc-950 border border-zinc-800 p-2 rounded-lg">
                        <span className="text-cyan-400 block mb-1">{ang}</span>
                        <div className="aspect-[3/4] bg-zinc-900 rounded flex items-center justify-center text-zinc-600">
                          {ang}
                        </div>
                      </div>
                    ))}
                  </div>

                  <h4 className="text-xs font-bold text-white uppercase pt-2">Full Body Angle Set</h4>
                  <div className="grid grid-cols-5 gap-2 text-center text-[10px] font-mono">
                    {["L45", "L30", "FRONT", "R30", "R45"].map((ang) => (
                      <div key={ang} className="bg-zinc-950 border border-zinc-800 p-2 rounded-lg">
                        <span className="text-cyan-400 block mb-1">{ang}</span>
                        <div className="aspect-[3/4] bg-zinc-900 rounded flex items-center justify-center text-zinc-600">
                          {ang}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tab 5: APPEARANCE */}
              {activeTab === "appearance" && (
                <div className="mt-5 space-y-3 text-xs bg-zinc-950 p-4 rounded-xl border border-zinc-800">
                  <h3 className="font-bold text-amber-400">Skin & Hair Profile</h3>
                  <div className="grid grid-cols-2 gap-3 text-zinc-300">
                    <div><span className="text-zinc-500">Skin Tone:</span> Fair Natural Warm</div>
                    <div><span className="text-zinc-500">Texture:</span> Fine Pore Natural Matte</div>
                    <div><span className="text-zinc-500">Hair Color:</span> Dark Ash Blonde</div>
                    <div><span className="text-zinc-500">Default Style:</span> Sleek Straight Center-Part</div>
                  </div>
                </div>
              )}

              {/* Tab 6: QA */}
              {activeTab === "qa" && (
                <div className="mt-5 grid grid-cols-2 gap-3 text-xs">
                  {["Identity PASS", "Body PASS", "Half-Body PASS", "Full-Body PASS", "Hands PASS", "Feet PASS", "Training ELIGIBLE", "Production APPROVED"].map((item) => (
                    <div key={item} className="bg-zinc-950 border border-zinc-800 p-3 rounded-xl flex items-center justify-between">
                      <span className="text-white font-medium">{item.split(" ")[0]}</span>
                      <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] font-bold rounded-full border border-emerald-500/30">
                        {item.split(" ")[1]}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Tab 7: VERSIONS */}
              {activeTab === "versions" && (
                <div className="mt-5 space-y-2 text-xs">
                  <div className="bg-zinc-950 border border-cyan-500/40 p-3 rounded-xl flex items-center justify-between">
                    <div>
                      <span className="font-bold text-white">Version 1.0 (Production Lock)</span>
                      <p className="text-[10px] text-zinc-500">Shahida V1.0 Approved Package</p>
                    </div>
                    <span className="px-2.5 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] font-bold rounded-full">ACTIVE</span>
                  </div>
                  <div className="bg-zinc-950 border border-zinc-800 p-3 rounded-xl flex items-center justify-between text-zinc-400">
                    <div>
                      <span className="font-medium text-zinc-300">Version 0.8 (Validation)</span>
                      <p className="text-[10px] text-zinc-500">Aryan Angle Gate Validation</p>
                    </div>
                    <span className="text-[10px] font-mono">ARCHIVED</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
