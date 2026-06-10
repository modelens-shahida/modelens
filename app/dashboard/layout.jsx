"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/dashboard/Sidebar";
import TopBar from "@/components/dashboard/TopBar";
import { Loader2 } from "lucide-react";

export default function DashboardLayout({ children }) {
  const { token, loading } = useAuth();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!loading && !token) {
      router.push("/auth/login");
    }
  }, [token, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex flex-col items-center justify-center gap-3">
        <Loader2 className="animate-spin text-purple-500" size={32} />
        <span className="text-zinc-400 text-sm tracking-widest uppercase font-medium animate-pulse">
          Loading ModeLens...
        </span>
      </div>
    );
  }

  // If not loading and has no token, don't render children (redirect will fire)
  if (!token) {
    return null;
  }

  const toggleSidebar = () => setSidebarOpen(!sidebarOpen);

  return (
    <div className="flex min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      {/* Sidebar Navigation */}
      <Sidebar isOpen={sidebarOpen} toggleSidebar={toggleSidebar} />

      {/* Main Content Pane */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar toggleSidebar={toggleSidebar} />
        <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-zinc-950 relative">
          {children}
        </main>
      </div>
    </div>
  );
}
