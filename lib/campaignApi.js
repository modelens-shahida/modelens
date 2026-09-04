import { api } from "./api";

export const campaignApi = {
  getFormats: async () => {
    return await api.get("/api/v1/campaigns/formats");
  },

  createJob: async (data) => {
    return await api.post("/api/v1/campaigns/jobs", data);
  },

  getExportZipUrl: (taskId, brandId) => {
    return `/api/v1/campaigns/jobs/${taskId}/export-zip?brand_id=${brandId}`;
  },
};
