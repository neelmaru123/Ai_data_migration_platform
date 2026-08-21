/**
 * TypeScript definitions matching execution_schemas.py in apps/api/app/modules/execution
 */

export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | string;

export interface ExecutionJobResponse {
  id: string;
  user_id: string;
  migration_plan_id: string;
  agent_id?: string | null;
  status: ExecutionStatus;
  started_at?: string | null;
  completed_at?: string | null;
  total_tables?: number | null;
  tables_completed?: number | null;
  total_rows?: number | null;
  rows_migrated?: number | null;
  progress_percent?: number | null;
  current_stage?: string | null;
  stage_details?: Record<string, any> | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExecutionProgressUpdate {
  status?: ExecutionStatus;
  progress_percent?: number;
  rows_migrated?: number;
  total_rows?: number;
  tables_completed?: number;
  total_tables?: number;
  current_stage?: string;
  stage_details?: Record<string, any>;
  error_message?: string;
}
