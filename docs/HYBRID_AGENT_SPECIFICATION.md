# Complete Architecture & System Specification: AI Data Migration Platform (Hybrid Agent Engine)

> **Document Purpose**: This standalone specification document details the vision, security model, communication protocols, API payloads, and execution architecture of the AI Data Migration Platform. It is designed to be passed to any AI model or software engineer to immediately implement or extend the system.

---

## 1. Executive Summary & Core Mission

### 1.1 The Problem
When migrating data between databases (e.g., PostgreSQL to MySQL, or consolidating 2 databases into 1), traditional cloud ETL platforms require customers to enter their database hostname, username, and password into a web interface. 
- **Security Barrier**: Customers cannot or will not share database credentials with third-party servers due to SOC2, HIPAA, compliance, or privacy concerns.
- **Network Barrier**: Enterprise databases live inside private VPCs / firewalls with no public IP address or open inbound ports.

### 1.2 The Solution: Hybrid Control-Plane / Data-Plane Architecture
The platform decouples **Migration Logic (Control Plane)** from **Data Execution (Data Plane)**:
- **Control Plane (Your SaaS Cloud API & Web Dashboard)**: Handles user authentication, AI schema mapping, transformation plan generation, team workspace sharing, and real-time job progress tracking. **NEVER receives or stores database passwords or raw data rows.**
- **Data Plane (Self-Hosted Docker Agent)**: A lightweight container deployed inside the customer's private network. It connects locally to the customer's databases, extracts non-sensitive schema metadata, fetches transformation recipes from the SaaS API via outbound polling, and executes the ETL in-memory using **Polars & DuckDB**.

---

## 2. Fundamental Security & Privacy Guarantees

1. **Zero Password Leakage**: Database URLs and credentials (`postgresql://user:pass@host...`) live exclusively in the local container's environment variables. They are never sent over HTTP/HTTPS to the SaaS backend.
2. **Zero Inbound Firewall Exposure**: The Agent initiates outbound HTTPS long-polling connections (`GET /api/v1/agents/jobs/poll`) to the SaaS API. Customers do **not** need to open inbound firewall ports or expose database ports (e.g., 5432/3306) to the internet.
3. **Metadata-Only Cloud Storage**: The SaaS database stores table names, column names, data types, and primary keys ONLY for AI mapping generation. No actual customer data rows ever touch the cloud server.
4. **Deterministic In-Memory Execution**: The Agent uses streaming Polars/DuckDB execution. No data is stored on disk or cached remotely.

---

## 3. High-Level System Architecture

```text
 ┌─────────────────────────────────────────────────────────────────────────────────┐
 │                            SAAS CONTROL PLANE (Cloud)                           │
 │                                                                                 │
 │   ┌───────────────────────────┐    ┌─────────────────────────┐                  │
 │   │   Next.js Web Dashboard   │    │    AI Reasoning Engine  │                  │
 │   │  (Review & Approve Plans) │    │  (Generates JSON Plan)  │                  │
 │   └─────────────┬─────────────┘    └────────────▲────────────┘                  │
 │                 │                               │                               │
 │                 ▼                               │                               │
 │   ┌─────────────────────────────────────────────┴───────────┐                   │
 │   │                   FastAPI Core Backend                  │                   │
 │   │   - Manages Users, Team Workspaces & Agents             │                   │
 │   │   - Stores Versioned JSON TransformationPlans           │                   │
 │   │   - Exposes Outbound Agent Polling & Progress APIs      │                   │
 │   └─────────────────────────────▲───────────────────────────┘                   │
 └─────────────────────────────────┼───────────────────────────────────────────────┘
                                   │
                                   │ Outbound HTTPS Polling & JSON Payload Exchange
                                   │ (NO Passwords, NO Raw Data Rows)
                                   │
 ┌─────────────────────────────────┴───────────────────────────────────────────────┐
 │                  CUSTOMER DATA PLANE (Private Network / VPC)                     │
 │                                                                                 │
 │   ┌─────────────────────────────────────────────────────────────────────────┐   │
 │   │                     SELF-HOSTED DOCKER AGENT CONTAINER                  │   │
 │   │                                                                         │   │
 │   │   - Environment Variables:                                              │   │
 │   │       AGENT_TOKEN="agt_live_998877"                                    │   │
 │   │       SOURCE_DB_1="mysql://user:pass@localhost:3306/legacy_db"          │   │
 │   │       SOURCE_DB_2="postgresql://user:pass@localhost:5432/user_db"       │   │
 │   │       TARGET_DB="postgresql://user:pass@localhost:5432/master_db"       │   │
 │   │                                                                         │   │
 │   │   - Internal Components:                                                │   │
 │   │       1. Schema Metadata Extractor (Information Schema SQL queries)     │   │
 │   │       2. SaaS API Poller & JSON Recipe Parser                           │   │
 │   │       3. Polars / DuckDB Local In-Memory ETL Engine                     │   │
 │   └───────────────┬─────────────────────┬─────────────────────┬─────────────┘   │
 │                   │                     │                     │                 │
 │                   ▼                     ▼                     ▼                 │
 │       ┌──────────────────────┐┌───────────────────┐┌────────────────────┐    │
 │       │ Legacy MySQL Source  ││ PostgreSQL Source ││ Master Target DB   │    │
 │       └──────────────────────┘└───────────────────┘└────────────────────┘    │
 └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. End-to-End Execution Sequence (Detailed Technical Flow)

### Phase 1: Agent Registration & Bootstrapping
1. The user logs into the Web Dashboard (`https://app.aimigration.com`) and navigates to **Agents -> Connect New Agent**.
2. The SaaS API generates an `AGENT_TOKEN` (e.g., `agt_live_998877`) and displays a 1-line Docker snippet:
   ```bash
   docker run -d \
     --name aimigration-agent \
     -e AGENT_TOKEN="agt_live_998877" \
     -e SAAS_URL="https://api.aimigration.com" \
     -e SOURCE_DB_1="mysql://root:pass123@localhost:3306/old_store" \
     -e TARGET_DB="postgresql://postgres:pass123@localhost:5432/new_store" \
     aimigration/agent:latest
   ```
3. The user pastes and executes this command on their local server.
4. The Agent boots up and calls `POST /api/v1/agents/heartbeat` to register its `status="ONLINE"` with system diagnostic metrics.

---

### Phase 2: Local Schema Discovery (Metadata Only)
1. The Agent connects locally to `SOURCE_DB_1`, `SOURCE_DB_2`, and `TARGET_DB` using its local environment variables.
2. It queries standard database catalogs (e.g., `information_schema.tables`, `information_schema.columns`).
3. The Agent builds a **Schema Metadata JSON** payload containing table structures, column names, data types, nullability, and primary key constraints.
4. The Agent sends metadata to SaaS API: `POST /api/v1/agents/schema-sync`.

---

### Phase 3: AI Transformation Plan Generation & Human Review
1. The Web Dashboard notifies the user: **"Schema Discovered!"**
2. The AI Engine inspects the schema metadata JSON and generates a deterministic **`TransformationPlan` JSON** (the "Recipe"):
   - Handles **1-to-1 table migrations** (e.g. `old_users` ➔ `new_users`).
   - Handles **Many-to-One consolidations** (joins `SOURCE_DB_1.orders` + `SOURCE_DB_2.profiles` into `TARGET_DB.master_orders`).
   - Applies column renames, data type casts, and SQL transformation expressions.
3. The user reviews the visual mapping diagram on the Web UI, customizes any rules, and clicks **"Approve & Execute"**.
4. The SaaS API updates the plan status to `status="APPROVED"`.

---

### Phase 4: Outbound Job Polling & Local Execution
1. The Agent continuously polls the SaaS API: `GET /api/v1/agents/jobs/poll`.
2. Upon approval, the SaaS API responds with the `TransformationPlan` JSON recipe.
3. The Agent parses the recipe locally and initializes **Polars** or **DuckDB**:
   - Opens local database streaming readers.
   - Applies filter, join, rename, and type transformation operations in memory.
   - Batch writes transformed rows to the target database.

---

### Phase 5: Real-Time Telemetry & Progress Dashboard
1. Every 2 seconds during ETL execution, the Agent posts progress stats: `POST /api/v1/agents/jobs/{job_id}/progress`.
   - `rows_processed`: 150000
   - `rows_failed`: 0
   - `throughput_rows_per_sec`: 18500
   - `current_table`: "orders"
2. The Web Dashboard displays real-time progress bars, speed gauges, and log diagnostics to the user.
3. When finished, the Agent sends `status="COMPLETED"`.

---

## 5. API Payload Specifications & JSON Schemas

### 5.1 Schema Sync Request Payload (`POST /api/v1/agents/schema-sync`)
```json
{
  "agent_token": "agt_live_998877",
  "databases": [
    {
      "alias": "SOURCE_DB_1",
      "engine": "mysql",
      "tables": [
        {
          "name": "customers",
          "columns": [
            {"name": "id", "type": "INT", "nullable": false, "primary_key": true},
            {"name": "full_name", "type": "VARCHAR(255)", "nullable": false},
            {"name": "email_address", "type": "VARCHAR(255)", "nullable": true}
          ]
        }
      ]
    },
    {
      "alias": "TARGET_DB",
      "engine": "postgresql",
      "tables": [
        {
          "name": "users",
          "columns": [
            {"name": "user_id", "type": "INTEGER", "nullable": false, "primary_key": true},
            {"name": "first_name", "type": "VARCHAR(100)", "nullable": false},
            {"name": "last_name", "type": "VARCHAR(100)", "nullable": false},
            {"name": "email", "type": "VARCHAR(255)", "nullable": false}
          ]
        }
      ]
    }
  ]
}
```

---

### 5.2 Polling Response / Transformation Plan Recipe (`GET /api/v1/agents/jobs/poll`)
```json
{
  "job_id": "job_uuid_99812",
  "plan_id": "plan_uuid_44102",
  "version": "1.0.0",
  "steps": [
    {
      "step_id": 1,
      "source_alias": "SOURCE_DB_1",
      "source_table": "customers",
      "target_alias": "TARGET_DB",
      "target_table": "users",
      "column_mappings": [
        {"source_col": "id", "target_col": "user_id", "transform": "none"},
        {"source_col": "email_address", "target_col": "email", "transform": "none"}
      ],
      "custom_transforms": [
        {
          "target_col": "first_name",
          "expr": "pl.col('full_name').str.split(' ').struct.get(0)"
        },
        {
          "target_col": "last_name",
          "expr": "pl.col('full_name').str.split(' ').struct.get(1)"
        }
      ]
    }
  ]
}
```

---

### 5.3 Progress Telemetry Payload (`POST /api/v1/agents/jobs/{job_id}/progress`)
```json
{
  "agent_token": "agt_live_998877",
  "status": "RUNNING",
  "current_step": 1,
  "current_table": "customers",
  "total_rows_estimated": 500000,
  "processed_rows": 250000,
  "successful_rows": 250000,
  "failed_rows": 0,
  "throughput_rows_sec": 12500,
  "error_samples": []
}
```

---

## 6. Many-to-One (Multi-Source) Migration Capability

The platform inherently supports migrating **multiple source databases into a single target database**.

- **Multi-Source Configuration**: The Agent accepts `SOURCE_DB_1`, `SOURCE_DB_2`, ... `SOURCE_DB_N` in its environment.
- **Local Cross-Database Joins via DuckDB**:
  When a transformation plan requires joining MySQL table `orders` with PostgreSQL table `user_profiles`, DuckDB attached to both DB drivers reads stream chunks into local memory, performs the SQL join, and streams the output directly into the target database.
- **Data Isolation**: All cross-database joining happens inside the user's local RAM/CPU. No cloud bandwidth is consumed.

---

## 7. Team Collaboration & Git Integration Workflows

### 7.1 Team Workspaces in SaaS
- Migration plans (`TransformationPlan`) are associated with a **Workspace ID**.
- Lead Developers create and approve official team migration plans.
- Teammates log into the Web UI, select the approved team plan, and run the agent locally against their respective dev environments.

### 7.2 Standalone Exportable Package for Git (`script_generator`)
For teams requiring offline execution or Git version control:
- Web UI provides an **"Export Migration Script (.zip)"** button.
- Generates a standalone ZIP package containing:
  - `migrate.py` (Self-contained Python script with Polars/DuckDB logic)
  - `plan.json` (Structured transformation specification)
  - `requirements.txt` (`polars`, `duckdb`, `psycopg2-binary`, `pymysql`)
- Developers commit this folder to their Git repository (`git push`). Teammates pull and run `python migrate.py` locally without needing the cloud SaaS backend online.

---

## 8. Developer & AI Implementation Roadmap

When implementing this architecture in code, target the following file organization:

1. **`apps/api/app/modules/agents/`**
   - `agent_models.py`: SQLAlchemy ORM model for Agents and Agent Jobs.
   - `agent_schemas.py`: Pydantic request/response validation schemas.
   - `agent_routes.py`: FastAPI endpoints (`/register`, `/heartbeat`, `/schema-sync`, `/jobs/poll`, `/progress`).

2. **`apps/agent/`** (New Package Directory)
   - `Dockerfile`: `python:3.11-slim` image definition.
   - `agent_runner.py`: Main python daemon process handling metadata extraction, polling, and Polars/DuckDB execution.
   - `connectors/`: Local database drivers (PostgreSQL, MySQL, SQLite, MongoDB).

3. **`apps/web/`** (Frontend Dashboard)
   - `components/AgentConnectModal.tsx`: Docker command generator & copy modal.
   - `app/dashboard/agents/page.tsx`: Agent status monitoring page.
