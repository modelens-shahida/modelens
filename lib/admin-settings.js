import { api } from "@/lib/api";

export const adminSettingsApi = {
  // Get dynamic platform settings and Prometheus metrics
  getSettings: async () => {
    return await api.get("/api/v1/admin/settings");
  },

  // Update dynamic settings (e.g. orchestrator rate limit)
  updateSettings: async (orchestrator_rate_limit) => {
    return await api.post("/api/v1/admin/settings", { orchestrator_rate_limit });
  },
};
