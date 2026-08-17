"use client";
import AuditLogsList from "@/components/dashboard/AuditLogsList";
import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Shield, Globe, Plus, X, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

export default function SettingsPage() {
  const { user } = useAuth();
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [ssoDomains, setSsoDomains] = useState([]);
  const [domainInput, setDomainInput] = useState("");
  const [addingDomain, setAddingDomain] = useState(false);
  const [deletingDomainId, setDeletingDomainId] = useState(null);
  const [loadingDomains, setLoadingDomains] = useState(false);

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
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-zinc-400 text-sm mt-1">Manage your workspace and security settings</p>
        </div>

        {/* Brand Selector */}
        {brands.length > 0 && (
          <div className="flex items-center gap-3">
            <label className="text-xs text-zinc-400">Brand:</label>
            <select value={selectedBrandId} onChange={(e) => setSelectedBrandId(e.target.value)} className="bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-200 outline-none">
              {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
        )}

        {/* SSO Domain Whitelist */}
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-2">
            <Shield className="w-5 h-5 text-purple-400" />
            <h2 className="text-base font-semibold text-white">SSO Domain Whitelist</h2>
          </div>
          <p className="text-xs text-zinc-400 mb-4">Allow users with matching email domains to automatically join your workspace.</p>
          <div className="flex gap-2 mb-4">
            <div className="flex-1 flex items-center gap-2 bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2">
              <Globe className="w-4 h-4 text-zinc-500 shrink-0" />
              <input type="text" value={domainInput} onChange={(e) => setDomainInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAddDomain()} placeholder="e.g. company.com" className="flex-1 bg-transparent text-sm text-zinc-200 outline-none placeholder-zinc-600" />
            </div>
            <button onClick={handleAddDomain} disabled={addingDomain || !domainInput.trim()} className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-4 py-2 rounded-xl text-sm font-medium transition">
              {addingDomain ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Add
            </button>
          </div>
          {loadingDomains ? (
            <div className="flex items-center justify-center py-6"><Loader2 className="w-5 h-5 animate-spin text-purple-400" /></div>
          ) : ssoDomains.length === 0 ? (
            <div className="text-center py-6 text-zinc-600 text-sm border border-dashed border-zinc-800 rounded-xl">No domains whitelisted yet</div>
          ) : (
            <div className="space-y-2">
              {ssoDomains.map(domain => (
                <div key={domain.id || domain} className="flex items-center justify-between bg-zinc-800/50 border border-zinc-700 rounded-xl px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <Globe className="w-3.5 h-3.5 text-purple-400" />
                    <span className="text-sm text-zinc-200">{domain.domain || domain}</span>
                  </div>
                  <button onClick={() => handleDeleteDomain(domain.id || domain)} disabled={deletingDomainId === (domain.id || domain)} className="text-zinc-500 hover:text-red-400 transition disabled:opacity-50">
                    {deletingDomainId === (domain.id || domain) ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Brand Audit Logs */}
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <Shield className="w-5 h-5 text-purple-400" />
            <div>
              <h2 className="text-base font-semibold text-white">Brand Audit Logs</h2>
              <p className="text-xs text-zinc-400 mt-0.5">Track asset uploads, deletions, credit transactions, and user invitations</p>
            </div>
          </div>
          {selectedBrandId && <AuditLogsList brandId={selectedBrandId} />}
        </div>
      </div>
    </div>
  );
}
