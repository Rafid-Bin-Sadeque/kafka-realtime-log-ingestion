"""
Phase 1 — Inspect Topics & Consumer Group Lag

Run this any time to see:
- What topics exist
- How many messages are in each partition
- How far behind your consumer group is (lag)
"""

from confluent_kafka.admin import AdminClient
from confluent_kafka import Consumer, TopicPartition
from dotenv import load_dotenv
import os

load_dotenv()

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
GROUP_ID = "order-processor"

admin = AdminClient({"bootstrap.servers": BOOTSTRAP})

# --- List topics ---
metadata = admin.list_topics(timeout=10)
topics = [t for t in metadata.topics if not t.startswith("__")]  # skip internal topics

print("=== Topics ===")
for topic_name in sorted(topics):
    topic = metadata.topics[topic_name]
    print(f"  {topic_name}  ({len(topic.partitions)} partition(s))")

# --- Consumer group lag ---
# Lag = (latest offset in partition) - (last committed offset by the group)
# Lag > 0 means your consumer is behind — it hasn't processed all messages yet

consumer = Consumer({
    "bootstrap.servers": BOOTSTRAP,
    "group.id": GROUP_ID,
})

print(f"\n=== Consumer Group Lag: '{GROUP_ID}' ===")
for topic_name in sorted(topics):
    topic = metadata.topics[topic_name]
    partitions = [TopicPartition(topic_name, p) for p in topic.partitions]

    # Get committed offsets (where the group is up to)
    committed = consumer.committed(partitions, timeout=10)

    # Get end offsets (latest message position)
    end_offsets = consumer.get_watermark_offsets

    for tp in committed:
        low, high = consumer.get_watermark_offsets(tp, timeout=5)
        committed_offset = tp.offset if tp.offset >= 0 else 0
        lag = high - committed_offset
        print(f"  {topic_name} partition={tp.partition} | "
              f"committed={committed_offset} latest={high} lag={lag}")

consumer.close()
