"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import ProductionComposer from "@/components/dashboard/ProductionComposer";
import { submitBatchGenerationJob } from "@/lib/generationService";
import { toast } from "react-hot-toast";

export default function CreateProductionPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  const handleGenerate = async (data) => {
    try {
      setSubmitting(true);
      const payload = {
        product_id: data.product?.id || "prod_1",
        character_id: data.character?.code || data.character?.id || "EE-F-002",
        character_version: data.character?.version || "v2.1",
        angle_slots: data.angles || ["FRONT", "L30", "R30", "L45"],
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
    </div>
  );
}

