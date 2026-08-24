"""
AST column transformation engine applying Polars in-memory batch transformations, PK resolution strategies, and residual field capture.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import duckdb
import polars as pl

logger = logging.getLogger("docker-agent-execution")


class ASTTransformer:
    """Applies all 9 AST column transformation types to a Polars DataFrame in-memory."""

    @staticmethod
    def transform_chunk(
        df: pl.DataFrame,
        column_mappings: List[Dict[str, Any]],
        primary_key_strategy: Optional[str] = None,
    ) -> Tuple[pl.DataFrame, int]:
        if df.is_empty():
            return df, 0

        exprs = []
        keep_columns = []
        row_errors = 0

        for col_spec in column_mappings:
            target_col = col_spec.get("target_column_name")
            trans_type = col_spec.get("transformation_type", "direct_copy")
            source_cols = col_spec.get("source_columns", [])
            expr_tmpl = col_spec.get("expression_template")
            const_val = col_spec.get("constant_value")

            if not target_col or trans_type == "drop_column":
                continue

            keep_columns.append(target_col)

            # 1. direct_copy
            if trans_type == "direct_copy":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    exprs.append(pl.col(src_name).alias(target_col))

            # 2. type_cast (e.g. INT -> UUID, STRING -> DATETIME UTC, PREFIX_ID)
            elif trans_type == "type_cast":
                src_name = source_cols[0]["column_name"] if source_cols and "column_name" in source_cols[0] else target_col
                src_ident = source_cols[0].get("identifier", "source") if source_cols else "source"
                target_dtype = col_spec.get("target_data_type", "varchar").lower()
                pk_strategy = primary_key_strategy or col_spec.get("primary_key_strategy", "uuid_v5")

                if src_name in df.columns:
                    if col_spec.get("is_primary_key"):
                        if pk_strategy == "keep_original":
                            if "int" in target_dtype:
                                pk_expr = pl.col(src_name).cast(pl.Int64, strict=False)
                            else:
                                pk_expr = pl.col(src_name).cast(pl.Utf8)
                        elif pk_strategy == "autoincrement_offset":
                            src_idx = col_spec.get("source_index", 0)
                            if not src_idx and src_ident:
                                nums = re.findall(r'\d+', str(src_ident))
                                if nums:
                                    src_idx = max(0, int(nums[-1]) - 1)
                            offset_val = 1_000_000_000 * int(src_idx)
                            pk_expr = (pl.col(src_name).cast(pl.Int64, strict=False) + offset_val).cast(pl.Int64)
                        elif pk_strategy == "uuid_v4_rekey":
                            pk_expr = pl.col(src_name).cast(pl.Utf8).map_elements(
                                lambda val: str(uuid.uuid4()),
                                return_dtype=pl.Utf8
                            )
                        elif pk_strategy == "prefix_id":
                            pk_expr = pl.col(src_name).cast(pl.Utf8).map_elements(
                                lambda val: f"{src_ident}_{val}" if val is not None and str(val) != "" else str(uuid.uuid4()),
                                return_dtype=pl.Utf8
                            )
                        else:
                            # Deterministic UUID v5 namespace hashing by default
                            pk_expr = pl.col(src_name).cast(pl.Utf8).map_elements(
                                lambda val: str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{src_ident}_{val}")) if val is not None and str(val) != "" else str(uuid.uuid4()),
                                return_dtype=pl.Utf8
                            )
                        exprs.append(pk_expr.alias(target_col))
                    elif "uuid" in target_dtype:
                        uuid_expr = pl.col(src_name).cast(pl.Utf8).map_elements(
                            lambda val: str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{src_ident}_{val}")) if val is not None and str(val) != "" and not (len(str(val)) == 36 and "-" in str(val)) else str(val or ""),
                            return_dtype=pl.Utf8
                        )
                        exprs.append(uuid_expr.alias(target_col))
                    elif "int" in target_dtype:
                        exprs.append(pl.col(src_name).cast(pl.Int64, strict=False).alias(target_col))
                    elif "timestamp" in target_dtype or "datetime" in target_dtype or "timestamptz" in target_dtype:
                        # ISO-8601 UTC normalization
                        dt_expr = (
                            pl.col(src_name)
                            .cast(pl.Utf8)
                            .str.replace(r" ", "T")
                            .str.to_datetime(strict=False)
                        )
                        exprs.append(dt_expr.alias(target_col))
                    else:
                        exprs.append(pl.col(src_name).cast(pl.Utf8).alias(target_col))

            # 3. merge_concat (e.g. CONCAT(first_name, ' ', last_name))
            elif trans_type == "merge_concat":
                available_srcs = [sc["column_name"] for sc in source_cols if sc["column_name"] in df.columns]
                if available_srcs:
                    concat_expr = pl.concat_str([pl.col(c).fill_null("") for c in available_srcs], separator=" ")
                    exprs.append(concat_expr.alias(target_col))

            # 4. split (e.g. SPLIT_PART(full_address, ',', 1))
            elif trans_type == "split":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    split_expr = pl.col(src_name).str.split(",").list.get(0)
                    exprs.append(split_expr.alias(target_col))

            # 5. default_constant
            elif trans_type == "default_constant":
                val = const_val if const_val is not None else ""
                exprs.append(pl.lit(val).alias(target_col))

            # 6. new_column_added (e.g. migrated_at timestamp)
            elif trans_type == "new_column_added":
                exprs.append(pl.lit(datetime.now(timezone.utc).isoformat()).alias(target_col))

            # 7. expression (e.g. price - discount, quantity * unit_price, or multi-column arithmetic)
            elif trans_type == "expression" and expr_tmpl:
                try:
                    calc_df = duckdb.sql(f'SELECT ({expr_tmpl}) AS "{target_col}" FROM df').pl()
                    if target_col in calc_df.columns:
                        exprs.append(calc_df[target_col])
                except Exception as expr_err:
                    logger.warning(f"Expression calculation notice for '{target_col}' ({expr_tmpl}): {expr_err}")
                    src_name = source_cols[0]["column_name"] if source_cols else target_col
                    if src_name in df.columns:
                        exprs.append(pl.col(src_name).alias(target_col))

            # 8. json_flatten (e.g. address.city -> address_city)
            elif trans_type == "json_flatten":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    exprs.append(pl.col(src_name).cast(pl.Utf8).alias(target_col))
                elif "." in src_name:
                    parts = src_name.split(".")
                    root_col = parts[0]
                    sub_paths = parts[1:]
                    if root_col in df.columns:
                        def _extract_nested(val, paths=sub_paths):
                            curr = val
                            if hasattr(curr, "to_dict"):
                                curr = curr.to_dict()
                            for p in paths:
                                if isinstance(curr, dict):
                                    curr = curr.get(p, "")
                                elif isinstance(curr, str) and curr.startswith("{"):
                                    try:
                                        curr = json.loads(curr).get(p, "")
                                    except Exception:
                                        return ""
                                else:
                                    return ""
                            return str(curr) if curr is not None else ""

                        flatten_expr = pl.col(root_col).map_elements(
                            _extract_nested, return_dtype=pl.Utf8
                        )
                        exprs.append(flatten_expr.alias(target_col))

            # 9. json_stringify (e.g. dict/list -> JSON string / JSONB payload)
            elif trans_type == "json_stringify":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    def _safe_json_dumps(val):
                        if hasattr(val, "to_dict"):
                            val = val.to_dict()
                        elif hasattr(val, "to_list"):
                            val = val.to_list()
                        if isinstance(val, (dict, list)):
                            return json.dumps(val)
                        if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                            return val
                        if val is not None:
                            return json.dumps(val)
                        return "{}"

                    stringify_expr = pl.col(src_name).map_elements(
                        _safe_json_dumps, return_dtype=pl.Utf8
                    )
                    exprs.append(stringify_expr.alias(target_col))

            # 10. array_to_csv (e.g. tags List -> "tag1,tag2")
            elif trans_type == "array_to_csv":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    def _safe_array_to_csv(val):
                        if hasattr(val, "to_list"):
                            val = val.to_list()
                        if isinstance(val, (list, tuple, set)):
                            return ",".join(map(str, val))
                        return str(val or "")

                    csv_expr = pl.col(src_name).map_elements(
                        _safe_array_to_csv, return_dtype=pl.Utf8
                    )
                    exprs.append(csv_expr.alias(target_col))

            # 11. array_to_json (e.g. tags List -> '["tag1", "tag2"]')
            elif trans_type == "array_to_json":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    def _safe_array_to_json(val):
                        if hasattr(val, "to_list"):
                            val = val.to_list()
                        if isinstance(val, (list, tuple, set)):
                            return json.dumps(val)
                        if val is not None:
                            return json.dumps([val])
                        return "[]"

                    json_arr_expr = pl.col(src_name).map_elements(
                        _safe_array_to_json, return_dtype=pl.Utf8
                    )
                    exprs.append(json_arr_expr.alias(target_col))

            # 12. nosql_field_promote
            elif trans_type == "nosql_field_promote":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    exprs.append(pl.col(src_name).cast(pl.Utf8).alias(target_col))

            # 13. lookup_join / fallback
            else:
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    exprs.append(pl.col(src_name).alias(target_col))

        # Residual/unmapped field capture (Fix 9)
        mapped_src_cols = set()
        for col_spec in column_mappings:
            if col_spec.get("target_column_name") and col_spec.get("transformation_type") != "drop_column":
                for sc in col_spec.get("source_columns", []):
                    if "column_name" in sc:
                        c_name = sc["column_name"]
                        mapped_src_cols.add(c_name)
                        if "." in c_name:
                            mapped_src_cols.add(c_name.split(".")[0])

        unmapped_cols = [c for c in df.columns if c not in mapped_src_cols and c not in ("_seq_id",)]
        if unmapped_cols:
            if "extra_attributes" not in keep_columns:
                keep_columns.append("extra_attributes")

            def _serialize_residual(struct_val, cols=unmapped_cols):
                res_dict = {}
                if isinstance(struct_val, dict):
                    for k, v in struct_val.items():
                        if v is not None:
                            if hasattr(v, "to_dict"):
                                v = v.to_dict()
                            elif hasattr(v, "to_list"):
                                v = v.to_list()
                            res_dict[k] = v
                return json.dumps(res_dict, default=str) if res_dict else "{}"

            try:
                extra_attr_expr = pl.struct([pl.col(c) for c in unmapped_cols if c in df.columns]).map_elements(
                    _serialize_residual, return_dtype=pl.Utf8
                )
                exprs.append(extra_attr_expr.alias("extra_attributes"))
            except Exception as exc:
                logger.warning(f"Residual field capture warning: {exc}")

        if exprs:
            try:
                transformed_df = df.with_columns(exprs)
                available_targets = [c for c in keep_columns if c in transformed_df.columns]
                return transformed_df.select(available_targets), row_errors
            except Exception as exc:
                logger.warning(f"Vectorized transformation warning, falling back with row error tracking: {exc}")
                row_errors += 1
                return df, row_errors

        return df, row_errors
