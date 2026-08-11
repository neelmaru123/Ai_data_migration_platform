---
name: code-decision-flow-auditor
description: Log code design choices in DECISIONS.md, map entry points and execution flow in EXECUTION_FLOW.md, and quiz the developer before accepting major code changes. Use whenever writing non-trivial code or implementing features.
---

# Code Decision & Execution Flow Auditor

This skill enforces deep transparency and codebase comprehension when generating or modifying code. It ensures developers never feel out of sync with AI-generated code by maintaining decision logs, execution flow diagrams, and interactive comprehension quizzes.

---

## 1. Decision Logging (`DECISIONS.md`)

Whenever introducing non-trivial code, architectural changes, or new dependencies, **automatically create or update `DECISIONS.md`** at the root of the workspace.

### Required Section Format for `DECISIONS.md`:

```markdown
## [YYYY-MM-DD] - [Feature / Change Title]

### 1. Decision Summary
Brief summary of the architectural or implementation decision made.

### 2. Why This Approach? (Rationale)
- **Problem Being Solved**: What requirement or bug necessitated this change?
- **Chosen Solution**: Detailed explanation of the approach used.
- **Why This Library / Technology**: Reasons for selecting specific packages, APIs, or design patterns (e.g., performance, memory safety, async compatibility).

### 3. Alternatives Considered & Rejected
- **Alternative A**: Description & why it was rejected (e.g., high memory overhead, complex maintenance).
- **Alternative B**: Description & why it was rejected.

### 4. Trade-offs & Future Considerations
- What trade-offs were made (e.g., slight complexity vs. scalability)?
- What potential technical debt or edge cases should be monitored?
```

---

## 2. Execution Flow Mapping (`EXECUTION_FLOW.md`)

Document how execution travels through the codebase for the new or modified functionality. Maintain `EXECUTION_FLOW.md` (or append a dedicated section) detailing:

### Required Execution Flow Format:

```markdown
# Execution Flow - [Feature / Module Name]

## 1. Entry Point
- **File**: [`app/main.py:L25`](file:///path/to/app/main.py#L25)
- **Trigger**: Incoming HTTP POST `/api/v1/migration/execute` or CLI invocation.

## 2. Step-by-Step Execution Sequence
1. **Entry Handler**: `create_migration_job()` in [`routes.py`](file:///path/to/routes.py#L40) validates input schema via Pydantic.
2. **Queue Dispatch**: `queue_task()` pushes payload to Redis queue via [`tasks.py`](file:///path/to/tasks.py#L12).
3. **Worker Consumer**: Celery worker picks up job in `run_worker()` in [`worker.py`](file:///path/to/worker.py#L88).
4. **Engine Processing**: Calls `stream_dataset()` in [`engine.py`](file:///path/to/engine.py#L102) using Polars LazyFrames.
5. **Database Sink**: Streams chunks into target database connector in [`connectors.py`](file:///path/to/connectors.py#L55).

## 3. Impact & Delta Analysis (AI Modifications)
- **[NEW]**: [`engine.py`](file:///path/to/engine.py#L102) - Added streaming chunk iterator.
- **[MODIFIED]**: [`worker.py`](file:///path/to/worker.py#L88) - Added retry lock logic for failed jobs.
- **[UNCHANGED]**: Database schemas and API routes.
```

---

## 3. Interactive Developer Comprehension Quiz

Before finalizing any major code changes or asking the developer to accept the output, **conduct an interactive quiz** to ensure complete alignment and eliminate code opacity.

### Quiz Guidelines:
1. **Prepare 3 short questions**:
   - **Question 1 (Architecture & Rationale)**: Test understanding of *why* a specific pattern or library was used.
   - **Question 2 (Execution Flow)**: Test understanding of the *entry point* and function call hierarchy.
   - **Question 3 (Impact & Security/Edge Cases)**: Test understanding of *what changed* and how errors are handled.
2. **Provide Multiple-Choice or Concise Prompts**: Ask the user to answer or pick the correct concept.
3. **Validate & Confirm**: Confirm answers and summarize key takeaways once the developer answers.

---

## Summary Checklist for AI Workflows

- [ ] Updated `DECISIONS.md` with rationale, libraries used, and trade-offs.
- [ ] Updated `EXECUTION_FLOW.md` with entry point, function call order, and modified files.
- [ ] Quizzed the developer on key changes before concluding major tasks.
