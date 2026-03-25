"""
Phase 2 — Consumer Lag Monitor

Shows how far behind the log consumer is.

Lag = (latest offset in Kafka) - (last committed offset by the consumer group)

  Lag = 0  → consumer has caught up, everything is processed
  Lag > 0  → messages are sitting in Kafka waiting to be consumed
             (consumer is slow, crashed, or not running)

Run this any time in a separate terminal:
    python 02_log_pipeline/monitor_lag.py
"""

from confluent_kafka.admin import AdminClient
from confluent_kafka import Consumer, TopicPartition
from dotenv import load_dotenv
import os

load_dotenv()

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
GROUP_ID = "log-to-postgres"
TOPIC = "app-logs"

admin = AdminClient({"bootstrap.servers": BOOTSTRAP})
metadata = admin.list_topics(timeout=10)

if TOPIC not in metadata.topics:
    print(f"Topic '{TOPIC}' does not exist yet. Start the producer first.")
    exit()

topic_meta = metadata.topics[TOPIC]
partitions = [TopicPartition(TOPIC, p) for p in topic_meta.partitions]

consumer = Consumer({
    "bootstrap.servers": BOOTSTRAP,
    "group.id": GROUP_ID,
})

committed = consumer.committed(partitions, timeout=10)

print(f"=== Lag Report: group='{GROUP_ID}' topic='{TOPIC}' ===\n")

total_lag = 0
for tp in committed:
    low, high = consumer.get_watermark_offsets(tp, timeout=5)
    committed_offset = tp.offset if tp.offset >= 0 else 0
    lag = high - committed_offset
    total_lag += lag

    status = "OK - caught up" if lag == 0 else f"BEHIND by {lag} messages"
    print(f"  Partition {tp.partition} | "
          f"committed={committed_offset}  latest={high}  lag={lag}  [{status}]")

print(f"\n  Total lag across all partitions: {total_lag}")

consumer.close()
