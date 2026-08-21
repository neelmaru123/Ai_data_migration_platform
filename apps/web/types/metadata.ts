/**
 * TypeScript definitions matching metadata_schemas.py in apps/api/app/modules/metadata
 */

export interface ColumnResponse {
  id: string;
  table_id: string;
  column_name: string;
  ordinal_position: number;
  data_type: string;
  native_data_type: string;
  nullable: boolean;
  is_primary_key: boolean;
  is_unique: boolean;
  default_value?: string | null;
  max_length?: number | null;
  numeric_precision?: number | null;
  numeric_scale?: number | null;
  null_count: number;
  distinct_count: number;
  statistics?: Record<string, any> | null;
  sample_values?: any[] | null;
  created_at: string;
}

export interface ConstraintResponse {
  id: string;
  table_id: string;
  constraint_name: string;
  constraint_type: string; // 'PRIMARY KEY' | 'FOREIGN KEY' | 'UNIQUE' | 'CHECK'
  definition?: string | null;
  created_at: string;
}

export interface TableResponse {
  id: string;
  schema_id: string;
  table_name: string;
  table_type: string; // 'table' | 'view' | 'materialized_view'
  row_count: number;
  size_bytes: number;
  columns: ColumnResponse[];
  constraints: ConstraintResponse[];
  created_at: string;
}

export interface SchemaResponse {
  id: string;
  snapshot_id: string;
  schema_name: string;
  tables: TableResponse[];
  created_at: string;
}

export interface RelationshipResponse {
  id: string;
  snapshot_id: string;
  source_table_id: string;
  source_column_id: string;
  target_table_id: string;
  target_column_id: string;
  relationship_type: string;
  confidence: number;
  created_at: string;
}

export interface MetadataSnapshotResponse {
  id: string;
  data_source_id: string;
  version: number;
  database_name: string;
  database_version?: string | null;
  total_tables: number;
  total_columns: number;
  total_rows: number;
  status: 'pending' | 'processing' | 'completed' | 'failed' | string;
  collected_at: string;
  created_at: string;
  updated_at: string;
}

export interface MetadataSnapshotDetailResponse extends MetadataSnapshotResponse {
  schemas: SchemaResponse[];
  relationships: RelationshipResponse[];
}
