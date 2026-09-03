import { api } from "./api";

export const fluidApi = {
  getPresets: async () => {
    return await api.get("/api/v1/fluid/presets");
  },

  getPreset: async (presetId) => {
    return await api.get(`/api/v1/fluid/presets/${presetId}`);
  },

  createJob: async (payload) => {
    return await api.post("/api/v1/fluid/jobs", payload);
  },
};
