"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { LayoutDashboard, Webhook, FolderKanban, Image as ImageIcon, LogOut, Menu, X, Megaphone, Sparkles, User, Terminal, Key, CreditCard, Wrench, BarChart3 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function Sidebar({ isOpen, toggleSidebar }) {
  const pathname = usePathname();
  const { logout, user } = useAuth();

  const menuItems = [
    { name: "Overview", path: "/dashboard", icon: LayoutDashboard },
    { name: "Brands", path: "/dashboard/brands", icon: FolderKanban },
    { name: "Assets", path: "/dashboard/assets", icon: ImageIcon },
    { name: "Fix Requests", path: "/dashboard/fix-requests", icon: Wrench },
    { name: "Webhooks", path: "/dashboard/webhooks", icon: Webhook },
    { name: "Campaigns", path: "/dashboard/campaigns", icon: Megaphone },
    { name: "AI Generator", path: "/dashboard/jobs", icon: Sparkles },
    { name: "AI Characters", path: "/dashboard/characters", icon: User },
    { name: "AI Prompts", path: "/dashboard/prompts", icon: Terminal },
    { name: "API Keys", path: "/dashboard/api-keys", icon: Key },
    { name: "Admin Stats", path: "/dashboard/admin-stats", icon: BarChart3 },
    { name: "Billing & Credits", path: "/dashboard/billing", icon: CreditCard },
  ];

  const sidebarContent = (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-200 border-r border-zinc-800/80">
      {/* Brand Header */}
      <div className="flex items-center justify-between px-6 h-16 border-b border-zinc-850">
        <Link href="/dashboard" className="flex items-center gap-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 121 25"
            fill="none"
            className="text-white"
          >
            <path d="M12.961 12.9599C11.912 14.0078 ... Z" fill="currentColor" />
          </svg>
          <span className="text-lg font-bold tracking-wider text-white">ModeLens</span>
        </Link>
        {/* Close button for mobile sidebar */}
        <button
          onClick={toggleSidebar}
          className="md:hidden text-zinc-400 hover:text-white p-1 rounded-lg focus:outline-none"
        >
          <X size={20} />
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-4 py-6 space-y-1">
        {menuItems.map((item) => {
          const isActive = pathname === item.path || (item.path !== "/dashboard" && pathname?.startsWith(item.path));
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all group ${
                isActive
                  ? "bg-purple-600 text-white shadow-md shadow-purple-950/20"
                  : "text-zinc-400 hover:bg-zinc-900/60 hover:text-zinc-100"
              }`}
            >
              <Icon
                size={18}
                className={`${
                  isActive ? "text-white" : "text-zinc-400 group-hover:text-zinc-200"
                } transition-colors`}
              />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* User Session Info / Logout Footer */}
      <div className="p-4 border-t border-zinc-850 bg-zinc-950">
        <div className="flex items-center justify-between mb-4 px-2">
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-semibold text-zinc-100 truncate">
              {user?.full_name || "User"}
            </span>
            <span className="text-[10px] text-zinc-400 truncate">
              {user?.email || "user@modelens.ai"}
            </span>
          </div>
          <span className="text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded-full uppercase tracking-wider font-medium">
            {user?.role || "user"}
          </span>
        </div>
        
        <button
          onClick={logout}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-medium text-rose-400 bg-rose-950/10 border border-rose-950/20 hover:bg-rose-950/20 hover:text-rose-300 transition-all cursor-pointer"
        >
          <LogOut size={14} />
          Sign Out
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar (Permanent) */}
      <aside className="hidden md:block w-64 h-screen shrink-0 sticky top-0">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer (Collapsible) */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={toggleSidebar}
              className="fixed inset-0 z-40 bg-black md:hidden"
            />
            {/* Drawer */}
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", bounce: 0, duration: 0.3 }}
              className="fixed inset-y-0 left-0 z-50 w-64 h-full md:hidden shadow-2xl"
            >
              {sidebarContent}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
