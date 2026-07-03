// Admin Stats API Service
import { api } from "@/lib/api";

export const adminStatsApi = {
  // Get summary statistics (total_users, total_assets, total_jobs, total_credits_consumed, total_revenue)
  getSummaryStats: async () => {
    return await api.get("/api/v1/admin/stats/summary");
  },

  // Get daily jobs for the last 30 days
  getDailyJobs: async () => {
    return await api.get("/api/v1/admin/stats/jobs/daily");
  },

  // Get user growth (new registrations per day) for the last 30 days
  getUserGrowth: async () => {
    return await api.get("/api/v1/admin/stats/users/growth");
  },

  // Get credit usage (credit spend per day) for the last 30 days
  getCreditUsage: async () => {
    return await api.get("/api/v1/admin/stats/credits/usage");
  },
};
