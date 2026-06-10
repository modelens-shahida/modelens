"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { FolderKanban, Plus, ArrowRight, Loader2, X, AlertCircle } from "lucide-react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

export default function BrandsPage() {
  const { user } = useAuth();
  const [brands, setBrands] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [brandName, setBrandName] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Fetch brands list
  const fetchBrands = async () => {
    try {
      const data = await api.get("/api/v1/brands");
      setBrands(data);
    } catch (error) {
      toast.error(error.message || "Failed to load brands");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBrands();
  }, []);

  const handleCreateBrand = async (e) => {
    e.preventDefault();
    if (!brandName.trim()) {
      toast.error("Brand name cannot be empty");
      return;
    }

    setIsCreating(true);
    try {
      await api.post("/api/v1/brands", { name: brandName });
      toast.success("Brand created successfully!");
      setBrandName("");
      setIsModalOpen(false);
      fetchBrands();
    } catch (error) {
      toast.error(error.message || "Failed to create brand");
    } finally {
      setIsCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="animate-spin text-purple-500" size={24} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header section */}
      <div className="flex justify-between items-center">
        <div className="space-y-1">
          <h2 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100">
            Brands
          </h2>
          <p className="text-xs text-zinc-400">
            Manage your brand accounts, team memberships, and asset structures
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20"
        >
          <Plus size={14} />
          New Brand
        </button>
      </div>

      {/* Zero State */}
      {brands.length === 0 ? (
        <div className="text-center py-16 bg-zinc-900/10 border border-zinc-900 rounded-2xl space-y-4 max-w-md mx-auto">
          <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-500 mx-auto">
            <FolderKanban size={22} />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-zinc-200">No Brands Yet</h3>
            <p className="text-xs text-zinc-400 px-6">
              Create a brand to organize your models, campaigns, collections, and catalog images.
            </p>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer"
          >
            <Plus size={14} />
            Create Brand
          </button>
        </div>
      ) : (
        /* Brands Grid */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {brands.map((brand) => {
            const isOwner = brand.owner_id === user?.id;

            return (
              <motion.div
                key={brand.id}
                whileHover={{ y: -4 }}
                className="bg-zinc-900/30 border border-zinc-850 rounded-2xl p-5 hover:bg-zinc-900/50 transition-all flex flex-col justify-between h-44 group relative overflow-hidden"
              >
                {/* Brand Initial Icon */}
                <div className="flex justify-between items-start">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600/30 to-indigo-600/30 border border-purple-500/10 flex items-center justify-center font-bold text-sm text-purple-400 uppercase">
                    {brand.name.charAt(0)}
                  </div>
                  {isOwner ? (
                    <span className="text-[10px] bg-purple-950/40 border border-purple-800/20 text-purple-400 px-2 py-0.5 rounded-full uppercase tracking-wider font-semibold">
                      Owner
                    </span>
                  ) : (
                    <span className="text-[10px] bg-zinc-850/60 border border-zinc-800 text-zinc-400 px-2 py-0.5 rounded-full uppercase tracking-wider font-semibold">
                      Member
                    </span>
                  )}
                </div>

                {/* Brand Title */}
                <div className="mt-4">
                  <h3 className="text-sm font-semibold text-zinc-200 group-hover:text-white truncate">
                    {brand.name}
                  </h3>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mt-0.5">
                    Brand ID: {brand.id}
                  </p>
                </div>

                {/* Arrow link */}
                <div className="border-t border-zinc-850/80 pt-3 mt-4 flex items-center justify-between">
                  <span className="text-xs text-zinc-500 font-medium group-hover:text-zinc-300 transition-colors">
                    Manage assets & team
                  </span>
                  <Link
                    href={`/dashboard/brands/${brand.id}`}
                    className="text-purple-400 hover:text-purple-300 text-xs font-semibold flex items-center gap-1 transition-colors"
                  >
                    View Details
                    <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
                  </Link>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Create Brand Modal */}
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
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 relative z-10 shadow-2xl space-y-4"
            >
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <FolderKanban className="text-purple-400" size={18} />
                  Create Brand Account
                </h3>
                <button
                  onClick={() => setIsModalOpen(false)}
                  className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg transition-colors cursor-pointer"
                >
                  <X size={16} />
                </button>
              </div>

              <form onSubmit={handleCreateBrand} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    Brand Name
                  </label>
                  <input
                    type="text"
                    required
                    value={brandName}
                    onChange={(e) => setBrandName(e.target.value)}
                    placeholder="e.g. Chanel, Zara, Zara Kids"
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-all"
                  />
                  <p className="text-[10px] text-zinc-500">
                    You'll automatically be assigned the Owner role.
                  </p>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="bg-zinc-800 hover:bg-zinc-750 text-zinc-300 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isCreating}
                    className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer flex items-center gap-1 shadow-md shadow-purple-950/20"
                  >
                    {isCreating ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : (
                      "Create"
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
