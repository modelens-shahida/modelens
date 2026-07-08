"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useSearchParams } from "next/navigation";
import { toast } from "react-hot-toast";
import { Mail, Lock, Eye, EyeOff, Loader2, ArrowRight, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { signIn } from "next-auth/react";

function LoginPageContent() {
  const { login } = useAuth();
  const searchParams = useSearchParams();
  const redirectTarget = searchParams.get("redirect") || "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isForgotOpen, setIsForgotOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [isForgotSubmitting, setIsForgotSubmitting] = useState(false);

  const handleForgotSubmit = async (e) => {
    e.preventDefault();
    if (!forgotEmail) {
      toast.error("Please enter your email address");
      return;
    }
    setIsForgotSubmitting(true);
    try {
      // Simulate recovery email send time
      await new Promise((resolve) => setTimeout(resolve, 1200));
      toast.success("Password recovery link sent to your email address! ✉️");
      setIsForgotOpen(false);
      setForgotEmail("");
    } catch (err) {
      toast.error("Failed to send recovery email. Please try again.");
    } finally {
      setIsForgotSubmitting(false);
    }
  };

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
              <button
                type="button"
                onClick={() => setIsForgotOpen(true)}
                className="text-xs text-purple-400 hover:text-purple-300 transition-colors cursor-pointer bg-transparent border-none outline-none"
              >
                Forgot password?
              </button>
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

        {/* Divider */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center" aria-hidden="true">
            <div className="w-full border-t border-zinc-800" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-zinc-950 px-2 text-zinc-500 font-semibold tracking-wider">
              Or continue with
            </span>
          </div>
        </div>

        {/* SSO Action Buttons */}
        <div className="grid grid-cols-2 gap-4">
          <button
            type="button"
            onClick={() => signIn("google", { callbackUrl: "/auth/sso-callback" })}
            className="flex items-center justify-center gap-2.5 bg-zinc-900/60 hover:bg-zinc-800 border border-zinc-800/80 text-zinc-200 hover:text-white text-xs font-semibold py-3 px-4 rounded-xl transition-all cursor-pointer"
          >
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335" />
            </svg>
            Google
          </button>
          <button
            type="button"
            onClick={() => signIn("github", { callbackUrl: "/auth/sso-callback" })}
            className="flex items-center justify-center gap-2.5 bg-zinc-900/60 hover:bg-zinc-800 border border-zinc-800/80 text-zinc-200 hover:text-white text-xs font-semibold py-3 px-4 rounded-xl transition-all cursor-pointer"
          >
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482C19.138 20.193 22 16.44 22 12.017 22 6.484 17.522 2 12 2z" />
            </svg>
            GitHub
          </button>
        </div>

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

      {/* Forgot Password Modal Overlay */}
      <AnimatePresence>
        {isForgotOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.6 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsForgotOpen(false)}
              className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            />
            {/* Modal Box */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 relative z-10 shadow-2xl space-y-4"
            >
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Mail className="text-purple-400" size={18} />
                  Reset Password
                </h3>
                <button
                  type="button"
                  onClick={() => setIsForgotOpen(false)}
                  className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg transition-colors cursor-pointer bg-transparent border-none"
                >
                  <X size={16} />
                </button>
              </div>
              <p className="text-xs text-zinc-400 leading-normal">
                Enter your email address below and we&apos;ll send you a link to reset your password.
              </p>
              <form onSubmit={handleForgotSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                    Email Address
                  </label>
                  <input
                    type="email"
                    required
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl px-4 py-2.5 text-xs text-zinc-100 outline-none"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsForgotOpen(false)}
                    className="bg-zinc-800 hover:bg-zinc-750 text-zinc-300 text-xs px-4 py-2.5 rounded-xl cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isForgotSubmitting}
                    className="bg-purple-600 hover:bg-purple-500 text-white text-xs px-4 py-2.5 rounded-xl cursor-pointer flex items-center gap-1 shadow-md"
                  >
                    {isForgotSubmitting ? <Loader2 className="animate-spin" size={12} /> : "Send Link"}
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
