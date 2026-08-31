"use client";

import React, { useState, useEffect } from "react";
import { 
  Users, 
  Shield, 
  UserPlus, 
  Trash2, 
  Check, 
  X, 
  Loader2, 
  Mail, 
  ShieldCheck, 
  Sliders, 
  Award,
  Sparkles,
  Eye,
  Lock,
  Globe
} from "lucide-react";
import { api } from "@/lib/api";
import toast from "react-hot-toast";

const ROLE_PERMISSIONS = {
  owner: {
    label: "Brand Owner",
    badge: "bg-purple-950/80 text-purple-300 border-purple-700",
    desc: "Full workspace ownership, billing, brand deletion, and team governance.",
    icon: ShieldCheck,
    scopes: ["ALL_PERMISSIONS", "BILLING_MANAGE", "BRAND_DELETE", "TEAM_ADMIN"],
  },
  brand_admin: {
    label: "Brand Admin",
    badge: "bg-indigo-950/80 text-indigo-300 border-indigo-700",
    desc: "Generation management, QA approvals, audit inspections, and member invites.",
    icon: Shield,
    scopes: ["GENERATION_WRITE", "QA_ADMIN", "AUDIT_READ", "MEMBER_INVITE"],
  },
  creative_director: {
    label: "Creative Director",
    badge: "bg-pink-950/80 text-pink-300 border-pink-700",
    desc: "Style taxonomies, character standards, reference sets, and pose approvals.",
    icon: Sparkles,
    scopes: ["TAXONOMY_MANAGE", "CHARACTERS_MANAGE", "GENERATION_WRITE"],
  },
  qa_reviewer: {
    label: "QA Reviewer",
    badge: "bg-amber-950/80 text-amber-300 border-amber-700",
    desc: "Multi-dimensional QA evaluation, hard-gate overrides, and defect tagging.",
    icon: Award,
    scopes: ["QA_EVALUATE", "QA_OVERRIDE", "TOUCHUP_DISPATCH"],
  },
  editor: {
    label: "Editor / Creator",
    badge: "bg-blue-950/80 text-blue-300 border-blue-700",
    desc: "Submits catalog batches, runs virtual try-on, and initiates touch-ups.",
    icon: Sliders,
    scopes: ["GENERATION_WRITE", "ASSET_UPLOAD", "TOUCHUP_REQUEST"],
  },
  viewer: {
    label: "Viewer",
    badge: "bg-zinc-800 text-zinc-300 border-zinc-700",
    desc: "Read-only access to deliverables, asset registry, and C2PA credentials.",
    icon: Eye,
    scopes: ["ASSET_READ", "C2PA_VERIFY", "EXPORT_ZIP"],
  },
};

export default function BrandTeamPermissionsManager({ brandId, canManage = true }) {
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [brand, setBrand] = useState(null);

  // Invite modal
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("editor");
  const [inviting, setInviting] = useState(false);
  const [updatingMemberId, setUpdatingMemberId] = useState(null);
  const [removingMemberId, setRemovingMemberId] = useState(null);

  useEffect(() => {
    if (brandId) {
      loadBrandAndMembers();
    }
  }, [brandId]);

  const loadBrandAndMembers = async () => {
    setLoading(true);
    try {
      const [brandData, membersData] = await Promise.all([
        api.get(`/api/v1/brands/${brandId}`),
        api.get(`/api/v1/brands/${brandId}/members`),
      ]);
      setBrand(brandData);
      setMembers(membersData || []);
    } catch (err) {
      console.error("Failed to load team members:", err);
      // Mock preview if API is not yet populated
      setMembers([
        { id: 1, user_id: 101, user_email: "indra@modelens.ai", role: "brand_admin", created_at: new Date().toISOString() },
        { id: 2, user_id: 102, user_email: "anshu@modelens.ai", role: "brand_admin", created_at: new Date().toISOString() },
        { id: 3, user_id: 103, user_email: "reviewer@modelens.ai", role: "qa_reviewer", created_at: new Date().toISOString() },
        { id: 4, user_id: 104, user_email: "creative@modelens.ai", role: "creative_director", created_at: new Date().toISOString() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleInvite = async (e) => {
    e.preventDefault();
    if (!inviteEmail) return;

    setInviting(true);
    try {
      await api.post(`/api/v1/brands/${brandId}/members`, {
        email: inviteEmail,
        role: inviteRole,
      });
      toast.success(`Invitation sent to ${inviteEmail}!`);
      setIsInviteModalOpen(false);
      setInviteEmail("");
      loadBrandAndMembers();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to invite member");
    } finally {
      setInviting(false);
    }
  };

  const handleUpdateRole = async (memberId, newRole) => {
    setUpdatingMemberId(memberId);
    try {
      await api.patch(`/api/v1/brands/${brandId}/members/${memberId}`, {
        role: newRole,
      });
      toast.success("Member role updated!");
      setMembers(members.map(m => m.id === memberId ? { ...m, role: newRole } : m));
    } catch (err) {
      toast.error("Failed to update role");
    } finally {
      setUpdatingMemberId(null);
    }
  };

  const handleRemoveMember = async (memberId) => {
    if (!confirm("Are you sure you want to remove this team member?")) return;

    setRemovingMemberId(memberId);
    try {
      await api.delete(`/api/v1/brands/${brandId}/members/${memberId}`);
      toast.success("Team member removed");
      setMembers(members.filter(m => m.id !== memberId));
    } catch (err) {
      toast.error("Failed to remove member");
    } finally {
      setRemovingMemberId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Invite Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Users className="w-5 h-5 text-purple-400" />
            Brand Team & Granular Permissions
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Role-Based Access Control (RBAC) governing studio submissions, QA overrides, and C2PA signing.
          </p>
        </div>

        {canManage && (
          <button
            onClick={() => setIsInviteModalOpen(true)}
            className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition shadow-lg shadow-purple-600/20"
          >
            <UserPlus size={14} /> Invite Member
          </button>
        )}
      </div>

      {/* Role Matrix Reference Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-xs">
        {Object.entries(ROLE_PERMISSIONS).map(([key, cfg]) => {
          const Icon = cfg.icon;
          return (
            <div key={key} className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-1">
              <div className="flex items-center gap-1.5">
                <Icon className="w-3.5 h-3.5 text-purple-400" />
                <span className="font-semibold text-zinc-200 truncate">{cfg.label}</span>
              </div>
              <p className="text-[10px] text-zinc-500 line-clamp-2 leading-tight">{cfg.desc}</p>
            </div>
          );
        })}
      </div>

      {/* Members Table */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl">
        {loading ? (
          <div className="py-16 text-center">
            <Loader2 className="w-6 h-6 text-purple-400 animate-spin mx-auto mb-2" />
            <p className="text-xs text-zinc-400">Loading team members...</p>
          </div>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="bg-zinc-900/60 border-b border-zinc-800 text-[11px] font-mono uppercase text-zinc-400">
              <tr>
                <th className="py-3 px-4">Member Email</th>
                <th className="py-3 px-4">Role & Scope</th>
                <th className="py-3 px-4">Permissions Breakdown</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-900 font-mono">
              {/* Brand Owner */}
              <tr className="bg-purple-950/10">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2 font-semibold text-white">
                    <ShieldCheck className="w-4 h-4 text-purple-400 shrink-0" />
                    <span>Workspace Creator / Owner</span>
                  </div>
                </td>
                <td className="py-3 px-4">
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] uppercase font-bold border bg-purple-950 text-purple-300 border-purple-800">
                    Owner
                  </span>
                </td>
                <td className="py-3 px-4 text-[11px] text-zinc-400 font-sans">
                  Full Administrative, Billing, and Team Governance Scopes
                </td>
                <td className="py-3 px-4 text-right text-zinc-500 text-xs">
                  Immutable
                </td>
              </tr>

              {/* Members */}
              {members.map((member) => {
                const roleCfg = ROLE_PERMISSIONS[member.role] || ROLE_PERMISSIONS.viewer;
                return (
                  <tr key={member.id} className="hover:bg-zinc-900/40 transition">
                    <td className="py-3 px-4 text-zinc-200 font-medium">
                      <div className="flex items-center gap-2">
                        <Mail className="w-3.5 h-3.5 text-zinc-500" />
                        <span>{member.user_email}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {canManage ? (
                        <select
                          value={member.role}
                          disabled={updatingMemberId === member.id}
                          onChange={(e) => handleUpdateRole(member.id, e.target.value)}
                          className="bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-lg px-2 py-1 text-xs outline-none focus:border-purple-500 font-mono"
                        >
                          <option value="brand_admin">Brand Admin</option>
                          <option value="creative_director">Creative Director</option>
                          <option value="qa_reviewer">QA Reviewer</option>
                          <option value="editor">Editor / Creator</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      ) : (
                        <span className={`px-2 py-0.5 rounded-full text-[10px] uppercase font-bold border ${roleCfg.badge}`}>
                          {roleCfg.label}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-[11px] text-zinc-400 font-sans">
                      {roleCfg.desc}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {canManage && (
                        <button
                          onClick={() => handleRemoveMember(member.id)}
                          disabled={removingMemberId === member.id}
                          className="text-zinc-500 hover:text-red-400 p-1.5 rounded-lg hover:bg-zinc-900 transition disabled:opacity-50"
                          title="Remove Member"
                        >
                          {removingMemberId === member.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="w-3.5 h-3.5" />
                          )}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Invite Member Modal */}
      {isInviteModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <UserPlus className="w-4 h-4 text-purple-400" />
                Invite Team Member
              </h3>
              <button onClick={() => setIsInviteModalOpen(false)} className="text-zinc-400 hover:text-white">
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleInvite} className="space-y-4 text-xs font-mono">
              <div>
                <label className="text-zinc-300 block mb-1.5 font-semibold">User Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="designer@brand.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2.5 text-zinc-200 outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="text-zinc-300 block mb-1.5 font-semibold">Assigned Role & Permissions</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2.5 text-zinc-200 outline-none focus:border-purple-500"
                >
                  <option value="brand_admin">Brand Admin (Generation + QA + Team)</option>
                  <option value="creative_director">Creative Director (Styles + Poses + Characters)</option>
                  <option value="qa_reviewer">QA Reviewer (Evaluation + Hard-Gate Overrides)</option>
                  <option value="editor">Editor (Try-On + Catalog Batches + Touch-Up)</option>
                  <option value="viewer">Viewer (Read-Only + ZIP Export)</option>
                </select>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  disabled={inviting}
                  className="flex-1 bg-purple-600 hover:bg-purple-500 text-white font-semibold py-2.5 rounded-xl transition flex items-center justify-center gap-1.5 shadow-lg shadow-purple-600/20"
                >
                  {inviting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  {inviting ? "Sending Invite..." : "Send Invitation"}
                </button>
                <button
                  type="button"
                  onClick={() => setIsInviteModalOpen(false)}
                  className="px-4 py-2.5 border border-zinc-800 text-zinc-400 hover:text-white rounded-xl transition"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
