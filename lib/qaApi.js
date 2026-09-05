import { api } from "./api";

export const qaApi = {
  /**
   * Run multi-dimensional QA evaluation on an asset.
   * @param {Object} payload
   * @param {number} payload.asset_id
   * @param {string} [payload.qa_profile_id="QA-PROFILE-CATALOG-001"]
   * @param {string} [payload.workflow_id]
   * @param {number[]} [payload.reference_asset_ids]
   * @param {string} [payload.generation_mode="studio_quality"]
   */
  async evaluateAsset(payload) {
    return api.post("/api/v1/qa/evaluate", payload);
  },

  /**
   * Get latest evaluation and evaluation history for an asset.
   * @param {number} assetId
   */
  async getEvaluations(assetId) {
    return api.get(`/api/v1/qa/evaluations/${assetId}`);
  },

  /**
   * Submit human review / hard-gate override for an evaluation.
   * @param {number} evaluationId
   * @param {Object} payload
   * @param {string} payload.decision - "QA-PASS" | "QA-FAIL" | "QA-AUTO-CORRECT"
   * @param {string} [payload.reviewer_notes]
   * @param {boolean} [payload.override_hard_gate=false]
   */
  async reviewEvaluation(evaluationId, payload) {
    return api.post(`/api/v1/qa/evaluations/${evaluationId}/review`, payload);
  },

  /**
   * Run targeted touch-up inpainting on an asset (WF-TOUCHUP-001).
   * @param {number} assetId
   * @param {Object} payload
   */
  async touchUpAsset(assetId, payload = {}) {
    return api.post(`/api/v1/assets/${assetId}/touch-up`, payload);
  },
};
