"use client";

import React from "react";
import { CheckCircle2, AlertCircle, Clock, ShieldCheck, UserCheck, Layers, Sparkles } from "lucide-react";
import { QA_STATUS } from "@/lib/characterSchema";

export default function CharacterQaGrid({ character }) {
  if (!character || !character.qa_matrix) return null;

  const { qa_matrix } = character;

  const categories = [
    { key: "identity_qa", label: "Identity QA", icon: UserCheck, desc: "Facial similarity & ArcFace embedding score" },
    { key: "body_qa", label: "Body QA", icon: ShieldCheck, desc: "Anatomical proportion & height scaling check" },
    { key: "angle_qa", label: "Angle QA", icon: Layers, desc: "Full-Body & Half-Body multi-angle consistency" },
    { key: "hands_qa", label: "Hands QA", icon: Sparkles, desc: "5-digit finger anatomy & articulation validation" },
    { key: "feet_qa", label: "Feet QA", icon: ShieldCheck, desc: "Footwear & ankle grounding alignment" },
    { key: "training_eligibility", label: "Training Eligibility", icon: CheckCircle2, desc: "Dataset freeze & legal consent registry" },
    { key: "production_eligibility", label: "Production Eligibility", icon: Clock, desc: "Shahida V1.0 Lock approval status" },
  ];

  return (
    <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl mt-6">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4 mb-6">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-indigo-400" />
            <span>Character QA & Production Validation Matrix</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Quality assurance audit gates for character release management.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {categories.map((cat) => {
          const data = qa_matrix[cat.key] || { status: "NOT_REVIEWED", reviewer: "System", note: "Pending audit" };
          const qaCfg = QA_STATUS[data.status] || QA_STATUS.NOT_REVIEWED;
          const Icon = cat.icon;

          return (
            <div
              key={cat.key}
              className="bg-zinc-950/70 border border-zinc-800/80 rounded-xl p-4 flex flex-col justify-between hover:border-zinc-700 transition-all"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <Icon className="w-4 h-4 text-indigo-400" />
                    <span>{cat.label}</span>
                  </div>
                  <span className={`px-2.5 py-0.5 text-[10px] font-bold rounded-full border ${qaCfg.color}`}>
                    {qaCfg.label}
                  </span>
                </div>
                <p className="text-[11px] text-zinc-500 mb-3">{cat.desc}</p>
              </div>

              <div className="border-t border-zinc-900 pt-2.5 flex items-center justify-between text-[10px] text-zinc-400">
                <span>Auditor: <strong className="text-zinc-300">{data.reviewer}</strong></span>
                <span className="text-zinc-400 italic truncate max-w-[150px]">{data.note}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
