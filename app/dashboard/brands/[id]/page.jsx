"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { ArrowLeft, Users, Settings, Plus, X, Mail, Shield, Loader2, Edit3, Check } from "lucide-react";
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
  const [activeTab, setActiveTab] = useState("members"); // "members" | "settings"

  // Settings states
  const [newBrandName, setNewBrandName] = useState("");
  const [isUpdatingName, setIsUpdatingName] = useState(false);

  // Invite states
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [isInviting, setIsInviting] = useState(false);

  // Fetch all page data
  const fetchData = async () => {
    try {
      const brandData = await api.get(`/api/v1/brands/${id}`);
      setBrand(brandData);
      setNewBrandName(brandData.name);

      const membersData = await api.get(`/api/v1/brands/${id}/members`);
      setMembers(membersData);
    } catch (error) {
      toast.error(error.message || "Failed to load brand details");
      router.push("/dashboard/brands");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) {
      fetchData();
    }
  }, [id]);

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
      await api.post(`/api/v1/brands/${id}/members`, {
        email: inviteEmail,
        role: inviteRole,
      });
      toast.success("Member invited successfully!");
      setInviteEmail("");
      setInviteRole("viewer");
      setIsInviteModalOpen(false);
      // Refresh members list
      const membersData = await api.get(`/api/v1/brands/${id}/members`);
      setMembers(membersData);
    } catch (error) {
      toast.error(error.message || "Failed to invite member");
    } finally {
      setIsInviting(false);
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
          <Users size={14} /> Team Members ({members.length + 1})
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
                      <span className={`text-[10px] uppercase tracking-wider font-semibold border px-2 py-0.5 rounded-full ${getRoleBadge(member.role)}`}>
                        {member.role}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-zinc-400">Active</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
    </div>
  );
}
