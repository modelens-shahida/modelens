"use client";

import React, { useEffect, useState } from "react";
import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";

export default function SSOCallbackPage() {
  const { data: session, status } = useSession();
  const { ssoLogin } = useAuth();
  const router = useRouter();
  const [errorOccurred, setErrorOccurred] = useState(false);

  useEffect(() => {
    async function exchangeToken() {
      if (status === "authenticated" && session?.user) {
        try {
          // 1. Call the backend /sso-login endpoint to log in or register
          const data = await api.post("/api/v1/auth/sso-login", {
            email: session.user.email,
            full_name: session.user.name || "SSO User",
            provider: "sso",
          });

          // 2. Resolve user profile
          const token = data.access_token;
          const profile = await api.get("/api/v1/auth/me", {
            headers: { Authorization: `Bearer ${token}` },
          });

          // 3. Save session in auth-context and cookies
          await ssoLogin(token, profile);

          // 4. Check if there was auto-provisioned/accepted brand and set alert info
          try {
            const brands = await api.get("/api/v1/brands", {
              headers: { Authorization: `Bearer ${token}` },
            });
            if (brands && brands.length > 0) {
              sessionStorage.setItem(
                "sso_welcome",
                JSON.stringify({
                  brandName: brands[0].name,
                  brandId: brands[0].id,
                })
              );
            }
          } catch (brandErr) {
            console.error("Failed to load user brands on callback", brandErr);
          }

          toast.success(`Successfully signed in as ${profile.full_name}! 🚀`);

          // 5. Sign out of NextAuth so that session state is strictly managed by JWT
          await signOut({ redirect: false });

          // 6. Redirect to dashboard
          router.push("/dashboard");
        } catch (err) {
          console.error("SSO Token Exchange failed:", err);
          toast.error(err.message || "SSO login exchange failed. Please try again.");
          setErrorOccurred(true);
        }
      } else if (status === "unauthenticated") {
        router.push("/auth/login");
      }
    }

    exchangeToken();
  }, [status, session]);

  if (errorOccurred) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-black text-zinc-300 font-sans p-6">
        <h2 className="text-xl font-bold text-red-500 mb-2">Authentication Failed</h2>
        <p className="text-sm text-zinc-500 mb-6 text-center max-w-sm">
          There was a problem authenticating with the server. Please try signing in again.
        </p>
        <button
          onClick={() => router.push("/auth/login")}
          className="bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-white text-xs font-semibold px-6 py-2.5 rounded-xl transition-all cursor-pointer"
        >
          Back to Login
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-black text-zinc-300 font-sans">
      <Loader2 className="animate-spin text-purple-500 mb-4" size={32} />
      <p className="text-sm tracking-wide text-zinc-400">Completing secure login...</p>
    </div>
  );
}
