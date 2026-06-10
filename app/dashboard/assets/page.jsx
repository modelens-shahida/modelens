"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Image as ImageIcon, Search, Plus, Filter, X, Upload, Loader2, Sparkles, Folder } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

export default function AssetsPage() {
  const { user } = useAuth();
  
  // Platform state
  const [brands, setBrands] = useState([]);
  const [schema, setSchema] = useState({});
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [selectedBrand, setSelectedBrand] = useState("");
  const [selectedTag, setSelectedTag] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Upload Modal State
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadBrand, setUploadBrand] = useState("");
  const [uploadName, setUploadName] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadAssetType, setUploadAssetType] = useState("image");
  const [uploadMeta, setUploadMeta] = useState({});
  const [isUploading, setIsUploading] = useState(false);

  // Debounce search query
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 400);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Load brands list & taxonomy schema
  useEffect(() => {
    async function initPage() {
      try {
        const brandList = await api.get("/api/v1/brands");
        setBrands(brandList);
        if (brandList.length > 0) {
          setUploadBrand(brandList[0].id.toString());
        }

        const schemaData = await api.get("/api/v1/assets/metadata/schema");
        setSchema(schemaData);

        // Prepopulate upload metadata keys
        const initialMeta = {};
        Object.keys(schemaData).forEach((key) => {
          initialMeta[key] = "";
        });
        setUploadMeta(initialMeta);
      } catch (error) {
        console.error("Failed to initialize assets workspace", error);
      }
    }
    initPage();
  }, []);

  // Fetch assets list when filters change
  const fetchAssets = async () => {
    try {
      setLoading(true);
      let endpoint = "/api/v1/assets?";
      if (selectedBrand) endpoint += `brand_id=${selectedBrand}&`;
      if (selectedTag) endpoint += `tag=${selectedTag}&`;
      if (debouncedSearch) endpoint += `search=${encodeURIComponent(debouncedSearch)}&`;

      const data = await api.get(endpoint);
      setAssets(data);
    } catch (error) {
      toast.error(error.message || "Failed to load assets");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, [selectedBrand, selectedTag, debouncedSearch]);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setUploadFile(e.target.files[0]);
    }
  };

  const handleMetaSelect = (category, val) => {
    setUploadMeta((prev) => ({
      ...prev,
      [category]: val,
    }));
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!uploadBrand) {
      toast.error("Please select a brand");
      return;
    }
    if (!uploadFile) {
      toast.error("Please pick a file to upload");
      return;
    }

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("brand_id", uploadBrand);
      formData.append("name", uploadName);
      formData.append("asset_type", uploadAssetType);
      
      // Clean metadata (omit blank entries)
      const cleanMeta = {};
      Object.entries(uploadMeta).forEach(([k, v]) => {
        if (v) cleanMeta[k] = v;
      });
      formData.append("metadata_json", JSON.stringify(cleanMeta));
      formData.append("file", uploadFile);

      await api.post("/api/v1/assets", formData);
      toast.success("Asset uploaded and cataloged successfully!");
      
      // Reset upload state
      setUploadName("");
      setUploadFile(null);
      
      const resetMeta = {};
      Object.keys(schema).forEach((key) => {
        resetMeta[key] = "";
      });
      setUploadMeta(resetMeta);
      setIsUploadOpen(false);

      // Refresh list
      fetchAssets();
    } catch (error) {
      toast.error(error.message || "Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="space-y-1">
          <h2 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100">
            Asset Workspace
          </h2>
          <p className="text-xs text-zinc-400">
            Browse, search, and classify your catalog images with AI taxonomy tags
          </p>
        </div>
        {brands.length > 0 && (
          <button
            onClick={() => setIsUploadOpen(true)}
            className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20"
          >
            <Upload size={14} />
            Upload Asset
          </button>
        )}
      </div>

      {/* Control panel & Filter bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 bg-zinc-900/10 border border-zinc-900 p-4 rounded-2xl">
        {/* Search Input */}
        <div className="relative md:col-span-2">
          <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-zinc-500">
            <Search size={16} />
          </span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search assets by file name..."
            className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl pl-9 pr-4 py-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none transition-all"
          />
        </div>

        {/* Brand Dropdown filter */}
        <div className="relative">
          <select
            value={selectedBrand}
            onChange={(e) => setSelectedBrand(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2 text-xs text-zinc-200 outline-none appearance-none cursor-pointer"
          >
            <option value="">All Brands</option>
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

        {/* Active Tag indicator clear */}
        {selectedTag && (
          <button
            onClick={() => setSelectedTag("")}
            className="flex items-center justify-between bg-purple-950/40 border border-purple-800/30 text-purple-400 rounded-xl px-4 py-2 text-xs hover:bg-purple-900/30 transition-all"
          >
            <span className="truncate">Tag: {selectedTag}</span>
            <X size={14} className="shrink-0 ml-2" />
          </button>
        )}
      </div>

      {/* Workspace Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        {/* Left Side: Taxonomy filter panel */}
        <div className="lg:col-span-1 bg-zinc-950 border border-zinc-900 rounded-2xl p-4 space-y-5">
          <div className="flex items-center gap-2 text-xs font-bold text-zinc-300 uppercase tracking-wider border-b border-zinc-900 pb-2.5">
            <Filter size={14} className="text-purple-400" />
            Taxonomy Filters
          </div>

          <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
            {Object.entries(schema).map(([category, tags]) => (
              <div key={category} className="space-y-2">
                <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide block">
                  {category}
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {tags.map((tag) => {
                    const isSelected = selectedTag === tag;
                    return (
                      <button
                        key={tag}
                        onClick={() => setSelectedTag(isSelected ? "" : tag)}
                        className={`text-[9px] font-semibold px-2 py-1 rounded-lg border transition-all cursor-pointer ${
                          isSelected
                            ? "bg-purple-600 border-purple-500 text-white shadow-sm"
                            : "bg-zinc-900/40 border-zinc-850/80 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                        }`}
                      >
                        {tag}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Side: Asset Grid View */}
        <div className="lg:col-span-3 space-y-6">
          {loading ? (
            <div className="flex h-[40vh] items-center justify-center">
              <Loader2 className="animate-spin text-purple-500" size={24} />
            </div>
          ) : assets.length === 0 ? (
            <div className="text-center py-16 bg-zinc-900/10 border border-zinc-900 rounded-2xl space-y-4">
              <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-500 mx-auto">
                <ImageIcon size={22} />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-zinc-200">No Assets Found</h3>
                <p className="text-xs text-zinc-500 px-6">
                  No images match the current search filters. Upload a new asset to get started.
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
              {assets.map((asset) => (
                <motion.div
                  key={asset.id}
                  whileHover={{ y: -3 }}
                  className="bg-zinc-900/20 border border-zinc-900 hover:border-zinc-800 rounded-2xl overflow-hidden flex flex-col justify-between h-80 group shadow-lg"
                >
                  {/* Thumbnail container */}
                  <div className="h-44 bg-zinc-950 flex items-center justify-center relative overflow-hidden shrink-0 border-b border-zinc-900">
                    <img
                      src={asset.storage_path}
                      alt={asset.name}
                      onError={(e) => {
                        // fallback mock vector icon
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'flex';
                      }}
                      className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
                    />
                    {/* Fallback Icon if Image doesn't load */}
                    <div className="hidden absolute inset-0 bg-zinc-950 flex-col items-center justify-center text-zinc-650 gap-2">
                      <ImageIcon size={32} />
                      <span className="text-[9px] font-semibold text-zinc-500">Image Asset Preview</span>
                    </div>

                    {/* Brand Identifier Badge */}
                    <div className="absolute top-3 left-3 bg-zinc-900/90 backdrop-blur-md border border-zinc-800 text-zinc-300 text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                      {brands.find((b) => b.id === asset.brand_id)?.name || `Brand #${asset.brand_id}`}
                    </div>
                  </div>

                  {/* Asset Details info */}
                  <div className="p-4 flex-1 flex flex-col justify-between">
                    <div className="space-y-1">
                      <h4 className="text-xs font-bold text-zinc-200 truncate group-hover:text-white transition-colors">
                        {asset.name}
                      </h4>
                      <p className="text-[9px] text-zinc-500 truncate">
                        File: {asset.filename}
                      </p>
                    </div>

                    {/* Tags List */}
                    <div className="flex flex-wrap gap-1 mt-2.5 max-h-12 overflow-hidden">
                      {asset.tags && asset.tags.length > 0 ? (
                        asset.tags.map((t) => (
                          <span
                            key={t}
                            className="text-[8px] font-bold bg-zinc-900 border border-zinc-850/60 text-zinc-400 px-1.5 py-0.5 rounded-md uppercase tracking-wider"
                          >
                            {t}
                          </span>
                        ))
                      ) : (
                        <span className="text-[8px] italic text-zinc-600">No semantic tags assigned</span>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Upload Asset Modal */}
      <AnimatePresence>
        {isUploadOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4 overflow-y-auto">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsUploadOpen(false)}
              className="fixed inset-0 bg-black"
            />

            {/* Modal Card */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 relative z-10 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto"
            >
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Sparkles className="text-purple-400" size={18} />
                  Upload & Classify Asset
                </h3>
                <button
                  onClick={() => setIsUploadOpen(false)}
                  className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg transition-colors cursor-pointer"
                >
                  <X size={16} />
                </button>
              </div>

              <form onSubmit={handleUploadSubmit} className="space-y-4 text-xs">
                {/* Brand Selector */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-zinc-300 uppercase tracking-wider">
                      Target Brand
                    </label>
                    <select
                      value={uploadBrand}
                      onChange={(e) => setUploadBrand(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-3 py-2.5 text-zinc-200 outline-none cursor-pointer"
                    >
                      {brands.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-zinc-300 uppercase tracking-wider">
                      Asset Name (Optional)
                    </label>
                    <input
                      type="text"
                      value={uploadName}
                      onChange={(e) => setUploadName(e.target.value)}
                      placeholder="e.g. Summer Hoodie front"
                      className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-3 py-2 text-zinc-100 placeholder-zinc-500 outline-none transition-all"
                    />
                  </div>
                </div>

                {/* File Picker */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-zinc-300 uppercase tracking-wider block">
                    Catalog File Upload
                  </label>
                  <div className="border border-dashed border-zinc-800 rounded-xl p-6 bg-zinc-950 text-center relative hover:bg-zinc-950/60 transition-all group">
                    <input
                      type="file"
                      required
                      accept="image/*"
                      onChange={handleFileChange}
                      className="absolute inset-0 opacity-0 w-full h-full cursor-pointer z-10"
                    />
                    <div className="space-y-2">
                      <div className="w-10 h-10 rounded-full bg-zinc-900 border border-zinc-850 flex items-center justify-center mx-auto text-zinc-400 group-hover:text-purple-400 group-hover:border-purple-800/40 transition-colors">
                        <Upload size={18} />
                      </div>
                      <p className="text-zinc-400 font-semibold">
                        {uploadFile ? uploadFile.name : "Click to browse local files"}
                      </p>
                      <p className="text-[10px] text-zinc-500">Supports JPG, PNG, WEBP files up to 10MB</p>
                    </div>
                  </div>
                </div>

                {/* Metadata Taxonomy Selectors */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-zinc-300 uppercase tracking-wider block border-b border-zinc-850 pb-1">
                    AI Taxonomy Classification
                  </label>
                  <div className="grid grid-cols-2 gap-4">
                    {Object.entries(schema).map(([category, tags]) => (
                      <div key={category} className="space-y-1">
                        <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-wide">
                          {category}
                        </span>
                        <select
                          value={uploadMeta[category] || ""}
                          onChange={(e) => handleMetaSelect(category, e.target.value)}
                          className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-2.5 py-1.5 text-zinc-300 outline-none cursor-pointer"
                        >
                          <option value="">(None)</option>
                          {tags.map((tag) => (
                            <option key={tag} value={tag}>
                              {tag}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-2 pt-4 border-t border-zinc-850">
                  <button
                    type="button"
                    onClick={() => setIsUploadOpen(false)}
                    className="bg-zinc-800 hover:bg-zinc-750 text-zinc-300 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isUploading}
                    className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer flex items-center gap-1 shadow-md shadow-purple-950/20"
                  >
                    {isUploading ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : (
                      "Upload & Save"
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
