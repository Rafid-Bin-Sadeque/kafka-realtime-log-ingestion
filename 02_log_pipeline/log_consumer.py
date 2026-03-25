"""
Phase 2 — Log Consumer

Reads log messages from Kafka, parses each line into structured fields,
and inserts a row into PostgreSQL.

Key insight: if this consumer crashes mid-day, Kafka remembers the last
committed offset. When you restart it, it picks up exactly where it left off —
no log lines are skipped or duplicated.

Run this in Terminal 3, after db_setup.py has been run once.
"""

import os
import psycopg2
from confluent_kafka import Consumer, KafkaError
from dotenv import load_dotenv

load_dotenv()

TOPIC = "app-logs"

# --- Kafka consumer ---
consumer = Consumer({
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    # A unique group ID means this consumer group tracks its own offset
    # independently of any other consumers on the same topic.
    "group.id": "log-to-postgres",
    "auto.offset.reset": "earliest",
})
consumer.subscribe([TOPIC])

# --- Postgres connection ---
conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST"),
    port=int(os.getenv("POSTGRES_PORT", 5432)),
    dbname=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
)
cursor = conn.cursor()


def parse_log_line(line: str) -> dict | None:
    """
    Parses a log line in the format produced by log_generator.py:

      2026-03-18 14:32:01.123 | INFO  | user_id=123 | endpoint=/api/orders | ...

    Returns a dict of fields, or None if the line can't be parsed.
    """
    try:
        parts = [p.strip() for p in line.split("|")]

        data = {
            "timestamp": parts[0].strip(),
            "level": parts[1].strip(),
        }

        # All remaining parts are key=value pairs
        for part in parts[2:]:
            if "=" in part:
                key, value = part.split("=", 1)
                data[key.strip()] = value.strip()

        return data
    except Exception:
        return None


def insert_log(data: dict):
    """Inserts one parsed log record into PostgreSQL."""
    cursor.execute(
        """
        INSERT INTO rafid_test.app_logs
            (timestamp, level, user_id, endpoint, method, status, duration_ms, ip, error)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            data.get("timestamp"),
            data.get("level"),
            data.get("user_id"),
            data.get("endpoint"),
            data.get("method"),
            int(data["status"]) if data.get("status") else None,
            int(data["duration_ms"]) if data.get("duration_ms") else None,
            data.get("ip"),
            data.get("error"),  # None if no error field — Postgres stores it as NULL
        ),
    )
    conn.commit()


print(f"Listening on topic '{TOPIC}', inserting into Postgres...\n")

try:
    while True:
        msg = consumer.poll(timeout=1.0)

        if msg is None:
            continue

        if msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                print(f"Kafka error: {msg.error()}")
            continue

        raw_line = msg.value().decode("utf-8")

        data = parse_log_line(raw_line)
        if not data:
            print(f"Could not parse line: {raw_line}")
            continue

        insert_log(data)

        print(
            f"Inserted | {data.get('timestamp')} | {data.get('level'):<5} | "
            f"{data.get('endpoint')} | status={data.get('status')} | "
            f"{data.get('duration_ms')}ms"
        )

except KeyboardInterrupt:
    print("\nStopping.")
finally:
    consumer.close()
    cursor.close()
    conn.close()
