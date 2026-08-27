# Module Specification: `metadata`

## 1. Overview & Responsibilities
The `metadata` module manages **Zero-Data Catalog Metadata Storage**. It stores structural schema introspection snapshots uploaded by Agent Daemons, including schemas, tables, columns, data types, constraints (PK/FK/Unique), and cross-database relationships. It provides the structured catalog context used by the AI Planning Engine.

---

## 2. Directory & File Inventory

| File / Subfolder | Layer / Type | Description |
| :--- | :--- | :--- |
| `metadata_models.py` | Database Models | SQLAlchemy models: `MetadataSnapshot`, `MetadataSchema`, `MetadataTable`, `MetadataColumn`, `MetadataConstraint`, `MetadataRelationship` |
| `metadata_schemas.py` | Schemas (DTOs) | Pydantic models for catalog ingestion payloads, table profiling details, and snapshot responses |
| `metadata_services.py` | Business Logic | `MetadataService` class for ingesting agent schema dumps, versioning snapshots, and querying catalog structures |
| `metadata_routes.py` | API Controller | FastAPI router defining endpoints for `/api/v1/metadata` |

---

## 3. Database Entities & Affected Tables

### Primary Tables Owned
1. **`metadata_snapshots`** (`MetadataSnapshot`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `data_source_id` → `data_sources.id` (CASCADE)
   - **Attributes:** `version` (auto-incrementing integer per source), `database_name`, `database_version`, `total_tables`, `total_columns`, `total_rows`, `status`, `collected_at`

2. **`metadata_schemas`** (`MetadataSchema`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `snapshot_id` → `metadata_snapshots.id` (CASCADE)
   - **Attributes:** `schema_name` (e.g. `public`, `sales`)

3. **`metadata_tables`** (`MetadataTable`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `schema_id` → `metadata_schemas.id` (CASCADE)
   - **Attributes:** `table_name`, `row_count_estimate`, `size_bytes`

4. **`metadata_columns`** (`MetadataColumn`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `table_id` → `metadata_tables.id` (CASCADE)
   - **Attributes:** `column_name`, `data_type`, `is_nullable`, `is_primary_key`, `default_value`, `ordinal_position`

5. **`metadata_constraints`** (`MetadataConstraint`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `table_id` → `metadata_tables.id` (CASCADE)
   - **Attributes:** `constraint_name`, `constraint_type` (`PRIMARY KEY`, `FOREIGN KEY`, `UNIQUE`), `definition` (JSON)

6. **`metadata_relationships`** (`MetadataRelationship`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `snapshot_id` → `metadata_snapshots.id` (CASCADE)
   - **Attributes:** `source_table`, `source_column`, `target_table`, `target_column`, `relationship_type`

---

## 4. Service Layer Specification (`MetadataService`)

### 1. `ingest_agent_metadata_snapshot(session, agent, payload)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent` (`Agent`): Authenticated `Agent` ORM instance uploading the snapshot.
  - `payload` (`MetadataSnapshotSyncPayload`): DTO containing `data_source_id` / `identifier`, `database_name`, `schemas`, `tables`, `relationships`, and summary stats.
- **Return Value:** `MetadataSnapshot` - Persisted snapshot header entity with preloaded schemas, tables, and relationships.
- **Business Logic:**
  1. **DataSource Resolution:** Matches target `data_source_id` or logical `identifier` (`src_db`, `dest_db`) against the agent's attached data sources. Raises `HTTP 404 Not Found` if match fails.
  2. **Version Calculation:** Queries max `version` for `data_source_id` and sets `next_version = latest_version + 1` (or `1`).
  3. **Snapshot Header Creation:** Inserts `MetadataSnapshot` record with status `"completed"`.
  4. **Schema & Table Mapping:** Grouping schema names and iterating tables to populate `MetadataSchema` and `MetadataTable` records.
  5. **Column & Constraint Insertion:** For each table, inserts `MetadataColumn` (data types, nullability, PK flag) and `MetadataConstraint` (Foreign keys, Unique key definitions).
  6. **Relationships Ingestion:** Inserts `MetadataRelationship` entries mapping FK table links.
  7. **Source Health Update:** Sets `data_source.status = "healthy"` and updates `last_checked_at`.
  8. Commits transaction and broadcasts WebSocket notification `METADATA_PROFILED` to Web UI clients.
- **Affected Tables:** `metadata_snapshots` (INSERT), `metadata_schemas` (INSERT), `metadata_tables` (INSERT), `metadata_columns` (INSERT), `metadata_constraints` (INSERT), `metadata_relationships` (INSERT), `data_sources` (UPDATE)
- **Exceptions:**
  - `HTTPException(404 Not Found)`: Data source identifier could not be matched.

---

### 2. `get_latest_snapshot_for_source(session, data_source_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `data_source_id` (`uuid.UUID`): Target data source UUID.
- **Return Value:** `Optional[MetadataSnapshot]` - Latest snapshot ORM model with eager loaded schemas, tables, columns, constraints, and relationships.
- **Business Logic:**
  1. Executes query selecting `MetadataSnapshot` for `data_source_id`.
  2. Orders by `MetadataSnapshot.version.desc()`, limiting to 1.
  3. Uses nested `selectinload` options to fetch complete catalog tree (`schemas → tables → columns`, `schemas → tables → constraints`, `relationships`).
  4. Returns single scalar or `None`.
- **Affected Tables:** All `metadata_*` tables (SELECT)
- **Exceptions:** None.

---

### 3. `get_snapshot_by_id(session, snapshot_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `snapshot_id` (`uuid.UUID`): Primary key of target snapshot.
- **Return Value:** `Optional[MetadataSnapshot]` - Matching `MetadataSnapshot` model with eager loaded hierarchy or `None`.
- **Business Logic:**
  1. Executes `select(MetadataSnapshot).where(MetadataSnapshot.id == snapshot_id)` with eager load options.
  2. Returns scalar or `None`.
- **Affected Tables:** All `metadata_*` tables (SELECT)
- **Exceptions:** None.

---

### 4. `list_snapshots_for_source(session, data_source_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `data_source_id` (`uuid.UUID`): Data source UUID.
- **Return Value:** `List[MetadataSnapshot]` - Historical list of snapshot headers for the data source.
- **Business Logic:**
  1. Queries `metadata_snapshots` table filtering by `data_source_id`.
  2. Orders by `version.desc()`.
  3. Returns list of snapshot headers.
- **Affected Tables:** `metadata_snapshots` (SELECT)
- **Exceptions:** None.

---

### 5. `delete_snapshot(session, snapshot_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `snapshot_id` (`uuid.UUID`): Target snapshot UUID.
- **Return Value:** `None`
- **Business Logic:**
  1. Selects `MetadataSnapshot` by `id == snapshot_id`. If missing, raises `HTTP 404 Not Found`.
  2. Calls `session.delete(snapshot)`.
  3. Commits transaction, triggering database foreign key cascade delete on child `metadata_schemas`, `metadata_tables`, `metadata_columns`, `metadata_constraints`, and `metadata_relationships`.
- **Affected Tables:** `metadata_snapshots` (SELECT, DELETE, cascades to all child `metadata_*` tables)
- **Exceptions:**
  - `HTTPException(404 Not Found)`: Snapshot not found.

---

## 5. API Routes Specification (`metadata_routes.py`)

| HTTP Method | Route Path | Description | Service Function Called | Auth Required |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/metadata/sync` | Upload agent schema introspection dump | `MetadataService.ingest_agent_metadata_snapshot` | Agent Token |
| `GET` | `/api/v1/metadata/sources/{source_id}/latest` | Get latest metadata snapshot | `MetadataService.get_latest_snapshot_for_source` | User JWT |
| `GET` | `/api/v1/metadata/sources/{source_id}/snapshots` | Get snapshot version history | `MetadataService.list_snapshots_for_source` | User JWT |
| `GET` | `/api/v1/metadata/snapshots/{snapshot_id}` | Get specific snapshot details | `MetadataService.get_snapshot_by_id` | User JWT |
| `DELETE` | `/api/v1/metadata/snapshots/{snapshot_id}` | Delete snapshot | `MetadataService.delete_snapshot` | User JWT |

### Key Introspection & Scaling Features
1. **Large Schema Introspection Cap**:
   - On databases with 500+ tables, `AgentMetadataEngine` automatically truncates metadata inspection to top 500 tables ordered by estimated row count (`estimated_rows DESC`).
   - Prevents database connection and HTTP request timeouts on enterprise schemas with thousands of tables.
2. **MongoDB Document Sampling & Recursive Path Flattening**:
   - Samples up to 1,000 documents per collection across depth = 3.
   - Calculates field occurrence frequencies, BSON types, and coverage percentages, representing nested JSON structures as flat dot-notation column attributes (`address.city`).

---

## 6. Inter-Module Dependencies

- **Incoming Dependencies (Modules referencing `metadata`):**
  - **`migration_plans`**: Loads snapshots to construct AI prompt context (`MetadataContextSerializer`).
- **Outgoing Dependencies (`metadata` calls these):**
  - **`sources`**: Verifies `data_source_id` validity.
