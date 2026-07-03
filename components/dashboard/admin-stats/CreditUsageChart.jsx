"use client";

import React from "react";
import { CreditCard } from "lucide-react";
import { motion } from "framer-motion";

export default function CreditUsageChart({ data }) {
  const maxUsage = Math.max(...data.map(d => d.credits_used || 0), 1);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.2 }}
      className="p-6 rounded-lg bg-zinc-900/50 border border-zinc-800/50 backdrop-blur-sm"
    >
      <div className="flex items-center gap-2 mb-6">
        <CreditCard className="text-emerald-400" size={20} />
        <h3 className="text-lg font-semibold text-white">Credit Usage (Last 30 Days)</h3>
      </div>

      {data.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-zinc-400">
          <p>No data available</p>
        </div>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {data.map((item, index) => (
            <motion.div
              key={item.date}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2, delay: index * 0.02 }}
              className="flex items-center gap-3"
            >
              <span className="text-xs font-medium text-zinc-400 w-24">{item.date}</span>
              <div className="flex-1 bg-zinc-800/50 rounded-full h-6 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full transition-all duration-500"
                  style={{ width: `${(item.credits_used / maxUsage) * 100}%` }}
                />
              </div>
              <span className="text-sm font-semibold text-emerald-300 w-16 text-right">
                {item.credits_used.toFixed(0)}
              </span>
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
