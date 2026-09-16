import { api } from "./api";

export const preservationApi = {
  // Create garment preservation profile
  createGarmentPreservation: (data) =>
    api.post("/api/v1/preservation/garment", data),

  // Define brand protection zones
  createBrandProtection: (data) =>
    api.post("/api/v1/preservation/brand-protection", data),

  // Build identity gate
  createIdentityGate: (data) =>
    api.post("/api/v1/preservation/identity-gate", data),

  // Generate protection mask
  generateProtectionMask: (data) =>
    api.post("/api/v1/preservation/protection-mask", data),

  // Validate constraints
  validateConstraints: (data) =>
    api.post("/api/v1/preservation/validate", data),

  // Get immutable credit ledger
  getCreditLedger: (brandId, limit = 100) =>
    api.get(`/api/v1/credits/ledger/${brandId}?limit=${limit}`),

  // Verify ledger hash chain integrity
  verifyLedgerIntegrity: (brandId) =>
    api.post(`/api/v1/credits/ledger/verify?brand_id=${brandId}`),
};
