"""
Production Database Seeder
Populates 1,000 production-grade records per table/collection across 3 databases of a unified E-Commerce Enterprise Platform:
1. PostgreSQL (Port 5435, DB: ecommerce_production): 5 tables x 1,000 rows = 5,000 rows
2. MySQL      (Port 3307, DB: inventory_production): 5 tables x 1,000 rows = 5,000 rows
3. MongoDB    (Port 27017, DB: analytics_production): 4 collections x 1,000 docs = 4,000 docs
Total Seed Data Volume: 14,000 production records.
"""

import time
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Connection URLs
# ---------------------------------------------------------------------------
PG_ADMIN_URL = "postgresql://postgres:postgres_password@127.0.0.1:5435/postgres"
PG_DB_URL = "postgresql://postgres:postgres_password@127.0.0.1:5435/ecommerce_production"

MYSQL_ADMIN_URL = "mysql+pymysql://root:mysql_password@127.0.0.1:3307/"
MYSQL_DB_URL = "mysql+pymysql://root:mysql_password@127.0.0.1:3307/inventory_production"

MONGO_URL = "mongodb://127.0.0.1:27017"

# ---------------------------------------------------------------------------
# Helper: Wait and Ensure Databases Exist
# ---------------------------------------------------------------------------
def ensure_databases_exist():
    print(">>> Ensuring PostgreSQL target database 'ecommerce_production' exists on port 5435...")
    for attempt in range(1, 15):
        try:
            engine = create_engine(PG_ADMIN_URL, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
            with engine.connect() as conn:
                res = conn.execute(text("SELECT 1 FROM pg_database WHERE datname='ecommerce_production'"))
                if not res.scalar():
                    conn.execute(text('CREATE DATABASE ecommerce_production'))
                    print("  [OK] Created PostgreSQL database 'ecommerce_production'.")
                else:
                    print("  [OK] PostgreSQL database 'ecommerce_production' verified.")
            break
        except Exception as e:
            print(f"  [Attempt {attempt}/15] Waiting for PostgreSQL (5435)... ({e})")
            time.sleep(2)

    print("\n>>> Ensuring MySQL target database 'inventory_production' exists on port 3307...")
    for attempt in range(1, 15):
        try:
            engine = create_engine(MYSQL_ADMIN_URL, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
            with engine.connect() as conn:
                conn.execute(text("CREATE DATABASE IF NOT EXISTS inventory_production"))
                print("  [OK] Created/verified MySQL database 'inventory_production'.")
            break
        except Exception as e:
            print(f"  [Attempt {attempt}/15] Waiting for MySQL (3307)... ({e})")
            time.sleep(2)


# ---------------------------------------------------------------------------
# Seed PostgreSQL: ecommerce_production (5 Tables x 1,000 rows)
# ---------------------------------------------------------------------------
def seed_postgres_ecommerce():
    print("\n================================================================================")
    print(" >>> SEEDING POSTGRESQL DATABASE: ecommerce_production (Port 5435)")
    print("================================================================================")

    engine = create_engine(PG_DB_URL, connect_args={"connect_timeout": 5})

    with engine.begin() as conn:
        conn.execute(text("""
            DROP TABLE IF EXISTS order_items CASCADE;
            DROP TABLE IF EXISTS orders CASCADE;
            DROP TABLE IF EXISTS products CASCADE;
            DROP TABLE IF EXISTS categories CASCADE;
            DROP TABLE IF EXISTS customers CASCADE;
        """))

        conn.execute(text("""
            CREATE TABLE customers (
                customer_id INT PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                phone VARCHAR(50),
                account_status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE categories (
                category_id INT PRIMARY KEY,
                category_name VARCHAR(100) NOT NULL,
                slug VARCHAR(120) UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE products (
                product_id INT PRIMARY KEY,
                category_id INT REFERENCES categories(category_id),
                sku VARCHAR(50) UNIQUE NOT NULL,
                product_name VARCHAR(200) NOT NULL,
                price NUMERIC(10, 2) NOT NULL,
                cost_price NUMERIC(10, 2) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE orders (
                order_id INT PRIMARY KEY,
                customer_id INT REFERENCES customers(customer_id),
                order_status VARCHAR(50) NOT NULL,
                total_amount NUMERIC(10, 2) NOT NULL,
                currency VARCHAR(10) NOT NULL DEFAULT 'USD',
                order_date TIMESTAMP WITH TIME ZONE NOT NULL
            );

            CREATE TABLE order_items (
                item_id INT PRIMARY KEY,
                order_id INT REFERENCES orders(order_id),
                product_id INT REFERENCES products(product_id),
                quantity INT NOT NULL,
                unit_price NUMERIC(10, 2) NOT NULL,
                subtotal NUMERIC(10, 2) NOT NULL
            );
        """))
        print("  [OK] DDL Created for 5 PostgreSQL tables.")

        base_time = datetime.now(timezone.utc) - timedelta(days=365)
        first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Sam", "Dakota", "Reese", "Quinn", "Chris", "Pat", "Avery", "Peyton", "Skyler"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson"]
        statuses = ["ACTIVE", "VERIFIED", "PREMIUM", "SUSPENDED"]

        # 1. Customers (1,000)
        cust_data = [
            {
                "customer_id": 1000 + i,
                "email": f"customer_{i+1:04d}@global-retail.com",
                "first_name": first_names[i % len(first_names)],
                "last_name": last_names[(i * 3) % len(last_names)],
                "phone": f"+1-555-{100 + (i % 900):03d}-{1000 + (i % 9000):04d}",
                "account_status": statuses[i % len(statuses)],
                "created_at": base_time + timedelta(hours=i * 8)
            }
            for i in range(1000)
        ]
        conn.execute(text("INSERT INTO customers (customer_id, email, first_name, last_name, phone, account_status, created_at) VALUES (:customer_id, :email, :first_name, :last_name, :phone, :account_status, :created_at)"), cust_data)
        print("  [OK] Seeded customers: 1,000 rows.")

        # 2. Categories (1,000)
        cat_data = [
            {
                "category_id": 100 + i,
                "category_name": f"Enterprise Category Domain {i+1}",
                "slug": f"enterprise-category-domain-{i+1}",
                "description": f"High performance specification for category group #{i+1}",
                "created_at": base_time + timedelta(days=i % 30)
            }
            for i in range(1000)
        ]
        conn.execute(text("INSERT INTO categories (category_id, category_name, slug, description, created_at) VALUES (:category_id, :category_name, :slug, :description, :created_at)"), cat_data)
        print("  [OK] Seeded categories: 1,000 rows.")

        # 3. Products (1,000)
        prod_data = [
            {
                "product_id": 5000 + i,
                "category_id": 100 + (i % 1000),
                "sku": f"SKU-PROD-{i+1:04d}",
                "product_name": f"Enterprise Grade Hardware SKU-{i+1:04d}",
                "price": round(19.99 + (i * 2.75), 2),
                "cost_price": round(9.99 + (i * 1.50), 2),
                "created_at": base_time + timedelta(hours=i * 4)
            }
            for i in range(1000)
        ]
        conn.execute(text("INSERT INTO products (product_id, category_id, sku, product_name, price, cost_price, created_at) VALUES (:product_id, :category_id, :sku, :product_name, :price, :cost_price, :created_at)"), prod_data)
        print("  [OK] Seeded products: 1,000 rows.")

        # 4. Orders (1,000)
        order_statuses = ["COMPLETED", "SHIPPED", "PROCESSING", "PENDING", "DELIVERED"]
        order_data = [
            {
                "order_id": 10000 + i,
                "customer_id": 1000 + (i % 1000),
                "order_status": order_statuses[i % len(order_statuses)],
                "total_amount": round(49.99 + (i * 5.25), 2),
                "currency": "USD",
                "order_date": base_time + timedelta(hours=i * 6)
            }
            for i in range(1000)
        ]
        conn.execute(text("INSERT INTO orders (order_id, customer_id, order_status, total_amount, currency, order_date) VALUES (:order_id, :customer_id, :order_status, :total_amount, :currency, :order_date)"), order_data)
        print("  [OK] Seeded orders: 1,000 rows.")

        # 5. Order Items (1,000)
        item_data = [
            {
                "item_id": 50000 + i,
                "order_id": 10000 + (i % 1000),
                "product_id": 5000 + (i % 1000),
                "quantity": (i % 5) + 1,
                "unit_price": round(19.99 + ((i % 1000) * 2.75), 2),
                "subtotal": round(((i % 5) + 1) * (19.99 + ((i % 1000) * 2.75)), 2)
            }
            for i in range(1000)
        ]
        conn.execute(text("INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price, subtotal) VALUES (:item_id, :order_id, :product_id, :quantity, :unit_price, :subtotal)"), item_data)
        print("  [OK] Seeded order_items: 1,000 rows.")

    print("  [SUCCESS] PostgreSQL ecommerce_production seeded with 5,000 total records.")


# ---------------------------------------------------------------------------
# Seed MySQL: inventory_production (5 Tables x 1,000 rows)
# ---------------------------------------------------------------------------
def seed_mysql_inventory():
    print("\n================================================================================")
    print(" >>> SEEDING MYSQL DATABASE: inventory_production (Port 3307)")
    print("================================================================================")

    engine = create_engine(MYSQL_DB_URL, connect_args={"connect_timeout": 5})

    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        conn.execute(text("DROP TABLE IF EXISTS stock_movements;"))
        conn.execute(text("DROP TABLE IF EXISTS shipments;"))
        conn.execute(text("DROP TABLE IF EXISTS inventory_items;"))
        conn.execute(text("DROP TABLE IF EXISTS warehouses;"))
        conn.execute(text("DROP TABLE IF EXISTS suppliers;"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

        conn.execute(text("""
            CREATE TABLE suppliers (
                supplier_id INT PRIMARY KEY,
                company_name VARCHAR(150) NOT NULL,
                contact_email VARCHAR(255) NOT NULL,
                phone VARCHAR(50),
                country VARCHAR(100) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """))

        conn.execute(text("""
            CREATE TABLE warehouses (
                warehouse_id INT PRIMARY KEY,
                warehouse_code VARCHAR(50) UNIQUE NOT NULL,
                location_name VARCHAR(150) NOT NULL,
                capacity INT NOT NULL,
                city VARCHAR(100) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """))

        conn.execute(text("""
            CREATE TABLE inventory_items (
                inventory_id INT PRIMARY KEY,
                warehouse_id INT,
                supplier_id INT,
                sku VARCHAR(50) NOT NULL,
                quantity_on_hand INT NOT NULL,
                reorder_level INT NOT NULL DEFAULT 50,
                last_restocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
            );
        """))

        conn.execute(text("""
            CREATE TABLE shipments (
                shipment_id INT PRIMARY KEY,
                warehouse_id INT,
                carrier VARCHAR(100) NOT NULL,
                tracking_number VARCHAR(100) UNIQUE NOT NULL,
                shipment_status VARCHAR(50) NOT NULL,
                shipped_at DATETIME NOT NULL,
                FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id)
            );
        """))

        conn.execute(text("""
            CREATE TABLE stock_movements (
                movement_id INT PRIMARY KEY,
                inventory_id INT,
                movement_type VARCHAR(50) NOT NULL,
                quantity_change INT NOT NULL,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (inventory_id) REFERENCES inventory_items(inventory_id)
            );
        """))
        print("  [OK] DDL Created for 5 MySQL tables.")

        base_time = datetime.now() - timedelta(days=365)
        countries = ["USA", "Germany", "Japan", "United Kingdom", "Canada", "Singapore", "Australia", "Netherlands", "France", "South Korea"]
        cities = ["Seattle", "Hamburg", "Tokyo", "London", "Toronto", "Singapore", "Sydney", "Amsterdam", "Paris", "Seoul"]
        carriers = ["FedEx Express", "DHL Supply Chain", "UPS Freight", "Amazon Logistics", "Maersk Line"]

        # 1. Suppliers (1,000)
        sup_data = [
            {
                "supplier_id": 2000 + i,
                "company_name": f"Global Supply Component Vendor #{i+1:04d}",
                "contact_email": f"supplier_{i+1:04d}@supplychain-network.com",
                "phone": f"+1-800-{100 + (i % 900):03d}-{1000 + (i % 9000):04d}",
                "country": countries[i % len(countries)],
                "created_at": base_time + timedelta(hours=i * 6)
            }
            for i in range(1000)
        ]
        conn.execute(text("INSERT INTO suppliers (supplier_id, company_name, contact_email, phone, country, created_at) VALUES (:supplier_id, :company_name, :contact_email, :phone, :country, :created_at)"), sup_data)
        print("  [OK] Seeded suppliers: 1,000 rows.")

        # 2. Warehouses (1,000)
        wh_data = [
            {
                "warehouse_id": 3000 + i,
                "warehouse_code": f"WH-NODE-{i+1:04d}",
                "location_name": f"Fulfillment Center Logistics Node #{i+1}",
                "capacity": 50000 + (i * 500),
                "city": cities[i % len(cities)],
                "created_at": base_time + timedelta(hours=i * 4)
            }
            for i in range(1000)
        ]
        conn.execute(text("INSERT INTO warehouses (warehouse_id, warehouse_code, location_name, capacity, city, created_at) VALUES (:warehouse_id, :warehouse_code, :location_name, :capacity, :city, :created_at)"), wh_data)
        print("  [OK] Seeded warehouses: 1,000 rows.")

        # 3. Inventory Items (1,000)
        inv_data = [
            {
                "inventory_id": 8000 + i,
                "warehouse_id": 3000 + (i % 1000),
                "supplier_id": 2000 + (i % 1000),
                "sku": f"SKU-PROD-{i+1:04d}",
                "quantity_on_hand": 100 + (i * 5),
                "reorder_level": 50,
                "last_restocked_at": base_time + timedelta(hours=i * 5)
            }
            for i in range(1000)
        ]
        conn.execute(text("INSERT INTO inventory_items (inventory_id, warehouse_id, supplier_id, sku, quantity_on_hand, reorder_level, last_restocked_at) VALUES (:inventory_id, :warehouse_id, :supplier_id, :sku, :quantity_on_hand, :reorder_level, :last_restocked_at)"), inv_data)
        print("  [OK] Seeded inventory_items: 1,000 rows.")

        # 4. Shipments (1,000)
        shipment_statuses = ["DELIVERED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DISPATCHED", "PENDING"]
        ship_data = [
            {
                "shipment_id": 15000 + i,
                "warehouse_id": 3000 + (i % 1000),
                "carrier": carriers[i % len(carriers)],
                "tracking_number": f"TRK-SYS-{i+1:04d}-{random.randint(1000, 9999)}",
                "shipment_status": shipment_statuses[i % len(shipment_statuses)],
                "shipped_at": base_time + timedelta(hours=i * 7)
            }
            for i in range(1000)
        ]
        conn.execute(text("INSERT INTO shipments (shipment_id, warehouse_id, carrier, tracking_number, shipment_status, shipped_at) VALUES (:shipment_id, :warehouse_id, :carrier, :tracking_number, :shipment_status, :shipped_at)"), ship_data)
        print("  [OK] Seeded shipments: 1,000 rows.")

        # 5. Stock Movements (1,000)
        move_types = ["RESTOCK", "INBOUND_SHIPMENT", "DISPATCH_ORDER", "CYCLE_COUNT_ADJUSTMENT"]
        move_data = [
            {
                "movement_id": 70000 + i,
                "inventory_id": 8000 + (i % 1000),
                "movement_type": move_types[i % len(move_types)],
                "quantity_change": (i % 20) + 1 if i % 2 == 0 else -((i % 15) + 1),
                "notes": f"Recorded inventory stock movement operation audit log entry #{i+1}",
                "created_at": base_time + timedelta(hours=i * 3)
            }
            for i in range(1000)
        ]
        conn.execute(text("INSERT INTO stock_movements (movement_id, inventory_id, movement_type, quantity_change, notes, created_at) VALUES (:movement_id, :inventory_id, :movement_type, :quantity_change, :notes, :created_at)"), move_data)
        print("  [OK] Seeded stock_movements: 1,000 rows.")

    print("  [SUCCESS] MySQL inventory_production seeded with 5,000 total records.")


# ---------------------------------------------------------------------------
# Seed MongoDB: analytics_production (4 Collections x 1,000 docs)
# ---------------------------------------------------------------------------
def seed_mongo_analytics():
    print("\n================================================================================")
    print(" >>> SEEDING MONGODB DOCUMENT STORE: analytics_production (Port 27017)")
    print("================================================================================")

    import pymongo
    client = pymongo.MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client["analytics_production"]

    # Drop existing collections
    db["clickstream_events"].drop()
    db["user_search_logs"].drop()
    db["product_view_metrics"].drop()
    db["session_summaries"].drop()

    base_time = datetime.now(timezone.utc) - timedelta(days=365)
    event_types = ["PAGE_VIEW", "CLICK", "ADD_TO_CART", "SEARCH_QUERY", "CHECKOUT_INITIATED", "PURCHASE"]
    browsers = ["Chrome 122.0", "Safari 17.3", "Firefox 123.0", "Edge 122.0"]
    os_list = ["macOS Sonoma", "Windows 11", "iOS 17.2", "Android 14"]

    # 1. Clickstream Events (1,000 docs)
    events_docs = [
        {
            "event_id": f"EVT-TELEMETRY-{i+1:04d}",
            "event_type": event_types[i % len(event_types)],
            "user_email": f"customer_{1000 + (i % 1000):04d}@global-retail.com",
            "session_id": f"SESS-GUID-{i+1:04d}",
            "device_info": {
                "os": os_list[i % len(os_list)],
                "browser": browsers[i % len(browsers)],
                "ip": f"192.168.1.{1 + (i % 254)}"
            },
            "timestamp": (base_time + timedelta(minutes=i * 15)).isoformat()
        }
        for i in range(1000)
    ]
    db["clickstream_events"].insert_many(events_docs)
    print("  [OK] Seeded clickstream_events: 1,000 documents.")

    # 2. User Search Logs (1,000 docs)
    queries = ["enterprise laptop", "wireless noise canceling headphones", "4k monitor", "mechanical keyboard", "ergonomic chair", "smart watch", "usb-c dock"]
    search_docs = [
        {
            "search_id": f"SRCH-LOG-{i+1:04d}",
            "user_email": f"customer_{1000 + (i % 1000):04d}@global-retail.com",
            "query_text": queries[i % len(queries)],
            "results_count": 15 + (i % 50),
            "clicked_sku": f"SKU-PROD-{(i % 1000) + 1:04d}",
            "session_id": f"SESS-GUID-{i+1:04d}",
            "timestamp": (base_time + timedelta(minutes=i * 20)).isoformat()
        }
        for i in range(1000)
    ]
    db["user_search_logs"].insert_many(search_docs)
    print("  [OK] Seeded user_search_logs: 1,000 documents.")

    # 3. Product View Metrics (1,000 docs)
    metrics_docs = [
        {
            "sku": f"SKU-PROD-{i+1:04d}",
            "category_name": f"Enterprise Category Domain {(i % 1000) + 1}",
            "view_count": 500 + (i * 12),
            "unique_viewers": 300 + (i * 8),
            "conversion_rate": round(2.5 + ((i % 10) * 0.4), 2),
            "last_viewed_at": (base_time + timedelta(hours=i * 4)).isoformat()
        }
        for i in range(1000)
    ]
    db["product_view_metrics"].insert_many(metrics_docs)
    print("  [OK] Seeded product_view_metrics: 1,000 documents.")

    # 4. Session Summaries (1,000 docs)
    session_docs = [
        {
            "session_id": f"SESS-GUID-{i+1:04d}",
            "user_email": f"customer_{1000 + (i % 1000):04d}@global-retail.com",
            "start_time": (base_time + timedelta(hours=i * 2)).isoformat(),
            "end_time": (base_time + timedelta(hours=i * 2, minutes=25)).isoformat(),
            "page_count": (i % 15) + 1,
            "device_type": os_list[i % len(os_list)],
            "is_converted": (i % 3 == 0)
        }
        for i in range(1000)
    ]
    db["session_summaries"].insert_many(session_docs)
    print("  [OK] Seeded session_summaries: 1,000 documents.")

    client.close()
    print("  [SUCCESS] MongoDB analytics_production seeded with 4,000 total documents.")


# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
def main():
    print("================================================================================")
    print(" >>> ENTERPRISE PRODUCTION MULTI-DATABASE SEEDER")
    print("     PostgreSQL (Port 5435): ecommerce_production - 5 Tables x 1,000 Rows = 5,000 Rows")
    print("     MySQL      (Port 3307): inventory_production - 5 Tables x 1,000 Rows = 5,000 Rows")
    print("     MongoDB    (Port 27017): analytics_production - 4 Collections x 1,000 Docs = 4,000 Docs")
    print("================================================================================\n")

    ensure_databases_exist()
    seed_postgres_ecommerce()
    seed_mysql_inventory()
    seed_mongo_analytics()

    print("\n================================================================================")
    print(" [SUCCESS] PRODUCTION ENTERPRISE MULTI-DATABASE SEEDING COMPLETE!")
    print(" Total Production Seed Records Created: 14,000 records across 14 tables/collections.")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
