"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Terminal, Plus, Loader2, Play, Save, ChevronRight, FileText } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "react-hot-toast";

export default function PromptsPage() {
  const { user } = useAuth();

  // Data states
  const [prompts, setPrompts] = useState([]);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [loading, setLoading] = useState(true);

  // Form states (Right Column Editor)
  const [isEditing, setIsEditing] = useState(false); // true if editing an existing, false if creating a new one
  const [promptName, setPromptName] = useState("");
  const [promptText, setPromptText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Fetch prompts list
  const fetchPrompts = async () => {
    try {
      setLoading(true);
      const data = await api.get("/api/v1/prompts");
      setPrompts(data);
      if (data.length > 0) {
        setSelectedPrompt(data[0]);
        setPromptName(data[0].name);
        setPromptText(data[0].prompt_text);
        setIsEditing(true);
      } else {
        // Set up blank form if list is empty
        handleNewPromptClick();
      }
    } catch (error) {
      toast.error(error.message || "Failed to load prompt templates");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrompts();
  }, []);

  // Set selected prompt details in editor
  const handleSelectPrompt = (prompt) => {
    setSelectedPrompt(prompt);
    setPromptName(prompt.name);
    setPromptText(prompt.prompt_text);
    setIsEditing(true);
  };

  // Set up form for creating a new template
  const handleNewPromptClick = () => {
    setSelectedPrompt(null);
    setPromptName("");
    setPromptText("");
    setIsEditing(false);
  };

  // Submit prompt form (Only POST supported currently on backend)

  const handleDeletePrompt = async () => {
    if (!selectedPrompt) return;
    if (!window.confirm(`Are you sure you want to delete "${selectedPrompt.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/api/v1/prompts/${selectedPrompt.id}`);
      toast.success("Prompt template deleted");
      setPrompts((prev) => prev.filter((p) => p.id !== selectedPrompt.id));
      setSelectedPrompt(null);
      setPromptName("");
      setPromptText("");
      setIsEditing(false);
    } catch (e) {
      toast.error("Failed to delete prompt template");
    }
  };

  const handleDeletePrompt = async () => {
    if (!selectedPrompt) return;
    if (!window.confirm(`Are you sure you want to delete "${selectedPrompt.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/api/v1/prompts/${selectedPrompt.id}`);
      toast.success("Prompt template deleted");
      setPrompts((prev) => prev.filter((p) => p.id !== selectedPrompt.id));
      setSelectedPrompt(null);
      setPromptName("");
      setPromptText("");
      setIsEditing(false);
    } catch (e) {
      toast.error("Failed to delete prompt template");
    }
  };

  const handleSavePrompt = async (e) => {
    e.preventDefault();
    if (!promptName.trim()) {
      toast.error("Template name is required");
      return;
    }
    if (!promptText.trim()) {
      toast.error("Prompt instruction text is required");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        name: promptName.trim(),
        prompt_text: promptText.trim(),
      };

      if (!isEditing) {
        // Create new prompt template
        const newPrompt = await api.post("/api/v1/prompts", payload);
        toast.success("Prompt template created successfully!");
        setPrompts((prev) => [...prev, newPrompt]);
        setSelectedPrompt(newPrompt);
        setIsEditing(true);
      } else {
        // PATCH existing prompt template in-place
        const updatedPrompt = await api.patch(`/api/v1/prompts/${selectedPrompt.id}`, payload);
        toast.success("Prompt template updated successfully!");
        setPrompts((prev) => prev.map((p) => p.id === selectedPrompt.id ? updatedPrompt : p));
        setSelectedPrompt(updatedPrompt);
      }
    } catch (error) {
      toast.error(error.message || "Failed to save prompt template");
    } finally {
      setIsSubmitting(false);
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
      <div className="flex justify-between items-center border-b border-zinc-900 pb-4">
        <div className="space-y-1">
          <h2 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100 flex items-center gap-2">
            <Terminal className="text-purple-400" size={22} />
            AI Prompts Library
          </h2>
          <p className="text-xs text-zinc-400">
            Write, review, and seed prompt templates utilized by your model catalog generation workflows
          </p>
        </div>
      </div>

      {/* Main split dashboard editor desk */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-stretch">
        
        {/* Left Column: Prompts List selector */}
        <div className="md:col-span-4 bg-zinc-900/10 border border-zinc-900 rounded-2xl p-4 flex flex-col space-y-4 min-h-[450px]">
          <div className="flex justify-between items-center shrink-0">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-500">
              Templates ({prompts.length})
            </span>
            <button
              onClick={handleNewPromptClick}
              className="flex items-center gap-1 bg-purple-600/20 hover:bg-purple-600/30 text-purple-400 text-[10px] font-bold px-2.5 py-1.5 rounded-lg transition-all cursor-pointer border border-purple-800/20"
            >
              <Plus size={10} />
              New Prompt
            </button>
          </div>

          {/* List items block */}
          <div className="flex-1 overflow-y-auto space-y-2 max-h-[500px] pr-1">
            {prompts.length === 0 ? (
              <div className="text-center py-16 text-xs text-zinc-550 flex flex-col items-center justify-center gap-2">
                <FileText size={18} />
                No templates seeded. Create a new prompt to get started.
              </div>
            ) : (
              prompts.map((prompt) => {
                const isSelected = selectedPrompt?.id === prompt.id;
                return (
                  <button
                    key={prompt.id}
                    onClick={() => handleSelectPrompt(prompt)}
                    className={`w-full text-left p-3.5 rounded-xl border flex items-center justify-between group transition-all cursor-pointer ${
                      isSelected
                        ? "bg-purple-950/20 border-purple-500/30 text-zinc-200"
                        : "bg-zinc-900/30 border-zinc-900 text-zinc-400 hover:border-zinc-800 hover:text-zinc-200"
                    }`}
                  >
                    <div className="min-w-0 pr-2">
                      <h4 className="text-xs font-bold truncate group-hover:text-zinc-150 transition-colors">
                        {prompt.name}
                      </h4>
                      <p className="text-[9px] text-zinc-550 truncate mt-0.5 max-w-[200px]">
                        {prompt.prompt_text}
                      </p>
                    </div>
                    <ChevronRight
                      size={12}
                      className={`shrink-0 text-zinc-600 group-hover:text-zinc-400 group-hover:translate-x-0.5 transition-all ${
                        isSelected ? "text-purple-400 translate-x-0.5" : ""
                      }`}
                    />
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Prompt parameters editor */}
        <div className="md:col-span-8 bg-zinc-900/20 border border-zinc-900 rounded-2xl p-5 flex flex-col justify-between">
          <form onSubmit={handleSavePrompt} className="space-y-4 flex flex-col h-full justify-between">
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
                <span className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Terminal size={14} className="text-purple-400" />
                  {isEditing ? `Edit Template: ${selectedPrompt?.name}` : "Create New Prompt"}
                </span>
                {isEditing && (
                  <span className="text-[9px] text-zinc-550 bg-zinc-900 px-2 py-0.5 rounded font-mono">
                    ID: {selectedPrompt?.id}
                  </span>
                )}
              </div>

              {/* Input: Template title */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-350 block uppercase tracking-wider">
                  Template Name
                </label>
                <input
                  type="text"
                  required
                  value={promptName}
                  onChange={(e) => setPromptName(e.target.value)}
                  placeholder="e.g. Studio Light Portrait - High Contrast, Mediterranean Vibe Outdoor"
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none transition-all"
                />
              </div>

              {/* Input: Code area for prompts */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-350 block uppercase tracking-wider">
                  Prompt Text Instructions
                </label>
                <textarea
                  rows={12}
                  required
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
                  placeholder="Write details instructions for the AI generation model. You can specify variables or format (e.g. 'Highly detailed studio photograph of model wearing, shot on 85mm lens, depth of field, warm color grading, soft focus background')..."
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-3 text-xs text-zinc-100 placeholder-zinc-500 outline-none transition-all resize-none leading-relaxed font-mono"
                />
              </div>
            </div>

            {/* Form footer tools */}
            <div className="flex justify-end gap-3 border-t border-zinc-900 pt-4 mt-6">
              {isEditing && (
                <button
                  type="button"
                  onClick={handleNewPromptClick}
                  className="bg-zinc-850 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer border border-zinc-800"
                >
                  Create New Instead
                </button>
              )}
              <button
                type="submit"
                disabled={isSubmitting}
                className="bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-550 text-white text-xs font-semibold px-5 py-2.5 rounded-xl transition-all cursor-pointer flex items-center gap-1.5 shadow-md shadow-purple-950/20"
              >
                {isSubmitting ? (
                  <Loader2 className="animate-spin" size={14} />
                ) : (
                  <Save size={12} />
                )}
                {isEditing ? "Save Changes" : "Save Template"}
              </button>
              {isEditing && (
                <button
                  type="button"
                  onClick={handleDeletePrompt}
                  className="px-4 py-2 text-sm font-medium text-red-400 border border-red-800 hover:bg-red-950/30 rounded-xl transition"
                >
                  Delete
                </button>
              )}
            </div>
          </form>
        </div>

      </div>
    </div>
  );
}
