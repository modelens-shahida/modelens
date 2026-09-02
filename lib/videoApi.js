import { api } from "./api";

export const videoApi = {
  getPresets: async () => {
    return await api.get("/api/v1/video/presets");
  },

  getPreset: async (presetId) => {
    return await api.get(`/api/v1/video/presets/${presetId}`);
  },

  createJob: async (payload) => {
    return await api.post("/api/v1/video/jobs", payload);
  },
};
