import { api } from "@/lib/api";

const TAXONOMY_TYPES = ["lighting", "pose", "camera", "hair", "skin"];

export const taxonomyApi = {
  // Get all items for a taxonomy type
  getAll: async (type, filters = {}) => {
    const params = new URLSearchParams();
    if (filters.status) params.append("status", filters.status);
    if (filters.family) params.append("family", filters.family);
    if (filters.search) params.append("search", filters.search);
    const query = params.toString() ? `?${params}` : "";
    return api.get(`/api/v1/taxonomy/${type}${query}`);
  },

  // Get single item
  getById: async (type, id) => {
    return api.get(`/api/v1/taxonomy/${type}/${id}`);
  },

  // Create new taxonomy item
  create: async (type, data) => {
    return api.post(`/api/v1/taxonomy/${type}`, data);
  },

  // Update taxonomy item
  update: async (type, id, data) => {
    return api.patch(`/api/v1/taxonomy/${type}/${id}`, data);
  },

  // Update approval status
  updateStatus: async (type, id, status) => {
    return api.patch(`/api/v1/taxonomy/${type}/${id}`, { approval_status: status });
  },

  // Approve item
  approve: async (type, id) => {
    return taxonomyApi.updateStatus(type, id, "approved");
  },

  // Reject item
  reject: async (type, id) => {
    return taxonomyApi.updateStatus(type, id, "rejected");
  },

  // Mark revision required
  revise: async (type, id) => {
    return taxonomyApi.updateStatus(type, id, "revision_required");
  },

  // Delete item
  delete: async (type, id) => {
    return api.delete(`/api/v1/taxonomy/${type}/${id}`);
  },

  // Get all taxonomy types
  getTypes: () => TAXONOMY_TYPES,
};

export default taxonomyApi;
