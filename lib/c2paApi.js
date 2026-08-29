import { api } from "./api";

export const c2paApi = {
  getManifest: async (assetId) => {
    return await api.get(`/api/v1/assets/${assetId}/c2pa`);
  },

  generateManifest: async (payload) => {
    return await api.post("/api/v1/c2pa/generate", payload);
  },

  verifySignature: async (manifest) => {
    return await api.post("/api/v1/c2pa/verify", { manifest });
  },
};
