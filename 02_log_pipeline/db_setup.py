"""
Phase 2 — Database Setup

Creates the schema 'rafid_test' and the app_logs table inside it.

In Postgres, a schema is a namespace inside a database.
Think of it like a folder: database > schema > table.

Run this ONCE before starting log_consumer.py.

Usage:
    python 02_log_pipeline/db_setup.py
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST"),
    port=int(os.getenv("POSTGRES_PORT", 5432)),
    dbname=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
)
cursor = conn.cursor()

# Create the schema if it doesn't exist yet
cursor.execute("CREATE SCHEMA IF NOT EXISTS rafid_test;")

# Create the table inside that schema
cursor.execute("""
    CREATE TABLE IF NOT EXISTS rafid_test.app_logs (
        id          SERIAL PRIMARY KEY,        -- auto-incrementing row ID
        timestamp   TIMESTAMP,                 -- when the log line was generated
        level       VARCHAR(10),               -- INFO, WARN, ERROR
        user_id     VARCHAR(20),               -- which user triggered the request
        endpoint    VARCHAR(100),              -- e.g. /api/orders
        method      VARCHAR(10),               -- GET, POST, PUT, DELETE
        status      INTEGER,                   -- HTTP status code
        duration_ms INTEGER,                   -- how long the request took
        ip          VARCHAR(45),               -- client IP (supports IPv6)
        error       TEXT,                      -- error message if status >= 500, else NULL
        created_at  TIMESTAMP DEFAULT NOW()    -- when this row was inserted into Postgres
    );
""")

conn.commit()
cursor.close()
conn.close()

print("Schema 'rafid_test' and table 'app_logs' are ready.")
