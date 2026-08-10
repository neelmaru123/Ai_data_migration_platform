# Transformation Engine Documentation

The `transformation_engine` package (`apps/api/packages/transformation_engine`) executes deterministic data cleaning, merging, and transformation plans using Polars and DuckDB.

## Features
- **Deterministic**: Independent of LLM or AI inference at runtime.
- **Operations Supported**:
  - `rename_column`
  - `cast_type`
  - `trim`
  - `lowercase`
  - `uppercase`
  - `normalize_date`
  - `handle_null`
  - `deduplicate`
  - `filter`
  - `join`
  - `merge`
  - `detect_outlier`
