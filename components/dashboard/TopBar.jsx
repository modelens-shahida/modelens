"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { Menu, Bell, User as UserIcon } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

export default function TopBar({ toggleSidebar }) {
  const pathname = usePathname();
  const { user } = useAuth();

  // Helper to format pathname into a page title
  const getPageTitle = () => {
    const segments = pathname.split("/").filter(Boolean);
    if (segments.length <= 1) return "Overview";
    
    // Capitalize each segment
    return segments
      .slice(1)
      .map((segment) => {
        if (segment.match(/^\d+$/)) return `ID: ${segment}`;
        return segment.charAt(0).toUpperCase() + segment.slice(1);
      })
      .join(" / ");
  };

  return (
    <header className="sticky top-0 z-30 h-16 w-full bg-zinc-950/80 border-b border-zinc-900/60 backdrop-blur-md flex items-center justify-between px-6">
      {/* Mobile Toggle & Title */}
      <div className="flex items-center gap-4">
        <button
          onClick={toggleSidebar}
          className="md:hidden text-zinc-400 hover:text-white p-1 rounded-lg focus:outline-none focus:ring-1 focus:ring-zinc-800"
        >
          <Menu size={22} />
        </button>
        <h1 className="text-base font-semibold text-zinc-100 tracking-wide">
          {getPageTitle()}
        </h1>
      </div>

      {/* Action Buttons & Profile */}
      <div className="flex items-center gap-4">
        {/* Notifications mock */}
        <button className="text-zinc-400 hover:text-zinc-200 p-1.5 rounded-full hover:bg-zinc-900/50 transition-colors relative cursor-pointer">
          <Bell size={18} />
          <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-purple-500 rounded-full" />
        </button>

        {/* Separator */}
        <div className="w-px h-5 bg-zinc-800" />

        {/* User profile identifier */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-xs font-semibold text-white uppercase shadow-inner shadow-black/20">
            {user?.full_name ? user.full_name.charAt(0) : <UserIcon size={14} />}
          </div>
          <span className="hidden sm:inline-block text-xs font-medium text-zinc-300">
            {user?.full_name || "Profile"}
          </span>
        </div>
      </div>
    </header>
  );
}
