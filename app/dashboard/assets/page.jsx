"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Image as ImageIcon, Search, Plus, Filter, X, Upload, Loader2, Sparkles, Folder, ChevronDown, ChevronUp, Sun, Camera, User, Users, Shirt, Tag, Megaphone, MapPin, Check, Trash2, RefreshCw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

export default function AssetsPage() {
  const { user } = useAuth();
  
  // Platform state
  const [brands, setBrands] = useState([]);
  const [schema, setSchema] = useState({});
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  // Filters
  const [selectedBrand, setSelectedBrand] = useState("");
  const [selectedTag, setSelectedTag] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [collapsedCategories, setCollapsedCategories] = useState({});

  const toggleCategory = (category) => {
    setCollapsedCategories((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  };

  const getCategoryIcon = (category) => {
    const catLower = category.toLowerCase();
    if (catLower.includes("light")) return <Sun size={13} className="text-amber-400" />;
    if (catLower.includes("camera") || catLower.includes("lens") || catLower.includes("view")) return <Camera size={13} className="text-blue-400" />;
    if (catLower.includes("mood") || catLower.includes("feel") || catLower.includes("vibe")) return <Sparkles size={13} className="text-pink-400" />;
    if (catLower.includes("model") || catLower.includes("person") || catLower.includes("gender") || catLower.includes("pose")) return <User size={13} className="text-emerald-400" />;
    if (catLower.includes("apparel") || catLower.includes("clothing") || catLower.includes("type") || catLower.includes("garment")) return <Shirt size={13} className="text-purple-400" />;
    if (catLower.includes("location") || catLower.includes("place")) return <MapPin size={13} className="text-rose-400" />;
    if (catLower.includes("campaign") || catLower.includes("theme")) return <Megaphone size={13} className="text-sky-400" />;
    return <Tag size={13} className="text-indigo-400" />;
  };

  // Upload Modal State
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadBrand, setUploadBrand] = useState("");
  const [uploadName, setUploadName] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadAssetType, setUploadAssetType] = useState("image");
  const [uploadMeta, setUploadMeta] = useState({});
  const [isUploading, setIsUploading] = useState(false);

  // Details Modal and Trash states
  const [isTrashView, setIsTrashView] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState(null);

  // Advanced filter states
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [filterAssetType, setFilterAssetType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterSortBy, setFilterSortBy] = useState("created_at");
  const [filterSortOrder, setFilterSortOrder] = useState("desc");
  const [filterCreatedAfter, setFilterCreatedAfter] = useState("");
  const [filterCreatedBefore, setFilterCreatedBefore] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  const handleDeleteAsset = async (assetId) => {
    if (!confirm("Are you sure you want to delete this asset? It will be moved to the Trash Bin.")) return;
    setIsDeleting(true);
    try {
      await api.delete(`/api/v1/assets/${assetId}`);
      toast.success("Asset moved to Trash");
      setSelectedAsset(null);
      fetchAssets();
    } catch (error) {
      toast.error(error.message || "Failed to delete asset");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleRestoreAsset = async (e, assetId) => {
    e.stopPropagation();
    setIsRestoring(true);
    try {
      await api.post(`/api/v1/assets/${assetId}/restore`);
      toast.success("Asset restored successfully");
      fetchAssets();
    } catch (error) {
      toast.error(error.message || "Failed to restore asset");
    } finally {
      setIsRestoring(false);
    }
  };

  // Tag management states & handlers inside details modal
  const [modalTags, setModalTags] = useState([]);
  const [newTagInput, setNewTagInput] = useState("");
  const [isAddingTag, setIsAddingTag] = useState(false);

  const fetchModalTags = async (assetId) => {
    try {
      const tags = await api.get(`/api/v1/assets/${assetId}/tags`);
      setModalTags(tags || []);
    } catch (err) {
      console.error("Failed to fetch tags for asset", err);
    }
  };

  useEffect(() => {
    if (selectedAsset) {
      fetchModalTags(selectedAsset.id);
    } else {
      setModalTags([]);
    }
  }, [selectedAsset]);

  const handleAddTag = async (e) => {
    e.preventDefault();
    if (!newTagInput.trim() || !selectedAsset) return;
    setIsAddingTag(true);
    try {
      const addedTag = await api.post(`/api/v1/assets/${selectedAsset.id}/tags?tag=${encodeURIComponent(newTagInput.trim())}`);
      setModalTags((prev) => [...prev, addedTag]);
      setNewTagInput("");
      fetchAssets();
    } catch (err) {
      toast.error(err.message || "Failed to add tag");
    } finally {
      setIsAddingTag(false);
    }
  };

  const handleDeleteTag = async (tagId) => {
    if (!selectedAsset) return;
    try {
      await api.delete(`/api/v1/assets/${selectedAsset.id}/tags/${tagId}`);
      setModalTags((prev) => prev.filter((t) => t.id !== tagId));
      fetchAssets();
    } catch (err) {
      toast.error(err.message || "Failed to delete tag");
    }
  };

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

      // Use faceted search when filters or search are active
      const hasFilters = debouncedSearch || filterAssetType || filterStatus || filterCreatedAfter || filterCreatedBefore;

      if (!isTrashView && selectedBrand && hasFilters) {
        let endpoint = `/api/v1/search/faceted?brand_id=${selectedBrand}&limit=${itemsPerPage}&offset=${(currentPage - 1) * itemsPerPage}`;
        if (debouncedSearch) endpoint += `&q=${encodeURIComponent(debouncedSearch)}`;
        if (filterAssetType) endpoint += `&asset_type=${encodeURIComponent(filterAssetType)}`;
        if (filterStatus) endpoint += `&status=${encodeURIComponent(filterStatus)}`;
        if (filterCreatedAfter) endpoint += `&created_after=${encodeURIComponent(filterCreatedAfter)}`;
        if (filterCreatedBefore) endpoint += `&created_before=${encodeURIComponent(filterCreatedBefore)}`;
        if (selectedTag) endpoint += `&tags=${encodeURIComponent(selectedTag)}`;
        endpoint += `&sort_by=${filterSortBy}&sort_order=${filterSortOrder}`;
        const data = await api.get(endpoint);
        setAssets(data.results || []);
      } else {
        let endpoint = isTrashView
          ? `/api/v1/assets/trash?limit=${itemsPerPage}&offset=${(currentPage - 1) * itemsPerPage}&`
          : `/api/v1/assets?limit=${itemsPerPage}&offset=${(currentPage - 1) * itemsPerPage}&`;
        if (selectedBrand) endpoint += `brand_id=${selectedBrand}&`;
        if (!isTrashView && selectedTag) endpoint += `tag=${selectedTag}&`;
        if (!isTrashView && debouncedSearch) endpoint += `search=${encodeURIComponent(debouncedSearch)}&`;
        const data = await api.get(endpoint);
        setAssets(data);
      }
    } catch (error) {
      toast.error(error.message || "Failed to load assets");
    } finally {
      setLoading(false);
    }
  };

  // Reset page when search, filters, or view changes
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedBrand, selectedTag, debouncedSearch, isTrashView, filterAssetType, filterStatus, filterCreatedAfter, filterCreatedBefore, filterSortBy, filterSortOrder]);

  useEffect(() => {
    fetchAssets();
  }, [selectedBrand, selectedTag, debouncedSearch, currentPage, isTrashView, filterAssetType, filterStatus, filterCreatedAfter, filterCreatedBefore, filterSortBy, filterSortOrder]);

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
        <div className="flex gap-2">
          <button
            onClick={() => setIsTrashView(!isTrashView)}
            className={`flex items-center gap-1.5 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer border ${
              isTrashView
                ? "bg-purple-950/40 border-purple-500/40 text-purple-300 hover:bg-purple-900/30"
                : "bg-zinc-900 border-zinc-800 text-zinc-300 hover:border-zinc-700"
            }`}
          >
            <Trash2 size={14} />
            {isTrashView ? "View Active" : "View Trash"}
          </button>
          {!isTrashView && brands.length > 0 && (
            <button
              onClick={() => setIsUploadOpen(true)}
              className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20"
            >
              <Upload size={14} />
              Upload Asset
            </button>
          )}
        </div>
      </div>



      {/* Advanced Filters Panel */}
      {showAdvancedFilters && (
        <div className="bg-zinc-900/20 border border-zinc-800 rounded-2xl p-4 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Asset Type */}
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Asset Type</label>
              <select
                value={filterAssetType}
                onChange={(e) => setFilterAssetType(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none"
              >
                <option value="">All Types</option>
                <option value="catalog">Catalog</option>
                <option value="generated">Generated</option>
                <option value="training">Training</option>
              </select>
            </div>

            {/* Status */}
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Status</label>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none"
              >
                <option value="">All Statuses</option>
                <option value="active">Active</option>
                <option value="processing">Processing</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            {/* Sort By */}
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Sort By</label>
              <select
                value={filterSortBy}
                onChange={(e) => setFilterSortBy(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none"
              >
                <option value="created_at">Date Created</option>
                <option value="name">Name</option>
                <option value="relevance">Relevance</option>
              </select>
            </div>

            {/* Sort Order */}
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Sort Order</label>
              <select
                value={filterSortOrder}
                onChange={(e) => setFilterSortOrder(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none"
              >
                <option value="desc">Newest First</option>
                <option value="asc">Oldest First</option>
              </select>
            </div>

            {/* Created After */}
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Created After</label>
              <input
                type="date"
                value={filterCreatedAfter}
                onChange={(e) => setFilterCreatedAfter(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none"
              />
            </div>

            {/* Created Before */}
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Created Before</label>
              <input
                type="date"
                value={filterCreatedBefore}
                onChange={(e) => setFilterCreatedBefore(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 outline-none"
              />
            </div>

            {/* Clear Filters */}
            <div className="flex items-end">
              <button
                onClick={() => {
                  setFilterAssetType("");
                  setFilterStatus("");
                  setFilterSortBy("created_at");
                  setFilterSortOrder("desc");
                  setFilterCreatedAfter("");
                  setFilterCreatedBefore("");
                }}
                className="w-full bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-300 transition"
              >
                Clear All Filters
              </button>
            </div>
          </div>

          {/* Active Filter Badges */}
          <div className="flex flex-wrap gap-2">
            {filterAssetType && (
              <span className="flex items-center gap-1 bg-purple-900/50 border border-purple-700 text-purple-300 text-xs px-2 py-1 rounded-full">
                Type: {filterAssetType}
                <button onClick={() => setFilterAssetType("")} className="ml-1 hover:text-white">×</button>
              </span>
            )}
            {filterStatus && (
              <span className="flex items-center gap-1 bg-purple-900/50 border border-purple-700 text-purple-300 text-xs px-2 py-1 rounded-full">
                Status: {filterStatus}
                <button onClick={() => setFilterStatus("")} className="ml-1 hover:text-white">×</button>
              </span>
            )}
            {filterCreatedAfter && (
              <span className="flex items-center gap-1 bg-purple-900/50 border border-purple-700 text-purple-300 text-xs px-2 py-1 rounded-full">
                After: {filterCreatedAfter}
                <button onClick={() => setFilterCreatedAfter("")} className="ml-1 hover:text-white">×</button>
              </span>
            )}
            {filterCreatedBefore && (
              <span className="flex items-center gap-1 bg-purple-900/50 border border-purple-700 text-purple-300 text-xs px-2 py-1 rounded-full">
                Before: {filterCreatedBefore}
                <button onClick={() => setFilterCreatedBefore("")} className="ml-1 hover:text-white">×</button>
              </span>
            )}
            {filterSortBy !== "created_at" && (
              <span className="flex items-center gap-1 bg-blue-900/50 border border-blue-700 text-blue-300 text-xs px-2 py-1 rounded-full">
                Sort: {filterSortBy}
                <button onClick={() => setFilterSortBy("created_at")} className="ml-1 hover:text-white">×</button>
              </span>
            )}
          </div>
        </div>
      )}

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

        {/* Advanced Filters Toggle */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
              showAdvancedFilters
                ? "bg-purple-600 border-purple-500 text-white"
                : "bg-zinc-950 border-zinc-700 text-zinc-400 hover:border-purple-500"
            }`}
          >
            <SlidersHorizontal size={14} />
            Filters {[filterAssetType, filterStatus, filterCreatedAfter, filterCreatedBefore].filter(Boolean).length > 0 &&
              `(${[filterAssetType, filterStatus, filterCreatedAfter, filterCreatedBefore].filter(Boolean).length})`}
          </button>
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
        <div className="lg:col-span-1 bg-zinc-950/40 backdrop-blur-xl border border-zinc-900/80 rounded-2xl p-4.5 space-y-4 shadow-xl shadow-black/20">
          <div className="flex items-center justify-between text-xs font-bold text-zinc-300 uppercase tracking-wider border-b border-zinc-900/60 pb-3">
            <div className="flex items-center gap-2">
              <Filter size={14} className="text-purple-400" />
              Taxonomy Filters
            </div>
            {selectedTag && (
              <button
                onClick={() => setSelectedTag("")}
                className="text-[9px] font-extrabold text-purple-400 hover:text-purple-300 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 px-2.5 py-0.5 rounded-lg transition-all cursor-pointer"
              >
                Clear Active
              </button>
            )}
          </div>

          {selectedTag && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="bg-purple-950/20 border border-purple-900/30 rounded-xl p-2.5 flex items-center justify-between text-[10px]"
            >
              <span className="text-purple-300 font-medium truncate flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
                Active: <strong className="text-white font-bold">{selectedTag}</strong>
              </span>
              <button
                onClick={() => setSelectedTag("")}
                className="text-purple-400 hover:text-purple-200 p-0.5 hover:bg-purple-900/40 rounded-lg transition-all"
              >
                <X size={12} />
              </button>
            </motion.div>
          )}

          {/* Scrollable Container */}
          <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-1 [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-thumb]:bg-zinc-800/80 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent">
            {Object.entries(schema).map(([category, tags]) => {
              const isCollapsed = !!collapsedCategories[category];
              const hasActiveTag = tags.includes(selectedTag);

              return (
                <div 
                  key={category} 
                  className={`bg-zinc-900/10 border rounded-xl overflow-hidden transition-all duration-300 ${
                    hasActiveTag 
                      ? "border-purple-500/30 bg-purple-500/5 shadow-md shadow-purple-950/10" 
                      : "border-zinc-900/80 hover:border-zinc-800/60"
                  }`}
                >
                  {/* Category Toggle Bar */}
                  <button
                    onClick={() => toggleCategory(category)}
                    className="flex justify-between items-center w-full px-4 py-3 bg-zinc-950/20 hover:bg-white/5 transition-all text-left cursor-pointer group"
                  >
                    <span className="text-[10px] font-bold text-zinc-350 uppercase tracking-wider group-hover:text-zinc-200 transition-colors flex items-center gap-2">
                      {getCategoryIcon(category)}
                      {category}
                    </span>
                    <div className="flex items-center gap-2">
                      {hasActiveTag ? (
                        <span className="text-[8px] bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider flex items-center gap-1">
                          <span className="w-1 h-1 rounded-full bg-purple-400 animate-pulse" />
                          Active
                        </span>
                      ) : (
                        <span className="text-[9px] bg-zinc-900/60 text-zinc-500 border border-zinc-800/40 px-2 py-0.5 rounded-full font-bold">
                          {tags.length}
                        </span>
                      )}
                      <motion.div
                        animate={{ rotate: isCollapsed ? 0 : 180 }}
                        transition={{ duration: 0.2 }}
                        className="text-zinc-500 group-hover:text-zinc-300"
                      >
                        <ChevronDown size={12} />
                      </motion.div>
                    </div>
                  </button>

                  {/* Tags Pill Box (Collapsed/Expanded content) */}
                  <AnimatePresence initial={false}>
                    {!isCollapsed && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <motion.div
                          variants={{
                            hidden: { opacity: 0 },
                            show: {
                              opacity: 1,
                              transition: { staggerChildren: 0.02 }
                            }
                          }}
                          initial="hidden"
                          animate="show"
                          className="p-3.5 flex flex-wrap gap-1.5 bg-zinc-950/30 border-t border-zinc-900/40"
                        >
                          {tags.map((tag) => {
                            const isSelected = selectedTag === tag;
                            return (
                              <motion.button
                                key={tag}
                                variants={{
                                  hidden: { opacity: 0, scale: 0.9, y: 4 },
                                  show: { opacity: 1, scale: 1, y: 0 }
                                }}
                                whileHover={{ scale: 1.04 }}
                                whileTap={{ scale: 0.96 }}
                                onClick={() => setSelectedTag(isSelected ? "" : tag)}
                                className={`text-[9px] font-bold px-2.5 py-1 rounded-xl border transition-all cursor-pointer flex items-center gap-1 ${
                                  isSelected
                                    ? "bg-gradient-to-r from-purple-500 via-purple-600 to-indigo-600 border-transparent text-white shadow-md shadow-purple-950/60 ring-1 ring-purple-400/30"
                                    : "bg-zinc-900/40 border-zinc-850/80 text-zinc-400 hover:border-purple-500/30 hover:bg-purple-500/5 hover:text-zinc-200"
                                }`}
                              >
                                {isSelected && <Check size={8} strokeWidth={3} className="text-white" />}
                                {tag}
                              </motion.button>
                            );
                          })}
                        </motion.div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
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
            <div className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
                {assets.map((asset) => (
                  <motion.div
                    key={asset.id}
                    whileHover={{ y: -3 }}
                    onClick={() => !isTrashView && setSelectedAsset(asset)}
                    className={`bg-zinc-900/20 border border-zinc-900 hover:border-zinc-800 rounded-2xl overflow-hidden flex flex-col justify-between h-80 group shadow-lg ${!isTrashView ? "cursor-pointer" : ""}`}
                  >
                    {/* Thumbnail container */}
                    <div className="h-44 bg-zinc-950 flex items-center justify-center relative overflow-hidden shrink-0 border-b border-zinc-900">
                      <img
                        src={asset.storage_path}
                        alt={asset.name}
                        loading="lazy"
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

                      {isTrashView ? (
                        <button
                          onClick={(e) => handleRestoreAsset(e, asset.id)}
                          disabled={isRestoring}
                          className="mt-3 w-full py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50 cursor-pointer"
                        >
                          {isRestoring ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                          Restore Asset
                        </button>
                      ) : (
                        /* Tags List */
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
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* Pagination Controls */}
              <div className="flex justify-between items-center bg-zinc-950 border border-zinc-900 rounded-2xl p-3 mt-4">
                <button
                  type="button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
                  className="bg-zinc-900 border border-zinc-850 hover:border-zinc-700 disabled:opacity-40 disabled:hover:border-zinc-850 text-zinc-300 px-3 py-1.5 rounded-xl text-xs transition-all cursor-pointer flex items-center gap-1 font-semibold"
                >
                  &larr; Previous
                </button>
                <span className="text-zinc-400 text-[10px] uppercase font-bold tracking-wider">
                  Page {currentPage}
                </span>
                <button
                  type="button"
                  disabled={assets.length < itemsPerPage}
                  onClick={() => setCurrentPage((p) => p + 1)}
                  className="bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-900 disabled:text-zinc-500 disabled:opacity-40 text-white px-4 py-1.5 rounded-xl text-xs transition-all cursor-pointer flex items-center gap-1 font-semibold shadow-md shadow-purple-950/20"
                >
                  Next &rarr;
                </button>
              </div>
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

      {/* Asset Details Modal */}
      <AnimatePresence>
        {selectedAsset && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4 overflow-y-auto">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedAsset(null)}
              className="fixed inset-0 bg-black"
            />

            {/* Modal Content */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-4xl p-6 relative z-10 shadow-2xl overflow-hidden flex flex-col md:flex-row gap-6 max-h-[90vh]"
            >
              {/* Left Side: Image Preview */}
              <div className="flex-1 bg-zinc-950 rounded-xl overflow-hidden flex items-center justify-center border border-zinc-850 relative min-h-[300px] md:min-h-[400px]">
                <img
                  src={selectedAsset.storage_path}
                  alt={selectedAsset.name}
                  className="max-w-full max-h-[60vh] object-contain"
                />
              </div>

              {/* Right Side: Details & Actions */}
              <div className="w-full md:w-80 flex flex-col justify-between space-y-6">
                <div className="space-y-5 overflow-y-auto pr-1 max-h-[50vh] md:max-h-[60vh] [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-thumb]:bg-zinc-800/85 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent">
                  {/* Header info */}
                  <div className="flex justify-between items-start">
                    <div className="space-y-1">
                      <h3 className="text-base font-bold text-zinc-100 truncate max-w-[200px]" title={selectedAsset.name}>
                        {selectedAsset.name}
                      </h3>
                      <p className="text-[10px] text-zinc-500 font-mono truncate max-w-[200px]">
                        ID: {selectedAsset.id}
                      </p>
                    </div>
                    <button
                      onClick={() => setSelectedAsset(null)}
                      className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg transition-colors cursor-pointer"
                    >
                      <X size={16} />
                    </button>
                  </div>

                  {/* Metadata fields */}
                  <div className="space-y-3.5 border-t border-zinc-850 pt-4">
                    <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                      Asset Metadata
                    </h4>
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs py-1 border-b border-zinc-850/40">
                        <span className="text-zinc-500 font-medium">Filename</span>
                        <span className="text-zinc-300 truncate max-w-[150px]" title={selectedAsset.filename}>
                          {selectedAsset.filename}
                        </span>
                      </div>
                      <div className="flex justify-between text-xs py-1 border-b border-zinc-850/40">
                        <span className="text-zinc-500 font-medium">Asset Type</span>
                        <span className="text-zinc-300 capitalize">{selectedAsset.asset_type}</span>
                      </div>
                      {selectedAsset.metadata && Object.entries(selectedAsset.metadata).map(([k, v]) => (
                        <div key={k} className="flex justify-between text-xs py-1 border-b border-zinc-850/40">
                          <span className="text-zinc-500 font-medium capitalize">{k}</span>
                          <span className="text-zinc-300">{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Tags */}
                  <div className="space-y-2.5 border-t border-zinc-850 pt-4">
                    <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                      Semantic Tags
                    </h4>
                    <div className="flex flex-wrap gap-1.5">
                      {modalTags.length > 0 ? (
                        modalTags.map((t) => (
                          <span
                            key={t.id}
                            className="text-[9px] font-bold bg-zinc-950 border border-zinc-800 text-zinc-300 pl-2.5 pr-1 py-0.5 rounded-lg uppercase tracking-wider flex items-center gap-1"
                          >
                            {t.tag}
                            <button
                              onClick={() => handleDeleteTag(t.id)}
                              className="text-zinc-500 hover:text-rose-400 p-0.5 transition-colors cursor-pointer"
                              title="Delete tag"
                            >
                              <X size={10} strokeWidth={3} />
                            </button>
                          </span>
                        ))
                      ) : (
                        <span className="text-[10px] italic text-zinc-650">No tags assigned</span>
                      )}
                    </div>

                    {/* Add Tag Form */}
                    <form onSubmit={handleAddTag} className="flex gap-1.5 pt-1.5">
                      <input
                        type="text"
                        value={newTagInput}
                        onChange={(e) => setNewTagInput(e.target.value)}
                        placeholder="Add tag (e.g. outdoor)..."
                        disabled={isAddingTag}
                        className="flex-1 bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-lg px-2.5 py-1.5 text-[10px] text-zinc-200 placeholder-zinc-600 outline-none transition-all disabled:opacity-50"
                      />
                      <button
                        type="submit"
                        disabled={isAddingTag || !newTagInput.trim()}
                        className="bg-purple-600 hover:bg-purple-500 text-white text-[10px] font-semibold px-3 py-1.5 rounded-lg transition-all cursor-pointer disabled:bg-zinc-800 disabled:text-zinc-650"
                      >
                        {isAddingTag ? <Loader2 size={10} className="animate-spin" /> : "Add"}
                      </button>
                    </form>
                  </div>
                </div>

                {/* Actions */}
                <div className="border-t border-zinc-850 pt-4 flex gap-2">
                  <button
                    onClick={() => setSelectedAsset(null)}
                    className="flex-1 bg-zinc-800 hover:bg-zinc-750 text-zinc-300 text-xs font-semibold py-2.5 rounded-xl transition-all cursor-pointer text-center"
                  >
                    Close
                  </button>
                  <button
                    onClick={() => handleDeleteAsset(selectedAsset.id)}
                    disabled={isDeleting}
                    className="flex-1 bg-rose-600/90 hover:bg-rose-650 text-white text-xs font-semibold py-2.5 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-1 disabled:opacity-50"
                  >
                    {isDeleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                    Delete Asset
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
