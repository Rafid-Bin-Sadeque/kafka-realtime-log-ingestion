"""
Phase 3 — Trading Log Producer

Tails the trading server log file and sends ONLY cid: login lines to Kafka.

Key design decision — filter at the producer, not the consumer:
  - Trading logs are ~550 lines/sec total
  - Only ~20% (cid: lines) need to go into the DB
  - Filtering here means Kafka only holds ~110 messages/sec
    instead of 550, reducing storage and consumer load by 80%

Run this in Terminal 2 (after log_generator.py has started):
    python 03_trading_pipeline/log_producer.py
"""

import os
import time
import datetime
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

TODAY = datetime.date.today().strftime("%Y%m%d")
LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", f"trading_{TODAY}.log")
TOPIC = "trading-access-logs"

producer = Producer({
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    # Batch settings for higher throughput
    # linger.ms: wait up to 50ms to fill a batch before sending
    # batch.size: max bytes per batch
    "linger.ms": 50,
    "batch.size": 65536,
})

sent = 0
skipped = 0


def delivery_report(err, msg):
    if err:
        print(f"  ✗ Delivery failed: {err}")


def tail_file(filepath: str):
    while not os.path.exists(filepath):
        print(f"Waiting for log file: {filepath}")
        time.sleep(1)

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, 2)  # jump to end — only new lines
        print(f"Tailing: {os.path.abspath(filepath)}")
        print(f"Sending cid: lines to Kafka topic: '{TOPIC}'\n")

        while True:
            line = f.readline()
            if line:
                yield line.strip()
            else:
                time.sleep(0.05)


print("Trading Log Producer starting...")

try:
    for raw_line in tail_file(LOG_FILE):
        # Filter: only send lines that contain 'cid:' — these are the login lines
        # Logout, Monitor, End of Day, trade lines are all dropped here
        if "cid:" not in raw_line:
            skipped += 1
            continue

        # Extract login as the partition key
        # e.g. "'11820785': login ..." → key = "11820785"
        # This ensures all events for the same login always go to the same partition,
        # so one consumer handles all activity for a given user (ordering guaranteed)
        try:
            key = raw_line.split("\t")[5].split(":")[0].strip().replace("'", "")
        except Exception:
            key = None

        producer.produce(
            topic=TOPIC,
            value=raw_line.encode("utf-8"),
            key=key.encode("utf-8") if key else None,
            callback=delivery_report,
        )
        producer.poll(0)
        sent += 1

        if sent % 500 == 0:
            print(f"  Sent: {sent:,} | Skipped (non-cid): {skipped:,}")

except KeyboardInterrupt:
    print(f"\nFlushing... sent={sent:,} skipped={skipped:,}")
    producer.flush()
    print("Done.")
