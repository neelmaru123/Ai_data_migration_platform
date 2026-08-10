# AI Planner Documentation

The `ai` package (`apps/api/packages/ai`) uses Google Gemini to semantically analyze dataset schemas, recommend column mappings, and construct validated `TransformationPlan` objects.

## Safety Constraint
The AI module NEVER returns raw executable code or calls `exec()`. It produces Pydantic-validated JSON contracts only.
