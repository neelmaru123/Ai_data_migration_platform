# Module Specification: `sources`

## 1. Overview & Responsibilities
The `sources` module manages **Data Source Identities** (PostgreSQL, MySQL, MongoDB, CSV/Parquet files) connected through an Agent. It registers database connection profiles, tracks connection health, and acts as the parent anchor for metadata snapshots collected by agents.

---

## 2. Directory & File Inventory

| File / Subfolder | Layer / Type | Description |
| :--- | :--- | :--- |
| `sources_models.py` | Database Models | `DataSource` SQLAlchemy ORM entity definition |
| `sources_schemas.py` | Schemas (DTOs) | Pydantic validation models (`DataSourceCreate`, `DataSourceUpdate`, `DataSourceResponse`, `DataSourceTestRequest`) |
| `sources_services.py` | Business Logic | `SourceService` class for registering sources, updating health check statuses, and managing source inventories |
| `sources_routes.py` | API Controller | FastAPI router defining endpoints for `/api/v1/sources` |
| `sources_dependencies.py` | Validation Middleware | Dependency helpers to verify data source existence and ownership |
| `sources_connectors/` | Connectors | Database driver abstractions for testing/connecting |
| `sources_loaders/` | Loaders | Ingestion loader handlers |

---

## 3. Database Entities & Affected Tables

### Primary Tables Owned
1. **`data_sources`** (`DataSource`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `agent_id` → `agents.id` (CASCADE)
   - **Unique Constraints:** `(agent_id, identifier)`
   - **Attributes:** `name`, `type` (`postgresql`, `mysql`, `mongodb`, `csv`, `parquet`), `role` (`source`, `target`, `both`), `identifier` (logical alias on agent daemon), `status` (`untested`, `healthy`, `unreachable`, `auth_failed`), `last_error`, `last_checked_at`, `created_at`, `updated_at`
   - **Cascade Relationships:**
     - `snapshots` (`MetadataSnapshot`, One-to-Many, CASCADE delete)

---

## 4. Service Layer Specification (`SourceService`)

### 1. `create_data_source(session, data)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `data` (`DataSourceCreate`): DTO containing `agent_id`, `name`, `type`, `role`, and `identifier`.
- **Return Value:** `DataSource` - Freshly created `DataSource` ORM object.
- **Business Logic:**
  1. Instantiates `DataSource` entity with sanitized inputs (`name.strip()`, `type.lower().strip()`, `role.lower().strip()`, `identifier.strip()`).
  2. Adds instance to DB session.
  3. Commits transaction and refreshes model.
  4. Returns created `DataSource`.
- **Affected Tables:** `data_sources` (INSERT)
- **Exceptions:** DB constraint errors if `(agent_id, identifier)` is duplicated.

---

### 2. `get_data_source_by_id(session, source_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `source_id` (`uuid.UUID`): Primary key UUID of data source.
- **Return Value:** `Optional[DataSource]` - Matching `DataSource` ORM model or `None`.
- **Business Logic:**
  1. Executes `select(DataSource).where(DataSource.id == source_id)`.
  2. Returns scalar result or `None`.
- **Affected Tables:** `data_sources` (SELECT)
- **Exceptions:** None.

---

### 3. `get_data_sources_by_agent(session, agent_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent_id` (`uuid.UUID`): Target agent UUID.
- **Return Value:** `List[DataSource]` - List of data sources belonging to the specified agent.
- **Business Logic:**
  1. Queries `data_sources` table filtering on `agent_id == agent_id`.
  2. Orders results by `created_at desc`.
  3. Returns list of records.
- **Affected Tables:** `data_sources` (SELECT)
- **Exceptions:** None.

---

### 4. `update_data_source(session, source, data)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `source` (`DataSource`): Target `DataSource` ORM model instance.
  - `data` (`DataSourceUpdate`): DTO containing optional `name`, `role`, `identifier`.
- **Return Value:** `DataSource` - Updated `DataSource` object.
- **Business Logic:**
  1. Compares incoming fields (`name`, `role`, `identifier`) with current entity values.
  2. If any field differs, updates entity attributes and sets `changed = True`.
  3. If no changes detected, returns original `source` without issuing DB write.
  4. If changed, commits session, refreshes entity, and returns it.
- **Affected Tables:** `data_sources` (UPDATE)
- **Exceptions:** None.

---

### 5. `delete_data_source(session, source)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `source` (`DataSource`): `DataSource` entity instance to remove.
- **Return Value:** `None`
- **Business Logic:**
  1. Calls `session.delete(source)`.
  2. Commits transaction, triggering database foreign key cascade delete on attached `metadata_snapshots` (and their nested schemas, tables, columns).
- **Affected Tables:** `data_sources` (DELETE, cascades to `metadata_snapshots`)
- **Exceptions:** None.

---

## 5. API Routes Specification (`sources_routes.py`)

| HTTP Method | Route Path | Description | Service Function Called | Auth Required |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/sources` | Register a new data source under an agent | `SourceService.create_data_source` | User JWT |
| `GET` | `/api/v1/sources/agent/{agent_id}` | List all data sources attached to an agent | `SourceService.get_data_sources_by_agent` | User JWT |
| `GET` | `/api/v1/sources/{source_id}` | Get data source details | `SourceService.get_data_source_by_id` | User JWT |
| `PATCH` | `/api/v1/sources/{source_id}` | Update data source details | `SourceService.update_data_source` | User JWT |
| `DELETE` | `/api/v1/sources/{source_id}` | Delete data source and metadata snapshots | `SourceService.delete_data_source` | User JWT |

---

## 6. Inter-Module Dependencies

- **Incoming Dependencies (Modules referencing `sources`):**
  - **`metadata`**: Links every `MetadataSnapshot` to a parent `DataSource`.
  - **`migration_plans`**: Inspects data source aliases (`src_db_1`, `target_db`) when serializing LLM context.
- **Outgoing Dependencies (`sources` calls these):**
  - **`agents`**: Verifies agent presence and ownership.
