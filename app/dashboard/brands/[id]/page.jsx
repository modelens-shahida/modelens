"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { 
  ArrowLeft, Users, Settings, Plus, X, Mail, Shield, 
  Loader2, Edit3, Check, Webhook, Activity, Trash2, Brain,
  Key, RefreshCw, Sliders, Eye, FileText, Download
} from "lucide-react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

export default function BrandDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const { user } = useAuth();
  
  const [brand, setBrand] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("members"); // "members" | "settings" | "webhooks" | "audit-logs"
  const [auditLogs, setAuditLogs] = useState([]);
  const [memoryData, setMemoryData] = useState(null);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [activeCategoryFilter, setActiveCategoryFilter] = useState("all");
  const [auditLogsOffset, setAuditLogsOffset] = useState(0);
  const [auditLogsLoading, setAuditLogsLoading] = useState(false);
  const [auditLogsHasMore, setAuditLogsHasMore] = useState(true);

  // Brand management states
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  // Settings states
  const [newBrandName, setNewBrandName] = useState("");
  const [isUpdatingName, setIsUpdatingName] = useState(false);
  const [domainWhitelist, setDomainWhitelist] = useState([]);
  const [whitelistInput, setWhitelistInput] = useState("");
  const [isUpdatingWhitelist, setIsUpdatingWhitelist] = useState(false);

  // Invite states
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [isInviting, setIsInviting] = useState(false);
  const [pendingInvites, setPendingInvites] = useState([]);

  // Webhooks states
  const [webhooks, setWebhooks] = useState([]);
  const [webhooksLoading, setWebhooksLoading] = useState(false);
  const [isCreateWebhookOpen, setIsCreateWebhookOpen] = useState(false);
  const [selectedWebhook, setSelectedWebhook] = useState(null);
  const [isLogsModalOpen, setIsLogsModalOpen] = useState(false);
  const [revealedSecrets, setRevealedSecrets] = useState({}); // { webhookId: boolean }

  // Create Webhook Form states
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookFormat, setWebhookFormat] = useState("verbose"); // "verbose" | "summary"
  const [webhookEvents, setWebhookEvents] = useState({
    "job.completed": true,
    "job.failed": true,
    "asset.processed": true,
    "character.training.completed": false,
    "character.training.failed": false,
  });
  const [filterRuleKey, setFilterRuleKey] = useState("");
  const [filterRuleValue, setFilterRuleValue] = useState("");
  const [isCreatingWebhook, setIsCreatingWebhook] = useState(false);

  // Delivery Logs states
  const [deliveryLogs, setDeliveryLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [logsLimit] = useState(15);
  const [logsOffset, setLogsOffset] = useState(0);
  const [hasMoreLogs, setHasMoreLogs] = useState(true);
  const [retryingLogId, setRetryingLogId] = useState(null);

  const AVAILABLE_EVENTS = [
    "job.completed",
    "job.failed",
    "asset.processed",
    "character.training.completed",
    "character.training.failed",
  ];

  // Fetch all page data
  const fetchData = async () => {
    try {
      const brandData = await api.get(`/api/v1/brands/${id}`);
      setBrand(brandData);
      setNewBrandName(brandData.name);

      const membersData = await api.get(`/api/v1/brands/${id}/members`);
      setMembers(membersData);

      try {
        const invitesData = await api.get(`/api/v1/brands/${id}/invites`);
        setPendingInvites(invitesData || []);
      } catch (err) {
        console.error("Failed to load invitations", err);
      }
    } catch (error) {
      toast.error(error.message || "Failed to load brand details");
      router.push("/dashboard/brands");
    } finally {
      setLoading(false);
    }
  };

  const fetchWebhooks = async () => {
    setWebhooksLoading(true);
    try {
      const data = await api.get(`/api/v1/webhooks?brand_id=${id}`);
      setWebhooks(data || []);
    } catch (error) {
      toast.error(error.message || "Failed to load webhooks");
    } finally {
      setWebhooksLoading(false);
    }
  };

  useEffect(() => {
    if (id) {
      fetchData();
    }
  }, [id]);

  const handleDeleteBrand = async () => {
    if (deleteConfirmText !== brand?.name) {
      toast.error("Brand name does not match");
      return;
    }
    setDeleting(true);
    try {
      await api.delete(`/api/v1/brands/${id}`);
      toast.success("Brand workspace deleted");
      router.push("/dashboard/brands");
    } catch (e) {
      toast.error("Failed to delete brand");
    } finally {
      setDeleting(false);
      setShowDeleteModal(false);
    }
  };

  const fetchAuthSettings = async () => {
    try {
      const data = await api.get(`/api/v1/brands/${id}/auth-settings`);
      setDomainWhitelist(data.domain_whitelist || []);
    } catch (error) {
      console.error("Failed to load auth settings", error);
    }
  };

  useEffect(() => {
    if (activeTab === "settings" && id) {
      fetchAuthSettings();
    }
  }, [activeTab, id]);

  useEffect(() => {
    if (activeTab === "webhooks") {
      fetchWebhooks();
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === "audit-logs" && id) {
      fetchAuditLogs(0);
    }
  }, [activeTab, id]);

  useEffect(() => {
    if (activeTab === "memory" && id) {
      fetchMemory();
    }
  }, [activeTab, id]);

  const fetchMemory = async () => {
    setMemoryLoading(true);
    try {
      const data = await api.get(`/api/v1/brands/${id}/memory`);
      setMemoryData(data);
    } catch (e) {
      toast.error("Failed to load brand memory");
    } finally {
      setMemoryLoading(false);
    }
  };

  const fetchAuditLogs = async (offset = 0) => {
    setAuditLogsLoading(true);
    try {
      const data = await api.get(`/api/v1/brands/${id}/audit-logs?limit=20&offset=${offset}`);
      if (offset === 0) {
        setAuditLogs(data);
      } else {
        setAuditLogs(prev => [...prev, ...data]);
      }
      setAuditLogsHasMore(data.length === 20);
      setAuditLogsOffset(offset + data.length);
    } catch (e) {
      toast.error("Failed to load audit logs");
    } finally {
      setAuditLogsLoading(false);
    }
  };

  const handleUpdateWhitelist = async (e) => {
    e?.preventDefault();
    setIsUpdatingWhitelist(true);
    try {
      const updated = await api.patch(`/api/v1/brands/${id}/auth-settings`, {
        domain_whitelist: domainWhitelist,
      });
      setDomainWhitelist(updated.domain_whitelist || []);
      toast.success("SSO domain whitelist saved!");
    } catch (error) {
      toast.error(error.message || "Failed to update auth settings");
    } finally {
      setIsUpdatingWhitelist(false);
    }
  };

  const handleUpdateName = async (e) => {
    e.preventDefault();
    if (!newBrandName.trim()) {
      toast.error("Brand name cannot be empty");
      return;
    }

    setIsUpdatingName(true);
    try {
      const updated = await api.patch(`/api/v1/brands/${id}`, { name: newBrandName });
      setBrand(updated);
      toast.success("Brand name updated successfully!");
    } catch (error) {
      toast.error(error.message || "Failed to update brand name");
    } finally {
      setIsUpdatingName(false);
    }
  };

  const handleInvite = async (e) => {
    e.preventDefault();
    if (!inviteEmail.trim()) {
      toast.error("Please enter a valid email address");
      return;
    }

    setIsInviting(true);
    try {
      await api.post(`/api/v1/brands/${id}/invites`, {
        email: inviteEmail,
        role: inviteRole,
      });
      toast.success("Invitation sent successfully!");
      setInviteEmail("");
      setInviteRole("viewer");
      setIsInviteModalOpen(false);
      // Refresh pending invites list
      const invitesData = await api.get(`/api/v1/brands/${id}/invites`);
      setPendingInvites(invitesData || []);
    } catch (error) {
      toast.error(error.message || "Failed to send invitation");
    } finally {
      setIsInviting(false);
    }
  };

  const handleRevokeInvite = async (inviteId) => {
    if (!confirm("Are you sure you want to revoke this invitation?")) return;

    try {
      await api.delete(`/api/v1/brands/${id}/invites/${inviteId}`);
      toast.success("Invitation revoked successfully!");
      // Refresh pending invites list
      const invitesData = await api.get(`/api/v1/brands/${id}/invites`);
      setPendingInvites(invitesData || []);
    } catch (error) {
      toast.error(error.message || "Failed to revoke invitation");
    }
  };

  // Webhook integration handlers
  const handleCreateWebhook = async (e) => {
    e.preventDefault();
    if (!webhookUrl.trim() || !webhookUrl.startsWith("http")) {
      toast.error("Please enter a valid webhook URL starting with http:// or https://");
      return;
    }

    const selectedEvents = Object.keys(webhookEvents).filter(e => webhookEvents[e]);
    if (selectedEvents.length === 0) {
      toast.error("Please select at least one event type.");
      return;
    }

    setIsCreatingWebhook(true);
    try {
      let filter_rules = null;
      if (filterRuleKey.trim() && filterRuleValue.trim()) {
        filter_rules = { [filterRuleKey.trim()]: filterRuleValue.trim() };
      }

      await api.post("/api/v1/webhooks", {
        brand_id: parseInt(id),
        url: webhookUrl,
        events: selectedEvents,
        payload_format: webhookFormat,
        filter_rules: filter_rules,
      });

      toast.success("Webhook subscription created!");
      setIsCreateWebhookOpen(false);
      setWebhookUrl("");
      setFilterRuleKey("");
      setFilterRuleValue("");
      fetchWebhooks();
    } catch (error) {
      toast.error(error.message || "Failed to create webhook");
    } finally {
      setIsCreatingWebhook(false);
    }
  };

  const handleDeleteWebhook = async (webhookId) => {
    if (!confirm("Are you sure you want to delete this webhook subscription?")) return;

    try {
      await api.delete(`/api/v1/webhooks/${webhookId}`);
      toast.success("Webhook deleted successfully.");
      fetchWebhooks();
    } catch (error) {
      toast.error(error.message || "Failed to delete webhook");
    }
  };

  const loadWebhookLogs = async (webhookId, reset = false) => {
    setLogsLoading(true);
    const currentOffset = reset ? 0 : logsOffset;
    try {
      const data = await api.get(`/api/v1/webhooks/${webhookId}/delivery-logs?limit=${logsLimit}&offset=${currentOffset}`);
      if (reset) {
        setDeliveryLogs(data || []);
        setLogsOffset(logsLimit);
      } else {
        setDeliveryLogs(prev => [...prev, ...(data || [])]);
        setLogsOffset(prev => prev + logsLimit);
      }
      setHasMoreLogs((data || []).length === logsLimit);
    } catch (error) {
      toast.error(error.message || "Failed to load delivery logs");
    } finally {
      setLogsLoading(false);
    }
  };

  const handleOpenLogs = (webhook) => {
    setSelectedWebhook(webhook);
    setDeliveryLogs([]);
    setLogsOffset(0);
    setHasMoreLogs(true);
    setIsLogsModalOpen(true);
    loadWebhookLogs(webhook.id, true);
  };

  const handleRetryDelivery = async (logId) => {
    setRetryingLogId(logId);
    try {
      await api.post(`/api/v1/webhooks/logs/${logId}/retry`);
      toast.success("Webhook delivery queued for retry.");
      // Reload logs to reflect 'retrying' status
      if (selectedWebhook) {
        loadWebhookLogs(selectedWebhook.id, true);
      }
    } catch (error) {
      toast.error(error.message || "Failed to retry delivery");
    } finally {
      setRetryingLogId(null);
    }
  };

  const handleExportAnalytics = async (format) => {
    setIsExporting(true);
    try {
      const token = localStorage.getItem("modelens_token");
      const headers = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      
      const response = await fetch(`/api/v1/analytics/export?brand_id=${id}&format=${format}`, {
        method: "GET",
        headers
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to export analytics");
      }

      // Download the blob
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `modelens_analytics_brand_${id}_${new Date().toISOString().slice(0, 10)}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success(`Analytics exported as ${format.toUpperCase()} successfully!`);
    } catch (error) {
      console.error("Export failed:", error);
      toast.error(error.message || "Failed to export analytics data");
    } finally {
      setIsExporting(false);
    }
  };

  // Helper to resolve role color badge
  const getRoleBadge = (role) => {
    const styles = {
      owner: "bg-purple-950/40 border-purple-800/30 text-purple-400",
      admin: "bg-blue-950/40 border-blue-800/30 text-blue-400",
      editor: "bg-emerald-950/40 border-emerald-800/30 text-emerald-400",
      viewer: "bg-zinc-850/60 border-zinc-800 text-zinc-400",
    };
    return styles[role] || styles.viewer;
  };

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="animate-spin text-purple-500" size={24} />
      </div>
    );
  }

  // Find user's membership on this brand
  const userIsOwner = brand?.owner_id === user?.id;
  const userMembership = members.find((m) => m.user_id === user?.id);
  const userRole = userIsOwner ? "owner" : userMembership?.role || "viewer";

  // Check RBAC permission for settings and invite
  const canManage = userRole === "owner" || userRole === "admin";


  const handleRemoveMember = async (memberId) => {
    try {
      await api.delete(`/api/v1/brands/${id}/members/${memberId}`);
      toast.success("Member removed");
      fetchData();
    } catch (e) {
      toast.error("Failed to remove member");
    }
  };

  const handleUpdateRole = async (memberId, newRole) => {
    try {
      await api.patch(`/api/v1/brands/${id}/members/${memberId}`, { role: newRole });
      toast.success("Role updated");
      fetchData();
    } catch (e) {
      toast.error("Failed to update role");
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Back link & Header */}
      <div className="flex flex-col gap-2">
        <Link
          href="/dashboard/brands"
          className="inline-flex items-center gap-1 text-zinc-400 hover:text-zinc-200 text-xs font-semibold"
        >
          <ArrowLeft size={12} /> Back to Brands
        </Link>
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div className="space-y-1">
            <h2 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100 flex items-center gap-3">
              {brand?.name}
              <span className={`text-[10px] uppercase tracking-wider font-semibold border px-2.5 py-0.5 rounded-full ${getRoleBadge(userRole)}`}>
                Your Role: {userRole}
              </span>
            </h2>
            <p className="text-xs text-zinc-500">Brand ID: {brand?.id}</p>
          </div>
          {activeTab === "members" && canManage && (
            <button
              onClick={() => setIsInviteModalOpen(true)}
              className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20"
            >
              <Plus size={14} />
              Invite Member
            </button>
          )}
          {activeTab === "webhooks" && canManage && (
            <button
              onClick={() => setIsCreateWebhookOpen(true)}
              className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20"
            >
              <Plus size={14} />
              Add Webhook
            </button>
          )}
        </div>
      </div>

      {/* Tabs Menu */}
      <div className="flex border-b border-zinc-850">
        <button
          onClick={() => setActiveTab("members")}
          className={`flex items-center gap-2 px-5 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer ${
            activeTab === "members"
              ? "border-purple-500 text-purple-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Users size={14} /> Team Members ({members.length + 1 + pendingInvites.length})
        </button>
        <button
          onClick={() => setActiveTab("webhooks")}
          className={`flex items-center gap-2 px-5 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer ${
            activeTab === "webhooks"
              ? "border-purple-500 text-purple-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Webhook size={14} /> Webhooks ({webhooks.length})
        </button>
        <button
          onClick={() => setActiveTab("settings")}
          className={`flex items-center gap-2 px-5 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer ${
            activeTab === "settings"
              ? "border-purple-500 text-purple-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Settings size={14} /> Settings & Roles
        </button>
        {canManage && (
          <button
            onClick={() => setActiveTab("audit-logs")}
            className={`flex items-center gap-2 px-5 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer ${
              activeTab === "audit-logs"
                ? "border-purple-500 text-purple-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Activity size={14} /> Audit Logs
          </button>
        )}
        <button
          onClick={() => setActiveTab("memory")}
          className={`flex items-center gap-2 px-5 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer ${
            activeTab === "memory"
              ? "border-purple-500 text-purple-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Brain size={14} /> Brand Memory
        </button>
      </div>

      {/* Tab Contents */}
      <div className="pt-2">
        {activeTab === "members" && (
          <div className="bg-zinc-900/10 border border-zinc-900 rounded-2xl overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-zinc-900 bg-zinc-950/40 text-zinc-500 text-[10px] font-bold uppercase tracking-wider">
                  <th className="px-6 py-4">User</th>
                  <th className="px-6 py-4">Role</th>
                  <th className="px-6 py-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900/60 text-xs">
                {/* Brand Creator/Owner row (Implicitly owner, not in members table) */}
                <tr className="hover:bg-zinc-900/20 transition-all">
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="font-semibold text-zinc-200">Brand Owner (Creator)</span>
                      <span className="text-[10px] text-zinc-500">ID: {brand?.owner_id}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-[10px] uppercase tracking-wider font-semibold border px-2 py-0.5 rounded-full bg-purple-950/40 border-purple-800/30 text-purple-400">
                      owner
                    </span>
                  </td>
                  <td className="px-6 py-4 text-zinc-400">Active</td>
                </tr>

                {/* Other members */}
                {members.map((member) => (
                  <tr key={member.id} className="hover:bg-zinc-900/20 transition-all">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-semibold text-zinc-200">{member.user_email}</span>
                        <span className="text-[10px] text-zinc-500">User ID: {member.user_id}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {canManage && member.user_id !== brand?.owner_id && member.user_id !== user?.id ? (
                        <select
                          value={member.role}
                          onChange={(e) => handleUpdateRole(member.user_id, e.target.value)}
                          className="bg-zinc-900 border border-zinc-700 rounded-lg px-2 py-1 text-xs text-zinc-200 outline-none cursor-pointer"
                        >
                          <option value="viewer">Viewer</option>
                          <option value="editor">Editor</option>
                          <option value="admin">Admin</option>
                        </select>
                      ) : (
                        <span className={`text-[10px] uppercase tracking-wider font-semibold border px-2 py-0.5 rounded-full ${getRoleBadge(member.role)}`}>
                          {member.role}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-zinc-400">
                      <div className="flex items-center justify-between">
                        <span>Active</span>
                        {canManage && member.user_id !== brand?.owner_id && member.user_id !== user?.id && (
                          <button
                            onClick={() => handleRemoveMember(member.user_id)}
                            className="text-red-400 hover:text-red-300 transition-colors p-1 rounded hover:bg-red-950/20"
                            title="Remove Member"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}

                {/* Pending invites */}
                {pendingInvites.map((invite) => (
                  <tr key={`invite-${invite.id}`} className="hover:bg-zinc-900/10 transition-all opacity-80">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-semibold text-zinc-300">{invite.email} (Pending)</span>
                        <span className="text-[10px] text-zinc-500">Expires: {new Date(invite.expires_at).toLocaleDateString()}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`text-[10px] uppercase tracking-wider font-semibold border px-2 py-0.5 rounded-full ${getRoleBadge(invite.role)}`}>
                        {invite.role}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-between">
                        <span className="text-amber-550 font-semibold">Invited</span>
                        {canManage && (
                          <button
                            onClick={() => handleRevokeInvite(invite.id)}
                            className="text-red-400 hover:text-red-300 transition-colors p-1 rounded hover:bg-red-950/20 cursor-pointer"
                            title="Revoke Invitation"
                          >
                            <X size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "webhooks" && (
          <div className="space-y-4">
            {webhooksLoading && webhooks.length === 0 ? (
              <div className="flex justify-center p-12">
                <Loader2 className="animate-spin text-purple-500" size={24} />
              </div>
            ) : webhooks.length === 0 ? (
              <div className="bg-zinc-900/10 border border-zinc-900 rounded-2xl p-12 text-center space-y-3">
                <Webhook className="mx-auto text-zinc-600" size={32} />
                <h3 className="text-sm font-semibold text-zinc-300">No webhooks registered</h3>
                <p className="text-xs text-zinc-500 max-w-sm mx-auto">
                  Register webhooks to receive real-time notifications when generation jobs finish or characters complete training.
                </p>
                {canManage && (
                  <button
                    onClick={() => setIsCreateWebhookOpen(true)}
                    className="inline-flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer mt-2"
                  >
                    <Plus size={14} /> Register Your First Webhook
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {webhooks.map((webhook) => (
                  <div key={webhook.id} className="bg-zinc-900/20 border border-zinc-900 p-5 rounded-2xl space-y-4 hover:border-zinc-800 transition-all">
                    <div className="flex flex-col sm:flex-row justify-between items-start gap-4">
                      <div className="space-y-1.5 flex-1 min-w-0">
                        <div className="flex items-center gap-2.5">
                          <span className={`h-2 w-2 rounded-full ${webhook.is_active ? "bg-emerald-500" : "bg-zinc-600"}`} />
                          <h4 className="text-xs font-bold text-zinc-200 truncate">{webhook.url}</h4>
                          <span className="text-[9px] uppercase tracking-widest font-bold border border-zinc-800 bg-zinc-950 px-2 py-0.5 rounded text-zinc-400">
                            {webhook.payload_format || "verbose"}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {webhook.events.map(ev => (
                            <span key={ev} className="text-[9px] bg-zinc-900 border border-zinc-850 px-2 py-0.5 rounded text-zinc-400 font-mono">
                              {ev}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleOpenLogs(webhook)}
                          className="flex items-center gap-1 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-850 p-2 rounded-xl text-xs transition-all cursor-pointer font-semibold"
                        >
                          <Activity size={14} /> Logs
                        </button>
                        {canManage && (
                          <button
                            onClick={() => handleDeleteWebhook(webhook.id)}
                            className="flex items-center gap-1 text-red-400 hover:text-red-300 hover:bg-red-950/20 p-2 rounded-xl text-xs transition-all cursor-pointer font-semibold"
                          >
                            <Trash2 size={14} /> Delete
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Signing Secret */}
                    <div className="flex flex-col sm:flex-row justify-between sm:items-center bg-zinc-950/40 border border-zinc-900 rounded-xl px-4 py-2.5 gap-2 text-xs">
                      <div className="flex items-center gap-2 text-zinc-400">
                        <Key size={13} className="text-purple-400" />
                        <span className="font-mono text-[10px]">Signing Secret:</span>
                        <span className="font-mono text-[11px] text-zinc-300 tracking-wider">
                          {revealedSecrets[webhook.id] ? webhook.secret_token : "••••••••••••••••••••••••••••••••••••••••"}
                        </span>
                      </div>
                      <button
                        onClick={() => toggleRevealSecret(webhook.id)}
                        className="text-purple-400 hover:text-purple-300 font-semibold text-[10px] uppercase tracking-wide self-end sm:self-auto cursor-pointer"
                      >
                        {revealedSecrets[webhook.id] ? "Hide" : "Reveal"}
                      </button>
                    </div>

                    {/* Filter Rules display if any */}
                    {webhook.filter_rules && Object.keys(webhook.filter_rules).length > 0 && (
                      <div className="flex items-center gap-2 text-[10px] text-zinc-500 bg-zinc-900/10 px-3 py-1.5 rounded-lg border border-zinc-900 max-w-fit">
                        <Sliders size={11} className="text-zinc-400" />
                        <span>Filter rules:</span>
                        {Object.entries(webhook.filter_rules).map(([k, v]) => (
                          <span key={k} className="font-mono text-zinc-400 border border-zinc-800 bg-zinc-950 px-1.5 py-0.5 rounded">
                            {k} = {String(v)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Danger Zone - Owner Only */}
            {userRole === "owner" && (
              <div className="border-t border-red-900/30 pt-6">
                <h3 className="text-sm font-semibold text-red-400 mb-1">Danger Zone</h3>
                <p className="text-xs text-zinc-500 mb-4">Permanently delete this brand workspace. This cannot be undone.</p>
                <button
                  onClick={() => { setShowDeleteModal(true); setDeleteConfirmText(""); }}
                  className="text-xs text-red-400 border border-red-800 hover:bg-red-950/30 px-4 py-2 rounded-xl transition"
                >
                  Delete Workspace
                </button>
              </div>
            )}
          </div>
        )}

  


      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-red-900/50 rounded-2xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold text-red-400 mb-2">Delete Workspace</h2>
            <p className="text-xs text-zinc-400 mb-4">
              This will permanently delete <strong className="text-white">{brand?.name}</strong> and all its data.
            </p>
            <p className="text-xs text-zinc-400 mb-2">Type <strong className="text-white">{brand?.name}</strong> to confirm:</p>
            <input
              type="text"
              value={deleteConfirmText}
              onChange={(e) => setDeleteConfirmText(e.target.value)}
              placeholder={brand?.name}
              className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-white outline-none mb-4"
            />
            <div className="flex gap-3">
              <button
                onClick={handleDeleteBrand}
                disabled={deleteConfirmText !== brand?.name || deleting}
                className="flex-1 bg-red-700 hover:bg-red-600 disabled:opacity-40 py-2 rounded-xl text-sm font-medium transition"
              >
                {deleting ? "Deleting..." : "Delete Workspace"}
              </button>
              <button
                onClick={() => setShowDeleteModal(false)}
                className="flex-1 border border-zinc-700 py-2 rounded-xl text-sm text-zinc-300 hover:text-white transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Brand Memory Tab */}
      {activeTab === "memory" && (
        <div className="space-y-6">
          {memoryLoading && (
            <div className="text-zinc-400 text-sm text-center py-8">Loading brand memory...</div>
          )}

          {memoryData && !memoryLoading && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Tag Cloud */}
              <div className="lg:col-span-2 bg-zinc-900/20 border border-zinc-800 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-white">Tag Cloud</h3>
                  <span className="text-xs text-zinc-500">{memoryData.total_assets} assets analyzed</span>
                </div>

                {/* Category Filters */}
                <div className="flex flex-wrap gap-2 mb-4">
                  {["all", ...new Set(
                    Object.keys(memoryData.tag_frequency || {})
                      .filter(k => k.includes(":"))
                      .map(k => k.split(":")[0])
                  )].map(cat => (
                    <button
                      key={cat}
                      onClick={() => setActiveCategoryFilter(cat)}
                      className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
                        activeCategoryFilter === cat
                          ? "bg-purple-600 border-purple-500 text-white"
                          : "border-zinc-700 text-zinc-400 hover:border-purple-500"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>

                {/* Tag Pills */}
                <div className="flex flex-wrap gap-2">
                  {Object.entries(memoryData.tag_frequency || {})
                    .filter(([tag]) => activeCategoryFilter === "all" || tag.startsWith(activeCategoryFilter + ":"))
                    .sort((a, b) => b[1] - a[1])
                    .map(([tag, count]) => {
                      const maxCount = Math.max(...Object.values(memoryData.tag_frequency));
                      const ratio = count / maxCount;
                      const size = ratio > 0.7 ? "text-lg px-4 py-2" : ratio > 0.4 ? "text-sm px-3 py-1.5" : "text-xs px-2 py-1";
                      const label = tag.includes(":") ? tag.split(":")[1] : tag;
                      return (
                        <span
                          key={tag}
                          className={`${size} rounded-full font-medium bg-gradient-to-r from-purple-900/60 to-indigo-900/60 border border-purple-700/40 text-purple-200`}
                          title={`${tag}: ${count} occurrences`}
                        >
                          {label} <span className="text-purple-400 text-xs">{count}</span>
                        </span>
                      );
                    })}
                </div>

                {Object.keys(memoryData.tag_frequency || {}).length === 0 && (
                  <div className="text-zinc-500 text-sm text-center py-8">No tags recorded yet. Upload and process assets to build brand memory.</div>
                )}
              </div>

              {/* Side Panel */}
              <div className="bg-gradient-to-br from-purple-950/30 to-indigo-950/30 border border-purple-800/30 rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-purple-300 mb-3">🧠 How Brand Memory Works</h3>
                <p className="text-xs text-zinc-400 leading-relaxed mb-4">
                  Brand Memory is a semantic profile built from your catalog assets. The AI orchestrator analyzes uploaded images and extracts visual attributes like lighting, mood, color palette, style, and composition.
                </p>
                <p className="text-xs text-zinc-400 leading-relaxed mb-4">
                  These tag frequencies are used to maintain consistency across AI-generated model catalog creatives, ensuring generated outputs align with your brand's visual identity.
                </p>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-500">Total Assets</span>
                    <span className="text-white font-semibold">{memoryData.total_assets}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-500">Unique Tags</span>
                    <span className="text-white font-semibold">{Object.keys(memoryData.tag_frequency || {}).length}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Audit Logs Tab */}
      {activeTab === "audit-logs" && canManage && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-zinc-200">Activity Timeline</h3>
              <p className="text-xs text-zinc-500">Security and audit trail of operations inside this workspace.</p>
            </div>
            {auditLogsLoading && (
              <Loader2 className="animate-spin text-purple-500" size={16} />
            )}
          </div>

          <div className="relative border-l border-zinc-800 ml-3.5 space-y-6 pt-2">
            {auditLogs.map((log) => {
              const actionLabel = log.action
                .replace(/_/g, " ")
                .replace(/\b\w/g, (c) => c.toUpperCase());

              // Premium timeline icons mapping
              const getActionIcon = (action) => {
                const act = action.toLowerCase();
                if (act.includes("member")) return <Users size={12} className="text-blue-400" />;
                if (act.includes("webhook")) return <Webhook size={12} className="text-emerald-400" />;
                if (act.includes("api_key")) return <Key size={12} className="text-amber-400" />;
                if (act.includes("asset")) return <FileText size={12} className="text-purple-400" />;
                if (act.includes("settings")) return <Settings size={12} className="text-zinc-400" />;
                return <Activity size={12} className="text-purple-400" />;
              };

              return (
                <div key={log.id} className="ml-6 relative">
                  <div className="absolute -left-9 top-1 w-6 h-6 rounded-full bg-zinc-950 border border-zinc-800 flex items-center justify-center shadow-lg">
                    {getActionIcon(log.action)}
                  </div>
                  <div className="bg-zinc-900/30 border border-zinc-900 rounded-xl p-4 space-y-2 backdrop-blur-md">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-zinc-250">{actionLabel}</span>
                      <span className="text-[10px] text-zinc-500">{new Date(log.created_at).toLocaleString()}</span>
                    </div>
                    {log.details && Object.keys(log.details).length > 0 && (
                      <div className="text-xs text-zinc-400 space-y-1 bg-zinc-950/20 p-2.5 rounded-lg border border-zinc-900/60 font-sans">
                        {Object.entries(log.details).map(([key, val]) => (
                          <div key={key} className="flex gap-2">
                            <span className="text-zinc-500">{key.replace(/_/g, " ")}:</span>
                            <span className="text-zinc-300 font-medium">{String(val)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {log.client_ip && (
                      <div className="text-[10px] text-zinc-600 flex items-center gap-1">
                        <span>IP Address:</span>
                        <span className="font-mono">{log.client_ip}</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {auditLogsHasMore && !auditLogsLoading && auditLogs.length > 0 && (
            <button
              onClick={() => fetchAuditLogs(auditLogsOffset)}
              className="w-full py-2.5 border border-zinc-850 hover:border-zinc-800 rounded-xl text-xs text-zinc-400 hover:text-white transition-all cursor-pointer font-semibold"
            >
              Load More Activity
            </button>
          )}

          {auditLogs.length === 0 && !auditLogsLoading && (
            <div className="text-zinc-500 text-xs text-center py-12 bg-zinc-900/10 border border-zinc-900 rounded-2xl">
              <Activity className="mx-auto text-zinc-700 mb-3" size={32} />
              <p>No activity logs found for this brand workspace.</p>
            </div>
          )}
        </div>
      )}

      {activeTab === "settings" && (
          <div className="bg-zinc-900/20 border border-zinc-900 rounded-2xl p-6 space-y-8">
            {/* Change Name Setting */}
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-zinc-200">Rename Brand</h3>
                <p className="text-xs text-zinc-500">Change the visible identifier name for this brand account.</p>
              </div>
              <form onSubmit={handleUpdateName} className="flex flex-col sm:flex-row gap-3 max-w-md">
                <input
                  type="text"
                  required
                  disabled={!canManage}
                  value={newBrandName}
                  onChange={(e) => setNewBrandName(e.target.value)}
                  className="flex-1 bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                />
                {canManage && (
                  <button
                    type="submit"
                    disabled={isUpdatingName || newBrandName.trim() === brand?.name}
                    className="bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-1 shadow-md shadow-purple-950/20 disabled:shadow-none"
                  >
                    {isUpdatingName ? <Loader2 className="animate-spin" size={14} /> : <Check size={14} />}
                    Update
                  </button>
                )}
              </form>
              {!canManage && (
                <p className="text-[10px] text-amber-500/80 flex items-center gap-1">
                  Requires Admin or Owner credentials to edit brand settings.
                </p>
              )}
            </div>

            {/* SSO & Domain Whitelist settings */}
            <div className="border-t border-zinc-850/60 pt-6 space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-zinc-200">SSO & Domain Whitelist</h3>
                <p className="text-xs text-zinc-500">
                  Allow users with matching email domains to automatically join this workspace as Viewers.
                </p>
              </div>

              {/* Tag List display */}
              <div className="flex flex-wrap gap-2 py-1">
                {domainWhitelist.length === 0 ? (
                  <span className="text-[10px] text-zinc-500 italic bg-zinc-950/40 px-3 py-1.5 rounded-lg border border-zinc-900">
                    No domains whitelisted. Only invited members can join.
                  </span>
                ) : (
                  domainWhitelist.map((domain) => (
                    <span
                      key={domain}
                      className="inline-flex items-center gap-1.5 text-[11px] font-medium text-purple-400 bg-purple-950/20 border border-purple-900/40 px-3 py-1.5 rounded-full"
                    >
                      {domain}
                      {canManage && (
                        <button
                          type="button"
                          onClick={() => {
                            setDomainWhitelist(domainWhitelist.filter((d) => d !== domain));
                          }}
                          className="hover:text-purple-300 text-purple-500 transition-colors bg-transparent border-none outline-none p-0 cursor-pointer"
                        >
                          <X size={10} />
                        </button>
                      )}
                    </span>
                  ))
                )}
              </div>

              {canManage && (
                <div className="space-y-3">
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      const cleaned = whitelistInput.trim().toLowerCase();
                      if (!cleaned) return;
                      if (!/^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$/.test(cleaned)) {
                        toast.error("Invalid domain format (e.g. company.com)");
                        return;
                      }
                      if (domainWhitelist.includes(cleaned)) {
                        toast.error("Domain already added");
                        return;
                      }
                      setDomainWhitelist([...domainWhitelist, cleaned]);
                      setWhitelistInput("");
                    }}
                    className="flex gap-3 max-w-md"
                  >
                    <input
                      type="text"
                      placeholder="e.g. company.com"
                      value={whitelistInput}
                      onChange={(e) => setWhitelistInput(e.target.value)}
                      className="flex-1 bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none transition-all"
                    />
                    <button
                      type="submit"
                      className="bg-zinc-800 hover:bg-zinc-700 text-zinc-100 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-1"
                    >
                      Add
                    </button>
                  </form>

                  <button
                    type="button"
                    disabled={isUpdatingWhitelist}
                    onClick={handleUpdateWhitelist}
                    className="bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-xs font-semibold px-5 py-2.5 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-1.5 shadow-md shadow-purple-950/20"
                  >
                    {isUpdatingWhitelist ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : (
                      <Check size={14} />
                    )}
                    Save Whitelist Settings
                  </button>
                </div>
              )}
            </div>

            {/* Analytics Export Panel */}
            <div className="border-t border-zinc-850/60 pt-6 space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-zinc-200">Analytics & Reporting Export</h3>
                <p className="text-xs text-zinc-500">
                  Export complete brand workspace usage details, including job success statistics, webhook deliverability telemetry, and quota histories.
                </p>
              </div>

              {canManage ? (
                <div className="flex flex-col sm:flex-row gap-3">
                  <button
                    type="button"
                    disabled={isExporting}
                    onClick={() => handleExportAnalytics("json")}
                    className="bg-zinc-800 hover:bg-zinc-750 disabled:bg-zinc-900 text-zinc-200 text-xs font-semibold px-5 py-3 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 border border-zinc-800 disabled:opacity-50"
                  >
                    <Download size={14} className={isExporting ? "animate-bounce" : ""} />
                    Export as JSON
                  </button>
                  <button
                    type="button"
                    disabled={isExporting}
                    onClick={() => handleExportAnalytics("csv")}
                    className="bg-purple-600 hover:bg-purple-500 disabled:bg-purple-900 text-white text-xs font-semibold px-5 py-3 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 shadow-md shadow-purple-950/20 disabled:opacity-50"
                  >
                    <Download size={14} className={isExporting ? "animate-bounce" : ""} />
                    Export as CSV
                  </button>
                </div>
              ) : (
                <p className="text-[10px] text-amber-500/80 flex items-center gap-1">
                  Requires Admin or Owner credentials to export brand analytics data.
                </p>
              )}
            </div>

            {/* Information board */}
            <div className="border-t border-zinc-850/60 pt-6 space-y-3">
              <h3 className="text-sm font-semibold text-zinc-200">Role Permissions Guide</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-[11px] leading-relaxed text-zinc-400">
                <div className="bg-zinc-950/40 border border-zinc-900 p-3.5 rounded-xl space-y-1">
                  <span className="text-purple-400 font-bold uppercase tracking-wider block">Owner / Admin</span>
                  <p>Full privileges: can rename the brand, invite new team members, upload brand catalog assets, delete items, and manage integrations.</p>
                </div>
                <div className="bg-zinc-950/40 border border-zinc-900 p-3.5 rounded-xl space-y-1">
                  <span className="text-emerald-400 font-bold uppercase tracking-wider block">Editor</span>
                  <p>Content creation rights: can upload new assets and define metadata descriptors, but cannot manage team lists or modify brand profile configurations.</p>
                </div>
                <div className="bg-zinc-950/40 border border-zinc-900 p-3.5 rounded-xl space-y-1">
                  <span className="text-zinc-300 font-bold uppercase tracking-wider block">Viewer</span>
                  <p>ReadOnly access: can navigate and browse the brand assets and view team list, but cannot edit anything or perform uploads.</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Invite Member Modal */}
      <AnimatePresence>
        {isInviteModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsInviteModalOpen(false)}
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
                  <Mail className="text-purple-400" size={18} />
                  Invite Brand Member
                </h3>
                <button
                  onClick={() => setIsInviteModalOpen(false)}
                  className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg transition-colors cursor-pointer"
                >
                  <X size={16} />
                </button>
              </div>

              <form onSubmit={handleInvite} className="space-y-4">
                {/* Email */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    User Email Address
                  </label>
                  <input
                    type="email"
                    required
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="member@company.com"
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-all"
                  />
                  <p className="text-[10px] text-zinc-500">
                    The user must have an active account registered on the platform.
                  </p>
                </div>

                {/* Role */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    Assigned Role
                  </label>
                  <div className="relative">
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-sm text-zinc-100 outline-none transition-all appearance-none cursor-pointer"
                    >
                      <option value="viewer">Viewer (Read Only)</option>
                      <option value="editor">Editor (Upload assets & tag)</option>
                      <option value="admin">Admin (Manage team & details)</option>
                    </select>
                    <div className="absolute inset-y-0 right-0 pr-4 flex items-center pointer-events-none text-zinc-500">
                      <Shield size={16} />
                    </div>
                  </div>
                </div>

                {/* Submit */}
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsInviteModalOpen(false)}
                    className="bg-zinc-800 hover:bg-zinc-750 text-zinc-300 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isInviting}
                    className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer flex items-center gap-1 shadow-md shadow-purple-950/20"
                  >
                    {isInviting ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : (
                      "Invite"
                    )}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Create Webhook Modal */}
      <AnimatePresence>
        {isCreateWebhookOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsCreateWebhookOpen(false)}
              className="fixed inset-0 bg-black"
            />

            {/* Modal Card */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 relative z-10 shadow-2xl space-y-4"
            >
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Webhook className="text-purple-400" size={18} />
                  Add Webhook Subscription
                </h3>
                <button
                  onClick={() => setIsCreateWebhookOpen(false)}
                  className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg transition-colors cursor-pointer"
                >
                  <X size={16} />
                </button>
              </div>

              <form onSubmit={handleCreateWebhook} className="space-y-4">
                {/* URL */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    Payload Delivery URL
                  </label>
                  <input
                    type="url"
                    required
                    value={webhookUrl}
                    onChange={(e) => setWebhookUrl(e.target.value)}
                    placeholder="https://yourdomain.com/webhooks/modelens"
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none transition-all"
                  />
                  <p className="text-[10px] text-zinc-500">
                    The endpoint URL where Modelens will dispatch HTTP POST request events.
                  </p>
                </div>

                {/* Event types checkboxes */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    Trigger Event Types
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs border border-zinc-850/60 bg-zinc-950/20 p-3.5 rounded-xl">
                    {AVAILABLE_EVENTS.map(event => (
                      <label key={event} className="flex items-center gap-2 cursor-pointer text-zinc-400 hover:text-zinc-200">
                        <input
                          type="checkbox"
                          checked={webhookEvents[event] || false}
                          onChange={(e) => setWebhookEvents(prev => ({ ...prev, [event]: e.target.checked }))}
                          className="accent-purple-500 h-3.5 w-3.5 rounded bg-zinc-900 border-zinc-800"
                        />
                        <span className="font-mono text-[10px]">{event}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Format selection */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                    Payload Format
                  </label>
                  <div className="flex gap-4 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer text-zinc-400 hover:text-zinc-200">
                      <input
                        type="radio"
                        name="format"
                        value="verbose"
                        checked={webhookFormat === "verbose"}
                        onChange={() => setWebhookFormat("verbose")}
                        className="accent-purple-500 h-3.5 w-3.5"
                      />
                      <span>Verbose (Full detailed payload)</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer text-zinc-400 hover:text-zinc-200">
                      <input
                        type="radio"
                        name="format"
                        value="summary"
                        checked={webhookFormat === "summary"}
                        onChange={() => setWebhookFormat("summary")}
                        className="accent-purple-500 h-3.5 w-3.5"
                      />
                      <span>Summary (Minimal status values)</span>
                    </label>
                  </div>
                </div>

                {/* Filter Rules (Optional) */}
                <div className="space-y-1.5 border-t border-zinc-850/60 pt-4">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-semibold text-zinc-300 block uppercase tracking-wider">
                      Faceted Filter Rule <span className="text-[10px] text-zinc-500 font-normal">(Optional)</span>
                    </label>
                  </div>
                  <p className="text-[10px] text-zinc-500">
                    Only deliver webhook payloads if they match a specific attribute (e.g. key `status`, value `completed`).
                  </p>
                  <div className="flex gap-3">
                    <input
                      type="text"
                      placeholder="Key (e.g. status)"
                      value={filterRuleKey}
                      onChange={(e) => setFilterRuleKey(e.target.value)}
                      className="w-1/2 bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none transition-all"
                    />
                    <input
                      type="text"
                      placeholder="Value (e.g. failed)"
                      value={filterRuleValue}
                      onChange={(e) => setFilterRuleValue(e.target.value)}
                      className="w-1/2 bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none transition-all"
                    />
                  </div>
                </div>

                {/* Submit */}
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsCreateWebhookOpen(false)}
                    className="bg-zinc-800 hover:bg-zinc-750 text-zinc-300 text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isCreatingWebhook}
                    className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all cursor-pointer flex items-center gap-1 shadow-md shadow-purple-950/20"
                  >
                    {isCreatingWebhook ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : (
                      "Register Webhook"
                    )}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Delivery Logs Modal */}
      <AnimatePresence>
        {isLogsModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsLogsModalOpen(false)}
              className="fixed inset-0 bg-black"
            />

            {/* Modal Card */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-4xl p-6 relative z-10 shadow-2xl space-y-4 max-h-[85vh] flex flex-col"
            >
              <div className="flex justify-between items-center flex-shrink-0">
                <div className="space-y-1">
                  <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                    <Activity className="text-purple-400" size={18} />
                    Webhook Delivery Logs
                  </h3>
                  <p className="text-[10px] text-zinc-500 truncate max-w-lg sm:max-w-xl">
                    Tracking delivery statuses to: {selectedWebhook?.url}
                  </p>
                </div>
                <button
                  onClick={() => setIsLogsModalOpen(false)}
                  className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg transition-colors cursor-pointer"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Logs Table Area */}
              <div className="flex-1 overflow-y-auto border border-zinc-900 rounded-xl bg-zinc-950/10 min-h-[300px]">
                {deliveryLogs.length === 0 && !logsLoading ? (
                  <div className="flex flex-col items-center justify-center p-12 text-center h-full text-zinc-500 space-y-2">
                    <FileText size={24} />
                    <span className="text-xs">No delivery attempts logged yet.</span>
                  </div>
                ) : (
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-zinc-900 bg-zinc-950/40 text-zinc-500 text-[9px] font-bold uppercase tracking-wider sticky top-0 z-10">
                        <th className="px-4 py-3">Event Type</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3 text-center">HTTP Code</th>
                        <th className="px-4 py-3 text-center">Latency</th>
                        <th className="px-4 py-3 text-center">Attempt</th>
                        <th className="px-4 py-3">Timestamp</th>
                        {canManage && <th className="px-4 py-3 text-right">Actions</th>}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-900/40 text-[11px] font-medium">
                      {deliveryLogs.map((log) => {
                        const statusColors = {
                          success: "bg-emerald-950/40 border-emerald-800/30 text-emerald-400",
                          failed: "bg-red-950/40 border-red-800/30 text-red-400",
                          retrying: "bg-amber-950/40 border-amber-800/30 text-amber-400",
                          dead: "bg-zinc-950/80 border-zinc-800 text-zinc-500",
                        };
                        const statusBadge = statusColors[log.status] || statusColors.failed;

                        return (
                          <tr key={log.id} className="hover:bg-zinc-900/10 transition-all text-zinc-300">
                            <td className="px-4 py-3 font-mono text-[10px] text-zinc-400">
                              {log.event_type}
                            </td>
                            <td className="px-4 py-3">
                              <span className={`text-[8px] uppercase tracking-wider font-bold border px-2 py-0.5 rounded-full ${statusBadge}`}>
                                {log.status}
                              </span>
                            </td>
                            <td className={`px-4 py-3 text-center font-bold ${log.response_status >= 200 && log.response_status < 300 ? "text-emerald-500" : "text-red-400"}`}>
                              {log.response_status || "—"}
                            </td>
                            <td className="px-4 py-3 text-center text-zinc-400">
                              {log.execution_time_ms ? `${log.execution_time_ms}ms` : "—"}
                            </td>
                            <td className="px-4 py-3 text-center text-zinc-400 font-mono">
                              #{log.attempt_number}
                            </td>
                            <td className="px-4 py-3 text-zinc-500">
                              {new Date(log.created_at).toLocaleString()}
                            </td>
                            {canManage && (
                              <td className="px-4 py-3 text-right">
                                {(log.status === "failed" || log.status === "dead") && (
                                  <button
                                    onClick={() => handleRetryDelivery(log.id)}
                                    disabled={retryingLogId === log.id}
                                    className="inline-flex items-center gap-1 text-[10px] font-bold text-purple-400 hover:text-purple-300 border border-purple-900/40 bg-purple-950/20 px-2.5 py-1 rounded-lg hover:border-purple-800/60 transition-all cursor-pointer disabled:opacity-50"
                                  >
                                    {retryingLogId === log.id ? (
                                      <Loader2 size={10} className="animate-spin" />
                                    ) : (
                                      <RefreshCw size={10} />
                                    )}
                                    Retry
                                  </button>
                                )}
                              </td>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Logs Modal Footer */}
              <div className="flex justify-between items-center flex-shrink-0 pt-2 border-t border-zinc-850/40">
                <div>
                  {logsLoading && (
                    <span className="flex items-center gap-1.5 text-[10px] text-zinc-500 font-semibold">
                      <Loader2 className="animate-spin text-purple-500" size={12} />
                      Fetching delivery logs...
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  {hasMoreLogs && !logsLoading && (
                    <button
                      onClick={() => loadWebhookLogs(selectedWebhook?.id)}
                      className="bg-zinc-800 hover:bg-zinc-750 text-zinc-300 text-xs font-semibold px-4 py-2 rounded-xl transition-all cursor-pointer"
                    >
                      Load More
                    </button>
                  )}
                  <button
                    onClick={() => setIsLogsModalOpen(false)}
                    className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20"
                  >
                    Close
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
