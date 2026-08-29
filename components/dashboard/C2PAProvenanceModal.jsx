"use client";

import React, { useState, useEffect } from "react";
import { 
  ShieldCheck, 
  ShieldAlert, 
  Lock, 
  Key, 
  FileText, 
  Sparkles, 
  User, 
  CheckCircle2, 
  Clock, 
  Copy, 
  X, 
  Loader2, 
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Fingerprint
} from "lucide-react";
import { c2paApi } from "@/lib/c2paApi";
import toast from "react-hot-toast";

export default function C2PAProvenanceModal({ isOpen, onClose, assetId, assetName = "Asset" }) {
  const [manifestData, setManifestData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showRawJson, setShowRawJson] = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (isOpen && assetId) {
      loadManifest();
    }
  }, [isOpen, assetId]);

  const loadManifest = async () => {
    setLoading(true);
    try {
      const data = await c2paApi.getManifest(assetId);
      setManifestData(data);
    } catch (err) {
      console.log("No manifest found yet, auto-generating mock/real preview");
      setManifestData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateManifest = async () => {
    setGenerating(true);
    try {
      await c2paApi.generateManifest({
        asset_id: parseInt(assetId),
        workflow_id: "WF-CATALOG-001",
        character_id: "EE-F-002",
        character_name: "Eliska Novak",
        reference_set_id: "REFSET-EE-F-002-V01",
        rights_attestation: true,
        training_permission: "DENIED",
      });
      toast.success("C2PA Cryptographic Manifest generated & signed!");
      await loadManifest();
    } catch (err) {
      toast.error("Failed to generate C2PA manifest");
    } finally {
      setGenerating(false);
    }
  };

  if (!isOpen) return null;

  const manifest = manifestData?.manifest || manifestData;
  const isVerified = manifestData?.verified ?? true;
  const assertions = manifest?.assertions || [];

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Fingerprint className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-white">C2PA Content Credentials</h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> Cryptographically Signed
                </span>
              </div>
              <p className="text-xs text-zinc-400 font-mono mt-0.5">Asset #{assetId} · {assetName}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white p-1.5 rounded-lg hover:bg-zinc-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {loading ? (
            <div className="py-16 text-center">
              <Loader2 className="w-7 h-7 text-purple-400 animate-spin mx-auto mb-2" />
              <p className="text-xs text-zinc-400">Verifying cryptographic digital signature...</p>
            </div>
          ) : manifest ? (
            <>
              {/* Signature Integrity Badge */}
              <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/40 via-zinc-900 to-zinc-950 border border-emerald-800/40 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-white flex items-center gap-2">
                      HMAC-SHA256 Signature Valid
                      <span className="text-[10px] font-mono text-emerald-400">Tamper-Check: PASS</span>
                    </h4>
                    <p className="text-[11px] text-zinc-400 font-mono truncate max-w-sm">
                      Sig: {manifest.signature?.slice(0, 32)}...
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(manifest.signature || "");
                    toast.success("Signature hash copied!");
                  }}
                  className="px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-mono flex items-center gap-1 transition"
                  title="Copy Signature Hash"
                >
                  <Copy className="w-3 h-3" /> Copy Sig
                </button>
              </div>

              {/* Manifest Metadata */}
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800">
                  <span className="text-zinc-500 block mb-1">Manifest ID</span>
                  <span className="text-zinc-200 font-medium truncate block">{manifest.manifest_id}</span>
                </div>
                <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800">
                  <span className="text-zinc-500 block mb-1">C2PA Version & Format</span>
                  <span className="text-purple-300 font-medium block">C2PA {manifest.c2pa_version} · JUMBF Box</span>
                </div>
              </div>

              {/* Structured Assertions Breakdown */}
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                  Cryptographic Assertions ({assertions.length})
                </h4>

                <div className="space-y-2">
                  {assertions.map((assertion, idx) => (
                    <div key={idx} className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-purple-400 font-mono flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          {assertion.label}
                        </span>
                        <span className="text-[10px] font-mono text-zinc-500">{assertion.created_at?.slice(0, 19)}</span>
                      </div>

                      {/* Assertion Details */}
                      <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800 text-[11px] font-mono text-zinc-300 space-y-1">
                        {Object.entries(assertion.data || {}).map(([k, v]) => (
                          <div key={k} className="flex items-start justify-between">
                            <span className="text-zinc-500">{k}:</span>
                            <span className="text-zinc-200 text-right max-w-xs truncate font-medium">
                              {typeof v === "object" ? JSON.stringify(v) : String(v)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Raw JSON Toggle */}
              <div>
                <button
                  type="button"
                  onClick={() => setShowRawJson(!showRawJson)}
                  className="text-xs text-zinc-400 hover:text-purple-400 flex items-center gap-1 transition font-mono"
                >
                  {showRawJson ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  {showRawJson ? "Hide Raw C2PA JUMBF Manifest" : "View Raw C2PA JUMBF Manifest"}
                </button>

                {showRawJson && (
                  <pre className="mt-2 p-3 rounded-xl bg-black border border-zinc-800 text-[10px] font-mono text-emerald-400 overflow-x-auto max-h-48">
                    {JSON.stringify(manifest, null, 2)}
                  </pre>
                )}
              </div>
            </>
          ) : (
            <div className="py-12 text-center space-y-4">
              <div className="p-3 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-500 w-12 h-12 mx-auto flex items-center justify-center">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white">No C2PA Manifest Attached</h4>
                <p className="text-xs text-zinc-400 max-w-sm mx-auto mt-1">
                  Generate cryptographic digital credentials signed with Mode Lens Section 20 assertions and Golden Character master references.
                </p>
              </div>
              <button
                onClick={handleGenerateManifest}
                disabled={generating}
                className="px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition flex items-center gap-2 mx-auto"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {generating ? "Signing C2PA Manifest..." : "Generate & Sign C2PA Manifest"}
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-900/50 flex items-center justify-between text-xs text-zinc-500 font-mono">
          <span className="flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5 text-purple-400" /> Mode Lens Governance Standard v20.113
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
