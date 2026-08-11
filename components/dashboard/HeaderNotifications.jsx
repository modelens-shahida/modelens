"use client";
import React, { useState, useEffect, useCallback } from "react";
import { Bell, CheckCircle2, XCircle, AlertTriangle, Webhook, Layers, X, CheckCheck } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const EVENT_CONFIG = {
  "job.completed": {
    icon: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
    color: "border-emerald-800/50 bg-emerald-950/30",
    label: "Job Completed",
  },
  "job.failed": {
    icon: <XCircle className="w-4 h-4 text-red-400" />,
    color: "border-red-800/50 bg-red-950/30",
    label: "Job Failed",
  },
  "low_credit": {
    icon: <AlertTriangle className="w-4 h-4 text-amber-400" />,
    color: "border-amber-800/50 bg-amber-950/30",
    label: "Low Credits",
  },
  "webhook.failed": {
    icon: <Webhook className="w-4 h-4 text-orange-400" />,
    color: "border-orange-800/50 bg-orange-950/30",
    label: "Webhook Failed",
  },
  "pose.completed": {
    icon: <Layers className="w-4 h-4 text-purple-400" />,
    color: "border-purple-800/50 bg-purple-950/30",
    label: "Pose Extracted",
  },
};

const DEFAULT_CONFIG = {
  icon: <Bell className="w-4 h-4 text-zinc-400" />,
  color: "border-zinc-700 bg-zinc-900/30",
  label: "Notification",
};

export default function HeaderNotifications({ wsEvents = [] }) {
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  // Map incoming WebSocket events to notifications
  useEffect(() => {
    if (!wsEvents?.length) return;
    const latest = wsEvents[wsEvents.length - 1];
    if (!latest) return;

    const newNotif = {
      id: Date.now(),
      type: latest.type || "notification",
      message: latest.message || latest.data?.message || JSON.stringify(latest.data || {}),
      timestamp: new Date(),
      read: false,
    };

    setNotifications(prev => [newNotif, ...prev].slice(0, 50));
    setUnreadCount(prev => prev + 1);
  }, [wsEvents]);

  const markAllRead = useCallback(() => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    setUnreadCount(0);
  }, []);

  const dismissNotification = useCallback((id) => {
    setNotifications(prev => {
      const notif = prev.find(n => n.id === id);
      if (notif && !notif.read) setUnreadCount(c => Math.max(0, c - 1));
      return prev.filter(n => n.id !== id);
    });
  }, []);

  const [now, setNow] = useState(null);

  useEffect(() => {
    setNow(Date.now());
    const timer = setInterval(() => {
      setNow(Date.now());
    }, 10000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (date) => {
    if (!now) return "Just now";
    const diff = Math.floor((now - date.getTime()) / 1000);
    if (diff < 60) return `${Math.max(0, diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  return (
    <div className="relative">
      {/* Bell Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-xl hover:bg-zinc-800 transition"
      >
        <Bell className="w-5 h-5 text-zinc-400" />
        {unreadCount > 0 && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute -top-1 -right-1 bg-purple-600 text-white text-xs w-5 h-5 rounded-full flex items-center justify-center font-bold"
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </motion.span>
        )}
      </button>

      {/* Dropdown Panel */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />

            <motion.div
              initial={{ opacity: 0, y: -10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 top-12 w-80 z-50 rounded-2xl border border-zinc-800 shadow-2xl shadow-black/50"
              style={{
                background: "rgba(9, 9, 11, 0.95)",
                backdropFilter: "blur(20px)",
              }}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
                <h3 className="text-sm font-semibold text-white">Notifications</h3>
                <div className="flex items-center gap-2">
                  {unreadCount > 0 && (
                    <button
                      onClick={markAllRead}
                      className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 transition"
                    >
                      <CheckCheck className="w-3.5 h-3.5" />
                      Mark all read
                    </button>
                  )}
                  <button onClick={() => setIsOpen(false)} className="text-zinc-500 hover:text-zinc-300 transition">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Notifications List */}
              <div className="max-h-96 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-zinc-600">
                    <Bell className="w-10 h-10 mb-2" />
                    <p className="text-xs">No notifications yet</p>
                  </div>
                ) : (
                  <div className="p-2 space-y-1">
                    <AnimatePresence>
                      {notifications.map(notif => {
                        const config = EVENT_CONFIG[notif.type] || DEFAULT_CONFIG;
                        return (
                          <motion.div
                            key={notif.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 10 }}
                            className={`relative flex items-start gap-3 p-3 rounded-xl border transition ${config.color} ${!notif.read ? "opacity-100" : "opacity-60"}`}
                          >
                            {/* Unread dot */}
                            {!notif.read && (
                              <span className="absolute top-3 right-3 w-2 h-2 bg-purple-500 rounded-full" />
                            )}
                            <div className="shrink-0 mt-0.5">{config.icon}</div>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-white">{config.label}</p>
                              <p className="text-xs text-zinc-400 truncate mt-0.5">{notif.message}</p>
                              <p className="text-xs text-zinc-600 mt-1">{formatTime(notif.timestamp)}</p>
                            </div>
                            <button
                              onClick={() => dismissNotification(notif.id)}
                              className="shrink-0 text-zinc-600 hover:text-zinc-400 transition mt-0.5"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </motion.div>
                        );
                      })}
                    </AnimatePresence>
                  </div>
                )}
              </div>

              {/* Footer */}
              {notifications.length > 0 && (
                <div className="px-4 py-3 border-t border-zinc-800">
                  <button
                    onClick={() => setNotifications([])}
                    className="text-xs text-zinc-500 hover:text-zinc-300 transition"
                  >
                    Clear all notifications
                  </button>
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
