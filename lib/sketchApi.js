import { api } from "./api";

export const sketchApi = {
  getModes: () => api.get("/api/v1/sketch/modes"),
  createJob: (payload) => api.post("/api/v1/sketch/jobs", payload),
};
