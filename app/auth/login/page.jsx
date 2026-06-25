"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useSearchParams } from "next/navigation";
import { toast } from "react-hot-toast";
import { motion } from "framer-motion";
import { Mail, Lock, Eye, EyeOff, Loader2, ArrowRight } from "lucide-react";

function LoginPageContent() {
  const { login } = useAuth();
  const searchParams = useSearchParams();
  const redirectTarget = searchParams.get("redirect") || "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Please fill in all fields");
      return;
    }

    setIsSubmitting(true);
    try {
      await login(email, password, redirectTarget);
      toast.success("Welcome back to ModeLens!");
    } catch (error) {
      toast.error(error.message || "Invalid credentials");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-black overflow-hidden font-sans px-4">
      {/* Dynamic Ambient Background Gradients */}
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-purple-900/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-[500px] h-[500px] bg-indigo-900/20 rounded-full blur-[120px] pointer-events-none" />

      {/* Main Login Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-md bg-zinc-900/40 border border-zinc-800/80 backdrop-blur-xl rounded-2xl p-8 shadow-2xl relative z-10"
      >
        {/* Logo and Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center items-center gap-2 mb-3">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="28"
              height="28"
              viewBox="0 0 121 25"
              fill="none"
              className="text-white"
            >
              <path d="M12.961 12.9599C11.912 14.0078 ... Z" fill="currentColor" />
            </svg>
            <span className="text-2xl font-bold tracking-wide text-white">
              ModeLens
            </span>
          </div>
          <p className="text-sm text-zinc-400">
            Sign in to manage your AI fashion assets & brands
          </p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Email input */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-zinc-300 tracking-wide block uppercase">
              Email Address
            </label>
            <div className="relative group">
              <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-zinc-500 group-focus-within:text-purple-400 transition-colors">
                <Mail size={18} />
              </span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full bg-zinc-950/60 border border-zinc-800 focus:border-purple-500/80 focus:ring-1 focus:ring-purple-500/80 rounded-xl pl-11 pr-4 py-3 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-all"
              />
            </div>
          </div>

          {/* Password input */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label className="text-xs font-semibold text-zinc-300 tracking-wide block uppercase">
                Password
              </label>
              <a href="#" className="text-xs text-purple-400 hover:text-purple-300 transition-colors">
                Forgot password?
              </a>
            </div>
            <div className="relative group">
              <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-zinc-500 group-focus-within:text-purple-400 transition-colors">
                <Lock size={18} />
              </span>
              <input
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-zinc-950/60 border border-zinc-800 focus:border-purple-500/80 focus:ring-1 focus:ring-purple-500/80 rounded-xl pl-11 pr-12 py-3 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-all"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-medium py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all cursor-pointer shadow-lg shadow-purple-950/30 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? (
              <Loader2 className="animate-spin" size={18} />
            ) : (
              <>
                Sign In
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        {/* Footer info */}
        <div className="mt-8 text-center border-t border-zinc-800/80 pt-6">
          <p className="text-sm text-zinc-400">
            Don't have an account?{" "}
            <Link
              href="/auth/register"
              className="text-purple-400 hover:text-purple-300 font-semibold transition-colors"
            >
              Sign up
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-black">
        <Loader2 className="animate-spin text-purple-500" size={24} />
      </div>
    }>
      <LoginPageContent />
    </Suspense>
  );
}
