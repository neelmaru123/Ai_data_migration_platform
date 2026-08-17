"""
LLM Plan Generator Engine
Implements:
- MetadataContextSerializer: Converts MetadataSnapshot trees into sanitized YAML context strings.
- LLMPlanGeneratorService: Invokes LangChain LLM with structured output & retry logic.
"""

import logging
from typing import List, Optional

from app.core.config import settings
from app.modules.metadata.metadata_models import (
    MetadataColumn,
    MetadataConstraint,
    MetadataRelationship,
    MetadataSchema,
    MetadataSnapshot,
    MetadataTable,
)
from app.modules.migration_plans.migration_plans_schemas import (
    TransformationPlanAST,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Prompt Version — bump when system prompt changes so stored plans are traceable
# ============================================================================
PROMPT_VERSION = "v1.0.0"

# ============================================================================
# System Prompt Template
# ============================================================================
SYSTEM_PROMPT = """You are an expert database migration architect. Your ONLY job is to generate a
TransformationPlan JSON object that describes how to combine one or more source databases
into a single target database.

RULES:
1. NEVER invent data, assume values, or make up column content.
2. Work ONLY from the structural metadata provided. No raw data will be given.
3. You MUST include ALL source tables in your table_mappings.
4. For each source table, decide ONE of:
   - direct_copy  → Copy this table unchanged from exactly 1 source database
   - merge        → Combine 2+ source tables into 1 target table (requires conflict_resolution)
   - split_target → Decompose 1 source table into 2+ target tables
5. For EVERY column in EVERY source table, you MUST output a column_mapping with:
   - transformation_type from the ALLOWED TAXONOMY.
   - ui_badge_type that EXACTLY matches transformation_type.
   - A plain-English "explanation" field readable by a non-technical business user.
6. Source columns with NO target equivalent MUST use transformation_type "drop_column".
   For drop_column: set target_column_name=null, target_data_type=null, nullable=null.
7. New target columns with no source equivalent use "new_column_added" with constant_value or expression_template.
8. For conflict resolution in merge tables:
   - Prefer UUID primary keys. Use uuid_v4_rekey for integer PKs.
   - Use email or unique business key for deduplication_key where available.
9. confidence_score: set per table AND overall. Use < 0.75 when mapping is ambiguous.
10. warnings: list any data quality risks, ambiguous type coercions, or manual steps needed.
11. pre_migration_ddl: include CREATE EXTENSION, CREATE TABLE DDL for target tables.
12. post_migration_ddl: include CREATE INDEX, ADD CONSTRAINT for target tables.
13. Temperature is 0.0. Output MUST be deterministic, valid JSON matching the schema exactly.

ALLOWED transformation_type TAXONOMY (column level):
  direct_copy      → Copy column value as-is from source to target
  merge_concat     → Combine 2+ source columns into 1 target column
  type_cast        → Data type conversion (e.g. VARCHAR → UUID, INT → BIGINT)
  split            → Decompose 1 source column into 2+ target columns
  expression       → Derive value using a sanitized SQL expression
  lookup_join      → Resolve FK foreign key → referenced table's descriptive column
  default_constant → Fill with hardcoded constant value
  drop_column      → Source column is NOT mapped (will be discarded)
  new_column_added → New target column with no source equivalent

ALLOWED transformation_type TAXONOMY (table level):
  direct_copy  → Table from exactly 1 source, copied unchanged
  merge        → 2+ source tables combined into 1 target table
  split_target → 1 source table decomposed into 2+ target tables

UI Badge Colors (for reference only — do not include in output):
  direct_copy=green, merge_concat=blue, type_cast=purple, split=orange,
  expression=yellow, lookup_join=teal, default_constant=gray,
  drop_column=red, new_column_added=indigo
"""


# ============================================================================
# Metadata Context Serializer — ZERO RAW DATA
# ============================================================================
class MetadataContextSerializer:
    """
    Converts MetadataSnapshot ORM objects into a sanitized YAML-like context string.
    STRICTLY enforces Zero Raw Data Policy:
    - No table row contents, no sample data
    - No passwords, hostnames, or connection strings
    - UUIDs replaced with logical aliases
    """

    @staticmethod
    def _format_column(col: MetadataColumn, pk_names: set) -> str:
        parts = [f"      - name: {col.column_name}"]
        parts.append(f"        type: {col.native_data_type or col.data_type}")
        parts.append(f"        nullable: {str(col.nullable).lower()}")
        if col.is_primary_key or col.column_name in pk_names:
            parts.append("        is_primary_key: true")
        if col.is_unique:
            parts.append("        is_unique: true")
        if col.max_length:
            parts.append(f"        max_length: {col.max_length}")
        if col.numeric_precision:
            parts.append(f"        numeric_precision: {col.numeric_precision}")
        if col.numeric_scale:
            parts.append(f"        numeric_scale: {col.numeric_scale}")
        if col.default_value:
            parts.append(f"        default_value: \"{col.default_value}\"")
        return "\n".join(parts)

    @staticmethod
    def _format_constraints(constraints: List[MetadataConstraint]) -> str:
        if not constraints:
            return ""
        lines = ["      constraints:"]
        seen = set()
        for c in constraints:
            key = (c.constraint_name, c.constraint_type)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"        - name: {c.constraint_name}, type: {c.constraint_type}")
        return "\n".join(lines)

    @classmethod
    def serialize(
        cls,
        snapshots: List[MetadataSnapshot],
        source_aliases: dict,
        target_db_type: str,
        custom_instructions: Optional[str] = None,
    ) -> str:
        """
        Produces a clean, sanitized structural-only YAML string from MetadataSnapshots.

        Parameters:
        - snapshots: List of MetadataSnapshot ORM objects (with loaded relationships)
        - source_aliases: Dict mapping data_source_id (str) → logical alias (e.g. 'source_db_1')
        - target_db_type: Target database dialect string
        - custom_instructions: Optional user-provided instructions to append
        """
        lines = ["# SOURCE DATABASE METADATA CONTEXT (Structural Schema Only — No Raw Data)\n"]

        for snapshot in snapshots:
            alias = source_aliases.get(str(snapshot.data_source_id), f"source_db_{str(snapshot.data_source_id)[:8]}")
            lines.append(f"# SOURCE DATABASE: {alias} ({snapshot.database_name} | {snapshot.database_version or 'Unknown version'})")
            lines.append(f"# Tables: {snapshot.total_tables}, Columns: {snapshot.total_columns}, Est. Rows: {snapshot.total_rows}\n")

            for schema in (snapshot.schemas or []):
                lines.append(f"schema: {schema.schema_name}")

                for table in (schema.tables or []):
                    # Build PK set from constraints
                    pk_names = {
                        c.constraint_name for c in (table.constraints or [])
                        if c.constraint_type.lower() in ("primary key", "primary_key")
                    }
                    lines.append(f"  table: {table.table_name} (type={table.table_type}, est_rows={table.row_count})")
                    lines.append("    columns:")
                    for col in sorted(table.columns or [], key=lambda c: c.ordinal_position):
                        lines.append(cls._format_column(col, pk_names))

                    cst_block = cls._format_constraints(table.constraints or [])
                    if cst_block:
                        lines.append(cst_block)
                    lines.append("")

            # Foreign key relationships
            if snapshot.relationships:
                lines.append("    foreign_keys:")
                for rel in snapshot.relationships:
                    src_tbl = next(
                        (t.table_name for s in (snapshot.schemas or []) for t in (s.tables or []) if t.id == rel.source_table_id),
                        str(rel.source_table_id)[:8],
                    )
                    src_col = next(
                        (c.column_name for s in (snapshot.schemas or []) for t in (s.tables or []) for c in (t.columns or []) if c.id == rel.source_column_id),
                        "?",
                    )
                    tgt_tbl = next(
                        (t.table_name for s in (snapshot.schemas or []) for t in (s.tables or []) if t.id == rel.target_table_id),
                        str(rel.target_table_id)[:8],
                    )
                    tgt_col = next(
                        (c.column_name for s in (snapshot.schemas or []) for t in (s.tables or []) for c in (t.columns or []) if c.id == rel.target_column_id),
                        "?",
                    )
                    lines.append(f"      - {alias}.{src_tbl}.{src_col} → {alias}.{tgt_tbl}.{tgt_col}")
                lines.append("")

        lines.append(f"\n# TARGET DATABASE: target_db ({target_db_type})")
        lines.append("# Instruction: Combine all source databases listed above into a single target_db.\n")

        if custom_instructions:
            lines.append(f"# ADDITIONAL USER INSTRUCTIONS:\n# {custom_instructions}\n")

        return "\n".join(lines)


# ============================================================================
# LLM Plan Generator Service
# ============================================================================
class LLMPlanGeneratorService:
    """
    Invokes LangChain LLM with with_structured_output(TransformationPlanAST).
    Implements retry loop on JSON parse/schema validation failures.
    """

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        """Lazily initialize LLM on first use (avoids import errors if keys not set)."""
        if self._llm is not None:
            return self._llm

        provider = settings.LLM_PROVIDER
        model = settings.LLM_MODEL
        temperature = settings.LLM_TEMPERATURE

        if provider == "gemini":
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._llm = ChatGoogleGenerativeAI(
                    model=model,
                    temperature=temperature,
                    google_api_key=settings.GEMINI_API_KEY,
                )
            except ImportError as exc:
                raise RuntimeError("langchain-google-genai is not installed. Run: poetry add langchain-google-genai") from exc

        elif provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model=model,
                    temperature=temperature,
                    api_key=settings.OPENAI_API_KEY,
                )
            except ImportError as exc:
                raise RuntimeError("langchain-openai is not installed. Run: poetry add langchain-openai") from exc

        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: '{provider}'. Must be 'gemini' or 'openai'.")

        return self._llm

    def generate(
        self,
        context_str: str,
        target_db_type: str,
    ) -> TransformationPlanAST:
        """
        Calls LLM with system prompt + sanitized metadata context.
        Uses with_structured_output(TransformationPlanAST) for Pydantic schema enforcement.
        Implements retry loop on validation failure (max LLM_MAX_RETRIES attempts).

        Returns a validated TransformationPlanAST instance.
        Raises RuntimeError if all retries are exhausted.
        """
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_core.output_parsers import PydanticOutputParser

        llm = self._get_llm()
        parser = PydanticOutputParser(pydantic_object=TransformationPlanAST)

        full_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"{parser.get_format_instructions()}\n\n"
            f"Analyze the following sanitized source database schemas and generate a complete "
            f"TransformationPlan to merge them into a single target database of type '{target_db_type}'.\n\n"
            f"{context_str}"
        )

        last_error: Optional[Exception] = None
        max_retries = settings.LLM_MAX_RETRIES

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"LLM plan generation attempt {attempt}/{max_retries}...")

                messages = [HumanMessage(content=full_prompt)]

                if last_error and attempt > 1:
                    messages.append(
                        HumanMessage(
                            content=(
                                f"Your previous response failed Pydantic schema validation. "
                                f"Error: {last_error}. "
                                f"Please correct and re-generate the complete TransformationPlan JSON."
                            )
                        )
                    )

                response = llm.invoke(messages)
                content = str(response.content)
                result = parser.parse(content)

                logger.info(f"LLM plan generation succeeded on attempt {attempt}.")
                return result

            except Exception as exc:
                last_error = exc
                logger.warning(f"LLM attempt {attempt} failed: {exc}")

        raise RuntimeError(
            f"LLM plan generation failed after {max_retries} attempts. "
            f"Last error: {last_error}"
        )


# Singleton instance
llm_plan_generator = LLMPlanGeneratorService()
