import { api } from "./api";

export const auditApi = {
  getLogs: async (params = {}) => {
    const query = new URLSearchParams();
    if (params.brand_id) query.append("brand_id", params.brand_id);
    if (params.event_type) query.append("event_type", params.event_type);
    if (params.severity) query.append("severity", params.severity);
    if (params.user_email) query.append("user_email", params.user_email);
    if (params.page) query.append("page", params.page);
    if (params.limit) query.append("limit", params.limit);
    
    return await api.get(`/api/v1/audit/logs?${query.toString()}`);
  },

  getLog: async (logId) => {
    return await api.get(`/api/v1/audit/logs/${logId}`);
  },

  getEventTypes: async () => {
    return await api.get("/api/v1/audit/event-types");
  },
};
