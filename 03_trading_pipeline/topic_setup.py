"""
Phase 3 — Topic Setup

Creates the trading-access-logs topic with 3 partitions.

Run this ONCE before starting the producer/consumer:
    python 03_trading_pipeline/topic_setup.py

Why 3 partitions?
  - Allows up to 3 consumers to run in parallel
  - Each consumer owns one partition and processes independently
  - At ~110 cid lines/sec, each consumer handles ~37 lines/sec

Partition key = login number
  - All messages from the same login always go to the same partition
  - This guarantees ordering per user (all events for login 11820785
    are processed in sequence by the same consumer)
"""

from confluent_kafka.admin import AdminClient, NewTopic
from dotenv import load_dotenv
import os

load_dotenv()

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = "trading-access-logs"
NUM_PARTITIONS = 3
REPLICATION_FACTOR = 1  # single broker setup

admin = AdminClient({"bootstrap.servers": BOOTSTRAP})

# Check if topic already exists
metadata = admin.list_topics(timeout=10)
if TOPIC in metadata.topics:
    existing = metadata.topics[TOPIC]
    print(f"Topic '{TOPIC}' already exists with {len(existing.partitions)} partition(s).")
    print("To change partition count, delete and recreate the topic.")
else:
    new_topic = NewTopic(
        topic=TOPIC,
        num_partitions=NUM_PARTITIONS,
        replication_factor=REPLICATION_FACTOR,
    )
    result = admin.create_topics([new_topic])
    for topic, future in result.items():
        try:
            future.result()
            print(f"Topic '{topic}' created with {NUM_PARTITIONS} partitions.")
        except Exception as e:
            print(f"Failed to create topic '{topic}': {e}")
