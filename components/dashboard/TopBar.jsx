"use client";

import React, { useState, useRef, useEffect } from "react";
import { usePathname } from "next/navigation";
import { Menu, Bell, User as UserIcon, LogOut, Settings, CreditCard, Shield } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

export default function TopBar({ toggleSidebar }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const notificationsRef = useRef(null);
  const profileRef = useRef(null);

  // Close dropdowns on click outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (notificationsRef.current && !notificationsRef.current.contains(event.target)) {
        setShowNotifications(false);
      }
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setShowProfile(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Helper to format pathname into a page title
  const getPageTitle = () => {
    const segments = (pathname || "").split("/").filter(Boolean);
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
        {/* Notifications Dropdown */}
        <div className="relative" ref={notificationsRef}>
          <button
            onClick={() => {
              setShowNotifications(!showNotifications);
              setShowProfile(false);
            }}
            className={`p-1.5 rounded-full transition-colors relative cursor-pointer hover:bg-zinc-900/50 ${
              showNotifications ? "text-purple-400 bg-zinc-900/60" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Bell size={18} />
            <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-purple-500 rounded-full" />
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2.5 w-80 bg-zinc-950 border border-zinc-850 rounded-2xl shadow-xl shadow-black/50 py-3 z-50 animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="flex items-center justify-between px-4 pb-2 border-b border-zinc-900">
                <span className="text-xs font-semibold text-zinc-200">Notifications</span>
                <button 
                  onClick={() => setShowNotifications(false)}
                  className="text-[10px] text-purple-400 hover:text-purple-300 font-medium cursor-pointer"
                >
                  Clear all
                </button>
              </div>
              <div className="divide-y divide-zinc-900 max-h-64 overflow-y-auto mt-1">
                <div className="p-3 hover:bg-zinc-900/40 transition-colors flex gap-2.5">
                  <div className="w-2 h-2 rounded-full bg-purple-500 mt-1.5 shrink-0" />
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-medium text-zinc-100">Asset validation complete</span>
                    <span className="text-[10px] text-zinc-400">Your upload "Blog_26_Banner" has been indexed.</span>
                    <span className="text-[9px] text-zinc-500 mt-0.5">10 minutes ago</span>
                  </div>
                </div>
                <div className="p-3 hover:bg-zinc-900/40 transition-colors flex gap-2.5">
                  <div className="w-2 h-2 rounded-full bg-purple-500 mt-1.5 shrink-0" />
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-medium text-zinc-100">AI job rendering completed</span>
                    <span className="text-[10px] text-zinc-400">Model replacement simulation #104 finished.</span>
                    <span className="text-[9px] text-zinc-500 mt-0.5">1 hour ago</span>
                  </div>
                </div>
                <div className="p-3 hover:bg-zinc-900/40 transition-colors flex gap-2.5">
                  <div className="w-2 h-2 rounded-full bg-zinc-700 mt-1.5 shrink-0" />
                  <div className="flex flex-col gap-0.5 opacity-80">
                    <span className="text-xs font-medium text-zinc-300">Brand member joined</span>
                    <span className="text-[10px] text-zinc-500">Anshu Roy joined your brand Chanel.</span>
                    <span className="text-[9px] text-zinc-500 mt-0.5">Yesterday</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Separator */}
        <div className="w-px h-5 bg-zinc-800" />

        {/* User profile identifier & dropdown */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => {
              setShowProfile(!showProfile);
              setShowNotifications(false);
            }}
            className="flex items-center gap-2.5 p-1 rounded-xl hover:bg-zinc-900/40 transition-colors cursor-pointer text-left focus:outline-none"
          >
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-xs font-semibold text-white uppercase shadow-inner shadow-black/20">
              {user?.full_name ? user.full_name.charAt(0) : <UserIcon size={14} />}
            </div>
            <span className="hidden sm:inline-block text-xs font-medium text-zinc-300">
              {user?.full_name || "Profile"}
            </span>
          </button>

          {showProfile && (
            <div className="absolute right-0 mt-2.5 w-56 bg-zinc-950 border border-zinc-850 rounded-2xl shadow-xl shadow-black/50 p-2 z-50 animate-in fade-in slide-in-from-top-2 duration-200">
              {/* User info */}
              <div className="px-3 py-2 border-b border-zinc-900 flex flex-col gap-0.5">
                <span className="text-xs font-semibold text-zinc-100 truncate">
                  {user?.full_name || "User"}
                </span>
                <span className="text-[10px] text-zinc-400 truncate">
                  {user?.email || "user@modelens.ai"}
                </span>
              </div>
              
              {/* Menu items */}
              <div className="mt-1.5 space-y-0.5">
                <div className="flex items-center justify-between px-3 py-2 hover:bg-zinc-900/50 rounded-xl transition-colors text-xs text-zinc-300 cursor-pointer">
                  <span className="flex items-center gap-2">
                    <CreditCard size={14} className="text-zinc-500" />
                    Billing & Credits
                  </span>
                  <span className="text-[10px] bg-zinc-900 text-zinc-400 px-2 py-0.5 rounded-full">
                    {user?.credits !== undefined ? `${user.credits} CR` : "100 CR"}
                  </span>
                </div>
                <div className="flex items-center gap-2 px-3 py-2 hover:bg-zinc-900/50 rounded-xl transition-colors text-xs text-zinc-300 cursor-pointer">
                  <Shield size={14} className="text-zinc-500" />
                  Role: <span className="capitalize text-zinc-400">{user?.role || "user"}</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-2 hover:bg-zinc-900/50 rounded-xl transition-colors text-xs text-zinc-300 cursor-pointer">
                  <Settings size={14} className="text-zinc-500" />
                  Account Settings
                </div>
                <div className="h-px bg-zinc-900 my-1" />
                <button
                  onClick={logout}
                  className="w-full flex items-center gap-2 px-3 py-2 hover:bg-rose-950/20 text-rose-400 hover:text-rose-300 rounded-xl transition-colors text-xs text-left cursor-pointer"
                >
                  <LogOut size={14} />
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
