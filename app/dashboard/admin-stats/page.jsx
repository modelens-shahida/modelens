"use client";

import React, { useState, useEffect } from "react";
import { adminStatsApi } from "@/lib/admin-stats";
import { Loader2, BarChart3, Users, Zap, TrendingUp, AlertTriangle } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "react-hot-toast";
import SummaryStats from "@/components/dashboard/admin-stats/SummaryStats";
import DailyJobsChart from "@/components/dashboard/admin-stats/DailyJobsChart";
import UserGrowthChart from "@/components/dashboard/admin-stats/UserGrowthChart";
import CreditUsageChart from "@/components/dashboard/admin-stats/CreditUsageChart";
import OrchestratorSettings from "@/components/dashboard/admin-stats/OrchestratorSettings";

export default function AdminStatsPage() {
  const [summary, setSummary] = useState(null);
  const [dailyJobs, setDailyJobs] = useState([]);
  const [userGrowth, setUserGrowth] = useState([]);
  const [creditUsage, setCreditUsage] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchStats() {
      try {
        setLoading(true);
        setError(null);

        // Fetch all stats in parallel
        const [summaryData, jobsData, growthData, creditData] = await Promise.all([
          adminStatsApi.getSummaryStats(),
          adminStatsApi.getDailyJobs(),
          adminStatsApi.getUserGrowth(),
          adminStatsApi.getCreditUsage(),
        ]);

        setSummary(summaryData);
        setDailyJobs(jobsData);
        setUserGrowth(growthData);
        setCreditUsage(creditData);
      } catch (error) {
        console.error("Failed to load admin stats:", error);
        setError(error.message || "Failed to load admin statistics");
        toast.error(error.message || "Failed to load admin stats");
      } finally {
        setLoading(false);
      }
    }

    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="animate-spin text-purple-500" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center gap-3"
      >
        <BarChart3 size={32} className="text-purple-500" />
        <div>
          <h1 className="text-3xl font-bold text-white">Admin Dashboard Stats</h1>
          <p className="text-zinc-400 mt-1">Platform-wide analytics and statistics</p>
        </div>
      </motion.div>

      {/* Error State */}
      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="p-4 rounded-lg bg-rose-950/20 border border-rose-800/30 flex items-start gap-3"
        >
          <AlertTriangle className="text-rose-400 shrink-0 mt-0.5" size={20} />
          <div>
            <h3 className="font-semibold text-rose-300">Error Loading Stats</h3>
            <p className="text-sm text-rose-200/70 mt-1">{error}</p>
          </div>
        </motion.div>
      )}

      {/* Summary Statistics Cards */}
      {summary && <SummaryStats data={summary} />}

      {/* System Settings & Orchestrator Metrics */}
      <OrchestratorSettings />

      {/* Charts and Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Jobs Chart */}
        <DailyJobsChart data={dailyJobs} />

        {/* User Growth Chart */}
        <UserGrowthChart data={userGrowth} />
      </div>

      {/* Credit Usage */}
      <CreditUsageChart data={creditUsage} />
    </div>
  );
}
