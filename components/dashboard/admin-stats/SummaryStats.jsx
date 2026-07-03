"use client";

import React from "react";
import { Users, Zap, Briefcase, CreditCard, TrendingUp } from "lucide-react";
import { motion } from "framer-motion";

export default function SummaryStats({ data }) {
  const stats = [
    {
      label: "Total Users",
      value: data?.total_users || 0,
      icon: Users,
      color: "text-blue-400",
      bgColor: "bg-blue-950/10",
      borderColor: "border-blue-800/30",
    },
    {
      label: "Total Assets",
      value: data?.total_assets || 0,
      icon: Briefcase,
      color: "text-purple-400",
      bgColor: "bg-purple-950/10",
      borderColor: "border-purple-800/30",
    },
    {
      label: "Total Jobs",
      value: data?.total_jobs || 0,
      icon: Zap,
      color: "text-yellow-400",
      bgColor: "bg-yellow-950/10",
      borderColor: "border-yellow-800/30",
    },
    {
      label: "Credits Consumed",
      value: (data?.total_credits_consumed || 0).toLocaleString(),
      icon: CreditCard,
      color: "text-emerald-400",
      bgColor: "bg-emerald-950/10",
      borderColor: "border-emerald-800/30",
    },
    {
      label: "Total Revenue",
      value: `$${(data?.total_revenue || 0).toFixed(2)}`,
      icon: TrendingUp,
      color: "text-rose-400",
      bgColor: "bg-rose-950/10",
      borderColor: "border-rose-800/30",
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      {stats.map((stat, index) => {
        const Icon = stat.icon;
        return (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            className={`p-4 rounded-lg border ${stat.bgColor} ${stat.borderColor} backdrop-blur-sm`}
          >
            <div className="flex items-start justify-between mb-3">
              <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                {stat.label}
              </span>
              <Icon className={`${stat.color} shrink-0`} size={18} />
            </div>
            <p className="text-2xl font-bold text-white">{stat.value}</p>
          </motion.div>
        );
      })}
    </div>
  );
}
