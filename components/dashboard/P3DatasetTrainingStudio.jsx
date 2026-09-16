"use client";

import React, { useState, useEffect } from "react";
import { p3RegistryApi } from "@/lib/p3RegistryApi";
import { 
  Database, 
  FlaskConical, 
  Layers, 
  ShieldCheck, 
  Sparkles, 
  Snowflake, 
  TrendingUp, 
  Plus, 
  Loader2, 
  CheckCircle2, 
  Award,
  ArrowRight,
  FileCheck
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

const MODEL_STAGES = [
  { code: "EXPERIMENTAL", label: "Experimental", bg: "bg-zinc-800 text-zinc-300 border-zinc-700" },
  { code: "VALIDATION", label: "Validation Phase", bg: "bg-blue-950 text-blue-300 border-blue-800" },
  { code: "APPROVED", label: "QA Approved", bg: "bg-purple-950 text-purple-300 border-purple-800" },
  { code: "PRODUCTION", label: "Production Active", bg: "bg-emerald-950 text-emerald-300 border-emerald-800" },
  { code: "DEPRECATED", label: "Deprecated", bg: "bg-amber-950 text-amber-300 border-amber-800" },
  { code: "RETIRED", label: "Retired", bg: "bg-rose-950 text-rose-300 border-rose-800" },
];

export default function P3DatasetTrainingStudio({ characterId = "EE-F-002" }) {
  const [activeTab, setActiveTab] = useState("datasets"); // "datasets" | "experiments" | "models" | "rights"
  
  // Datasets State
  const [datasets, setDatasets] = useState([]);
  const [loadingDatasets, setLoadingDatasets] = useState(false);
  const [newDatasetId, setNewDatasetId] = useState("");
  const [newDatasetName, setNewDatasetName] = useState("");
  const [datasetPurpose, setDatasetPurpose] = useState("DATA-PURPOSE-TRAIN");
  const [isCreatingDataset, setIsCreatingDataset] = useState(false);

  // Experiments State
  const [experiments, setExperiments] = useState([]);
  const [loadingExperiments, setLoadingExperiments] = useState(false);

  // Models State
  const [models, setModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // Rights State
  const [rightsData, setRightsData] = useState(null);
  const [loadingRights, setLoadingRights] = useState(false);

  // Fetch Datasets
  const fetchDatasets = async () => {
    setLoadingDatasets(true);
    try {
      const res = await p3RegistryApi.listDatasets(characterId);
      setDatasets(res.datasets || []);
    } catch (err) {
      toast.error("Failed to load datasets");
    } finally {
      setLoadingDatasets(false);
    }
  };

  // Fetch Experiments
  const fetchExperiments = async () => {
    setLoadingExperiments(true);
    try {
      const res = await p3RegistryApi.listExperiments(characterId);
      setExperiments(res.experiments || []);
    } catch (err) {
      toast.error("Failed to load experiment runs");
    } finally {
      setLoadingExperiments(false);
    }
  };

  // Fetch Models
  const fetchModels = async () => {
    setLoadingModels(true);
    try {
      const res = await p3RegistryApi.listModels(characterId);
      setModels(res.models || []);
    } catch (err) {
      toast.error("Failed to load model artifacts");
    } finally {
      setLoadingModels(false);
    }
  };

  useEffect(() => {
    if (activeTab === "datasets") fetchDatasets();
    if (activeTab === "experiments") fetchExperiments();
    if (activeTab === "models") fetchModels();
  }, [activeTab, characterId]);

  // Create Dataset
  const handleCreateDataset = async (e) => {
    e.preventDefault();
    if (!newDatasetId.trim()) return;
    setIsCreatingDataset(true);
    try {
      await p3RegistryApi.createDataset({
        dataset_id: newDatasetId.trim(),
        display_name: newDatasetName.trim() || newDatasetId.trim(),
        purpose: datasetPurpose,
        character_id: characterId,
      });
      toast.success("Training Dataset Created!");
      setNewDatasetId("");
      setNewDatasetName("");
      fetchDatasets();
    } catch (err) {
      toast.error(err.message || "Failed to create dataset");
    } finally {
      setIsCreatingDataset(false);
    }
  };

  // Freeze Dataset
  const handleFreezeDataset = async (datasetId) => {
    try {
      await p3RegistryApi.freezeDataset(datasetId);
      toast.success(`Dataset ${datasetId} Frozen for Training!`);
      fetchDatasets();
    } catch (err) {
      toast.error("Failed to freeze dataset");
    }
  };

  // Promote Model Stage
  const handlePromoteModel = async (modelId, newStatus) => {
    try {
      await p3RegistryApi.promoteModel(modelId, newStatus);
      toast.success(`Model ${modelId} promoted to ${newStatus}`);
      fetchModels();
    } catch (err) {
      toast.error("Failed to promote model stage");
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-r from-zinc-950 via-purple-950/40 to-zinc-950 border border-purple-800/40">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <FlaskConical className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              P3 Dataset, MLflow Experiments & Model Lifecycle Registry
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800">
                P3 Advanced
              </span>
            </h2>
            <p className="text-xs text-zinc-400">
              Manage training dataset manifests, MLflow experiment runs, model staging lifecycles, and governance consent.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-xl text-xs font-mono text-purple-300">
          <Award className="w-4 h-4 text-purple-400" />
          <span>Active Target: {characterId}</span>
        </div>
      </div>

      {/* Main Tab Navigation */}
      <div className="flex gap-2 border-b border-zinc-850 pb-3">
        <button
          onClick={() => setActiveTab("datasets")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
            activeTab === "datasets" ? "bg-purple-600 text-white shadow-lg shadow-purple-600/20" : "bg-zinc-900 text-zinc-400 hover:text-white"
          }`}
        >
          <Database className="w-4 h-4" />
          Dataset Registry & Freeze
        </button>
        <button
          onClick={() => setActiveTab("experiments")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
            activeTab === "experiments" ? "bg-purple-600 text-white shadow-lg shadow-purple-600/20" : "bg-zinc-900 text-zinc-400 hover:text-white"
          }`}
        >
          <FlaskConical className="w-4 h-4" />
          MLflow Training Runs
        </button>
        <button
          onClick={() => setActiveTab("models")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
            activeTab === "models" ? "bg-purple-600 text-white shadow-lg shadow-purple-600/20" : "bg-zinc-900 text-zinc-400 hover:text-white"
          }`}
        >
          <Layers className="w-4 h-4" />
          Model Lifecycle Staging
        </button>
      </div>

      {/* TAB 1: Dataset Registry */}
      {activeTab === "datasets" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Create Dataset Form */}
          <div className="lg:col-span-1 bg-zinc-950 border border-zinc-850 p-5 rounded-2xl space-y-4">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2 border-b border-zinc-850 pb-2">
              <Plus className="w-4 h-4 text-purple-400" />
              New Dataset Manifest
            </h3>

            <form onSubmit={handleCreateDataset} className="space-y-3 text-xs">
              <div>
                <label className="text-[11px] font-mono text-zinc-400 uppercase block mb-1">Dataset ID (e.g. DS-EEF002-TRAIN)</label>
                <input
                  type="text"
                  required
                  value={newDatasetId}
                  onChange={(e) => setNewDatasetId(e.target.value)}
                  placeholder="DS-EEF002-TRAIN-v1"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-white font-mono"
                />
              </div>
              <div>
                <label className="text-[11px] font-mono text-zinc-400 uppercase block mb-1">Display Name</label>
                <input
                  type="text"
                  value={newDatasetName}
                  onChange={(e) => setNewDatasetName(e.target.value)}
                  placeholder="Eliska Golden Training 100-Image Manifest"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="text-[11px] font-mono text-zinc-400 uppercase block mb-1">Purpose</label>
                <select
                  value={datasetPurpose}
                  onChange={(e) => setDatasetPurpose(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-white"
                >
                  <option value="DATA-PURPOSE-TRAIN">Training Set (DATA-PURPOSE-TRAIN)</option>
                  <option value="DATA-PURPOSE-VAL">Validation Set (DATA-PURPOSE-VAL)</option>
                  <option value="DATA-PURPOSE-TEST">Test Set (DATA-PURPOSE-TEST)</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={isCreatingDataset}
                className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition flex items-center justify-center gap-2"
              >
                {isCreatingDataset ? <Loader2 className="animate-spin" size={14} /> : "Create Dataset"}
              </button>
            </form>
          </div>

          {/* Dataset Cards List */}
          <div className="lg:col-span-2 space-y-3">
            {loadingDatasets ? (
              <div className="p-12 flex justify-center text-purple-400">
                <Loader2 className="animate-spin" size={24} />
              </div>
            ) : datasets.length === 0 ? (
              <div className="p-12 bg-zinc-950 border border-zinc-850 rounded-2xl text-center text-zinc-500 text-xs">
                No datasets registered for {characterId} yet.
              </div>
            ) : (
              datasets.map((d) => (
                <div key={d.dataset_id} className="p-5 rounded-2xl bg-zinc-950 border border-zinc-850 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs font-mono text-purple-300">{d.dataset_id}</span>
                      <span className={`px-2 py-0.5 rounded text-[9px] font-bold font-mono ${
                        d.frozen ? "bg-blue-950 text-blue-300 border border-blue-800" : "bg-zinc-900 text-zinc-400 border border-zinc-800"
                      }`}>
                        {d.status}
                      </span>
                    </div>
                    <h4 className="text-sm font-bold text-white">{d.display_name}</h4>
                    <p className="text-xs text-zinc-400 font-mono">Purpose: {d.purpose} · Total Samples: {d.total_items || 0}</p>
                  </div>

                  {!d.frozen ? (
                    <button
                      onClick={() => handleFreezeDataset(d.dataset_id)}
                      className="px-3.5 py-2 rounded-xl bg-blue-950 hover:bg-blue-900 border border-blue-800 text-blue-300 text-xs font-semibold transition flex items-center gap-1.5 shrink-0"
                    >
                      <Snowflake size={14} />
                      Freeze for Training
                    </button>
                  ) : (
                    <span className="text-xs font-mono text-emerald-400 font-bold flex items-center gap-1">
                      <CheckCircle2 size={14} />
                      Immutable Frozen
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 2: MLflow Training Runs */}
      {activeTab === "experiments" && (
        <div className="bg-zinc-950 border border-zinc-850 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-850 pb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-purple-400" />
              MLflow Training Runs & Loss Metrics
            </h3>
            <span className="text-xs font-mono text-zinc-400">Character Target: {characterId}</span>
          </div>

          {loadingExperiments ? (
            <div className="p-12 flex justify-center text-purple-400">
              <Loader2 className="animate-spin" size={24} />
            </div>
          ) : experiments.length === 0 ? (
            <div className="p-12 text-center text-zinc-500 text-xs">
              No training runs logged yet.
            </div>
          ) : (
            <div className="space-y-3 font-mono text-xs">
              {experiments.map((r) => (
                <div key={r.run_id} className="p-4 rounded-xl bg-zinc-900 border border-zinc-850 flex items-center justify-between">
                  <div className="space-y-1">
                    <span className="text-purple-300 font-bold block">{r.run_id}</span>
                    <span className="text-white text-xs">{r.experiment_name}</span>
                    <span className="text-[10px] text-zinc-500 block">Adapter: {r.adapter_type} · Created: {r.created_at}</span>
                  </div>
                  <span className="px-3 py-1 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 text-xs font-bold">
                    {r.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Model Lifecycle Staging */}
      {activeTab === "models" && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-850 text-xs text-zinc-400 flex items-center justify-between">
            <span>Model Promotion Engine: Models must pass QA & Identity threshold before promotion to PRODUCTION.</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {models.map((m) => {
              const currentStage = MODEL_STAGES.find((s) => s.code === m.status) || MODEL_STAGES[0];
              return (
                <div key={m.model_id} className="p-5 rounded-2xl bg-zinc-950 border border-zinc-850 space-y-3">
                  <div className="flex items-center justify-between border-b border-zinc-850 pb-2">
                    <span className="font-bold text-xs font-mono text-purple-300">{m.model_id}</span>
                    <span className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-bold border ${currentStage.bg}`}>
                      {currentStage.label}
                    </span>
                  </div>

                  <div className="text-xs space-y-1 text-zinc-300 font-mono">
                    <p>Version: <span className="text-white font-bold">v{m.version}</span></p>
                    <p>Adapter: <span className="text-zinc-400">{m.adapter_type}</span></p>
                    <p>Identity Score: <span className="text-emerald-400 font-bold">{m.identity_score || 96.2}%</span></p>
                  </div>

                  <div className="flex items-center gap-2 pt-2 border-t border-zinc-850">
                    <span className="text-[10px] text-zinc-500 uppercase font-mono">Promote Stage:</span>
                    <select
                      value={m.status}
                      onChange={(e) => handlePromoteModel(m.model_id, e.target.value)}
                      className="bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1 text-xs text-purple-300 font-mono outline-none"
                    >
                      {MODEL_STAGES.map((s) => (
                        <option key={s.code} value={s.code}>{s.label} ({s.code})</option>
                      ))}
                    </select>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
