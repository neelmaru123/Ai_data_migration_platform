# Contributing Guidelines — AI Data Migration Platform

Welcome to the **AI Data Migration Platform** repository. Please adhere to these guidelines during development.

---

## Core Development Rules

1. **Inspect Before Modifying**: Always inspect existing code and architecture before making additions or updates.
2. **Do Not Overbuild**: Focus on established MVP capabilities. Avoid adding unrequested microservices, billing systems, or dynamic plugins.
3. **Strict Dependency Management**:
   - Use **Poetry** for Python dependencies (`apps/api/pyproject.toml`).
   - Do NOT add top-level `requirements.txt` or manually edit lockfiles.
4. **No Dynamic AI Code Execution**:
   - The AI module MUST only return structured data conforming to the `TransformationPlan` schema.
   - NEVER call `exec()`, `eval()`, or execute raw AI-generated code.
5. **No Full Dataset In-Memory Loading**:
   - Always use streaming iterators, chunking, or lazy evaluation in Polars/DuckDB.
6. **Decoupled API Handlers**:
   - Keep FastAPI routes thin. All business logic must reside in `apps/api/packages/` or `app/services/`.
7. **Use Background Workers for Heavy Work**:
   - Profiling, migrations, and script generation MUST run as asynchronous background jobs via Redis worker.
8. **Keep TransformationPlan Versioned**:
   - Ensure backwards compatibility for `TransformationPlan` JSON versions.
9. **Test Requirements**:
   - Write unit tests for all domain packages inside `apps/api/tests/unit/`.
   - Run tests before submitting pull requests: `poetry run pytest`.
10. **Linting and Formatting**:
    - Format and lint Python code using `ruff`: `poetry run ruff check .`.

---

## Workflow & Git Branching

- Main branch: `main`
- Feature branches: `feature/<feature-name>` (e.g. `feature/connectors`, `feature/profiler`, `feature/transformation-engine`)
- Never commit credentials, `.env` files, `.venv`, `node_modules`, or dataset dumps.
