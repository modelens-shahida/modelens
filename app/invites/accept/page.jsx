"use client";

import React, { useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { toast } from "react-hot-toast";
import { motion } from "framer-motion";
import { Mail, CheckCircle, Loader2, ShieldAlert, LogIn, UserPlus, ArrowRight } from "lucide-react";
import Link from "next/link";

function AcceptInvitationContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  
  const token = searchParams.get("token");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [success, setSuccess] = useState(false);

  const handleAccept = async () => {
    if (!token) {
      setErrorMsg("Invitation token is missing. Please check your invitation link.");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg("");
    try {
      await api.post("/api/v1/invites/accept", { token });
      toast.success("Invitation accepted! Welcome to the brand.");
      setSuccess(true);
      setTimeout(() => {
        router.push("/dashboard/brands");
      }, 1500);
    } catch (err) {
      setErrorMsg(err.message || "Failed to accept invitation. The invitation may be expired or invalid.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-black">
        <Loader2 className="animate-spin text-purple-500" size={24} />
      </div>
    );
  }

  // If not logged in, ask to log in
  if (!user) {
    const redirectUrl = encodeURIComponent(`/invites/accept?token=${token || ""}`);
    return (
      <div className="relative min-h-screen flex items-center justify-center bg-black px-4 font-sans">
        <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-purple-900/10 rounded-full blur-[100px] pointer-events-none" />
        
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md bg-zinc-900/40 border border-zinc-800/80 backdrop-blur-xl rounded-2xl p-8 shadow-2xl relative z-10 text-center space-y-6"
        >
          <div className="mx-auto h-12 w-12 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center text-purple-400">
            <Mail size={22} />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-bold text-zinc-100">Team Invitation</h3>
            <p className="text-xs text-zinc-400">
              You have been invited to join a brand team on ModeLens. Please log in or create an account to accept the invitation.
            </p>
          </div>

          <div className="flex flex-col gap-3">
            <Link
              href={`/auth/login?redirect=${redirectUrl}`}
              className="flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-3 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20"
            >
              <LogIn size={14} /> Log In to Accept Invite
            </Link>
            <Link
              href={`/auth/register?redirect=${redirectUrl}`}
              className="flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-750 text-zinc-300 text-xs font-semibold px-4 py-3 rounded-xl transition-all cursor-pointer border border-zinc-800/60"
            >
              <UserPlus size={14} /> Sign Up on ModeLens
            </Link>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-black px-4 font-sans">
      {/* Ambient background blur */}
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-purple-900/10 rounded-full blur-[100px] pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md bg-zinc-900/40 border border-zinc-800/80 backdrop-blur-xl rounded-2xl p-8 shadow-2xl relative z-10 text-center space-y-6"
      >
        {success ? (
          <div className="space-y-4">
            <div className="mx-auto h-12 w-12 rounded-full bg-emerald-950/40 border border-emerald-800/30 flex items-center justify-center text-emerald-400">
              <CheckCircle size={24} className="animate-bounce" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-bold text-zinc-100">Invitation Accepted!</h3>
              <p className="text-xs text-zinc-400">
                You are now part of the brand team. Redirecting you to your dashboard...
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="mx-auto h-12 w-12 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center text-purple-400 animate-pulse">
              <Mail size={22} />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-bold text-zinc-100">Accept Invitation</h3>
              <p className="text-xs text-zinc-400">
                Logged in as <strong className="text-zinc-200">{user.email}</strong>. Click the button below to accept your invitation and join the brand workspace.
              </p>
            </div>

            {errorMsg && (
              <div className="flex gap-2.5 items-start text-left bg-red-950/30 border border-red-900/40 text-red-400 p-4 rounded-xl text-xs leading-relaxed">
                <ShieldAlert size={16} className="flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Acceptance failed</span>
                  <p className="text-red-400/90 mt-1">{errorMsg}</p>
                </div>
              </div>
            )}

            <div className="flex flex-col gap-3">
              <button
                onClick={handleAccept}
                disabled={isSubmitting || !token}
                className="flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-xs font-semibold px-4 py-3 rounded-xl transition-all cursor-pointer shadow-md shadow-purple-950/20 disabled:shadow-none"
              >
                {isSubmitting ? (
                  <Loader2 className="animate-spin" size={14} />
                ) : (
                  <>
                    Join Team Workspace <ArrowRight size={14} />
                  </>
                )}
              </button>
              
              <Link
                href="/dashboard"
                className="text-xs text-zinc-500 hover:text-zinc-300 font-semibold"
              >
                Go to Dashboard
              </Link>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={
      <div className="flex h-screen items-center justify-center bg-black">
        <Loader2 className="animate-spin text-purple-500" size={24} />
      </div>
    }>
      <AcceptInvitationContent />
    </Suspense>
  );
}
