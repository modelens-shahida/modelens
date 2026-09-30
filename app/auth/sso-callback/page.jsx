"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import { useSession, signOut } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { safeRedirect } from "@/lib/safe-redirect";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";

function SSOCallbackContent() {
  const { data: session, status } = useSession();
  const { ssoLogin } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTarget = safeRedirect(searchParams.get("redirect"));
  const [errorOccurred, setErrorOccurred] = useState(false);
  // Signing out of NextAuth flips status to "unauthenticated"; don't treat that as a failed login
  const handled = useRef(false);

  useEffect(() => {
    async function exchangeToken() {
      if (handled.current) return;
      if (status === "authenticated" && session?.user) {
        handled.current = true;
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

          // 3. Resolve the active brand (auto-provisioned or accepted invite)
          let activeBrand = null;
          try {
            const brands = await api.get("/api/v1/brands", {
              headers: { Authorization: `Bearer ${token}` },
            });
            activeBrand = Array.isArray(brands) && brands.length > 0 ? brands[0] : null;
          } catch (brandErr) {
            console.error("Failed to load user brands on callback", brandErr);
          }

          // 4. Save session and active brand in auth-context and cookies
          await ssoLogin(token, profile, {
            refreshToken: data.refresh_token,
            activeBrandId: activeBrand?.id ?? null,
          });

          if (activeBrand) {
            sessionStorage.setItem(
              "sso_welcome",
              JSON.stringify({ brandName: activeBrand.name, brandId: activeBrand.id })
            );
          } else {
            sessionStorage.removeItem("sso_welcome");
          }

          toast.success(`Successfully signed in as ${profile.full_name}! 🚀`);

          // 5. Sign out of NextAuth so that session state is strictly managed by JWT
          await signOut({ redirect: false });

          // 6. Send the user to where they were headed
          router.replace(redirectTarget);
        } catch (err) {
          console.error("SSO Token Exchange failed:", err);
          toast.error(err.message || "SSO login exchange failed. Please try again.");
          setErrorOccurred(true);
        }
      } else if (status === "unauthenticated") {
        handled.current = true;
        router.replace(`/auth/login?redirect=${encodeURIComponent(redirectTarget)}`);
      }
    }

    exchangeToken();
  }, [status, session, ssoLogin, router, redirectTarget]);

  if (errorOccurred) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-black text-zinc-300 font-sans p-6">
        <h2 className="text-xl font-bold text-red-500 mb-2">Authentication Failed</h2>
        <p className="text-sm text-zinc-500 mb-6 text-center max-w-sm">
          There was a problem authenticating with the server. Please try signing in again.
        </p>
        <button
          onClick={() => router.push(`/auth/login?redirect=${encodeURIComponent(redirectTarget)}`)}
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

export default function SSOCallbackPage() {
  return (
    <Suspense fallback={null}>
      <SSOCallbackContent />
    </Suspense>
  );
}
