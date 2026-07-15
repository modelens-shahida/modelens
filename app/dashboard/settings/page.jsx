"use client";
import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { notificationsApi } from "@/lib/notifications";
import { User, Bell, Sparkles, Brain, Check, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

export default function AccountSettingsPage() {
  const { user } = useAuth();
  const [preferences, setPreferences] = useState({
    notify_on_job_complete: true,
    notify_on_training_complete: true,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    notificationsApi.getPreferences().then((data) => {
      if (data) setPreferences(data);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleToggle = async (key) => {
    const updated = { ...preferences, [key]: !preferences[key] };
    setPreferences(updated);
    setSaving(true);
    try {
      await notificationsApi.updatePreferences(updated);
      toast.success("Preferences updated!");
    } catch {
      toast.error("Failed to update preferences");
      setPreferences(preferences);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white p-6 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Account Settings</h1>
        <p className="text-zinc-400 text-sm mt-1">Manage your profile and notification preferences</p>
      </div>

      {/* Profile Card */}
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <User className="w-5 h-5 text-purple-400" />
          <h2 className="text-sm font-semibold text-white">Profile Information</h2>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-zinc-500 block mb-1">Full Name</label>
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-zinc-200">
              {user?.full_name || user?.name || "—"}
            </div>
          </div>
          <div>
            <label className="text-xs text-zinc-500 block mb-1">Email Address</label>
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-zinc-200">
              {user?.email || "—"}
            </div>
          </div>
          <div>
            <label className="text-xs text-zinc-500 block mb-1">Role</label>
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-zinc-200 capitalize">
              {user?.role || "user"}
            </div>
          </div>
        </div>
      </div>

      {/* Notification Preferences Card */}
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Bell className="w-5 h-5 text-purple-400" />
            <h2 className="text-sm font-semibold text-white">Notification Preferences</h2>
          </div>
          {saving && <Loader2 className="w-4 h-4 animate-spin text-purple-400" />}
        </div>

        {loading ? (
          <div className="text-zinc-400 text-sm">Loading preferences...</div>
        ) : (
          <div className="space-y-4">
            {/* Job Complete Toggle */}
            <div className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-xl p-4">
              <div className="flex items-center gap-3">
                <Sparkles className="w-4 h-4 text-purple-400" />
                <div>
                  <p className="text-sm font-medium text-white">AI Job Completion</p>
                  <p className="text-xs text-zinc-400">Receive in-app alerts when catalog generations complete.</p>
                </div>
              </div>
              <button
                onClick={() => handleToggle("notify_on_job_complete")}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  preferences.notify_on_job_complete ? "bg-purple-600" : "bg-zinc-700"
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  preferences.notify_on_job_complete ? "translate-x-5" : "translate-x-0"
                }`} />
              </button>
            </div>

            {/* Training Complete Toggle */}
            <div className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-xl p-4">
              <div className="flex items-center gap-3">
                <Brain className="w-4 h-4 text-purple-400" />
                <div>
                  <p className="text-sm font-medium text-white">Model Training Completion</p>
                  <p className="text-xs text-zinc-400">Receive alerts when custom AI model training runs finish.</p>
                </div>
              </div>
              <button
                onClick={() => handleToggle("notify_on_training_complete")}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  preferences.notify_on_training_complete ? "bg-purple-600" : "bg-zinc-700"
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  preferences.notify_on_training_complete ? "translate-x-5" : "translate-x-0"
                }`} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
