"""
Comprehensive Multi-Database Seeding Script for End-to-End Migration Testing.

Creates 3 complex databases with rich schema structures:
1. PostgreSQL (Port 5435): complex_pg_db (Relational Core: pg_customers, pg_products, pg_orders, pg_order_items)
2. MySQL (Port 3307): complex_mysql_db (Legacy ERP: mysql_accounts, mysql_inventory, mysql_audit_logs)
3. MongoDB (Port 27017): complex_mongo_db (Document Store: user_profiles [Depth 3 nested], events_stream, product_reviews_nosql)
"""

import time
import json
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text

# Connection URLs
PG_HOST_URL = "postgresql://postgres:postgres_password@localhost:5435/postgres"
PG_DB_URL = "postgresql://postgres:postgres_password@localhost:5435/complex_pg_db"

MYSQL_HOST_URL = "mysql+pymysql://root:mysql_password@localhost:3307/mysql"
MYSQL_DB_URL = "mysql+pymysql://root:mysql_password@localhost:3307/complex_mysql_db"

MONGO_URL = "mongodb://127.0.0.1:27017"


def wait_for_postgres():
    print("Connecting to PostgreSQL (Port 5435)...")
    for attempt in range(1, 10):
        try:
            engine = create_engine(PG_HOST_URL, connect_args={"connect_timeout": 3})
            with engine.connect() as conn:
                conn.execute(text("COMMIT;"))
                conn.execute(text("CREATE DATABASE complex_pg_db;"))
            print("  [OK] Created database 'complex_pg_db'!")
            break
        except Exception as e:
            if "already exists" in str(e):
                print("  [OK] Database 'complex_pg_db' already exists.")
                break
            print(f"  [Attempt {attempt}/10] Waiting for Postgres 5435... ({e})")
            time.sleep(2)


def wait_for_mysql():
    print("Connecting to MySQL (Port 3307)...")
    for attempt in range(1, 10):
        try:
            engine = create_engine(MYSQL_HOST_URL, connect_args={"connect_timeout": 3})
            with engine.connect() as conn:
                conn.execute(text("CREATE DATABASE IF NOT EXISTS complex_mysql_db;"))
            print("  [OK] Created database 'complex_mysql_db'!")
            break
        except Exception as e:
            print(f"  [Attempt {attempt}/10] Waiting for MySQL 3307... ({e})")
            time.sleep(2)


def setup_postgresql():
    print("\n=======================================================")
    print(" >>> Setting up PostgreSQL 'complex_pg_db' (Port 5435)")
    print("=======================================================")
    engine = create_engine(PG_DB_URL, connect_args={"connect_timeout": 5})

    with engine.begin() as conn:
        conn.execute(text("""
            DROP TABLE IF EXISTS pg_order_items CASCADE;
            DROP TABLE IF EXISTS pg_orders CASCADE;
            DROP TABLE IF EXISTS pg_products CASCADE;
            DROP TABLE IF EXISTS pg_customers CASCADE;
        """))

        conn.execute(text("""
            CREATE TABLE pg_customers (
                customer_id INT PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                phone VARCHAR(50),
                billing_address_raw VARCHAR(500) NOT NULL,
                is_vip BOOLEAN DEFAULT FALSE,
                metadata_json JSONB,
                legacy_account_code VARCHAR(50),
                registered_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE pg_products (
                product_id INT PRIMARY KEY,
                sku VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(200) NOT NULL,
                unit_price NUMERIC(10, 2) NOT NULL,
                tax_rate NUMERIC(5, 4) DEFAULT 0.0825,
                is_active BOOLEAN DEFAULT TRUE
            );

            CREATE TABLE pg_orders (
                order_id INT PRIMARY KEY,
                customer_id INT REFERENCES pg_customers(customer_id),
                status VARCHAR(50) NOT NULL,
                subtotal NUMERIC(10, 2) NOT NULL,
                discount NUMERIC(10, 2) DEFAULT 0.00,
                total_amount NUMERIC(10, 2) NOT NULL,
                order_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE pg_order_items (
                item_id INT PRIMARY KEY,
                order_id INT REFERENCES pg_orders(order_id),
                product_id INT REFERENCES pg_products(product_id),
                quantity INT NOT NULL,
                unit_price NUMERIC(10, 2) NOT NULL
            );
        """))
        print("  [DDL OK] PostgreSQL schema created successfully.")

        # Seed pg_customers (50 rows)
        first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Sam", "Dakota", "Reese", "Quinn"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        cities = ["New York, NY, 10001", "Los Angeles, CA, 90001", "Chicago, IL, 60601", "Houston, TX, 77001", "Phoenix, AZ, 85001"]
        base_time = datetime.now(timezone.utc) - timedelta(days=100)

        customers_data = [
            {
                "customer_id": 1001 + i,
                "email": f"user_{i+1}@omni-enterprise.com",
                "first_name": first_names[i % len(first_names)],
                "last_name": last_names[i % len(last_names)],
                "phone": f"+1-555-01{i+1:02d}",
                "billing_address_raw": f"Building {i+1} Suite 200, {cities[i % len(cities)]}",
                "is_vip": (i % 3 == 0),
                "metadata_json": json.dumps({"preferred_locale": "en_US", "tier": "gold" if i % 3 == 0 else "standard"}),
                "legacy_account_code": f"LEGACY_PG_{1000+i}",
                "registered_at": base_time + timedelta(days=i),
            }
            for i in range(50)
        ]
        conn.execute(text("""
            INSERT INTO pg_customers (customer_id, email, first_name, last_name, phone, billing_address_raw, is_vip, metadata_json, legacy_account_code, registered_at)
            VALUES (:customer_id, :email, :first_name, :last_name, :phone, :billing_address_raw, :is_vip, CAST(:metadata_json AS jsonb), :legacy_account_code, :registered_at);
        """), customers_data)

        # Seed pg_products (50 rows)
        products_data = [
            {
                "product_id": 2001 + i,
                "sku": f"SKU-PROD-{i+1:03d}",
                "name": f"Omni Enterprise Device Model-{i+1}",
                "unit_price": round(49.99 + (i * 15.5), 2),
                "tax_rate": 0.0825,
                "is_active": True,
            }
            for i in range(50)
        ]
        conn.execute(text("""
            INSERT INTO pg_products (product_id, sku, name, unit_price, tax_rate, is_active)
            VALUES (:product_id, :sku, :name, :unit_price, :tax_rate, :is_active);
        """), products_data)

        # Seed pg_orders (50 rows)
        statuses = ["COMPLETED", "SHIPPED", "PROCESSING", "PENDING"]
        orders_data = [
            {
                "order_id": 5001 + i,
                "customer_id": 1001 + (i % 50),
                "status": statuses[i % len(statuses)],
                "subtotal": round(100.0 + (i * 20.0), 2),
                "discount": round((i % 5) * 5.0, 2),
                "total_amount": round((100.0 + (i * 20.0)) - ((i % 5) * 5.0), 2),
                "order_date": base_time + timedelta(days=i, hours=4),
            }
            for i in range(50)
        ]
        conn.execute(text("""
            INSERT INTO pg_orders (order_id, customer_id, status, subtotal, discount, total_amount, order_date)
            VALUES (:order_id, :customer_id, :status, :subtotal, :discount, :total_amount, :order_date);
        """), orders_data)

        # Seed pg_order_items (50 rows)
        items_data = [
            {
                "item_id": 9001 + i,
                "order_id": 5001 + i,
                "product_id": 2001 + (i % 50),
                "quantity": (i % 3) + 1,
                "unit_price": round(49.99 + (i * 15.5), 2),
            }
            for i in range(50)
        ]
        conn.execute(text("""
            INSERT INTO pg_order_items (item_id, order_id, product_id, quantity, unit_price)
            VALUES (:item_id, :order_id, :product_id, :quantity, :unit_price);
        """), items_data)

        print("  [DATA OK] Seeded 4 tables x 50 records = 200 PostgreSQL records.")
    engine.dispose()


def setup_mysql():
    print("\n=======================================================")
    print(" >>> Setting up MySQL 'complex_mysql_db' (Port 3307)")
    print("=======================================================")
    engine = create_engine(MYSQL_DB_URL, connect_args={"connect_timeout": 5})

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS mysql_audit_logs;"))
        conn.execute(text("DROP TABLE IF EXISTS mysql_inventory;"))
        conn.execute(text("DROP TABLE IF EXISTS mysql_accounts;"))

        conn.execute(text("""
            CREATE TABLE mysql_accounts (
                account_id INT PRIMARY KEY AUTO_INCREMENT,
                email_address VARCHAR(255) NOT NULL,
                full_name VARCHAR(200) NOT NULL,
                company_name VARCHAR(150),
                credit_limit DECIMAL(12, 2) NOT NULL DEFAULT 5000.00,
                account_status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
                created_time DATETIME NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE mysql_inventory (
                inventory_id INT PRIMARY KEY AUTO_INCREMENT,
                product_sku VARCHAR(50) NOT NULL,
                warehouse_code VARCHAR(50) NOT NULL,
                stock_quantity INT NOT NULL,
                reorder_level INT NOT NULL,
                last_stock_check DATETIME NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE mysql_audit_logs (
                log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
                account_id INT NOT NULL,
                action_name VARCHAR(100) NOT NULL,
                ip_address VARCHAR(45) NOT NULL,
                executed_at DATETIME NOT NULL
            );
        """))
        print("  [DDL OK] MySQL schema created successfully.")

        # Seed mysql_accounts (50 rows) — uses exact email matches for 3-way consolidation test
        first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Sam", "Dakota", "Reese", "Quinn"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        base_time = datetime.now(timezone.utc) - timedelta(days=90)

        accounts_data = [
            {
                "email_address": f"user_{i+1}@omni-enterprise.com",
                "full_name": f"{first_names[i % len(first_names)]} {last_names[i % len(last_names)]}",
                "company_name": f"Enterprise Client Corp-{i+1}",
                "credit_limit": round(5000.0 + (i * 250.0), 2),
                "account_status": "ACTIVE" if i % 4 != 0 else "SUSPENDED",
                "created_time": (base_time + timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S"),
            }
            for i in range(50)
        ]
        conn.execute(text("""
            INSERT INTO mysql_accounts (email_address, full_name, company_name, credit_limit, account_status, created_time)
            VALUES (:email_address, :full_name, :company_name, :credit_limit, :account_status, :created_time);
        """), accounts_data)

        # Seed mysql_inventory (50 rows)
        inventory_data = [
            {
                "product_sku": f"SKU-PROD-{i+1:03d}",
                "warehouse_code": f"WH-US-NODE-{ (i % 5) + 1 }",
                "stock_quantity": 500 + (i * 15),
                "reorder_level": 50,
                "last_stock_check": (base_time + timedelta(days=i, hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            }
            for i in range(50)
        ]
        conn.execute(text("""
            INSERT INTO mysql_inventory (product_sku, warehouse_code, stock_quantity, reorder_level, last_stock_check)
            VALUES (:product_sku, :warehouse_code, :stock_quantity, :reorder_level, :last_stock_check);
        """), inventory_data)

        # Seed mysql_audit_logs (50 rows)
        actions = ["USER_LOGIN", "UPDATE_PROFILE", "EXPORT_REPORT", "PAYMENT_INITIATED", "PASSWORD_CHANGE"]
        logs_data = [
            {
                "account_id": (i % 50) + 1,
                "action_name": actions[i % len(actions)],
                "ip_address": f"192.168.1.{10+i}",
                "executed_at": (base_time + timedelta(days=i, hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
            }
            for i in range(50)
        ]
        conn.execute(text("""
            INSERT INTO mysql_audit_logs (account_id, action_name, ip_address, executed_at)
            VALUES (:account_id, :action_name, :ip_address, :executed_at);
        """), logs_data)

        print("  [DATA OK] Seeded 3 tables x 50 records = 150 MySQL records.")
    engine.dispose()


def setup_mongodb():
    print("\n=======================================================")
    print(" >>> Setting up MongoDB 'complex_mongo_db' (Port 27017)")
    print("=======================================================")
    import pymongo

    client = pymongo.MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    db = client["complex_mongo_db"]

    # Drop existing collections
    db["user_profiles"].drop()
    db["events_stream"].drop()
    db["product_reviews_nosql"].drop()

    # 1. Seed user_profiles (50 docs with Depth = 3 nesting)
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]
    genders = ["Male", "Female", "Non-Binary", "Prefer Not To Say"]

    profiles_docs = []
    base_time = datetime.now(timezone.utc) - timedelta(days=80)

    for i in range(50):
        profiles_docs.append({
            "contact_email": f"user_{i+1}@omni-enterprise.com",
            "personal_info": {  # Depth 1
                "gender": genders[i % len(genders)],
                "birthdate": f"198{i % 10}-0{ (i % 9) + 1 }-15",
                "contact": {  # Depth 2
                    "mobile": f"+1-555-99{i+1:02d}",
                    "location": {  # Depth 3 (Tests json_flatten at Depth 3)
                        "city": cities[i % len(cities)],
                        "country": "USA",
                        "postal_code": f"100{i+1:02d}",
                    }
                }
            },
            "preferences": {
                "newsletter": (i % 2 == 0),
                "theme": "dark" if i % 2 == 0 else "light",
            },
            "tags": ["vip", "early_adopter", f"region_0{ (i % 4) + 1 }"],  # Tests array_to_csv
            "device_history": [  # Tests json_stringify
                {"device_id": f"DEV-MAC-{i+1:03d}", "os": "macOS 14", "last_active": base_time.isoformat()},
                {"device_id": f"DEV-IOS-{i+1:03d}", "os": "iOS 17", "last_active": base_time.isoformat()},
            ],
            "updated_at": base_time.isoformat(),
        })
    db["user_profiles"].insert_many(profiles_docs)

    # 2. Seed events_stream (50 docs)
    event_names = ["PAGE_VIEW", "SEARCH", "ADD_TO_CART", "CHECKOUT_INIT", "PAYMENT_SUCCESS"]
    events_docs = [
        {
            "event_id": f"EVT-OMNI-{i+1:03d}",
            "event_name": event_names[i % len(event_names)],
            "user_email": f"user_{i+1}@omni-enterprise.com",
            "session_attributes": {
                "ip": f"10.0.0.{i+1}",
                "user_agent": "Mozilla/5.0 Chrome/120.0",
                "duration_seconds": (i + 1) * 18,
            },
            "payload_json": {"query": f"enterprise product {i+1}", "results_count": i + 5},
            "timestamp": (base_time + timedelta(days=i, hours=1)).isoformat(),
        }
        for i in range(50)
    ]
    db["events_stream"].insert_many(events_docs)

    # 3. Seed product_reviews_nosql (50 docs)
    reviews_docs = [
        {
            "sku": f"SKU-PROD-{i+1:03d}",
            "reviewer_email": f"user_{i+1}@omni-enterprise.com",
            "rating": (i % 5) + 1,
            "review_text": f"Verified customer assessment score {(i%5)+1}/5 stars for product SKU-PROD-{i+1:03d}.",
            "verified_buyer": True,  # Tests nosql_field_promote
            "created_at": (base_time + timedelta(days=i, hours=3)).isoformat(),
        }
        for i in range(50)
    ]
    db["product_reviews_nosql"].insert_many(reviews_docs)

    client.close()
    print("  [DATA OK] Seeded 3 collections x 50 docs = 150 MongoDB documents.")


def main():
    print("================================================================================")
    print(" >>> SEEDING COMPLEX MULTI-DATABASE ENTERPRISE MIGRATION SCENARIO")
    print("     PostgreSQL (Port 5435): complex_pg_db   - 4 Tables, 200 Rows")
    print("     MySQL      (Port 3307): complex_mysql_db- 3 Tables, 150 Rows")
    print("     MongoDB    (Port 27017):complex_mongo_db- 3 Collections (Depth 3), 150 Docs")
    print("================================================================================")

    wait_for_postgres()
    wait_for_mysql()

    setup_postgresql()
    setup_mysql()
    setup_mongodb()

    print("\n================================================================================")
    print(" [SUCCESS] COMPLEX MULTI-DATABASE SETUP COMPLETE!")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
