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
    const normalizeOptionId = (id) => {
      if (!id || typeof id !== "string") return id;
      const val = id.trim();
      if (val.startsWith("hair_")) return val.replace(/^hair_/, "");
      if (val.startsWith("makeup_")) return val.replace(/^makeup_/, "");
      if (val.startsWith("expr_")) return val.replace(/^expr_/, "");
      if (val.startsWith("pose_")) return val.replace(/^pose_/, "");
      if (val.startsWith("scene_")) return val.replace(/^scene_/, "").toUpperCase();
      if (val.startsWith("campaign_")) return val.replace(/^campaign_/, "");
      if (val.startsWith("lighting_")) return val.replace(/^lighting_/, "").toUpperCase();
      return val;
    };

    const sanitizedPayload = {
      ...payload,
      appearance: payload?.appearance ? {
        hair: normalizeOptionId(payload.appearance.hair),
        makeup: normalizeOptionId(payload.appearance.makeup),
        expression: normalizeOptionId(payload.appearance.expression),
      } : payload?.appearance,
      pose_id: normalizeOptionId(payload?.pose_id),
      location_id: normalizeOptionId(payload?.location_id),
      campaign_preset: normalizeOptionId(payload?.campaign_preset),
      lighting_id: normalizeOptionId(payload?.lighting_id),
    };

    return api.post("/api/v1/productions/dispatch", sanitizedPayload, {
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
