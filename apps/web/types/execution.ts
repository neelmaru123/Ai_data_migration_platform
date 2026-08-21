/**
 * TypeScript definitions matching execution_schemas.py in apps/api/app/modules/execution
 */

export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | string;

export interface ExecutionJobResponse {
  id: string;
  migration_plan_id: string;
  agent_id?: string | null;
  status: ExecutionStatus;
  progress: number;
  total_rows: number;
  processed_rows: number;
  successful_rows: number;
  failed_rows: number;
  skipped_rows?: number;
  current_table?: string | null;
  current_stage?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExecutionProgressUpdate {
  status?: ExecutionStatus;
  progress?: number;
  total_rows?: number;
  processed_rows?: number;
  successful_rows?: number;
  failed_rows?: number;
  skipped_rows?: number;
  current_table?: string;
  current_stage?: string;
  error_message?: string;
}
