"use client";

import React from "react";
import Link from "next/link";
import GenerationProgressMonitor from "@/components/dashboard/GenerationProgressMonitor";
import { ArrowLeft, ArrowRight } from "lucide-react";

export default function GenerationProgressPage({ params }) {
  const jobId = params?.id || "JOB-SPRING-2027-001";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 space-y-6">
      <div className="max-w-5xl mx-auto flex items-center justify-between">
        <Link
          href="/dashboard/create"
          className="flex items-center gap-2 text-xs font-semibold text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Photoshoot Composer</span>
        </Link>

        <Link
          href="/dashboard/results/AST-2027-001"
          className="flex items-center gap-2 text-xs font-bold text-cyan-400 hover:text-cyan-300 transition-colors bg-cyan-500/10 border border-cyan-500/30 px-4 py-2 rounded-xl"
        >
          <span>View Completed Results Workspace</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      <GenerationProgressMonitor jobId={jobId} />
    </div>
  );
}
