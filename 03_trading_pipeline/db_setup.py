"""
Phase 3 — Database Setup

Creates the access_log_realtime table in the schema set by POSTGRES_SCHEMA env var.

Run ONCE before starting log_consumer.py:
    python 03_trading_pipeline/db_setup.py
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

SCHEMA = os.getenv("POSTGRES_SCHEMA", "kafka_learn")

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST"),
    port=int(os.getenv("POSTGRES_PORT", 5432)),
    dbname=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
)
cursor = conn.cursor()

cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};")

cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.access_log_realtime (
        id            SERIAL PRIMARY KEY,
        file_name     VARCHAR(100),          -- source log file (e.g. trading_20260318.log)
        log_date      DATE,                  -- date extracted from file name
        log_time      VARCHAR(20),           -- HH:MM:SS.mmm from the log line
        ip            VARCHAR(45),           -- client IP address
        login         VARCHAR(50),           -- trading account login number
        cid           VARCHAR(64),           -- connection ID hash
        device        VARCHAR(100),          -- e.g. "Client iPhone", "Client Android"
        server        VARCHAR(150),          -- e.g. "point: Access Server India"
        flag          VARCHAR(10) DEFAULT 'pending',  -- 'trade', 'lilo', or 'pending' (EOD updates this)
        investor      VARCHAR(5),            -- 'yes' or 'no'
        etl_timestamp TIMESTAMP DEFAULT NOW()
    );
""")

# Index on log_date + ip for fast EOD UPDATE queries
cursor.execute(f"""
    CREATE INDEX IF NOT EXISTS idx_access_log_date_ip
    ON {SCHEMA}.access_log_realtime (log_date, ip);
""")

# Index on flag for fast pending → trade/lilo updates
cursor.execute(f"""
    CREATE INDEX IF NOT EXISTS idx_access_log_flag
    ON {SCHEMA}.access_log_realtime (flag);
""")

conn.commit()
cursor.close()
conn.close()

print(f"Table {SCHEMA}.access_log_realtime is ready (with indexes).")
