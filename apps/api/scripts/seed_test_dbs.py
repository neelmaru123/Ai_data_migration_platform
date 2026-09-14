"""
Seed Test Databases Script
Initializes schemas and populates 50 records per table across 2 PostgreSQL source databases:
1. ecommerce_db (Port 5435) - 5 interconnected tables (categories, products, customers, orders, order_items)
2. crm_db (Port 5436) - 5 interconnected tables (support_agents, leads, tickets, interactions, product_reviews)
"""

import os
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text


ECOMMERCE_DB_URL = "postgresql://postgres:postgres_password@127.0.0.1:5435/ecommerce_db"
CRM_DB_URL = "postgresql://postgres:postgres_password@127.0.0.1:5436/crm_db"
MYSQL_DB_URL = "mysql+pymysql://root:mysql_password@127.0.0.1:3307/inventory_db"
MONGO_DB_URL = "mongodb://127.0.0.1:27017"


def ensure_postgres_db_exists(port: int, db_name: str):
    admin_url = f"postgresql://postgres:postgres_password@127.0.0.1:{port}/postgres"
    try:
        engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            res = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"))
            if not res.scalar():
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                print(f" [OK] Created PostgreSQL database '{db_name}' on port {port}.")
    except Exception as e:
        print(f" [Notice] PostgreSQL admin check on port {port}: {e}")


def ensure_mysql_db_exists(db_name: str):
    admin_url = "mysql+pymysql://root:mysql_password@127.0.0.1:3307/"
    try:
        engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
            print(f" [OK] Created/verified MySQL database '{db_name}' on port 3307.")
    except Exception as e:
        print(f" [Notice] MySQL admin check: {e}")


def wait_for_db(db_url: str, db_name: str, max_retries: int = 15):
    print(f"Connecting to {db_name}...")
    for attempt in range(1, max_retries + 1):
        try:
            engine = create_engine(db_url, connect_args={"connect_timeout": 2})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
            print(f" [OK] Successfully connected to {db_name}!")
            return engine
        except Exception as e:
            print(f" [Attempt {attempt}/{max_retries}] Waiting for {db_name} to be ready ({e})...")
            time.sleep(2)
    raise RuntimeError(f"Could not connect to {db_name} after {max_retries} attempts.")


def setup_ecommerce_db(engine):
    print("\n--- Setting up ecommerce_db Schema & Data (Port 5435) ---")
    with engine.begin() as conn:
        conn.execute(text("""
            DROP TABLE IF EXISTS order_items CASCADE;
            DROP TABLE IF EXISTS orders CASCADE;
            DROP TABLE IF EXISTS products CASCADE;
            DROP TABLE IF EXISTS categories CASCADE;
            DROP TABLE IF EXISTS customers CASCADE;
        """))

        conn.execute(text("""
            CREATE TABLE categories (
                category_id INT PRIMARY KEY,
                category_name VARCHAR(100) NOT NULL,
                description TEXT
            );

            CREATE TABLE products (
                product_id INT PRIMARY KEY,
                category_id INT REFERENCES categories(category_id),
                sku VARCHAR(50) UNIQUE NOT NULL,
                product_name VARCHAR(200) NOT NULL,
                price NUMERIC(10, 2) NOT NULL
            );

            CREATE TABLE customers (
                customer_id INT PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                phone VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE orders (
                order_id INT PRIMARY KEY,
                customer_id INT REFERENCES customers(customer_id),
                order_status VARCHAR(50) NOT NULL,
                order_date TIMESTAMP WITH TIME ZONE NOT NULL,
                total_amount NUMERIC(10, 2) NOT NULL
            );

            CREATE TABLE order_items (
                item_id INT PRIMARY KEY,
                order_id INT REFERENCES orders(order_id),
                product_id INT REFERENCES products(product_id),
                quantity INT NOT NULL,
                unit_price NUMERIC(10, 2) NOT NULL
            );
        """))
        print("  [OK] ecommerce_db DDL created successfully.")

        category_names = [
            "Electronics", "Computers", "Smartphones", "Audio", "Cameras",
            "Home Appliances", "Kitchenware", "Furniture", "Lighting", "Bedding",
            "Men's Clothing", "Women's Clothing", "Footwear", "Sportswear", "Jewelry",
            "Fitness", "Outdoor Gear", "Cycling", "Camping", "Water Sports",
            "Toys", "Board Games", "Video Games", "Books", "Stationery",
            "Beauty", "Skincare", "Haircare", "Fragrances", "Personal Care",
            "Automotive", "Tools", "Garden", "Pet Supplies", "Groceries",
            "Beverages", "Snacks", "Health", "Vitamins", "Baby Products",
            "Luggage", "Watches", "Office Supplies", "Crafts", "Musical Instruments",
            "Software", "Collectibles", "Art", "Smart Home", "Accessories"
        ]
        categories_data = [
            {"category_id": i + 1, "category_name": category_names[i], "description": f"Quality {category_names[i].lower()} products"}
            for i in range(50)
        ]
        conn.execute(text("INSERT INTO categories (category_id, category_name, description) VALUES (:category_id, :category_name, :description);"), categories_data)

        products_data = [
            {
                "product_id": 101 + i,
                "category_id": (i % 50) + 1,
                "sku": f"SKU-10{i+1:02d}",
                "product_name": f"Enterprise Product Grade-{i+1}",
                "price": round(29.99 + (i * 12.5), 2)
            }
            for i in range(50)
        ]
        conn.execute(text("INSERT INTO products (product_id, category_id, sku, product_name, price) VALUES (:product_id, :category_id, :sku, :product_name, :price);"), products_data)

        first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Sam", "Dakota", "Reese", "Quinn"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        base_time = datetime.now(timezone.utc) - timedelta(days=100)
        customers_data = [
            {
                "customer_id": 1001 + i,
                "email": f"client_{i+1}@enterprise-test.com",
                "first_name": first_names[i % len(first_names)],
                "last_name": last_names[i % len(last_names)],
                "phone": f"+1-555-01{i+1:02d}",
                "created_at": base_time + timedelta(days=i)
            }
            for i in range(50)
        ]
        conn.execute(text("INSERT INTO customers (customer_id, email, first_name, last_name, phone, created_at) VALUES (:customer_id, :email, :first_name, :last_name, :phone, :created_at);"), customers_data)

        statuses = ["COMPLETED", "SHIPPED", "PENDING", "PROCESSING"]
        orders_data = [
            {
                "order_id": 5001 + i,
                "customer_id": 1001 + (i % 50),
                "order_status": statuses[i % len(statuses)],
                "order_date": base_time + timedelta(days=i, hours=2),
                "total_amount": round(50.0 + (i * 25.5), 2)
            }
            for i in range(50)
        ]
        conn.execute(text("INSERT INTO orders (order_id, customer_id, order_status, order_date, total_amount) VALUES (:order_id, :customer_id, :order_status, :order_date, :total_amount);"), orders_data)

        items_data = [
            {
                "item_id": 10001 + i,
                "order_id": 5001 + i,
                "product_id": 101 + (i % 50),
                "quantity": (i % 4) + 1,
                "unit_price": round(29.99 + (i * 12.5), 2)
            }
            for i in range(50)
        ]
        conn.execute(text("INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price) VALUES (:item_id, :order_id, :product_id, :quantity, :unit_price);"), items_data)

    print("  [OK] ecommerce_db seeded 5 tables x 50 records = 250 records.")


def setup_crm_db(engine):
    print("\n--- Setting up crm_db Schema & Data (Port 5436) ---")
    with engine.begin() as conn:
        conn.execute(text("""
            DROP TABLE IF EXISTS product_reviews CASCADE;
            DROP TABLE IF EXISTS interactions CASCADE;
            DROP TABLE IF EXISTS tickets CASCADE;
            DROP TABLE IF EXISTS leads CASCADE;
            DROP TABLE IF EXISTS support_agents CASCADE;
        """))

        conn.execute(text("""
            CREATE TABLE support_agents (
                agent_id INT PRIMARY KEY,
                agent_name VARCHAR(150) NOT NULL,
                email VARCHAR(255) NOT NULL,
                department VARCHAR(100) NOT NULL
            );

            CREATE TABLE leads (
                lead_id INT PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                full_name VARCHAR(200) NOT NULL,
                company VARCHAR(150),
                lead_source VARCHAR(100),
                status VARCHAR(50) NOT NULL
            );

            CREATE TABLE tickets (
                ticket_id INT PRIMARY KEY,
                customer_email VARCHAR(255) REFERENCES leads(email),
                assigned_agent_id INT REFERENCES support_agents(agent_id),
                subject VARCHAR(255) NOT NULL,
                priority VARCHAR(20) NOT NULL,
                status VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE interactions (
                interaction_id INT PRIMARY KEY,
                ticket_id INT REFERENCES tickets(ticket_id),
                channel VARCHAR(50) NOT NULL,
                notes TEXT NOT NULL,
                interaction_date TIMESTAMP WITH TIME ZONE NOT NULL
            );

            CREATE TABLE product_reviews (
                review_id INT PRIMARY KEY,
                product_sku VARCHAR(50) NOT NULL,
                reviewer_email VARCHAR(255) NOT NULL,
                rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
                review_text TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """))
        print("  [OK] crm_db DDL created successfully.")

        depts = ["Tier 1 Support", "Tier 2 Technical", "Billing & Claims", "Customer Success", "Enterprise Accounts"]
        agents_data = [
            {
                "agent_id": i + 1,
                "agent_name": f"Agent Specialist-{i+1}",
                "email": f"agent_{i+1}@crm-support.com",
                "department": depts[i % len(depts)]
            }
            for i in range(50)
        ]
        conn.execute(text("INSERT INTO support_agents (agent_id, agent_name, email, department) VALUES (:agent_id, :agent_name, :email, :department);"), agents_data)

        first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Sam", "Dakota", "Reese", "Quinn"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        sources = ["ORGANIC_WEB", "INBOUND_CALL", "PARTNER_REFERRAL", "CAMPAIGN_EMAIL", "LINKEDIN"]
        lead_statuses = ["QUALIFIED", "NEW", "CONTACTED", "CONVERTED", "PROSPECT"]
        leads_data = [
            {
                "lead_id": 2001 + i,
                "email": f"client_{i+1}@enterprise-test.com",
                "full_name": f"{first_names[i % len(first_names)]} {last_names[i % len(last_names)]}",
                "company": f"Company Global Corp-{i+1}",
                "lead_source": sources[i % len(sources)],
                "status": lead_statuses[i % len(lead_statuses)]
            }
            for i in range(50)
        ]
        conn.execute(text("INSERT INTO leads (lead_id, email, full_name, company, lead_source, status) VALUES (:lead_id, :email, :full_name, :company, :lead_source, :status);"), leads_data)

        base_time = datetime.now(timezone.utc) - timedelta(days=90)
        priorities = ["HIGH", "MEDIUM", "LOW", "URGENT"]
        ticket_statuses = ["RESOLVED", "OPEN", "IN_PROGRESS", "CLOSED"]
        tickets_data = [
            {
                "ticket_id": 8001 + i,
                "customer_email": f"client_{i+1}@enterprise-test.com",
                "assigned_agent_id": (i % 50) + 1,
                "subject": f"Inquiry regard account service level #{i+1}",
                "priority": priorities[i % len(priorities)],
                "status": ticket_statuses[i % len(ticket_statuses)],
                "created_at": base_time + timedelta(days=i)
            }
            for i in range(50)
        ]
        conn.execute(text("INSERT INTO tickets (ticket_id, customer_email, assigned_agent_id, subject, priority, status, created_at) VALUES (:ticket_id, :customer_email, :assigned_agent_id, :subject, :priority, :status, :created_at);"), tickets_data)

        channels = ["EMAIL", "PHONE", "LIVE_CHAT", "PORTAL"]
        interactions_data = [
            {
                "interaction_id": 12001 + i,
                "ticket_id": 8001 + i,
                "channel": channels[i % len(channels)],
                "notes": f"Recorded customer communication log entry for ticket #{8001+i}",
                "interaction_date": base_time + timedelta(days=i, hours=3)
            }
            for i in range(50)
        ]
        conn.execute(text("INSERT INTO interactions (interaction_id, ticket_id, channel, notes, interaction_date) VALUES (:interaction_id, :ticket_id, :channel, :notes, :interaction_date);"), interactions_data)

        reviews_data = [
            {
                "review_id": 15001 + i,
                "product_sku": f"SKU-10{i+1:02d}",
                "reviewer_email": f"client_{i+1}@enterprise-test.com",
                "rating": (i % 5) + 1,
                "review_text": f"Verified buyer evaluation rating {(i%5)+1}/5 stars for product SKU-10{i+1:02d}.",
                "created_at": base_time + timedelta(days=i)
            }
            for i in range(50)
        ]
        conn.execute(text("INSERT INTO product_reviews (review_id, product_sku, reviewer_email, rating, review_text, created_at) VALUES (:review_id, :product_sku, :reviewer_email, :rating, :review_text, :created_at);"), reviews_data)

    print("  [OK] crm_db seeded 5 tables x 50 records = 250 records.")


MYSQL_DB_URL = os.getenv("MYSQL_DB_URL", "mysql+pymysql://root:mysql_password@localhost:3307/inventory_db")
MONGO_DB_URL = os.getenv("MONGO_DB_URL", "mongodb://127.0.0.1:27017")


def setup_mysql_db():
    print("\n--- Setting up MySQL inventory_db Schema & Data (Port 3307) ---")
    try:
        engine = create_engine(MYSQL_DB_URL, connect_args={"connect_timeout": 3})
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS inventory_items;"))
            conn.execute(text("DROP TABLE IF EXISTS warehouses;"))
            conn.execute(text("""
                CREATE TABLE warehouses (
                    warehouse_id INT PRIMARY KEY,
                    location_name VARCHAR(100) NOT NULL,
                    capacity INT NOT NULL
                );
            """))
            conn.execute(text("""
                CREATE TABLE inventory_items (
                    item_id INT PRIMARY KEY,
                    warehouse_id INT REFERENCES warehouses(warehouse_id),
                    item_code VARCHAR(50) NOT NULL,
                    quantity_on_hand INT NOT NULL
                );
            """))
            warehouses = [
                {"warehouse_id": i + 1, "location_name": f"Facility Node-{i+1}", "capacity": 1000 * (i + 1)}
                for i in range(50)
            ]
            conn.execute(text("INSERT INTO warehouses (warehouse_id, location_name, capacity) VALUES (:warehouse_id, :location_name, :capacity);"), warehouses)

            items = [
                {"item_id": 100 + i, "warehouse_id": (i % 50) + 1, "item_code": f"INV-{i+1:03d}", "quantity_on_hand": (i + 1) * 10}
                for i in range(50)
            ]
            conn.execute(text("INSERT INTO inventory_items (item_id, warehouse_id, item_code, quantity_on_hand) VALUES (:item_id, :warehouse_id, :item_code, :quantity_on_hand);"), items)
        print("  [OK] MySQL inventory_db seeded 2 tables x 50 records = 100 records.")
    except Exception as e:
        print(f"  [Notice] Skipping MySQL seed ({e})")


def setup_mongo_db():
    print("\n--- Setting up MongoDB analytics_db Schema & Data (Port 27017) ---")
    try:
        import pymongo
        client = pymongo.MongoClient(MONGO_DB_URL, serverSelectionTimeoutMS=3000)
        db = client["analytics_db"]

        # Drop existing collections
        db["events"].drop()
        db["user_metrics"].drop()

        # Seed events collection (50 documents)
        event_types = ["PAGE_VIEW", "CLICK", "CONVERSION", "ADD_TO_CART", "CHECKOUT"]
        events_docs = [
            {
                "event_id": f"EVT-100{i+1:02d}",
                "event_type": event_types[i % len(event_types)],
                "user_email": f"client_{i+1}@enterprise-test.com",
                "properties": {
                    "session_id": f"SESS-{i+1:03d}",
                    "device": "desktop" if i % 2 == 0 else "mobile",
                    "duration_seconds": (i + 1) * 12,
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(50)
        ]
        db["events"].insert_many(events_docs)

        # Seed user_metrics collection (50 documents)
        metrics_docs = [
            {
                "user_email": f"client_{i+1}@enterprise-test.com",
                "total_orders": (i % 10) + 1,
                "lifetime_value": round(150.0 + (i * 45.2), 2),
                "churn_risk": "LOW" if i % 3 == 0 else "MEDIUM",
                "last_active": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(50)
        ]
        db["user_metrics"].insert_many(metrics_docs)
        client.close()

        print("  [OK] MongoDB analytics_db seeded 2 collections x 50 docs = 100 documents.")
    except Exception as e:
        print(f"  [Notice] Skipping MongoDB seed ({e})")


def main():
    print("================================================================================")
    print(" >>> SEEDING SOURCE DATABASES FOR MULTI-DB MIGRATION TESTING")
    print("     PostgreSQL 1: ecommerce_db (Port 5435) - 5 Tables, 250 Rows")
    print("     PostgreSQL 2: crm_db       (Port 5436) - 5 Tables, 250 Rows")
    print("     MySQL 1:      inventory_db (Port 3307) - 2 Tables, 100 Rows")
    print("     MongoDB 1:    analytics_db (Port 27017)- 2 Collections, 100 Docs")
    print("================================================================================")

    ensure_postgres_db_exists(5435, "ecommerce_db")
    ensure_postgres_db_exists(5436, "crm_db")
    ensure_mysql_db_exists("inventory_db")

    eng_ecommerce = wait_for_db(ECOMMERCE_DB_URL, "ecommerce_db (Port 5435)")
    setup_ecommerce_db(eng_ecommerce)

    eng_crm = wait_for_db(CRM_DB_URL, "crm_db (Port 5436)")
    setup_crm_db(eng_crm)

    setup_mysql_db()
    setup_mongo_db()

    print("\n================================================================================")
    print(" [SUCCESS] MULTI-DATABASE SETUP COMPLETE!")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
