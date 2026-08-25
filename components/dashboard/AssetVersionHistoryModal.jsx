"use client";

import React, { useState, useEffect } from "react";
import { assetRegistryApi } from "@/lib/assetRegistryApi";
import { X, History, Plus, Hash, FileCode, CheckCircle2, Copy, Loader2, Calendar, HardDrive } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";

export default function AssetVersionHistoryModal({ asset, isOpen, onClose }) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddVersion, setShowAddVersion] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [copiedHash, setCopiedHash] = useState(null);

  // New Version Form State
  const [newStorageUri, setNewStorageUri] = useState("");
  const [newWidth, setNewWidth] = useState("");
  const [newHeight, setNewHeight] = useState("");
  const [newMimeType, setNewMimeType] = useState("image/png");
  const [newSha256, setNewSha256] = useState("");

  useEffect(() => {
    if (isOpen && asset?.id) {
      fetchVersions();
    }
  }, [isOpen, asset]);

  const fetchVersions = async () => {
    setLoading(true);
    try {
      const data = await assetRegistryApi.getVersions(asset.id);
      setVersions(data?.versions || []);
    } catch (err) {
      console.error("Failed to fetch asset versions:", err);
      toast.error("Could not load version history");
      setVersions([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateVersion = async (e) => {
    e.preventDefault();
    if (!newStorageUri.trim()) {
      toast.error("Storage URI is required");
      return;
    }

    setSubmitting(true);
    try {
      await assetRegistryApi.createVersion(asset.id, {
        storage_uri: newStorageUri.trim(),
        width: newWidth ? parseInt(newWidth) : null,
        height: newHeight ? parseInt(newHeight) : null,
        mime_type: newMimeType,
        content_hash_sha256: newSha256.trim() || undefined,
      });

      toast.success("New asset version created successfully");
      setShowAddVersion(false);
      setNewStorageUri("");
      setNewWidth("");
      setNewHeight("");
      setNewSha256("");
      fetchVersions();
    } catch (err) {
      console.error("Failed to create version:", err);
      toast.error(err?.message || "Failed to create version");
    } finally {
      setSubmitting(false);
    }
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(id);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopiedHash(null), 2000);
  };

  if (!isOpen || !asset) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-zinc-950 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800/80 bg-zinc-900/40">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                Version History
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                  {asset.name || `Asset #${asset.id}`}
                </span>
              </h3>
              <p className="text-xs text-zinc-400">Immutable version chain and SHA-256 byte checksums</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {/* Action Bar */}
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-400">
              Total Versions: <strong className="text-white">{versions.length}</strong>
            </span>
            <button
              onClick={() => setShowAddVersion(!showAddVersion)}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition flex items-center gap-1.5 shadow-lg shadow-indigo-500/20"
            >
              <Plus className="w-3.5 h-3.5" />
              {showAddVersion ? "Cancel" : "Add New Version"}
            </button>
          </div>

          {/* Add Version Form */}
          <AnimatePresence>
            {showAddVersion && (
              <motion.form
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                onSubmit={handleCreateVersion}
                className="p-4 rounded-xl bg-zinc-900/80 border border-indigo-500/30 space-y-3 overflow-hidden"
              >
                <h4 className="text-xs font-semibold text-indigo-300 uppercase tracking-wider">
                  Register Sequential Version (v{versions.length + 1})
                </h4>

                <div>
                  <label className="text-[11px] text-zinc-400 block mb-1">Storage URI / Image URL *</label>
                  <input
                    type="text"
                    value={newStorageUri}
                    onChange={(e) => setNewStorageUri(e.target.value)}
                    placeholder="https://... or s3://..."
                    required
                    className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-white text-xs font-mono focus:border-indigo-500 outline-none"
                  />
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[11px] text-zinc-400 block mb-1">Width (px)</label>
                    <input
                      type="number"
                      value={newWidth}
                      onChange={(e) => setNewWidth(e.target.value)}
                      placeholder="2048"
                      className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-white text-xs font-mono focus:border-indigo-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-zinc-400 block mb-1">Height (px)</label>
                    <input
                      type="number"
                      value={newHeight}
                      onChange={(e) => setNewHeight(e.target.value)}
                      placeholder="2560"
                      className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-white text-xs font-mono focus:border-indigo-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-zinc-400 block mb-1">MIME Type</label>
                    <select
                      value={newMimeType}
                      onChange={(e) => setNewMimeType(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-white text-xs focus:border-indigo-500 outline-none"
                    >
                      <option value="image/png">image/png</option>
                      <option value="image/jpeg">image/jpeg</option>
                      <option value="image/webp">image/webp</option>
                      <option value="video/mp4">video/mp4</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="text-[11px] text-zinc-400 block mb-1">SHA-256 Checksum (Optional)</label>
                  <input
                    type="text"
                    value={newSha256}
                    onChange={(e) => setNewSha256(e.target.value)}
                    placeholder="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                    className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-white text-xs font-mono focus:border-indigo-500 outline-none"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setShowAddVersion(false)}
                    className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition flex items-center gap-1.5"
                  >
                    {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Save Version
                  </button>
                </div>
              </motion.form>
            )}
          </AnimatePresence>

          {/* Versions List */}
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 text-zinc-500 space-y-2">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
              <p className="text-xs">Loading version chain...</p>
            </div>
          ) : versions.length === 0 ? (
            <div className="text-center py-12 rounded-xl border border-dashed border-zinc-800 text-zinc-500 text-xs">
              No version history records found for this asset.
            </div>
          ) : (
            <div className="space-y-3">
              {versions.map((ver, idx) => (
                <div
                  key={ver.id || idx}
                  className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 transition space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-full bg-indigo-950/80 border border-indigo-700 text-indigo-300 text-xs font-mono font-bold">
                        v{ver.version || (versions.length - idx)}
                      </span>
                      {idx === 0 && (
                        <span className="px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-[10px] uppercase font-bold tracking-wider">
                          Latest Active
                        </span>
                      )}
                    </div>

                    <span className="text-[11px] text-zinc-500 flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {ver.created_at ? new Date(ver.created_at).toLocaleString() : "Recently"}
                    </span>
                  </div>

                  {/* URI Link */}
                  <div className="flex items-center justify-between p-2 rounded bg-zinc-950 border border-zinc-800/60 font-mono text-xs">
                    <span className="text-zinc-300 truncate max-w-md">{ver.storage_uri}</span>
                    <button
                      onClick={() => copyToClipboard(ver.storage_uri, `uri-${ver.id}`)}
                      className="p-1 text-zinc-500 hover:text-zinc-300 transition"
                      title="Copy URI"
                    >
                      {copiedHash === `uri-${ver.id}` ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>

                  {/* Checksum Hash & Metadata */}
                  {ver.content_hash_sha256 && (
                    <div className="flex items-center gap-2 text-[11px] font-mono text-zinc-400">
                      <Hash className="w-3 h-3 text-zinc-500 shrink-0" />
                      <span className="truncate">{ver.content_hash_sha256}</span>
                      <button
                        onClick={() => copyToClipboard(ver.content_hash_sha256, `hash-${ver.id}`)}
                        className="text-zinc-500 hover:text-zinc-300 shrink-0"
                      >
                        {copiedHash === `hash-${ver.id}` ? "Copied" : "Copy"}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
