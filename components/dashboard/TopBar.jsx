"use client";

import React, { useState, useRef, useEffect } from "react";
import { usePathname } from "next/navigation";
import { Menu, Bell, User as UserIcon, LogOut, Settings, CreditCard, Shield } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { notificationsApi } from "@/lib/notifications";
import { useWebSocket } from "@/lib/useWebSocket";

export default function TopBar({ toggleSidebar }) {
  const pathname = usePathname();
  const { user, logout, token } = useAuth();
  const [lowCredits, setLowCredits] = useState(false);
  const [creditBalance, setCreditBalance] = useState(null);

  // Fetch credit balance
  useEffect(() => {
    if (!token) return;
    const checkCredits = async () => {
      try {
        const { api } = await import("@/lib/api");
        const data = await api.get("/api/v1/credits/balance");
        setLowCredits(data?.low_credits || false);
        setCreditBalance(data?.balance);
      } catch {}
    };
    checkCredits();
    const interval = setInterval(checkCredits, 60000);
    return () => clearInterval(interval);
  }, [token]);

  // Real-time WebSocket for notifications
  useWebSocket({
    token,
    brandId: user?.activeBrandId,
    onEvent: (event) => {
      // Refresh notifications on any real-time event
      fetchNotifications();
    },
  });
  
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const notificationsRef = useRef(null);
  const profileRef = useRef(null);

  // Load notifications from backend
  const fetchNotifications = async () => {
    try {
      const data = await notificationsApi.list(false, 10, 0);
      setNotifications(data || []);
      // Calculate unread count
      const unread = (data || []).filter((n) => !n.is_read).length;
      setUnreadCount(unread);
    } catch (error) {
      console.error("Failed to load notifications", error);
    }
  };

  useEffect(() => {
    if (user) {
      fetchNotifications();
      // Poll notifications every 30 seconds
      const interval = setInterval(fetchNotifications, 30000);
      return () => clearInterval(interval);
    }
  }, [user]);

  // Mark all as read
  const handleMarkAllAsRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error("Failed to mark all as read", error);
    }
  };

  // Mark single as read
  const handleMarkAsRead = async (id) => {
    try {
      await notificationsApi.markAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (error) {
      console.error("Failed to mark notification as read", error);
    }
  };

  // Format created_at to a human readable time
  const formatTime = (dateStr) => {
    if (!dateStr) return "";
    try {
      const date = new Date(dateStr);
      const seconds = Math.floor((new Date() - date) / 1000);
      if (seconds < 60) return "just now";
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes}m ago`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours}h ago`;
      const days = Math.floor(hours / 24);
      return `${days}d ago`;
    } catch (e) {
      return "";
    }
  };

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
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 bg-purple-500 rounded-full animate-pulse" />
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2.5 w-80 bg-zinc-950 border border-zinc-850 rounded-2xl shadow-xl shadow-black/50 py-3 z-50 animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="flex items-center justify-between px-4 pb-2 border-b border-zinc-900">
                <span className="text-xs font-semibold text-zinc-200">Notifications</span>
                {unreadCount > 0 && (
                  <button 
                    onClick={handleMarkAllAsRead}
                    className="text-[10px] text-purple-400 hover:text-purple-300 font-medium cursor-pointer"
                  >
                    Mark all as read
                  </button>
                )}
              </div>
              <div className="divide-y divide-zinc-900 max-h-64 overflow-y-auto mt-1">
                {notifications.length === 0 ? (
                  <div className="p-4 text-center text-xs text-zinc-500">
                    No notifications
                  </div>
                ) : (
                  notifications.map((notif) => (
                    <div 
                      key={notif.id} 
                      onClick={() => !notif.is_read && handleMarkAsRead(notif.id)}
                      className={`p-3 hover:bg-zinc-900/40 transition-colors flex gap-2.5 cursor-pointer ${
                        !notif.is_read ? "bg-purple-950/5" : ""
                      }`}
                    >
                      <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                        !notif.is_read ? "bg-purple-500" : "bg-zinc-700"
                      }`} />
                      <div className="flex flex-col gap-0.5">
                        <span className={`text-xs font-medium ${!notif.is_read ? "text-zinc-100" : "text-zinc-300"}`}>
                          {notif.title}
                        </span>
                        <span className={`text-[10px] ${!notif.is_read ? "text-zinc-400" : "text-zinc-500"}`}>
                          {notif.message}
                        </span>
                        <span className="text-[9px] text-zinc-600 mt-0.5">
                          {formatTime(notif.created_at)}
                        </span>
                      </div>
                    </div>
                  ))
                )}
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
