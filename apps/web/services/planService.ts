import { apiClient } from './axios';
import {
  PlanDetailResponse,
  PlanResponse,
  PlanValidationResultResponse,
  TargetDatabaseConfig,
} from '../types/migrationPlan';

export const planService = {
  /**
   * Create and generate an AI migration plan for an agent
   */
  async createPlan(agentId: string, targetConfig: TargetDatabaseConfig): Promise<PlanDetailResponse> {
    const response = await apiClient.post<PlanDetailResponse>(
      '/plans/generate',
      {
        agent_id: agentId,
        target_config: targetConfig,
      },
      { timeout: 180000 } // 3 minutes timeout for complex LLM generation graph (EC-09)
    );
    return response.data;
  },

  /**
   * Fetch all migration plans for the current authenticated user
   */
  async listPlans(): Promise<PlanResponse[]> {
    const response = await apiClient.get<PlanResponse[]>('/plans');
    return response.data;
  },

  /**
   * Fetch details of a specific migration plan by ID
   */
  async getPlan(planId: string): Promise<PlanDetailResponse> {
    const response = await apiClient.get<PlanDetailResponse>(`/plans/${planId}`);
    return response.data;
  },

  /**
   * Update plan AST manually
   */
  async updatePlan(planId: string, planData: Record<string, any>): Promise<PlanDetailResponse> {
    const response = await apiClient.put<PlanDetailResponse>(`/plans/${planId}`, planData);
    return response.data;
  },

  /**
   * Refine an existing migration plan using natural language prompt feedback
   */
  async refinePlan(planId: string, userFeedback: string): Promise<PlanDetailResponse> {
    const response = await apiClient.post<PlanDetailResponse>(
      `/plans/${planId}/refine`,
      {
        user_feedback: userFeedback,
      },
      { timeout: 180000 } // 3 minutes timeout for LLM plan refinement (EC-09)
    );
    return response.data;
  },

  /**
   * Validate plan feasibility against latest data source snapshots
   */
  async validatePlan(planId: string): Promise<PlanValidationResultResponse> {
    const response = await apiClient.post<PlanValidationResultResponse>(`/plans/${planId}/validate`);
    return response.data;
  },

  /**
   * Approve plan for execution
   */
  async approvePlan(planId: string): Promise<PlanDetailResponse> {
    const response = await apiClient.post<PlanDetailResponse>(`/plans/${planId}/approve`);
    return response.data;
  },

  /**
   * Fetch all version snapshots for a migration plan
   */
  async listPlanVersions(planId: string): Promise<import('../types/migrationPlan').PlanVersionListItem[]> {
    const response = await apiClient.get<import('../types/migrationPlan').PlanVersionListItem[]>(`/plans/${planId}/versions`);
    return response.data;
  },

  /**
   * Fetch full AST details for a specific version snapshot
   */
  async getPlanVersion(planId: string, versionNumber: number): Promise<import('../types/migrationPlan').PlanVersionDetailResponse> {
    const response = await apiClient.get<import('../types/migrationPlan').PlanVersionDetailResponse>(`/plans/${planId}/versions/${versionNumber}`);
    return response.data;
  },

  /**
   * Restore plan AST to a historical version snapshot
   */
  async restorePlanVersion(planId: string, versionNumber: number): Promise<PlanDetailResponse> {
    const response = await apiClient.post<PlanDetailResponse>(`/plans/${planId}/versions/${versionNumber}/restore`);
    return response.data;
  },
};

export default planService;
