"""
Phase 3 — Consumer Lag Monitor

Shows per-partition lag for the trading-access-logs topic.

With 3 partitions and 3 consumers, you can see each consumer's
individual lag — useful to spot if one consumer is falling behind.

Run any time:
    python 03_trading_pipeline/monitor_lag.py
"""

from confluent_kafka.admin import AdminClient
from confluent_kafka import Consumer, TopicPartition
from dotenv import load_dotenv
import os

load_dotenv()

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
GROUP_ID = "log-to-postgres"
TOPIC = "trading-access-logs"

admin = AdminClient({"bootstrap.servers": BOOTSTRAP})
metadata = admin.list_topics(timeout=10)

if TOPIC not in metadata.topics:
    print(f"Topic '{TOPIC}' does not exist yet. Run topic_setup.py first.")
    exit()

topic_meta = metadata.topics[TOPIC]
partitions = [TopicPartition(TOPIC, p) for p in topic_meta.partitions]

consumer = Consumer({
    "bootstrap.servers": BOOTSTRAP,
    "group.id": GROUP_ID,
})

committed = consumer.committed(partitions, timeout=10)

print(f"=== Lag Report ===")
print(f"Topic : {TOPIC}")
print(f"Group : {GROUP_ID}")
print(f"Partitions: {len(partitions)}\n")

total_lag = 0
for tp in committed:
    low, high = consumer.get_watermark_offsets(tp, timeout=5)
    committed_offset = tp.offset if tp.offset >= 0 else 0
    lag = high - committed_offset
    total_lag += lag
    status = "OK" if lag == 0 else f"BEHIND by {lag:,}"
    print(f"  Partition {tp.partition} | committed={committed_offset:,}  latest={high:,}  lag={lag:,}  [{status}]")

print(f"\n  Total lag: {total_lag:,} messages")

consumer.close()
