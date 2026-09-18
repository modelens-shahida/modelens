"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { User, Plus, X, Loader2, Sparkles, Database, Layers, ShieldCheck, Camera, Dna, ArrowRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

import { MOCK_ELISKA_CHARACTER, CHARACTER_STATUS } from "@/lib/characterSchema";
import CharacterProfileCard from "@/components/dashboard/CharacterProfileCard";
import CharacterDnaTabs from "@/components/dashboard/CharacterDnaTabs";
import CharacterAngleGallery from "@/components/dashboard/CharacterAngleGallery";
import CharacterQaGrid from "@/components/dashboard/CharacterQaGrid";

export default function CharactersPage() {
  const { user } = useAuth();
  
  // Data state
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [characters, setCharacters] = useState([MOCK_ELISKA_CHARACTER]);
  const [selectedCharacter, setSelectedCharacter] = useState(MOCK_ELISKA_CHARACTER);

  // Loading states
  const [loadingBrands, setLoadingBrands] = useState(true);
  const [loadingCharacters, setLoadingCharacters] = useState(false);
  
  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [charName, setCharName] = useState("");
  const [charDescription, setCharDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Initialize: Load brands
  useEffect(() => {
    async function loadBrands() {
      try {
        setLoadingBrands(true);
        const data = await api.get("/api/v1/brands");
        setBrands(data);
        if (data.length > 0) {
          setSelectedBrandId(data[0].id.toString());
        }
      } catch (error) {
        console.warn("Using fallback default brand", error);
      } finally {
        setLoadingBrands(false);
      }
    }
    loadBrands();
  }, []);

  // Fetch characters when active brand changes
  const fetchCharacters = async () => {
    if (!selectedBrandId) return;
    try {
      setLoadingCharacters(true);
      const data = await api.get(`/api/v1/characters?brand_id=${selectedBrandId}`);
      if (data && data.length > 0) {
        // Merge API characters with flagship Eliska template
        setCharacters([MOCK_ELISKA_CHARACTER, ...data]);
      } else {
        setCharacters([MOCK_ELISKA_CHARACTER]);
      }
    } catch (error) {
      console.warn("Using mock Eliska dataset fallback", error);
      setCharacters([MOCK_ELISKA_CHARACTER]);
    } finally {
      setLoadingCharacters(false);
    }
  };

  useEffect(() => {
    fetchCharacters();
  }, [selectedBrandId]);

  // Handle character creation submission
  const handleCreateCharacter = async (e) => {
    e.preventDefault();
    if (!charName.trim()) {
      toast.error("Character name is required");
      return;
    }
    try {
      setIsCreating(true);
      const payload = {
        name: charName,
        description: charDescription,
        brand_id: parseInt(selectedBrandId),
        version: "0.1",
        status: "DEVELOPMENT",
      };
      const created = await api.post("/api/v1/characters", payload);
      toast.success("Character record created successfully!");
      setIsModalOpen(false);
      setCharName("");
      setCharDescription("");
      fetchCharacters();
    } catch (error) {
      toast.error(error.message || "Failed to create character");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 space-y-8">
      {/* Top Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              <Dna className="w-8 h-8 text-cyan-400" />
              <span>AI Character Architecture & Library</span>
            </h1>
            <span className="px-3 py-1 bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono font-semibold rounded-full">
              Directive EE-F-002 V1.0
            </span>
          </div>
          <p className="text-sm text-zinc-400 mt-1">
            Universal, data-driven AI Model Character Registry. Flagship: <strong className="text-white">EE-F-002 (Eliska Novak)</strong>.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Brand Selector */}
          <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 px-3 py-2 rounded-xl">
            <span className="text-xs text-zinc-500">Brand:</span>
            {loadingBrands ? (
              <Loader2 className="w-4 h-4 animate-spin text-zinc-400" />
            ) : (
              <select
                value={selectedBrandId}
                onChange={(e) => setSelectedBrandId(e.target.value)}
                className="bg-transparent text-xs text-white font-medium focus:outline-none cursor-pointer"
              >
                {brands.map((b) => (
                  <option key={b.id} value={b.id} className="bg-zinc-900 text-white">
                    {b.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs px-4 py-2.5 rounded-xl transition-all shadow-lg shadow-cyan-500/20"
          >
            <Plus className="w-4 h-4" />
            <span>New Character Record</span>
          </button>
        </div>
      </div>

      {/* Character Selector Strip */}
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-4 backdrop-blur-md shadow-lg">
        <div className="flex items-center justify-between mb-3 px-1">
          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Registered Models ({characters.length})
          </span>
          <span className="text-[11px] text-zinc-500 font-mono">
            Active: {selectedCharacter?.id || "None"} (v{selectedCharacter?.version || "1.0"})
          </span>
        </div>

        <div className="flex items-center gap-3 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-zinc-800">
          {characters.map((char) => {
            const isSelected = selectedCharacter?.id === char.id;
            const statusCfg = CHARACTER_STATUS[char.status] || CHARACTER_STATUS.VALIDATION;

            return (
              <button
                key={char.id}
                onClick={() => setSelectedCharacter(char)}
                className={`flex-shrink-0 border rounded-xl p-3 text-left transition-all min-w-[220px] ${
                  isSelected
                    ? "bg-cyan-500/10 border-cyan-500/60 shadow-md shadow-cyan-500/10 ring-1 ring-cyan-500/30"
                    : "bg-zinc-950/70 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/50"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-mono font-bold text-cyan-400">{char.id}</span>
                  <span className={`px-2 py-0.5 text-[9px] font-semibold rounded-full border ${statusCfg.color}`}>
                    {statusCfg.label}
                  </span>
                </div>
                <h4 className="text-xs font-bold text-white truncate">{char.display_name}</h4>
                <div className="flex items-center justify-between text-[10px] text-zinc-500 mt-1">
                  <span>v{char.version}</span>
                  <span>{char.gender_presentation || "Model"}</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Selected Character Architecture View */}
      {selectedCharacter && (
        <div className="space-y-6">
          {/* 1. Character Profile & Header Card */}
          <CharacterProfileCard character={selectedCharacter} />

          {/* 2. Permanent Character DNA vs Production Controls Tabs */}
          <CharacterDnaTabs character={selectedCharacter} />

          {/* 3. Canonical Angle Reference Board */}
          <CharacterAngleGallery character={selectedCharacter} />

          {/* 4. QA Status Matrix */}
          <CharacterQaGrid character={selectedCharacter} />
        </div>
      )}

      {/* New Character Record Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-5"
            >
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-cyan-400" />
                  <span>Create Character Record</span>
                </h3>
                <button
                  onClick={() => setIsModalOpen(false)}
                  className="text-zinc-500 hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreateCharacter} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">
                    Character Display Name
                  </label>
                  <input
                    type="text"
                    value={charName}
                    onChange={(e) => setCharName(e.target.value)}
                    placeholder="e.g. SORA KIM / EE-F-003"
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-xs text-white focus:border-cyan-500 focus:outline-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">
                    Internal Description & Archetype
                  </label>
                  <textarea
                    value={charDescription}
                    onChange={(e) => setCharDescription(e.target.value)}
                    placeholder="High-Fashion Runway model archetype..."
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-xs text-white focus:border-cyan-500 focus:outline-none h-24 resize-none"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-xs font-semibold text-zinc-300 rounded-xl transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isCreating}
                    className="px-5 py-2 bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs rounded-xl transition-all shadow-md shadow-cyan-500/20 flex items-center gap-2"
                  >
                    {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : "Create Template"}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
