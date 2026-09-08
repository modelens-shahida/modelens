import { api } from "./api";

export const ghostApi = {
  getViews: async () => {
    return await api.get("/api/v1/ghost-jobs/views");
  },

  createVolumetricJob: async (data) => {
    return await api.post("/api/v1/ghost-jobs/volumetric", data);
  },
};
