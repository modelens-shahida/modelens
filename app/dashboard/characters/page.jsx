"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { User, Plus, X, Loader2, Folder, Sparkles, AlertCircle, Image as ImageIcon } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

export default function CharactersPage() {
  const { user } = useAuth();
  
  // Data state
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [characters, setCharacters] = useState([]);
  const [brandAssets, setBrandAssets] = useState([]);
  
  // Loading states
  const [loadingBrands, setLoadingBrands] = useState(true);
  const [loadingCharacters, setLoadingCharacters] = useState(false);
  const [loadingAssets, setLoadingAssets] = useState(false);
  
  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [charName, setCharName] = useState("");
  const [charDescription, setCharDescription] = useState("");
  const [selectedAssetPath, setSelectedAssetPath] = useState("");
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
        toast.error(error.message || "Failed to load brands");
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
      setCharacters(data);
    } catch (error) {
      toast.error(error.message || "Failed to load characters");
    } finally {
      setLoadingCharacters(false);
    }
  };

  useEffect(() => {
    fetchCharacters();
  }, [selectedBrandId]);

  // Fetch assets for creation modal when it opens
  const fetchBrandAssets = async () => {
    if (!selectedBrandId) return;
    try {
      setLoadingAssets(true);
      const data = await api.get(`/api/v1/assets?brand_id=${selectedBrandId}`);
      setBrandAssets(data);
      if (data.length > 0) {
        setSelectedAssetPath(data[0].storage_path);
      } else {
        setSelectedAssetPath("");
      }
    } catch (error) {
      console.error("Failed to load brand assets", error);
    } finally {
      setLoadingAssets(false);
    }
  };

  useEffect(() => {
    if (isModalOpen) {
      fetchBrandAssets();
    }
  }, [isModalOpen, selectedBrandId]);

  // Handle character creation submission
  const handleCreateCharacter = async (e) => {
    e.preventDefault();
    if (!charName.trim()) {
      toast.error("Character name is required");
      return;
    }
    if (!selectedAssetPath) {
      toast.error("Please select a base catalog image asset");
      return;
    }

    setIsCreating(true);
    try {
      const payload = {
        brand_id: parseInt(selectedBrandId),
        name: charName.trim(),
        description: charDescription.trim(),
        image_path: selectedAssetPath
      };

      await api.post("/api/v1/characters", payload);
      toast.success("AI Character template created successfully!");
      
      // Reset form
      setCharName("");
      setCharDescription("");
      setSelectedAssetPath("");
      setIsModalOpen(false);
      
      // Refresh characters list
      fetchCharacters();
    } catch (error) {
      toast.error(error.message || "Failed to create character");
    } finally {
      setIsCreating(false);
    }
  };

  if (loadingBrands) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="animate-spin text-purple-500" size={24} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header section */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
        <div className="space-y-1">
          <h2 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100 flex items-center gap-2">
            <User className="text-purple-400" size={24} />
            AI Characters
          </h2>
          <p className="text-xs text-zinc-400">
            Define and manage synthetic model characters for your brand catalog campaigns
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Brand Selector */}
          <div className="relative min-w-[180px]">
            <select
              value={selectedBrandId}
              onChange={(e) => setSelectedBrandId(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 focus:border-purple-500 rounded-xl pl-4 pr-10 py-2.5 text-xs text-zinc-100 outline-none appearance-none cursor-pointer"
            >
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <div className="absolute inset-y-0 right-0 pr-3.5 flex items-center pointer-events-none text-zinc-500">
              <Folder size={12} />
            </div>
          </div>

          <button
            onClick={() => setIsModalOpen(true)}
            disabled={brands.length === 0}
            className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20 disabled:shadow-none"
          >
            <Plus size={14} />
            New Character
          </button>
        </div>
      </div>

      {/* Grid listing */}
      {loadingCharacters ? (
        <div className="flex h-[40vh] items-center justify-center">
          <Loader2 className="animate-spin text-purple-500" size={24} />
        </div>
      ) : characters.length === 0 ? (
        <div className="text-center py-16 bg-zinc-900/10 border border-zinc-900 rounded-2xl space-y-4 max-w-md mx-auto">
          <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-500 mx-auto">
            <User size={22} />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-zinc-200">No Characters Yet</h3>
            <p className="text-xs text-zinc-400 px-6">
              Create a custom character profile specifying base face model coordinates and descriptors.
            </p>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            disabled={brands.length === 0}
            className="inline-flex items-center gap-1.5 bg-zinc-850 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer border border-zinc-800"
          >
            <Plus size={14} />
            Create Character
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {characters.map((char) => (
            <motion.div
              key={char.id}
              whileHover={{ y: -4 }}
              className="bg-zinc-900/30 border border-zinc-850 rounded-2xl overflow-hidden flex flex-col justify-between h-80 group shadow-lg"
            >
              {/* Image Preview Container */}
              <div className="h-44 bg-zinc-950 flex items-center justify-center relative overflow-hidden shrink-0 border-b border-zinc-900">
                <img
                  src={char.image_path}
                  alt={char.name}
                  loading="lazy"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'flex';
                  }}
                  className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
                />
                {/* Fallback Icon */}
                <div className="hidden absolute inset-0 bg-zinc-950 flex-col items-center justify-center text-zinc-650 gap-2">
                  <User size={32} />
                  <span className="text-[9px] font-semibold text-zinc-500">Character Base Image</span>
                </div>
              </div>

              {/* Text metadata */}
              <div className="p-5 flex-1 flex flex-col justify-between">
                <div className="space-y-1.5">
                  <h4 className="text-sm font-bold text-zinc-200 truncate group-hover:text-white transition-colors">
                    {char.name}
                  </h4>
                  <p className="text-xs text-zinc-400 line-clamp-3 leading-relaxed">
                    {char.description || "No description provided."}
                  </p>
                </div>
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">
                  Char ID: {char.id}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Creation Modal popup */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsModalOpen(false)}
              className="fixed inset-0 bg-black"
            />

            {/* Modal Card */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-2xl p-6 relative z-10 shadow-2xl space-y-5 flex flex-col max-h-[90vh] overflow-hidden"
            >
              <div className="flex justify-between items-center shrink-0">
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Sparkles className="text-purple-400" size={18} />
                  Define Brand Model Character
                </h3>
                <button
                  onClick={() => setIsModalOpen(false)}
                  className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg transition-colors cursor-pointer"
                >
                  <X size={16} />
                </button>
              </div>

              <form onSubmit={handleCreateCharacter} className="space-y-5 flex-1 overflow-y-auto pr-1">
                {/* Form Row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  {/* Left form metadata */}
                  <div className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                        Character Name
                      </label>
                      <input
                        type="text"
                        required
                        value={charName}
                        onChange={(e) => setCharName(e.target.value)}
                        placeholder="e.g. Liam - Casual Male, Sophie - Summer Vibe"
                        className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none transition-all"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                        Character Bio / Description
                      </label>
                      <textarea
                        rows={5}
                        required
                        value={charDescription}
                        onChange={(e) => setCharDescription(e.target.value)}
                        placeholder="Enter character physical appearance parameters (e.g., age, hair type, eye color, structure traits, posing guidelines) to pass to generator..."
                        className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none transition-all resize-none leading-relaxed"
                      />
                    </div>
                  </div>

                  {/* Right Image selector grid */}
                  <div className="space-y-2 flex flex-col h-full">
                    <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                      Select Base Model Asset
                    </label>
                    <div className="flex-1 bg-zinc-950 border border-zinc-850 rounded-xl p-3 flex flex-col min-h-[220px]">
                      {loadingAssets ? (
                        <div className="flex-1 flex items-center justify-center">
                          <Loader2 className="animate-spin text-zinc-500" size={20} />
                        </div>
                      ) : brandAssets.length === 0 ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-center text-zinc-650 p-4 gap-2">
                          <AlertCircle size={20} />
                          <span className="text-[10px] font-medium leading-relaxed">
                            No assets in Brand database. Upload photo assets under the Assets Library page first.
                          </span>
                        </div>
                      ) : (
                        <div className="grid grid-cols-3 gap-2 overflow-y-auto max-h-[200px] pr-1">
                          {brandAssets.map((asset) => {
                            const isSelected = selectedAssetPath === asset.storage_path;
                            return (
                              <button
                                type="button"
                                key={asset.id}
                                onClick={() => setSelectedAssetPath(asset.storage_path)}
                                className={`aspect-square rounded-lg overflow-hidden border-2 relative transition-all group cursor-pointer ${
                                  isSelected ? "border-purple-500 scale-95 shadow-md" : "border-transparent hover:border-zinc-700"
                                }`}
                              >
                                <img
                                  src={asset.storage_path}
                                  alt={asset.name}
                                  className="w-full h-full object-cover"
                                />
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                    {selectedAssetPath && (
                      <div className="text-[9px] text-zinc-500 truncate mt-1">
                        Selected: <span className="font-mono text-zinc-400">{selectedAssetPath}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-zinc-855 shrink-0">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="bg-zinc-800 hover:bg-zinc-750 text-zinc-300 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isCreating || brandAssets.length === 0}
                    className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer flex items-center gap-1 shadow-md shadow-purple-950/20 disabled:bg-zinc-800 disabled:text-zinc-500"
                  >
                    {isCreating ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : (
                      "Save Character"
                    )}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
