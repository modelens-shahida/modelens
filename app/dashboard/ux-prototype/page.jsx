"use client";

import React, { useState } from "react";
import { Sparkles, ArrowRight, ArrowLeft, LayoutDashboard, Users, User, Camera, Layers, CheckCircle2, ShieldCheck, Grid, Video, PenTool } from "lucide-react";
import Link from "next/link";

import StudioQuickLaunchCard from "@/components/dashboard/StudioQuickLaunchCard";
import CharacterProfileCard from "@/components/dashboard/CharacterProfileCard";
import CharacterDnaTabs from "@/components/dashboard/CharacterDnaTabs";
import CharacterAngleGallery from "@/components/dashboard/CharacterAngleGallery";
import CharacterQaGrid from "@/components/dashboard/CharacterQaGrid";
import ProductionComposer from "@/components/dashboard/ProductionComposer";
import GenerationProgressMonitor from "@/components/dashboard/GenerationProgressMonitor";
import ReviewComparisonWorkspace from "@/components/dashboard/ReviewComparisonWorkspace";

import { MOCK_ELISKA_CHARACTER, CHARACTER_STATUS } from "@/lib/characterSchema";

export default function UxPrototypeControllerPage() {
  const [currentStep, setCurrentStep] = useState(1); // 1 to 6

  const steps = [
    { num: 1, name: "Dashboard", href: "/dashboard" },
    { num: 2, name: "Character Library", href: "/dashboard/characters" },
    { num: 3, name: "Eliska Character Detail", href: "/dashboard/characters/EE-F-002" },
    { num: 4, name: "Create Production", href: "/dashboard/create" },
    { num: 5, name: "Generation", href: "/dashboard/generation/JOB-001" },
    { num: 6, name: "Results / QA", href: "/dashboard/results/AST-001" },
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 space-y-6">
      {/* Top Prototype Navigation Controller */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 backdrop-blur-md shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-500/10 border border-cyan-500/30 rounded-xl text-cyan-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-extrabold text-white tracking-tight">
              ModeLens UX Prototype — Phase 1 Core Journey
            </h1>
            <p className="text-xs text-zinc-400">
              Interactive walkthrough of Shahida's 6 priority desktop-first screens.
            </p>
          </div>
        </div>

        {/* Step Indicator Buttons */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {steps.map((step) => {
            const active = currentStep === step.num;
            return (
              <button
                key={step.num}
                onClick={() => setCurrentStep(step.num)}
                className={`px-3 py-1.5 text-xs font-mono font-semibold rounded-xl border transition-all flex items-center gap-1.5 whitespace-nowrap ${
                  active
                    ? "bg-cyan-500 text-black border-cyan-400 shadow-md shadow-cyan-500/20"
                    : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:border-zinc-700 hover:text-white"
                }`}
              >
                <span>{step.num}. {step.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Screen Render Switcher */}
      <div className="transition-all duration-300">
        {/* Screen 1: Dashboard */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
              <div>
                <h2 className="text-2xl font-bold text-white">Good morning, Shahida</h2>
                <p className="text-xs text-zinc-400">ModeLens Fashion Production Operating System</p>
              </div>
              <button
                onClick={() => setCurrentStep(4)}
                className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs px-4 py-2.5 rounded-xl shadow-lg shadow-cyan-500/20 flex items-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                <span>+ CREATE PRODUCTION</span>
              </button>
            </div>

            {/* Studios Quick Launch Grid */}
            <div>
              <h3 className="text-xs font-mono font-semibold text-zinc-400 uppercase tracking-wider mb-3">
                Production Studios
              </h3>
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

            {/* Needs Attention & Status */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <span className="text-zinc-500">Active Projects</span>
                <p className="text-xl font-bold text-white mt-1">8</p>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <span className="text-zinc-500">Generating Jobs</span>
                <p className="text-xl font-bold text-amber-400 mt-1">24</p>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <span className="text-zinc-500">Ready for Review</span>
                <p className="text-xl font-bold text-cyan-400 mt-1">16</p>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <span className="text-zinc-500">Completed Production</span>
                <p className="text-xl font-bold text-emerald-400 mt-1">142</p>
              </div>
            </div>
          </div>
        )}

        {/* Screen 2: Character Library */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
              <div>
                <h2 className="text-2xl font-bold text-white">Model Casting Board (Character Library)</h2>
                <p className="text-xs text-zinc-400">Browse ModeLens model identity packages</p>
              </div>
              <button
                onClick={() => setCurrentStep(3)}
                className="bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-bold text-xs px-4 py-2 rounded-xl flex items-center gap-2"
              >
                <span>Inspect Eliska Novak Profile</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div
                onClick={() => setCurrentStep(3)}
                className="cursor-pointer bg-zinc-900 border border-zinc-800 hover:border-cyan-500/50 rounded-2xl p-6 transition-all space-y-4"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-cyan-400 font-bold">EE-F-002</span>
                  <span className="px-2.5 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold rounded-full">
                    PRODUCTION
                  </span>
                </div>
                <h3 className="text-xl font-bold text-white">ELISKA NOVAK</h3>
                <p className="text-xs text-zinc-400">178 cm • Tall • High-Fashion Runway Slim</p>
                <div className="aspect-[3/4] bg-zinc-950 rounded-xl flex items-center justify-center border border-zinc-800 text-zinc-600">
                  <User className="w-12 h-12 stroke-[1]" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Screen 3: Eliska Character Detail */}
        {currentStep === 3 && (
          <div className="space-y-6">
            <CharacterProfileCard character={MOCK_ELISKA_CHARACTER} />
            <CharacterDnaTabs character={MOCK_ELISKA_CHARACTER} />
            <CharacterAngleGallery character={MOCK_ELISKA_CHARACTER} />
            <CharacterQaGrid character={MOCK_ELISKA_CHARACTER} />
          </div>
        )}

        {/* Screen 4: Create Production */}
        {currentStep === 4 && (
          <ProductionComposer onGenerate={() => setCurrentStep(5)} />
        )}

        {/* Screen 5: Generation Progress */}
        {currentStep === 5 && (
          <GenerationProgressMonitor onComplete={() => setCurrentStep(6)} />
        )}

        {/* Screen 6: Results / QA Workspace */}
        {currentStep === 6 && (
          <ReviewComparisonWorkspace />
        )}
      </div>

      {/* Bottom Interactive Flow Controller Bar */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 flex items-center justify-between text-xs font-mono">
        <button
          onClick={() => setCurrentStep(Math.max(1, currentStep - 1))}
          disabled={currentStep === 1}
          className="flex items-center gap-2 text-zinc-400 hover:text-white disabled:opacity-30 disabled:hover:text-zinc-400"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Previous Screen</span>
        </button>

        <span className="text-zinc-500">
          Step {currentStep} of {steps.length}: <strong className="text-cyan-400">{steps[currentStep - 1].name}</strong>
        </span>

        <button
          onClick={() => setCurrentStep(Math.min(6, currentStep + 1))}
          disabled={currentStep === 6}
          className="flex items-center gap-2 text-cyan-400 hover:text-cyan-300 font-bold disabled:opacity-30 disabled:hover:text-cyan-400"
        >
          <span>Next Screen</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
