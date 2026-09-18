"use client";

import React from "react";
import Link from "next/link";
import ReviewComparisonWorkspace from "@/components/dashboard/ReviewComparisonWorkspace";
import { ArrowLeft } from "lucide-react";

export default function ResultsQaPage({ params }) {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 space-y-6">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <Link
          href="/dashboard"
          className="flex items-center gap-2 text-xs font-semibold text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>
      </div>

      <ReviewComparisonWorkspace />
    </div>
  );
}
