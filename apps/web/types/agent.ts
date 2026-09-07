/**
 * TypeScript DTOs matching FastAPI backend Pydantic schemas in apps/api/app/modules/agents
 */

export type ValidSourceType = 'postgresql' | 'mysql' | 'mongodb' | 'csv' | 'excel';
export type ValidSourceRole = 'source' | 'target' | 'both';
export type TopologyType = '1:1' | '2:1' | '3:1' | 'custom';

export interface InitialDataSourceCreate {
  name: string;
  type: ValidSourceType;
  role: ValidSourceRole;
  identifier: string;
}

export interface DataSourceResponse {
  id: string;
  agent_id: string;
  name: string;
  type: ValidSourceType;
  role: ValidSourceRole;
  identifier: string;
  status?: string;
  last_error?: string | null;
  last_checked_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentCreatePayload {
  name: string;
  agent_identifier: string;
  version?: string;
  data_sources?: InitialDataSourceCreate[];
}

export interface AgentResponse {
  id: string;
  user_id: string;
  name: string;
  agent_identifier: string;
  status: 'online' | 'offline' | 'degraded' | 'busy' | 'error' | string;
  version?: string | null;
  api_token?: string | null;
  last_seen_at?: string | null;
  last_error?: string | null;
  error_category?: string | null;
  last_error_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentDetailResponse extends AgentResponse {
  data_sources: DataSourceResponse[];
  docker_command?: string | null;
  docker_command_powershell?: string | null;
  docker_command_oneline?: string | null;
  env_template?: string | null;
}

export interface AgentDockerCommandResponse {
  agent_id: string;
  agent_identifier: string;
  docker_command: string;
  docker_command_powershell: string;
  docker_command_oneline: string;
  env_template: string;
  environment_variables: Record<string, string>;
}

export interface TopologyOption {
  id: TopologyType;
  title: string;
  subtitle: string;
  description: string;
  sourceCount: number;
  badge?: string;
  iconName: string;
}
