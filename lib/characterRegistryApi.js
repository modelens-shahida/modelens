import { api } from "./api";

export const characterRegistryApi = {
  // List all characters with optional workspace filter
  listCharacters: (workspaceId) =>
    api.get(`/api/v1/characters${workspaceId ? `?workspace_id=${workspaceId}` : ""}`),

  // Get full character details (identity, body, skin, hair, runtime)
  getCharacter: (characterId) =>
    api.get(`/api/v1/characters/${characterId}`),

  // Create Identity Profile
  createIdentityProfile: (data) =>
    api.post("/api/v1/characters/identity", data),

  // Create/Update Body Profile
  createBodyProfile: (characterId, data) =>
    api.post(`/api/v1/characters/${characterId}/body`, data),

  // Create/Update Skin Profile
  createSkinProfile: (characterId, data) =>
    api.post(`/api/v1/characters/${characterId}/skin`, data),

  // Create/Update Hair Profile
  createHairProfile: (characterId, data) =>
    api.post(`/api/v1/characters/${characterId}/hair`, data),

  // Create/Update Runtime Profile
  createRuntimeProfile: (characterId, data) =>
    api.post(`/api/v1/characters/${characterId}/runtime`, data),

  // Transition Lifecycle Status
  updateStatus: (characterId, newStatus) =>
    api.patch(`/api/v1/characters/${characterId}/status?new_status=${newStatus}`),

  // Character Version Registry (v2 endpoints)
  getCurrentVersion: (characterId) =>
    api.get(`/api/v1/characters-v2/${characterId}/current-version`),

  listVersions: (characterId) =>
    api.get(`/api/v1/characters-v2/${characterId}/versions`),

  getVersion: (characterId, version) =>
    api.get(`/api/v1/characters-v2/${characterId}/versions/${version}`),

  createDraftVersion: (characterId, data) =>
    api.post(`/api/v1/characters-v2/${characterId}/versions`, data),

  updateDraftVersion: (characterId, version, data) =>
    api.patch(`/api/v1/characters-v2/${characterId}/versions/${version}`, data),

  deleteDraftVersion: (characterId, version) =>
    api.delete(`/api/v1/characters-v2/${characterId}/versions/${version}`),

  lockVersion: (characterId, version) =>
    api.post(`/api/v1/characters-v2/${characterId}/versions/${version}/lock`),

  // Appearance & Styling Options
  getStylingOptions: (characterId) =>
    api.get(`/api/v1/characters/${characterId}/styling-options`),

  // Capability Packs (product types supported in production)
  getCapabilities: (characterId) =>
    api.get(`/api/v1/characters/${characterId}/capabilities`),

  // Product-Aware Poses
  getPoses: (characterId, productType = "garment") =>
    api.get(`/api/v1/characters/${characterId}/poses?product_type=${encodeURIComponent(productType)}`),

  // Production Dispatch & Runtime Resolution
  dispatchProduction: (payload, idempotencyKey) => {
    const key = idempotencyKey || (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `idemp_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`);
    return api.post("/api/v1/productions/dispatch", payload, {
      headers: { "Idempotency-Key": key },
    });
  },

  // Get production job status & outputs (customer view)
  getProduction: (productionId) =>
    api.get(`/api/v1/productions/${productionId}`),

  // Presets Registry (customer-facing production feeds)
  getLocations: () =>
    api.get("/api/v1/presets/locations"),

  getLightingPresets: () =>
    api.get("/api/v1/presets/lighting"),

  getCampaignPresets: () =>
    api.get("/api/v1/presets/campaigns"),
};
