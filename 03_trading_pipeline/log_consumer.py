"""
Phase 3 — Trading Log Consumer

Reads trading server login lines from Kafka, parses them, and batch-inserts into Postgres.

Parsing logic:
  - Split by comma first (log format uses comma as field separator within the message)
  - Then split the first segment by tab to get timestamp, ip, login prefix
  - Extract: time, ip, login, cid, device, server_info, investor

Batch insert design:
  - Accumulates up to BATCH_SIZE rows in memory
  - Flushes to Postgres when batch is full OR FLUSH_INTERVAL seconds pass
  - At 110 cid lines/sec, this means ~11 bulk inserts/sec with batch=10
    or ~1 bulk insert every ~9 seconds with batch=1000
  - execute_values is far more efficient than individual INSERTs

Run this in Terminal 3 (after db_setup.py has been run once):
    python 03_trading_pipeline/log_consumer.py
"""

import os
import time
from confluent_kafka import Consumer, KafkaError
from psycopg2.extras import execute_values
import psycopg2
from dotenv import load_dotenv

load_dotenv()

SCHEMA = os.getenv("POSTGRES_SCHEMA", "kafka_learn")
TOPIC = "trading-access-logs"
BATCH_SIZE = 500        # insert when this many rows are buffered
FLUSH_INTERVAL = 3.0    # also insert if this many seconds pass (even if batch not full)

# --- Kafka ---
consumer = Consumer({
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    "group.id": "log-to-postgres",
    "auto.offset.reset": "earliest",
})
consumer.subscribe([TOPIC])

# --- Postgres ---
conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST"),
    port=int(os.getenv("POSTGRES_PORT", 5432)),
    dbname=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
)
cursor = conn.cursor()


def parse_log_line(raw_line: str, source_file: str) -> list | None:
    """
    Parses one cid: login line.

    Input format (tab + comma delimited):
      MM  4  3  00:00:00.028  49.206.98.46  '11820785': login (Client iPhone build 5545,
      cid: d0ccc64..., point: Access Server India, ping: 20.56 ms, geo: IN, ...)

    Returns: [file_name, log_date, log_time, ip, login, cid, device, server_info, flag, investor]
    """
    try:
        # Step 1: split by comma
        a = raw_line.split(",")

        # Step 2: split the first segment by tab
        v_list_part_1 = a[0].split("\t")
        v_list_part_2 = a[1:]

        # Step 3: reconstruct final_list with file and date prepended
        # This mirrors access_log.py exactly
        import datetime
        log_date = datetime.date.today().isoformat()

        final_list = [source_file, log_date] + v_list_part_1 + v_list_part_2

        while len(final_list) < 10:
            final_list.append("Unknown")

        # Extract fields — index positions match access_log.py after the 2 inserts
        # final_list[0] = source_file
        # final_list[1] = log_date
        # final_list[2] = server code (e.g. "MM")
        # final_list[3] = "4"
        # final_list[4] = "3"
        # final_list[5] = timestamp (HH:MM:SS.mmm)
        # final_list[6] = ip
        # final_list[7] = "'login': login (Client ... build XXXX"
        # final_list[8] = " cid: <hash>"
        # final_list[9] = " point: Access Server ..."

        file_name = final_list[0]
        date      = final_list[1]
        log_time  = final_list[5]

        try:
            ip = final_list[6]
        except Exception:
            ip = "unknown"

        try:
            login = final_list[7].split(":")[0].strip().split(" ")[-1].replace("'", "")
        except Exception:
            login = "unknown"

        try:
            cid = final_list[8].strip().split(": ")[1]
        except Exception:
            cid = "unknown"

        try:
            server_info = final_list[9].strip()
        except Exception:
            server_info = "unknown"

        try:
            device = final_list[7].split("(")[1].split("build")[0].strip()
        except Exception:
            device = "unknown"

        investor = "yes" if "investor" in raw_line else "no"
        flag = "pending"  # will be updated to 'trade' or 'lilo' by eod_flag_updater.py

        return [file_name, date, log_time, ip, login, cid, device, server_info, flag, investor]

    except Exception as e:
        return None


def flush_batch(batch: list) -> int:
    """Bulk-inserts a batch of rows using execute_values (same as access_log.py)."""
    if not batch:
        return 0
    try:
        execute_values(
            cursor,
            f"""
            INSERT INTO {SCHEMA}.access_log_realtime
                (file_name, log_date, log_time, ip, login, cid, device, server, flag, investor)
            VALUES %s
            """,
            batch,
        )
        conn.commit()
        return len(batch)
    except Exception as e:
        conn.rollback()
        print(f"  Insert error: {e}")
        return 0


print(f"Trading Log Consumer starting — topic='{TOPIC}', batch_size={BATCH_SIZE}")
print(f"Inserting into {SCHEMA}.access_log_realtime\n")

SOURCE_FILE = f"trading_{os.environ.get('LOG_DATE', '')}.log"
batch = []
last_flush = time.time()
total_inserted = 0
total_failed = 0

try:
    while True:
        msg = consumer.poll(timeout=0.5)

        if msg is not None and not msg.error():
            raw_line = msg.value().decode("utf-8")
            row = parse_log_line(raw_line, SOURCE_FILE)

            if row:
                batch.append(row)
            else:
                total_failed += 1

        elif msg is not None and msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                print(f"Kafka error: {msg.error()}")

        # Flush when batch is full OR flush interval has passed
        now = time.time()
        if len(batch) >= BATCH_SIZE or (batch and now - last_flush >= FLUSH_INTERVAL):
            n = flush_batch(batch)
            total_inserted += n
            print(
                f"Inserted {n} rows (batch) | total={total_inserted:,} | "
                f"parse_errors={total_failed}"
            )
            batch.clear()
            last_flush = now

except KeyboardInterrupt:
    print("\nFlushing remaining batch...")
    if batch:
        n = flush_batch(batch)
        total_inserted += n
    print(f"Done. Total inserted: {total_inserted:,}")
finally:
    consumer.close()
    cursor.close()
    conn.close()
