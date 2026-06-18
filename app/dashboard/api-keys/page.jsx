"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Key, Plus, Loader2, Trash2, Copy, Check, ShieldAlert, KeyRound } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);

  // Form states
  const [keyName, setKeyName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Generated Key display states
  const [newPlaintextKey, setNewPlaintextKey] = useState(null);
  const [copied, setCopied] = useState(false);

  // Fetch API keys list
  const fetchApiKeys = async () => {
    try {
      setLoading(true);
      const data = await api.get("/api/v1/api-keys");
      setKeys(data || []);
    } catch (error) {
      toast.error(error.message || "Failed to load API keys");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApiKeys();
  }, []);

  // Handle key generation
  const handleGenerateKey = async (e) => {
    e.preventDefault();
    if (!keyName.trim()) {
      toast.error("Please enter a name for the API key");
      return;
    }

    setIsSubmitting(true);
    setNewPlaintextKey(null);
    setCopied(false);

    try {
      const payload = { name: keyName.trim() };
      const response = await api.post("/api/v1/api-keys", payload);
      
      setNewPlaintextKey(response.plaintext_key);
      setKeyName("");
      toast.success("API Key generated successfully!");
      
      // Refresh list to show the new key metadata
      fetchApiKeys();
    } catch (error) {
      toast.error(error.message || "Failed to generate API key");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle key revocation
  const handleDeleteKey = async (keyId) => {
    if (!confirm("Are you sure you want to revoke and delete this API key? Any applications currently using this key will immediately lose access.")) {
      return;
    }

    try {
      await api.delete(`/api/v1/api-keys/${keyId}`);
      toast.success("API Key revoked successfully.");
      setKeys((prev) => prev.filter((k) => k.id !== keyId));
    } catch (error) {
      toast.error(error.message || "Failed to revoke API key");
    }
  };

  // Copy helper
  const handleCopyKey = () => {
    if (!newPlaintextKey) return;
    navigator.clipboard.writeText(newPlaintextKey);
    setCopied(true);
    toast.success("Copied to clipboard!");
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading && keys.length === 0) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="animate-spin text-purple-500" size={24} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header section */}
      <div className="flex justify-between items-center border-b border-zinc-900 pb-4">
        <div className="space-y-1">
          <h2 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100 flex items-center gap-2.5">
            <Key className="text-purple-400" size={22} />
            API Keys Access Management
          </h2>
          <p className="text-xs text-zinc-400">
            Generate and manage developer credentials for accessing ModeLens catalog endpoints programmatically
          </p>
        </div>
      </div>

      {/* Main split dashboard block */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
        
        {/* Left Column: API Keys list */}
        <div className="md:col-span-7 bg-zinc-900/10 border border-zinc-900 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-500">
              Active Credentials ({keys.length})
            </span>
          </div>

          <div className="space-y-3">
            {keys.length === 0 ? (
              <div className="text-center py-16 text-xs text-zinc-500 flex flex-col items-center justify-center gap-2">
                <KeyRound size={24} className="text-zinc-700" />
                No API keys generated yet. Use the configurator panel to generate credentials.
              </div>
            ) : (
              keys.map((k) => (
                <div
                  key={k.id}
                  className="bg-zinc-900/25 border border-zinc-900 hover:border-zinc-800 p-4 rounded-xl flex items-center justify-between gap-4 transition-all"
                >
                  <div className="space-y-1.5 min-w-0">
                    <div className="flex items-center gap-2.5">
                      <h4 className="text-xs font-bold text-zinc-200 truncate">{k.name}</h4>
                      <span className={`text-[8px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                        k.is_active ? "text-emerald-400 bg-emerald-950/20 border border-emerald-900/30" : "text-zinc-500 bg-zinc-900"
                      }`}>
                        {k.is_active ? "Active" : "Inactive"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <code className="text-[10px] font-mono text-zinc-400 bg-zinc-950 px-2.5 py-1 rounded border border-zinc-900">
                        {k.masked_key}
                      </code>
                    </div>
                    <p className="text-[9px] text-zinc-500">
                      Created on {new Date(k.created_at).toLocaleDateString()}
                    </p>
                  </div>

                  <button
                    onClick={() => handleDeleteKey(k.id)}
                    className="p-2 text-zinc-500 hover:text-rose-400 hover:bg-rose-950/15 rounded-lg border border-transparent hover:border-rose-900/20 transition-all cursor-pointer"
                    title="Revoke and Delete API Key"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Column: Key generation forms */}
        <div className="md:col-span-5 space-y-6">
          
          {/* Key Generator Config Card */}
          <div className="bg-zinc-900/20 border border-zinc-900 rounded-2xl p-5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2 border-b border-zinc-900 pb-3 mb-4">
              <Plus size={14} className="text-purple-400" />
              Generate Credentials
            </h3>

            <form onSubmit={handleGenerateKey} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 block">
                  Key Name / Description
                </label>
                <input
                  type="text"
                  required
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  placeholder="e.g. Production Webhook Client, Local API Test"
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-3 py-2.5 text-xs text-zinc-100 placeholder-zinc-650 outline-none transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting || !keyName.trim()}
                className="w-full bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-xs font-semibold py-2.5 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 shadow-md shadow-purple-950/20"
              >
                {isSubmitting ? (
                  <Loader2 className="animate-spin" size={14} />
                ) : (
                  <Plus size={14} />
                )}
                Create API Key
              </button>
            </form>
          </div>

          {/* New Plaintext Key Alert Box */}
          <AnimatePresence>
            {newPlaintextKey && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="bg-purple-950/10 border border-purple-800/30 rounded-2xl p-5 space-y-4 relative overflow-hidden"
              >
                {/* Subtle warning glow */}
                <div className="absolute top-0 right-0 w-24 h-24 bg-purple-600/10 rounded-full blur-2xl pointer-events-none" />

                <div className="flex items-start gap-2.5 text-purple-400">
                  <ShieldAlert size={16} className="shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <span className="text-xs font-bold uppercase tracking-wider block">
                      Copy API Key Credentials
                    </span>
                    <p className="text-[10px] text-zinc-350 leading-relaxed">
                      For security, this plaintext token will only be shown **once**. If you navigate away or close this block, you will not be able to retrieve it.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 bg-zinc-950 p-2.5 rounded-xl border border-zinc-850">
                  <code className="text-xs font-mono text-zinc-200 select-all truncate flex-1">
                    {newPlaintextKey}
                  </code>
                  <button
                    onClick={handleCopyKey}
                    className="p-2 text-zinc-400 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded-lg transition-all cursor-pointer flex items-center justify-center"
                    title="Copy to Clipboard"
                  >
                    {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

      </div>
    </div>
  );
}
