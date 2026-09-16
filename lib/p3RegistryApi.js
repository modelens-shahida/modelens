import { api } from "./api";

export const p3RegistryApi = {
  // Dataset Registry
  createDataset: (data) => api.post("/api/v1/datasets", data),
  listDatasets: (characterId, workspaceId) => {
    const params = new URLSearchParams();
    if (characterId) params.append("character_id", characterId);
    if (workspaceId) params.append("workspace_id", workspaceId);
    return api.get(`/api/v1/datasets?${params.toString()}`);
  },
  addDatasetItem: (datasetId, data) => api.post(`/api/v1/datasets/${datasetId}/items`, data),
  freezeDataset: (datasetId) => api.post(`/api/v1/datasets/${datasetId}/freeze`),

  // Experiment Registry
  createExperimentRun: (data) => api.post("/api/v1/experiments", data),
  listExperiments: (characterId) => api.get(`/api/v1/experiments${characterId ? `?character_id=${characterId}` : ""}`),
  logMetric: (runId, data) => api.post(`/api/v1/experiments/${runId}/metrics`, data),

  // Model Lifecycle Management
  createModelArtifact: (data) => api.post("/api/v1/models", data),
  listModels: (characterId, statusFilter) => {
    const params = new URLSearchParams();
    if (characterId) params.append("character_id", characterId);
    if (statusFilter) params.append("status_filter", statusFilter);
    return api.get(`/api/v1/models?${params.toString()}`);
  },
  promoteModel: (modelId, newStatus) => api.patch(`/api/v1/models/${modelId}/promote?new_status=${newStatus}`),

  // Rights & Governance
  createRightsRecord: (data) => api.post("/api/v1/rights", data),
  getRights: (resourceType, resourceId) => api.get(`/api/v1/rights/${resourceType}/${resourceId}`),
};
