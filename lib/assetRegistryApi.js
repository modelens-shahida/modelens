import { api } from "./api";

export const assetRegistryApi = {
  // ================= Asset Versions =================
  async getVersions(assetId) {
    return api.get(`/api/v1/assets/${assetId}/versions`);
  },

  async createVersion(assetId, versionData) {
    return api.post(`/api/v1/assets/${assetId}/versions`, versionData);
  },

  // ================= Asset Relationships =================
  async getRelationships(assetId, direction = "both") {
    return api.get(`/api/v1/assets/${assetId}/relationships?direction=${direction}`);
  },

  async createRelationship(payload) {
    return api.post("/api/v1/assets/relationships", payload);
  },

  // ================= Reference Sets =================
  async listReferenceSets(characterId = null) {
    const url = characterId
      ? `/api/v1/assets/reference-sets?character_id=${characterId}`
      : "/api/v1/assets/reference-sets";
    return api.get(url);
  },

  async getReferenceSet(setId) {
    return api.get(`/api/v1/assets/reference-sets/${setId}`);
  },

  async createReferenceSet(payload) {
    return api.post("/api/v1/assets/reference-sets", payload);
  },

  async addItemToReferenceSet(setId, itemData) {
    return api.post(`/api/v1/assets/reference-sets/${setId}/items`, itemData);
  },

  // ================= Localized Touch-Up =================
  async touchUpAsset(assetId, payload) {
    return api.post(`/api/v1/assets/${assetId}/touch-up`, payload);
  },
};
