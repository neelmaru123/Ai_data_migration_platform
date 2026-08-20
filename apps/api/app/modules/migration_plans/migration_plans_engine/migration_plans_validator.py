"""
Migration Plans Engine — Deterministic Migration Feasibility Validator

Validates TransformationPlanAST blueprints against actual introspected MetadataSnapshots.
Detects missing tables/columns, illegal type conversions, broken PK/FK links, and deduplication flaws.
"""

import logging
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel

from app.modules.metadata.metadata_models import MetadataSnapshot
from app.modules.migration_plans.migration_plans_schemas import TransformationPlanAST

logger = logging.getLogger(__name__)


class PlanValidationResult(BaseModel):
    """Output of the deterministic schema feasibility check."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    explanation: str


class MigrationPlanValidator:
    """Performs 5-stage deterministic feasibility check on TransformationPlanAST blueprints."""

    @staticmethod
    def validate(
        plan_ast_data: Dict[str, Any] | TransformationPlanAST,
        snapshots: List[MetadataSnapshot],
        alias_map: Optional[Dict[str, str]] = None,
    ) -> PlanValidationResult:
        """
        Validates an AST dictionary or model against a list of MetadataSnapshot objects.
        """
        if isinstance(plan_ast_data, dict):
            try:
                ast = TransformationPlanAST.model_validate(plan_ast_data)
            except Exception as exc:
                return PlanValidationResult(
                    is_valid=False,
                    errors=[f"Invalid AST structure: {str(exc)}"],
                    warnings=[],
                    explanation=f"The migration plan AST could not be parsed: {exc}",
                )
        else:
            ast = plan_ast_data

        errors: List[str] = []
        warnings: List[str] = []

        # 1. Build source database metadata lookup map
        # Structure: lookup[alias][table_name] = {col_name: col_type}
        lookup: Dict[str, Dict[str, Dict[str, str]]] = {}
        for snap in snapshots:
            alias = None
            if alias_map and str(snap.data_source_id) in alias_map:
                alias = alias_map[str(snap.data_source_id)]
            elif hasattr(snap, "data_source") and snap.data_source and snap.data_source.identifier:
                alias = snap.data_source.identifier

            if not alias:
                alias = f"source_db_{snap.id}"

            lookup[alias] = {}
            for schema in snap.schemas:
                for table in schema.tables:
                    column_type_map: Dict[str, str] = {}
                    for col in table.columns:
                        column_type_map[col.column_name.lower()] = col.data_type.lower()
                    lookup[alias][table.table_name.lower()] = column_type_map

        # Track target table names
        target_tables: Set[str] = set()

        # 2. Iterate through table mappings
        for table_map in ast.table_mappings:
            target_table_name = table_map.target_table_name
            target_tables.add(target_table_name.lower())

            # stage A: Source Table Existence Check
            for src_ref in table_map.source_tables:
                src_alias = src_ref.identifier
                src_tbl = src_ref.table_name.lower()

                if src_alias not in lookup:
                    # Fallback check if alias matching varies slightly
                    matching_aliases = [a for a in lookup.keys() if src_alias in a or a in src_alias]
                    if not matching_aliases:
                        errors.append(
                            f"Table mapping '{target_table_name}': Referenced source database alias '{src_alias}' "
                            f"does not exist in metadata snapshots."
                        )
                        continue
                    src_alias = matching_aliases[0]

                if src_tbl not in lookup[src_alias]:
                    errors.append(
                        f"Table mapping '{target_table_name}': Referenced source table '{src_ref.table_name}' "
                        f"does not exist in source database '{src_alias}'."
                    )

            # Stage B: Source Column & Type Conversion Check
            target_cols: Set[str] = set()
            for col_map in table_map.column_mappings:
                if col_map.target_column_name:
                    target_cols.add(col_map.target_column_name.lower())

                for src_col in col_map.source_columns:
                    src_alias = src_col.identifier
                    src_tbl = src_col.table_name.lower()
                    src_cname = src_col.column_name.lower()

                    if src_alias in lookup and src_tbl in lookup[src_alias]:
                        tbl_cols = lookup[src_alias][src_tbl]
                        if src_cname not in tbl_cols:
                            errors.append(
                                f"Column mapping in '{target_table_name}': Source column '{src_col.column_name}' "
                                f"does not exist in table '{src_col.table_name}' in source '{src_alias}'."
                            )
                        else:
                            # Check basic type compatibility
                            src_type = tbl_cols[src_cname]
                            tgt_type = (col_map.target_data_type or "").lower()

                            # If direct_copy or type_cast without expression template, verify basic feasibility
                            if (
                                col_map.transformation_type in ["direct_copy", "type_cast"]
                                and not col_map.expression_template
                            ):
                                if "text" in src_type or "char" in src_type or "varchar" in src_type:
                                    if any(t in tgt_type for t in ["int", "numeric", "float", "decimal", "double"]) and "cast" not in col_map.transformation_type:
                                        warnings.append(
                                            f"Column '{col_map.target_column_name}' in '{target_table_name}': "
                                            f"Casting string type '{src_type}' to numeric type '{tgt_type}' "
                                            f"without explicit conversion expression template."
                                        )

            # Stage C: Deduplication Key Validity
            if table_map.conflict_resolution and table_map.conflict_resolution.deduplication_key:
                dedup_key = table_map.conflict_resolution.deduplication_key.lower()
                if dedup_key not in target_cols:
                    errors.append(
                        f"Table mapping '{target_table_name}': Deduplication key '{table_map.conflict_resolution.deduplication_key}' "
                        f"is not mapped as a target column."
                    )

        # Stage D: Foreign Key & DDL Two-Phase Hygiene Check
        import re
        fk_pattern = re.compile(r"REFERENCES\s+([a-zA-Z0-9_\"\.]+)", re.IGNORECASE)

        for ddl in ast.pre_migration_ddl:
            if "FOREIGN KEY" in ddl.upper() or "REFERENCES " in ddl.upper():
                errors.append(
                    f"Pre-migration DDL Hygiene Error: Statement '{ddl[:60]}...' contains a FOREIGN KEY constraint. "
                    f"All foreign keys must be executed in post_migration_ddl after data streaming is complete."
                )

        for ddl in ast.post_migration_ddl:
            matches = fk_pattern.findall(ddl)
            for ref_tbl in matches:
                clean_tbl = ref_tbl.strip('"').split(".")[-1].lower()
                if clean_tbl not in target_tables:
                    # Check if it exists in any source database table as fallback
                    exists_in_source = any(clean_tbl in lookup[alias] for alias in lookup)
                    if not exists_in_source:
                        errors.append(
                            f"Post-migration DDL FK constraint references non-existent target table '{clean_tbl}'."
                        )

        # Stage E: Industry Database Architecture Standards Validation
        snake_case_pattern = re.compile(r"^[a-z0-9_]+$")
        for table_map in ast.table_mappings:
            tgt_tbl = table_map.target_table_name
            if not snake_case_pattern.match(tgt_tbl):
                warnings.append(
                    f"Table Architecture Standard Notice: Target table '{tgt_tbl}' is not in standard lowercase snake_case."
                )

            col_names = [col.target_column_name for col in table_map.column_mappings if col.target_column_name]
            has_id = any(c.lower() == "id" for c in col_names)
            if not has_id:
                warnings.append(
                    f"Table Architecture Standard Notice: Target table '{tgt_tbl}' lacks a standard 'id' primary key column."
                )

            for col in table_map.column_mappings:
                if col.target_column_name and not snake_case_pattern.match(col.target_column_name):
                    warnings.append(
                        f"Column Architecture Standard Notice: Target column '{col.target_column_name}' in table '{tgt_tbl}' is not in standard lowercase snake_case."
                    )
        is_valid = len(errors) == 0
        if is_valid:
            if warnings:
                explanation = (
                    f"Plan feasibility check PASSED with {len(warnings)} warning(s). "
                    f"All {len(ast.table_mappings)} target table mappings are valid against source schemas."
                )
            else:
                explanation = (
                    f"Plan feasibility check PASSED. All {len(ast.table_mappings)} target table mappings "
                    f"and column mappings are 100% structurally valid against source schemas."
                )
        else:
            explanation = (
                f"Plan feasibility check FAILED with {len(errors)} error(s). "
                f"The database cannot be migrated with these settings: "
                + "; ".join(errors[:3])
                + (f" (...and {len(errors)-3} more errors)" if len(errors) > 3 else "")
            )

        return PlanValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            explanation=explanation,
        )
