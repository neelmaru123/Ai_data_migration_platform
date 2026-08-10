# Architecture Specification — AI Data Migration Platform

## 1. High-Level Architectural Pattern

The platform decouples **transformation intent** from **transformation execution**.

```text
               User Request / Raw Schemas
                           │
                           ▼
                 Dataset Profiling Module
                           │
                           ▼
                    AI Reasoning Engine
                           │
                           ▼
         Structured TransformationPlan (JSON Contract)
                           │
                           ▼
                Human Review & Approval UI
                           │
                           ▼
                    Execution Policy
                           │
           ┌───────────────┴───────────────┐
           ▼                               ▼
    Cloud Executor                Script Generator
   (Polars / DuckDB)            (Self-contained ZIP)
           │                               │
           ▼                               ▼
     Target Database             Local Execution Runtime
```

---

## 2. Fundamental Architectural Guarantees

1. **Deterministic Execution**:
   - The AI module produces ONLY validated `TransformationPlan` schema instances.
   - ETL execution is completely deterministic using Polars or DuckDB.
   - Arbitrary code execution (`exec()`, dynamic eval) is strictly forbidden.

2. **Unified Semantics**:
   - The exact same `TransformationPlan` contract is consumed by both the Cloud Executor and the generated Local Migration Package.

3. **Memory Safety & Streaming**:
   - Large datasets are read using streaming iterators, chunked reads, or lazy frames.
   - Datasets are never buffered entirely in application memory.

4. **Self-Contained Backend**:
   - `apps/api` holds all domain logic packages (`contracts`, `connectors`, `profiler`, `transformation_engine`, `ai`, `script_generator`) and worker processes.
   - All Python dependencies are strictly managed by `pyproject.toml` via **Poetry**.

---

## 3. Data Flow & Execution Modes

### Mode A: Cloud Execution
Suitable for datasets within platform capacity.
1. Web client initiates job via FastAPI endpoint.
2. Job is pushed to Redis queue.
3. Worker picks up job, streams source dataset through `transformation_engine` via Polars/DuckDB, and writes to target database.

### Mode B: Local Script Package Generation
Suitable for massive datasets, compliance-restricted data, or air-gapped environments.
1. Web client initiates local package generation request.
2. `script_generator` packages the verified `TransformationPlan` alongside a standalone Python runtime (`run.py`, `requirements.txt`, validation scripts).
3. User downloads ZIP package and executes locally against on-premise target databases.

---

## 4. Platform Metadata Schema

The Application Database (PostgreSQL) manages platform metadata ONLY:

- `users`: User identity and auth.
- `data_sources`: Source connection configs (encrypted credentials).
- `datasets`: Registered dataset metadata.
- `dataset_profiles`: Summary profiling metrics (counts, types, nulls, min/max).
- `schema_mappings`: Recommended and saved column mappings.
- `transformation_plans`: Versioned JSON transformation plans.
- `migration_jobs`: Active, queued, completed, or failed job status.
- `execution_logs`: Audit and execution diagnostic logs.
