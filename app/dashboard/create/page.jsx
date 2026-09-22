"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import ProductionComposer from "@/components/dashboard/ProductionComposer";
import { submitBatchGenerationJob, checkSufficientCredits } from "@/lib/generationService";
import { toast } from "react-hot-toast";
import { AlertCircle, CreditCard, ArrowRight, X } from "lucide-react";
import Link from "next/link";

export default function CreateProductionPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [shortfallModal, setShortfallModal] = useState(null); // { required, balance, shortfall }

  const handleGenerate = async (data) => {
    try {
      setSubmitting(true);
      const angles = data.angles || ["FRONT", "L30", "R30", "L45"];
      const qMode = data.quality === "fast_draft" ? "FAST_DRAFT" : "STUDIO_QUALITY";

      // 1. Pre-flight credit check
      const creditCheck = await checkSufficientCredits({
        quality_mode: qMode,
        resolution: "2K",
        angle_count: angles.length,
      });

      if (creditCheck && !creditCheck.sufficient) {
        setShortfallModal({
          required: creditCheck.required,
          balance: creditCheck.balance,
          shortfall: creditCheck.shortfall,
        });
        setSubmitting(false);
        return;
      }

      // 2. Dispatch batch generation job
      const payload = {
        product_id: data.product?.id || "prod_1",
        character_id: data.character?.code || data.character?.id || "EE-F-002",
        character_version: data.character?.version || "v2.1",
        angle_slots: angles,
        environment_id: data.background?.id || "bg_1",
        quality_mode: data.quality || "studio_quality",
        parallel: data.parallel ?? true,
      };

      const res = await submitBatchGenerationJob(payload);
      const targetJobId = res.job_id || "JOB-SPRING-2027-001";
      toast.success(`Batch generation initiated: ${targetJobId}`);
      router.push(`/dashboard/generation/${targetJobId}`);
    } catch (error) {
      toast.error(error.message || "Failed to initiate generation");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <ProductionComposer onGenerate={handleGenerate} isSubmitting={submitting} />

      {/* Insufficient Credits Alert Modal */}
      {shortfallModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 w-full max-w-md rounded-2xl p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2 text-amber-400">
                <AlertCircle className="w-5 h-5" />
                <h3 className="text-base font-bold text-white">Insufficient Credits</h3>
              </div>
              <button onClick={() => setShortfallModal(null)} className="text-zinc-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-zinc-300 leading-relaxed">
                This batch photoshoot requires <strong className="text-white font-mono">{shortfallModal.required} credits</strong>, but your brand balance is currently <strong className="text-amber-400 font-mono">{shortfallModal.balance} credits</strong>.
              </p>

              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-2">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Required for Shoot:</span>
                  <span className="font-mono text-white font-bold">{shortfallModal.required} cr</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Available Balance:</span>
                  <span className="font-mono text-zinc-400">{shortfallModal.balance} cr</span>
                </div>
                <div className="flex justify-between border-t border-zinc-800 pt-2 text-rose-400 font-bold">
                  <span>Credit Shortfall:</span>
                  <span className="font-mono">-{shortfallModal.shortfall} cr</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setShortfallModal(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-zinc-400 hover:text-white"
              >
                Cancel
              </button>
              <Link
                href="/dashboard/billing"
                className="flex items-center gap-2 bg-gradient-to-r from-amber-500 to-cyan-500 text-black font-extrabold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-amber-500/20"
              >
                <CreditCard className="w-4 h-4" />
                <span>Top Up Credits</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


