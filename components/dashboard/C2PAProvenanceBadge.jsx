"use client";

import React, { useState } from "react";
import { ShieldCheck, Lock, Fingerprint } from "lucide-react";
import C2PAProvenanceModal from "@/components/dashboard/C2PAProvenanceModal";

export default function C2PAProvenanceBadge({ 
  assetId, 
  assetName = "Asset", 
  variant = "badge", // "badge" | "button" | "pill" | "icon"
  className = "" 
}) {
  const [isOpen, setIsOpen] = useState(false);

  if (!assetId) return null;

  return (
    <>
      {variant === "icon" ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsOpen(true);
          }}
          className={`p-1 rounded-md bg-emerald-950/80 hover:bg-emerald-900 text-emerald-400 border border-emerald-800 transition ${className}`}
          title="View C2PA Content Credentials"
        >
          <Lock className="w-3 h-3" />
        </button>
      ) : variant === "pill" ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsOpen(true);
          }}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/80 hover:bg-emerald-900/90 text-emerald-300 border border-emerald-700/80 text-[10px] font-mono font-bold tracking-wide transition shadow-sm ${className}`}
          title="Cryptographically Signed C2PA Deliverable"
        >
          <ShieldCheck className="w-3 h-3 text-emerald-400" />
          <span>C2PA Verified</span>
        </button>
      ) : variant === "button" ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsOpen(true);
          }}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-emerald-300 border border-zinc-800 text-xs font-medium transition ${className}`}
          title="Inspect C2PA Content Credentials"
        >
          <Lock className="w-3 h-3 text-emerald-400" />
          <span>C2PA</span>
        </button>
      ) : (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsOpen(true);
          }}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-gradient-to-r from-emerald-950/90 to-zinc-900 hover:from-emerald-900/90 hover:to-zinc-850 text-emerald-300 border border-emerald-700/70 text-xs font-mono font-semibold transition shadow-md shadow-emerald-950/30 ${className}`}
          title="Inspect C2PA Cryptographic Provenance"
        >
          <Fingerprint className="w-3.5 h-3.5 text-emerald-400" />
          <span>🔒 C2PA Verified</span>
        </button>
      )}

      {/* C2PA Provenance Modal */}
      {isOpen && (
        <C2PAProvenanceModal
          isOpen={isOpen}
          onClose={() => setIsOpen(false)}
          assetId={assetId}
          assetName={assetName}
        />
      )}
    </>
  );
}
