"use client";
import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { notificationsApi } from "@/lib/notifications";
import { User, Bell, Sparkles, Brain, Check, Loader2, Shield, Plus, X, Globe } from "lucide-react";
import { api } from "@/lib/api";
import toast from "react-hot-toast";

export default function AccountSettingsPage() {
  const { user, refreshUser } = useAuth();
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [ssoDomains, setSsoDomains] = useState([]);
  const [domainInput, setDomainInput] = useState("");
  const [addingDomain, setAddingDomain] = useState(false);
  const [deletingDomainId, setDeletingDomainId] = useState(null);
  const [loadingDomains, setLoadingDomains] = useState(false);
  const [preferences, setPreferences] = useState({
    notify_on_job_complete: true,
    notify_on_training_complete: true,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");


  const handleEditProfile = () => {
    setEditName(user?.full_name || user?.name || "");
    setEditEmail(user?.email || "");
    setIsEditingProfile(true);
  };

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const { api } = await import("@/lib/api");
      await api.patch("/api/v1/auth/profile", {
        full_name: editName,
        email: editEmail,
      });
      if (refreshUser) await refreshUser();
      toast.success("Profile updated successfully!");
      setIsEditingProfile(false);
    } catch (e) {
      toast.error("Failed to update profile");
    } finally {
      setSaving(false);
    }
  };

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

  useEffect(() => {
    api.get("/api/v1/brands").then(data => {
      setBrands(data || []);
      if (data?.length > 0) setSelectedBrandId(data[0].id.toString());
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedBrandId) return;
    fetchSsoDomains();
  }, [selectedBrandId]);

  const fetchSsoDomains = async () => {
    setLoadingDomains(true);
    try {
      const data = await api.get(`/api/v1/brands/${selectedBrandId}/sso-domains`);
      setSsoDomains(data?.domains || data || []);
    } catch {
      setSsoDomains([]);
    } finally {
      setLoadingDomains(false);
    }
  };

  const handleAddDomain = async () => {
    if (!domainInput.trim()) { toast.error("Enter a domain"); return; }
    setAddingDomain(true);
    try {
      await api.post(`/api/v1/brands/${selectedBrandId}/sso-domains`, { domain: domainInput.trim() });
      toast.success("Domain added!");
      setDomainInput("");
      fetchSsoDomains();
    } catch (e) {
      toast.error(e.message || "Failed to add domain");
    } finally {
      setAddingDomain(false);
    }
  };

  const handleDeleteDomain = async (domainId) => {
    setDeletingDomainId(domainId);
    try {
      await api.delete(`/api/v1/brands/${selectedBrandId}/sso-domains/${domainId}`);
      toast.success("Domain removed!");
      fetchSsoDomains();
    } catch {
      toast.error("Failed to remove domain");
    } finally {
      setDeletingDomainId(null);
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
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <User className="w-5 h-5 text-purple-400" />
            <h2 className="text-sm font-semibold text-white">Profile Information</h2>
          </div>
          {!isEditingProfile ? (
            <button
              onClick={handleEditProfile}
              className="text-xs text-purple-400 hover:text-purple-300 border border-purple-800 hover:border-purple-600 px-3 py-1.5 rounded-lg transition"
            >
              Edit Profile
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={handleSaveProfile}
                disabled={saving}
                className="text-xs bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg transition"
              >
                {saving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => setIsEditingProfile(false)}
                className="text-xs border border-zinc-600 text-zinc-400 hover:text-white px-3 py-1.5 rounded-lg transition"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-zinc-500 block mb-1">Full Name</label>
            {isEditingProfile ? (
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full bg-zinc-900 border border-purple-600 rounded-xl px-4 py-2.5 text-sm text-zinc-200 outline-none"
              />
            ) : (
              <div className="bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-zinc-200">
                {user?.full_name || user?.name || "—"}
              </div>
            )}
          </div>
          <div>
            <label className="text-xs text-zinc-500 block mb-1">Email Address</label>
            {isEditingProfile ? (
              <input
                type="email"
                value={editEmail}
                onChange={(e) => setEditEmail(e.target.value)}
                className="w-full bg-zinc-900 border border-purple-600 rounded-xl px-4 py-2.5 text-sm text-zinc-200 outline-none"
              />
            ) : (
              <div className="bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-zinc-200">
                {user?.email || "—"}
              </div>
            )}
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

      {/* SSO Domain Whitelist Card */}
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-2">
          <Shield className="w-5 h-5 text-purple-400" />
          <h2 className="text-base font-semibold text-white">SSO Domain Whitelist</h2>
        </div>
        <p className="text-xs text-zinc-400 mb-4">Allow users with matching email domains to automatically join your workspace as Viewers.</p>

        {/* Brand Selector */}
        {brands.length > 1 && (
          <div className="mb-4">
            <label className="text-xs text-zinc-400 mb-1 block">Brand Workspace</label>
            <select value={selectedBrandId} onChange={(e) => setSelectedBrandId(e.target.value)} className="bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-200 outline-none">
              {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
        )}

        {/* Add Domain Form */}
        <div className="flex gap-2 mb-4">
          <div className="flex-1 flex items-center gap-2 bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2">
            <Globe className="w-4 h-4 text-zinc-500 shrink-0" />
            <input
              type="text"
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddDomain()}
              placeholder="e.g. company.com"
              className="flex-1 bg-transparent text-sm text-zinc-200 outline-none placeholder-zinc-600"
            />
          </div>
          <button
            onClick={handleAddDomain}
            disabled={addingDomain || !domainInput.trim()}
            className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-4 py-2 rounded-xl text-sm font-medium transition"
          >
            {addingDomain ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Add
          </button>
        </div>

        {/* Domain List */}
        {loadingDomains ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="w-5 h-5 animate-spin text-purple-400" />
          </div>
        ) : ssoDomains.length === 0 ? (
          <div className="text-center py-6 text-zinc-600 text-sm border border-dashed border-zinc-800 rounded-xl">
            No domains whitelisted yet
          </div>
        ) : (
          <div className="space-y-2">
            {ssoDomains.map(domain => (
              <div key={domain.id || domain} className="flex items-center justify-between bg-zinc-800/50 border border-zinc-700 rounded-xl px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <Globe className="w-3.5 h-3.5 text-purple-400" />
                  <span className="text-sm text-zinc-200">{domain.domain || domain}</span>
                </div>
                <button
                  onClick={() => handleDeleteDomain(domain.id || domain)}
                  disabled={deletingDomainId === (domain.id || domain)}
                  className="text-zinc-500 hover:text-red-400 transition disabled:opacity-50"
                >
                  {deletingDomainId === (domain.id || domain) ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      </div>
    </div>
  );
}
