import { api } from "./api";

export const catalogExportApi = {
  getMarketplaces: async () => {
    return await api.get("/api/v1/catalog-jobs/marketplaces");
  },

  getMarketplaceFeedUrl: (jobId, marketplace) => {
    return `/api/v1/catalog-jobs/${jobId}/export-feed/${marketplace}`;
  },

  getMultiFeedZipUrl: (jobId) => {
    return `/api/v1/catalog-jobs/${jobId}/export-multi-feed`;
  },
};
