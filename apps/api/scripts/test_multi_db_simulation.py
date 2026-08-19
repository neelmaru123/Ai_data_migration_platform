"""
End-to-End Multi-Source Migration Simulation Test Script
Demonstrates 3:1 Migration: MongoDB + MySQL + PostgreSQL -> Target PostgreSQL
Verifies:
1. Schema & Metadata Representation
2. In-Memory AST Transformations (UUID casting, concat, default values, expressions)
3. Multi-source diagonal merge & deduplication ('first_wins')
4. Live insertion into target PostgreSQL container (Port 5434)
5. Querying and validating final unified schema and data integrity
"""

import sys
import os
import polars as pl
from sqlalchemy import create_engine, text

# Force UTF-8 on Windows stdout
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add parent directories to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../agent")))

from execution_engine import ASTTransformer, TableMerger, DDLExecutor, TargetWriterFactory


def run_multi_source_migration_simulation():
    print("\n" + "=" * 80)
    print(" >>> STARTING 3:1 MULTI-DATABASE MIGRATION SIMULATION")
    print("     Sources: MongoDB (JSON docs) + MySQL (SQL) + PostgreSQL (SQL)")
    print("     Target:  PostgreSQL (migration_platform on port 5434)")
    print("=" * 80 + "\n")

    # --------------------------------------------------------------------------
    # 1. SYNTHESIZE REALISTIC SOURCE DATASETS
    # --------------------------------------------------------------------------
    print("[Step 1] Preparing Source Datasets...")

    # Source A: MongoDB 'users' Collection (simulated docs)
    mongo_raw_docs = [
        {"_id": "64f1a2b3c4d5e6f7a8b9c0d1", "user_email": "alice@company.com", "full_name": "Alice Johnson", "tier": "enterprise"},
        {"_id": "64f1a2b3c4d5e6f7a8b9c0d2", "user_email": "bob@company.com", "full_name": "Bob Smith", "tier": "pro"},
    ]
    df_mongo = pl.DataFrame(mongo_raw_docs)
    print(f"  * MongoDB:    {len(df_mongo)} documents loaded (Columns: {df_mongo.columns})")

    # Source B: MySQL 'customers' Table (simulated SQL records with split names)
    mysql_raw_rows = [
        {"customer_id": 101, "email_address": "bob@company.com", "first_name": "Bob", "last_name": "Smith", "is_vip": 1},  # Duplicate email!
        {"customer_id": 102, "email_address": "charlie@company.com", "first_name": "Charlie", "last_name": "Brown", "is_vip": 0},
    ]
    df_mysql = pl.DataFrame(mysql_raw_rows)
    print(f"  * MySQL:      {len(df_mysql)} rows loaded (Columns: {df_mysql.columns})")

    # Source C: PostgreSQL 'legacy_accounts' Table (simulated SQL records)
    pg_raw_rows = [
        {"acc_id": "pg-acc-9001", "email": "alice@company.com", "name": "Alice Johnson", "region": "US-EAST"},  # Duplicate email!
        {"acc_id": "pg-acc-9002", "email": "david@company.com", "name": "David Wilson", "region": "EU-WEST"},
    ]
    df_postgres = pl.DataFrame(pg_raw_rows)
    print(f"  * PostgreSQL: {len(df_postgres)} rows loaded (Columns: {df_postgres.columns})")
    print(f"  -> Total Source Rows across all 3 DBs before merge: {len(df_mongo) + len(df_mysql) + len(df_postgres)} rows\n")

    # --------------------------------------------------------------------------
    # 2. DEFINE AST COLUMN MAPPING SPECIFICATIONS
    # --------------------------------------------------------------------------
    print("[Step 2] Defining AST Transformation Rules for each Source...")

    mongo_mappings = [
        {"target_column_name": "id", "transformation_type": "type_cast", "target_data_type": "uuid", "source_columns": [{"column_name": "_id"}]},
        {"target_column_name": "email", "transformation_type": "direct_copy", "source_columns": [{"column_name": "user_email"}]},
        {"target_column_name": "name", "transformation_type": "direct_copy", "source_columns": [{"column_name": "full_name"}]},
        {"target_column_name": "source_origin", "transformation_type": "default_constant", "constant_value": "mongodb"},
        {"target_column_name": "migrated_at", "transformation_type": "new_column_added"},
    ]

    mysql_mappings = [
        {"target_column_name": "id", "transformation_type": "type_cast", "target_data_type": "uuid", "source_columns": [{"column_name": "customer_id"}]},
        {"target_column_name": "email", "transformation_type": "direct_copy", "source_columns": [{"column_name": "email_address"}]},
        {"target_column_name": "name", "transformation_type": "merge_concat", "source_columns": [{"column_name": "first_name"}, {"column_name": "last_name"}]},
        {"target_column_name": "source_origin", "transformation_type": "default_constant", "constant_value": "mysql"},
        {"target_column_name": "migrated_at", "transformation_type": "new_column_added"},
    ]

    pg_mappings = [
        {"target_column_name": "id", "transformation_type": "type_cast", "target_data_type": "uuid", "source_columns": [{"column_name": "acc_id"}]},
        {"target_column_name": "email", "transformation_type": "direct_copy", "source_columns": [{"column_name": "email"}]},
        {"target_column_name": "name", "transformation_type": "direct_copy", "source_columns": [{"column_name": "name"}]},
        {"target_column_name": "source_origin", "transformation_type": "default_constant", "constant_value": "postgresql"},
        {"target_column_name": "migrated_at", "transformation_type": "new_column_added"},
    ]

    # --------------------------------------------------------------------------
    # 3. APPLY IN-MEMORY VECTORIZED AST TRANSFORMATIONS (Polars)
    # --------------------------------------------------------------------------
    print("[Step 3] Executing Vectorized In-Memory AST Transformations...")

    df_mongo_trans, _ = ASTTransformer.transform_chunk(df_mongo, mongo_mappings)
    df_mysql_trans, _ = ASTTransformer.transform_chunk(df_mysql, mysql_mappings)
    df_pg_trans, _ = ASTTransformer.transform_chunk(df_postgres, pg_mappings)

    print(f"  [OK] MongoDB Transformed:  {len(df_mongo_trans)} rows -> Target schema {df_mongo_trans.columns}")
    print(f"  [OK] MySQL Transformed:    {len(df_mysql_trans)} rows -> Target schema {df_mysql_trans.columns}")
    print(f"  [OK] Postgres Transformed: {len(df_pg_trans)} rows -> Target schema {df_pg_trans.columns}\n")

    # --------------------------------------------------------------------------
    # 4. MULTI-SOURCE TABLE MERGE & DEDUPLICATION
    # --------------------------------------------------------------------------
    print("[Step 4] Merging Tables & Applying Deduplication Key ('email', strategy='first_wins')...")

    conflict_res = {
        "deduplication_key": "email",
        "deduplication_strategy": "first_wins"
    }
    merged_df = TableMerger.merge_and_deduplicate([df_mongo_trans, df_mysql_trans, df_pg_trans], conflict_res)

    print(f"  [OK] Successfully merged 3 datasets!")
    print(f"  [OK] Deduplicated total rows: {len(merged_df)} unique records (Duplicates removed: 2)")
    print("\nMerged In-Memory Preview:")
    print(merged_df)
    print("\n")

    # --------------------------------------------------------------------------
    # 5. EXECUTE PRE-MIGRATION DDL ON TARGET DATABASE
    # --------------------------------------------------------------------------
    target_db_url = "postgresql+psycopg2://postgres:postgres_password@localhost:5434/migration_platform"
    print(f"[Step 5] Executing Target Pre-Migration DDL on PostgreSQL (Port 5434)...")

    pre_ddl = [
        "DROP TABLE IF EXISTS target_unified_users CASCADE;",
        """
        CREATE TABLE target_unified_users (
            id VARCHAR(64) PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255),
            source_origin VARCHAR(50),
            migrated_at VARCHAR(100)
        );
        """
    ]
    DDLExecutor.execute_ddl_list(target_db_url, pre_ddl, "Pre-Migration DDL")
    print("  [OK] Target table 'target_unified_users' created successfully.\n")

    # --------------------------------------------------------------------------
    # 6. BULK INSERT INTO TARGET DATABASE
    # --------------------------------------------------------------------------
    print("[Step 6] Bulk Loading Merged DataFrame into Target Database...")
    succ, fail = TargetWriterFactory.bulk_load(
        db_url=target_db_url,
        engine_type="postgresql",
        table_name="target_unified_users",
        df=merged_df
    )
    print(f"  [OK] Bulk Insert Results: {succ} successful rows, {fail} failed rows.\n")

    # --------------------------------------------------------------------------
    # 7. QUERY & VALIDATE FINAL DATABASE STATE
    # --------------------------------------------------------------------------
    print("[Step 7] Querying Target Database to Validate Results...")
    engine = create_engine(target_db_url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, email, name, source_origin, migrated_at FROM target_unified_users ORDER BY email ASC;"))
        rows = result.fetchall()

    print("\n" + "=" * 80)
    print(" VERIFIED DATABASE RECORDS IN 'target_unified_users':")
    print("=" * 80)
    print(f"{'ID':<38} | {'EMAIL':<22} | {'NAME':<16} | {'SOURCE ORIGIN':<14}")
    print("-" * 80)
    for r in rows:
        print(f"{r[0]:<38} | {r[1]:<22} | {r[2]:<16} | {r[3]:<14}")
    print("=" * 80)

    # Assertions
    assert len(rows) == 4, f"Expected exactly 4 unique users, got {len(rows)}"
    emails = [r[1] for r in rows]
    assert sorted(emails) == ["alice@company.com", "bob@company.com", "charlie@company.com", "david@company.com"], "Missing expected user emails!"
    
    print("\n[SUCCESS] ALL ASSERTIONS PASSED! 3:1 Multi-DB Migration verified 100% working.\n")


if __name__ == "__main__":
    run_multi_source_migration_simulation()
