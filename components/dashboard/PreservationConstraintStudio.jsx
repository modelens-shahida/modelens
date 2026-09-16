"use client";

import React, { useState, useEffect } from "react";
import { preservationApi } from "@/lib/preservationApi";
import { 
  ShieldCheck, 
  Lock, 
  Sparkles, 
  Layers, 
  CheckCircle2, 
  AlertTriangle, 
  FileText, 
  Download, 
  RefreshCw, 
  Sliders, 
  Key, 
  Link, 
  Award,
  Loader2,
  Eye,
  Box
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

export default function PreservationConstraintStudio({ brandId = 1 }) {
  const [activeTab, setActiveTab] = useState("preservation"); // "preservation" | "ledger"
  
  // Garment Preservation States
  const [productId, setProductId] = useState("PROD-GAR-9940");
  const [preservePrint, setPreservePrint] = useState(true);
  const [preserveConstruction, setPreserveConstruction] = useState(true);
  const [preserveColor, setPreserveColor] = useState(true);
  const [preserveSilhouette, setPreserveSilhouette] = useState(true);
  const [preserveEmbellishment, setPreserveEmbellishment] = useState(true);

  // Identity Gate States
  const [characterId, setCharacterId] = useState("EE-F-002");
  const [arcfaceThreshold, setArcfaceThreshold] = useState(94.0);
  const [checkMarkers, setCheckMarkers] = useState(true);
  const [checkAge, setCheckAge] = useState(true);

  // Brand Protection States
  const [logoRegionX, setLogoRegionX] = useState(10);
  const [logoRegionY, setLogoRegionY] = useState(10);
  const [logoRegionW, setLogoRegionW] = useState(15);
  const [logoRegionH, setLogoRegionH] = useState(10);

  // Generated Profile State
  const [generatedProfile, setGeneratedProfile] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // Credit Ledger States
  const [ledgerData, setLedgerData] = useState([]);
  const [chainIntegrity, setChainIntegrity] = useState(null);
  const [loadingLedger, setLoadingLedger] = useState(false);
  const [verifyingLedger, setVerifyingLedger] = useState(false);

  // Generate Preservation Profile
  const handleGenerateProfile = async () => {
    setIsGenerating(true);
    try {
      const res = await preservationApi.createGarmentPreservation({
        product_id: productId,
        brand_id: brandId,
        preserve_print: preservePrint,
        preserve_construction: preserveConstruction,
        preserve_color: preserveColor,
        preserve_silhouette: preserveSilhouette,
        preserve_embellishment: preserveEmbellishment,
        custom_zones: [
          {
            type: "logo",
            bounding_box: { x: logoRegionX, y: logoRegionY, width: logoRegionW, height: logoRegionH },
            priority: "CRITICAL"
          }
        ]
      });
      setGeneratedProfile(res.profile);
      toast.success("Garment & Brand Protection Profile Generated!");
    } catch (err) {
      toast.error("Failed to generate preservation profile");
    } finally {
      setIsGenerating(false);
    }
  };

  // Load Credit Ledger
  const fetchLedger = async () => {
    setLoadingLedger(true);
    try {
      const res = await preservationApi.getCreditLedger(brandId);
      setLedgerData(res.transactions || []);
      setChainIntegrity(res.chain_integrity);
    } catch (err) {
      toast.error("Failed to load credit ledger");
    } finally {
      setLoadingLedger(false);
    }
  };

  useEffect(() => {
    if (activeTab === "ledger") {
      fetchLedger();
    }
  }, [activeTab, brandId]);

  // Verify Ledger Hash Chain
  const handleVerifyChain = async () => {
    setVerifyingLedger(true);
    try {
      const res = await preservationApi.verifyLedgerIntegrity(brandId);
      setChainIntegrity(res);
      if (res.valid) {
        toast.success("SHA-256 Ledger Integrity Verified 100% Intact!");
      } else {
        toast.error(`Integrity Failure: ${res.reason || "Hash chain mismatch"}`);
      }
    } catch (err) {
      toast.error("Verification failed");
    } finally {
      setVerifyingLedger(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-r from-zinc-950 via-emerald-950/30 to-zinc-950 border border-emerald-800/40">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              Preservation Engine & Immutable Credit Ledger
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800">
                P2 Hardened
              </span>
            </h2>
            <p className="text-xs text-zinc-400">
              Set brand/apparel protection masks and audit SHA-256 cryptographic credit transaction chains.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("preservation")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition ${
              activeTab === "preservation" ? "bg-emerald-600 text-white shadow-lg shadow-emerald-600/20" : "bg-zinc-900 text-zinc-400 hover:text-white"
            }`}
          >
            Preservation Engine
          </button>
          <button
            onClick={() => setActiveTab("ledger")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition ${
              activeTab === "ledger" ? "bg-emerald-600 text-white shadow-lg shadow-emerald-600/20" : "bg-zinc-900 text-zinc-400 hover:text-white"
            }`}
          >
            Immutable Credit Ledger
          </button>
        </div>
      </div>

      {/* TAB 1: Preservation Engine */}
      {activeTab === "preservation" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Controls */}
          <div className="space-y-5 bg-zinc-950 border border-zinc-850 p-6 rounded-2xl">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 border-b border-zinc-850 pb-3">
              <Lock className="w-4 h-4 text-emerald-400" />
              Garment & Identity Preservation Rules
            </h3>

            {/* Product & Identity Target */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-mono text-zinc-400 uppercase">Product ID</label>
                <input
                  type="text"
                  value={productId}
                  onChange={(e) => setProductId(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white font-mono"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-mono text-zinc-400 uppercase">Target Character</label>
                <input
                  type="text"
                  value={characterId}
                  onChange={(e) => setCharacterId(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white font-mono"
                />
              </div>
            </div>

            {/* Garment Feature Protection Toggles */}
            <div className="space-y-3 pt-2">
              <label className="text-xs font-bold text-white uppercase tracking-wider block">
                Garment Feature Protection Rules
              </label>

              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <label className="flex items-center gap-2 p-2.5 rounded-xl bg-zinc-900 border border-zinc-850 cursor-pointer">
                  <input type="checkbox" checked={preservePrint} onChange={(e) => setPreservePrint(e.target.checked)} className="rounded text-emerald-500 focus:ring-0" />
                  <span className="text-zinc-200">Preserve Print/Pattern</span>
                </label>
                <label className="flex items-center gap-2 p-2.5 rounded-xl bg-zinc-900 border border-zinc-850 cursor-pointer">
                  <input type="checkbox" checked={preserveConstruction} onChange={(e) => setPreserveConstruction(e.target.checked)} className="rounded text-emerald-500 focus:ring-0" />
                  <span className="text-zinc-200">Preserve Seams/Stitching</span>
                </label>
                <label className="flex items-center gap-2 p-2.5 rounded-xl bg-zinc-900 border border-zinc-850 cursor-pointer">
                  <input type="checkbox" checked={preserveColor} onChange={(e) => setPreserveColor(e.target.checked)} className="rounded text-emerald-500 focus:ring-0" />
                  <span className="text-zinc-200">Preserve Color Shade</span>
                </label>
                <label className="flex items-center gap-2 p-2.5 rounded-xl bg-zinc-900 border border-zinc-850 cursor-pointer">
                  <input type="checkbox" checked={preserveSilhouette} onChange={(e) => setPreserveSilhouette(e.target.checked)} className="rounded text-emerald-500 focus:ring-0" />
                  <span className="text-zinc-200">Preserve Silhouette</span>
                </label>
              </div>
            </div>

            {/* ArcFace Identity Gate Slider */}
            <div className="space-y-2 pt-2 border-t border-zinc-850">
              <div className="flex justify-between text-xs">
                <span className="font-bold text-white uppercase tracking-wider">ArcFace Facial Similarity Gate</span>
                <span className="font-mono text-emerald-400 font-bold">{arcfaceThreshold}% Min Score</span>
              </div>
              <input
                type="range"
                min="85"
                max="99"
                step="0.5"
                value={arcfaceThreshold}
                onChange={(e) => setArcfaceThreshold(parseFloat(e.target.value))}
                className="w-full accent-emerald-500"
              />
              <p className="text-[10px] text-zinc-500 leading-normal">
                Generations scoring &lt;{arcfaceThreshold}% identity similarity are automatically blocked and auto-refunded via DLQ.
              </p>
            </div>

            {/* Logo Protection Region Box */}
            <div className="space-y-2 pt-2 border-t border-zinc-850">
              <span className="text-xs font-bold text-white uppercase tracking-wider block">
                Brand Protection Zone (Chest Logo Region %)
              </span>
              <div className="grid grid-cols-4 gap-2 text-xs font-mono">
                <div>
                  <span className="text-[9px] text-zinc-500">X %</span>
                  <input type="number" value={logoRegionX} onChange={(e) => setLogoRegionX(parseInt(e.target.value))} className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-1.5 text-center text-white" />
                </div>
                <div>
                  <span className="text-[9px] text-zinc-500">Y %</span>
                  <input type="number" value={logoRegionY} onChange={(e) => setLogoRegionY(parseInt(e.target.value))} className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-1.5 text-center text-white" />
                </div>
                <div>
                  <span className="text-[9px] text-zinc-500">Width %</span>
                  <input type="number" value={logoRegionW} onChange={(e) => setLogoRegionW(parseInt(e.target.value))} className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-1.5 text-center text-white" />
                </div>
                <div>
                  <span className="text-[9px] text-zinc-500">Height %</span>
                  <input type="number" value={logoRegionH} onChange={(e) => setLogoRegionH(parseInt(e.target.value))} className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-1.5 text-center text-white" />
                </div>
              </div>
            </div>

            <button
              onClick={handleGenerateProfile}
              disabled={isGenerating}
              className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/20"
            >
              {isGenerating ? <Loader2 className="animate-spin" size={16} /> : "Build Protection Profile & Constraints"}
            </button>
          </div>

          {/* Right Protection Profile Output Visualizer */}
          <div className="bg-zinc-950 border border-zinc-850 p-6 rounded-2xl space-y-4">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 border-b border-zinc-850 pb-3">
              <Box className="w-4 h-4 text-emerald-400" />
              Generated Protection Mask & Manifest
            </h3>

            {!generatedProfile ? (
              <div className="h-64 flex flex-col items-center justify-center text-zinc-650 text-xs text-center space-y-2">
                <ShieldCheck size={32} className="text-zinc-800" />
                <p>Click &quot;Build Protection Profile&quot; to compute feature priorities & protection masks.</p>
              </div>
            ) : (
              <div className="space-y-4 font-mono text-xs">
                <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-850 space-y-2">
                  <div className="flex items-center justify-between text-emerald-400 font-bold">
                    <span>Profile ID: {generatedProfile.profile_id}</span>
                    <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 text-[10px]">
                      COMPUTED
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400">Target Product: {generatedProfile.product_id}</p>
                </div>

                <div className="space-y-2">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Feature Preservation Priorities</span>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(generatedProfile.rules || {}).map(([key, rule]) => (
                      <div key={key} className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-850 flex items-center justify-between">
                        <span className="text-zinc-300 capitalize">{key}</span>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                          rule.priority === "CRITICAL" ? "bg-red-950 text-red-300 border border-red-800" : "bg-emerald-950 text-emerald-300 border border-emerald-800"
                        }`}>
                          {rule.priority}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-850 space-y-1 text-zinc-400 text-[11px]">
                  <span className="text-white font-bold block mb-1">Protection Zones Active:</span>
                  <p>• Logo Chest Region: [{logoRegionX}%, {logoRegionY}%, {logoRegionW}%, {logoRegionH}%] (CRITICAL)</p>
                  <p>• Identity ArcFace Threshold: &ge; {arcfaceThreshold}% Similarity</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Immutable Credit Ledger */}
      {activeTab === "ledger" && (
        <div className="space-y-6">
          {/* Integrity Header Card */}
          <div className="p-5 rounded-2xl bg-zinc-950 border border-zinc-850 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Key className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold text-white">SHA-256 Cryptographic Hash Chain Ledger</h3>
                {chainIntegrity && (
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold flex items-center gap-1 ${
                    chainIntegrity.valid ? "bg-emerald-950 text-emerald-300 border border-emerald-800" : "bg-red-950 text-red-300 border border-red-800"
                  }`}>
                    {chainIntegrity.valid ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <AlertTriangle className="w-3.5 h-3.5 text-red-400" />}
                    {chainIntegrity.valid ? "Hash Chain 100% Verified" : "Tampering Detected"}
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400">
                Every credit top-up, deduction, auto-refund, and monthly quota reset is cryptographically signed.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleVerifyChain}
                disabled={verifyingLedger}
                className="px-3.5 py-2 rounded-xl bg-emerald-950 hover:bg-emerald-900 border border-emerald-800 text-emerald-300 text-xs font-semibold transition flex items-center gap-1.5"
              >
                {verifyingLedger ? <Loader2 className="animate-spin" size={14} /> : <RefreshCw size={14} />}
                Verify Chain
              </button>
              <a
                href={`/api/v1/credits/ledger/${brandId}/export`}
                target="_blank"
                rel="noreferrer"
                className="px-3.5 py-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-white text-xs font-semibold transition flex items-center gap-1.5"
              >
                <Download size={14} />
                Export Ledger CSV
              </a>
            </div>
          </div>

          {/* Transactions Hash Chain Table */}
          <div className="bg-zinc-950 border border-zinc-850 rounded-2xl overflow-hidden shadow-xl">
            {loadingLedger ? (
              <div className="p-12 flex justify-center text-emerald-400">
                <Loader2 className="animate-spin" size={24} />
              </div>
            ) : ledgerData.length === 0 ? (
              <div className="p-12 text-center text-zinc-500 text-xs">
                No credit transactions recorded yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-zinc-850 bg-zinc-900/60 font-mono text-[10px] text-zinc-400 uppercase tracking-wider">
                      <th className="p-3">Txn ID</th>
                      <th className="p-3">Type</th>
                      <th className="p-3">Amount</th>
                      <th className="p-3">Balance After</th>
                      <th className="p-3">Previous Hash</th>
                      <th className="p-3">SHA-256 Chain Hash</th>
                      <th className="p-3">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-850/60 font-mono text-xs">
                    {ledgerData.map((t) => (
                      <tr key={t.id} className="hover:bg-zinc-900/40 transition">
                        <td className="p-3 text-white font-bold">#{t.id}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            t.transaction_type === "top_up" ? "bg-emerald-950 text-emerald-300 border border-emerald-800" :
                            t.transaction_type === "refund" ? "bg-blue-950 text-blue-300 border border-blue-800" :
                            "bg-zinc-900 text-zinc-300 border border-zinc-800"
                          }`}>
                            {t.transaction_type}
                          </span>
                        </td>
                        <td className={`p-3 font-bold ${t.amount >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {t.amount > 0 ? `+${t.amount}` : t.amount}
                        </td>
                        <td className="p-3 text-zinc-200 font-bold">{t.balance_after || "—"}</td>
                        <td className="p-3 text-[10px] text-zinc-500 truncate max-w-[120px]" title={t.previous_hash}>
                          {t.previous_hash || "GENESIS"}
                        </td>
                        <td className="p-3 text-[10px] text-emerald-300 truncate max-w-[180px]" title={t.chain_hash}>
                          {t.chain_hash || "—"}
                        </td>
                        <td className="p-3 text-[10px] text-zinc-400">{t.created_at}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
