"use client";

import React from "react";
import { useRouter } from "next/navigation";
import ProductionComposer from "@/components/dashboard/ProductionComposer";

export default function CreateProductionPage() {
  const router = useRouter();

  const handleGenerate = (data) => {
    // Navigate to Generation Progress screen
    router.push("/dashboard/generation/JOB-SPRING-2027-001");
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <ProductionComposer onGenerate={handleGenerate} />
    </div>
  );
}
