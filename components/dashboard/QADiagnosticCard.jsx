"use client";

import React, { useState, useEffect } from "react";
import { qaApi } from "@/lib/qaApi";
import { 
  Award, 
  ShieldCheck, 
  AlertTriangle, 
  ShieldAlert, 
  CheckCircle2, 
  Sliders, 
  Wrench, 
  History, 
  UserCheck, 
  Loader2, 
  RefreshCw,
  Info,
  Sparkles
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import CanvasRetouchModal from "@/components/dashboard/CanvasRetouchModal";

const DECISION_CONFIG = {
  "QA-PASS": { label: "QA Passed", color: "bg-emerald-950/80 text-emerald-300 border-emerald-700", icon: CheckCircle2 },
  "QA-PASS-WARNING": { label: "Passed with Warnings", color: "bg-amber-950/80 text-amber-300 border-amber-700", icon: AlertTriangle },
  "QA-AUTO-CORRECT": { label: "Auto-Correct Routed", color: "bg-purple-950/80 text-purple-300 border-purple-700", icon: Wrench },
  "QA-HUMAN-REVIEW": { label: "Human Review Required", color: "bg-blue-950/80 text-blue-300 border-blue-700", icon: UserCheck },
  "QA-FAIL": { label: "QA Failed", color: "bg-red-950/80 text-red-300 border-red-700", icon: ShieldAlert },
};

const SEVERITY_CONFIG = {
  "SEV-1": { label: "Minor (SEV-1)", color: "bg-zinc-800 text-zinc-300 border-zinc-700" },
  "SEV-2": { label: "Moderate (SEV-2)", color: "bg-amber-950 text-amber-300 border-amber-800" },
  "SEV-3": { label: "Major (SEV-3)", color: "bg-orange-950 text-orange-300 border-orange-800" },
  "SEV-4": { label: "Critical (SEV-4)", color: "bg-red-950 text-red-300 border-red-800" },
};

export default function QADiagnosticCard({ assetId, qaProfileId = "QA-PROFILE-CATALOG-001", className = "" }) {
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [reviewDecision, setReviewDecision] = useState("QA-PASS");
  const [reviewerNotes, setReviewerNotes] = useState("");
  const [overrideHardGate, setOverrideHardGate] = useState(false);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [showRetouchModal, setShowRetouchModal] = useState(false);
  const [selectedDefectForRetouch, setSelectedDefectForRetouch] = useState("ART-HAND-001");

  useEffect(() => {
    if (assetId) {
      fetchLatestEvaluation();
    }
  }, [assetId]);

  const fetchLatestEvaluation = async () => {
    setLoading(true);
    try {
      const data = await qaApi.getEvaluations(assetId);
      setEvaluation(data?.latest || null);
    } catch (err) {
      console.error("Failed to load QA evaluation:", err);
      setEvaluation(null);
    } finally {
      setLoading(false);
    }
  };

  const runEvaluation = async () => {
    setEvaluating(true);
    try {
      const res = await qaApi.evaluateAsset({
        asset_id: parseInt(assetId),
        qa_profile_id: qaProfileId,
        generation_mode: "studio_quality",
      });
      setEvaluation(res);
      toast.success("QA evaluation completed");
    } catch (err) {
      console.error("Failed to run QA evaluation:", err);
      toast.error(err?.message || "Evaluation failed");
    } finally {
      setEvaluating(false);
    }
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    if (!evaluation?.evaluation_id && !evaluation?.id) return;
    const evalId = evaluation.evaluation_id || evaluation.id;

    setSubmittingReview(true);
    try {
      await qaApi.reviewEvaluation(evalId, {
        decision: reviewDecision,
        reviewer_notes: reviewerNotes.trim() || undefined,
        override_hard_gate: overrideHardGate,
      });

      toast.success("Human review decision recorded");
      setShowReviewModal(false);
      fetchLatestEvaluation();
    } catch (err) {
      console.error("Failed to submit review:", err);
      toast.error(err?.message || "Failed to submit review");
    } finally {
      setSubmittingReview(false);
    }
  };

  const decisionCfg = DECISION_CONFIG[evaluation?.decision] || DECISION_CONFIG["QA-HUMAN-REVIEW"];
  const DecisionIcon = decisionCfg.icon;

  return (
    <div className={`p-5 rounded-2xl bg-zinc-950 border border-zinc-800 text-zinc-100 shadow-xl space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Award className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white flex items-center gap-2">
              QA & Validation Diagnostics
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                {qaProfileId}
              </span>
            </h4>
            <p className="text-xs text-zinc-400">Multi-dimensional scoring & defect artifact detection</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={runEvaluation}
            disabled={evaluating}
            className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-medium transition flex items-center gap-1.5 border border-zinc-800"
            title="Run QA Engine on this asset"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${evaluating ? "animate-spin text-indigo-400" : ""}`} />
            {evaluating ? "Evaluating..." : "Run QA Engine"}
          </button>

          {evaluation && (
            <button
              onClick={() => setShowReviewModal(true)}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition flex items-center gap-1 shadow-lg shadow-indigo-500/20"
            >
              <UserCheck className="w-3.5 h-3.5" />
              Human Review
            </button>
          )}
        </div>
      </div>

      {/* Main Body */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-10 text-zinc-500 space-y-2">
          <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
          <p className="text-xs">Loading QA diagnostics...</p>
        </div>
      ) : !evaluation ? (
        <div className="p-8 rounded-xl border border-dashed border-zinc-800 text-center text-zinc-500 text-xs space-y-2">
          <p>No QA evaluation record found for this asset.</p>
          <button
            onClick={runEvaluation}
            disabled={evaluating}
            className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition inline-flex items-center gap-1"
          >
            Run Initial QA Evaluation
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Top Score Banner */}
          <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="text-center px-4 py-2 rounded-xl bg-zinc-950 border border-zinc-800 font-mono">
                <span className="text-2xl font-bold text-indigo-300">{evaluation.overall_score || 0}</span>
                <span className="text-[10px] text-zinc-500 block">/ 100</span>
              </div>
              <div>
                <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold font-mono border ${decisionCfg.color}`}>
                  <DecisionIcon className="w-3.5 h-3.5" />
                  {decisionCfg.label}
                </span>
                <p className="text-xs text-zinc-400 mt-1">
                  {evaluation.overall_score >= 94
                    ? "Production Quality Ready · All critical hard gates passed"
                    : "Requires human review or localized touch-up before publishing"}
                </p>
              </div>
            </div>

            {/* Hard Gate Failures Alert */}
            {evaluation.hard_gate_failures && evaluation.hard_gate_failures.length > 0 && (
              <div className="px-3 py-1.5 rounded-lg bg-red-950/60 border border-red-800 text-red-300 text-xs font-mono font-medium flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-red-400 shrink-0" />
                <span>Hard Gate Failed: {evaluation.hard_gate_failures.join(", ")}</span>
              </div>
            )}
          </div>

          {/* Dimension Scores Progress Grid */}
          <div className="space-y-2">
            <h5 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Dimension Evaluation Breakdown
            </h5>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {evaluation.dimension_scores &&
                Object.entries(evaluation.dimension_scores).map(([dim, score]) => {
                  const isPass = score >= 90;
                  return (
                    <div key={dim} className="p-3 rounded-xl bg-zinc-900/40 border border-zinc-800/80 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[11px] font-mono capitalize text-zinc-300 font-medium">{dim}</span>
                        <span className={`font-mono font-bold ${isPass ? "text-emerald-400" : "text-amber-400"}`}>
                          {score}%
                        </span>
                      </div>
                      <div className="w-full bg-zinc-950 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${isPass ? "bg-emerald-500" : "bg-amber-500"}`}
                          style={{ width: `${Math.min(score, 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Detected Artifacts / Defects */}
          {evaluation.artifacts && evaluation.artifacts.length > 0 && (
            <div className="space-y-2">
              <h5 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                Detected Defects & Defect Artifacts ({evaluation.artifacts.length})
              </h5>
              <div className="space-y-1.5">
                {evaluation.artifacts.map((art, idx) => {
                  const sev = SEVERITY_CONFIG[art.severity] || SEVERITY_CONFIG["SEV-1"];
                  return (
                    <div key={idx} className="p-2.5 rounded-xl bg-zinc-900/60 border border-zinc-800 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-zinc-200 font-bold">{art.artifact_code}</span>
                        {art.description && <span className="text-zinc-400 text-[11px]">— {art.description}</span>}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border uppercase ${sev.color}`}>
                          {sev.label}
                        </span>
                        <button
                          onClick={() => {
                            setSelectedDefectForRetouch(art.artifact_code);
                            setShowRetouchModal(true);
                          }}
                          className="px-2 py-0.5 rounded bg-purple-950/80 hover:bg-purple-900 text-purple-300 border border-purple-800 text-[10px] font-bold font-mono transition flex items-center gap-1"
                        >
                          <Sparkles className="w-2.5 h-2.5" /> Inpaint
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Canvas Retouch Modal */}
      {showRetouchModal && (
        <CanvasRetouchModal
          isOpen={showRetouchModal}
          onClose={() => setShowRetouchModal(false)}
          asset={{ id: assetId, storage_uri: evaluation?.storage_uri }}
          initialDefectCode={selectedDefectForRetouch}
          onSuccess={() => {
            fetchLatestEvaluation();
          }}
        />
      )}

      {/* Human Review Modal */}
      {showReviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <form onSubmit={handleReviewSubmit} className="w-full max-w-md bg-zinc-950 border border-zinc-800 rounded-2xl p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-indigo-400" />
              Human Review & Hard-Gate Override
            </h3>
            <p className="text-xs text-zinc-400">
              Submit your authorized manual evaluation decision and optional override notes for this asset.
            </p>

            <div>
              <label className="text-xs text-zinc-400 block mb-1 font-medium">Review Decision</label>
              <select
                value={reviewDecision}
                onChange={(e) => setReviewDecision(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs outline-none focus:border-indigo-500 font-mono"
              >
                <option value="QA-PASS">QA-PASS (Approved for Production)</option>
                <option value="QA-AUTO-CORRECT">QA-AUTO-CORRECT (Route for Inpaint Touch-up)</option>
                <option value="QA-FAIL">QA-FAIL (Reject Asset)</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-zinc-400 block mb-1 font-medium">Reviewer Audit Notes</label>
              <textarea
                value={reviewerNotes}
                onChange={(e) => setReviewerNotes(e.target.value)}
                placeholder="e.g. Verified garment seam accuracy manually..."
                rows={3}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs outline-none focus:border-indigo-500"
              />
            </div>

            <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-zinc-300">
              <input
                type="checkbox"
                checked={overrideHardGate}
                onChange={(e) => setOverrideHardGate(e.target.checked)}
                className="rounded bg-zinc-900 border-zinc-700 text-indigo-600 focus:ring-0"
              />
              <span>Override Hard Gate failure with review authority</span>
            </label>

            <div className="flex justify-end gap-2 pt-2 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setShowReviewModal(false)}
                className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submittingReview}
                className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5"
              >
                {submittingReview && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Submit Review Decision
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
