import { api } from "./api";

export const taxonomyResolverApi = {
  /**
   * Resolve taxonomy IDs to execution parameters and preview settings.
   * @param {Object} params
   * @param {Object} params.taxonomy_ids - Map of taxonomy_type to taxonomy_id
   * @param {string} [params.workflow_id] - Target workflow ID (e.g. WF-CATALOG-001)
   * @param {string} [params.generation_mode="studio_quality"] - "fast_draft" or "studio_quality"
   * @param {boolean} [params.dry_run=false] - When true, simulates resolution with zero credits spent
   * @param {string} [params.product_type] - e.g. "lingerie", "swimwear", "apparel"
   * @param {string} [params.model_age_group] - e.g. "child", "teen", "adult"
   */
  async resolve(params) {
    return api.post("/api/v1/resolve", params);
  },

  /**
   * Get workflow ComfyUI node mappings for a specific workflow.
   * @param {string} workflowId
   */
  async getWorkflowNodeMaps(workflowId) {
    return api.get(`/api/v1/workflow-node-maps/${workflowId}`);
  },
};
