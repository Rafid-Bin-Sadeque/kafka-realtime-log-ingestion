"""
Phase 1 — Basic Consumer

A consumer reads messages from a Kafka topic.

Key idea: consumers don't "receive" messages — they POLL for them.
Your app is in control of when it reads and how fast.

Run this in a separate terminal while producer.py is running.
"""

import json
import time
from confluent_kafka import Consumer, KafkaError
from dotenv import load_dotenv
import os

load_dotenv()

# --- Config ---
consumer = Consumer({
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),

    # group.id = which consumer group this consumer belongs to.
    # A consumer group tracks YOUR progress through the topic independently
    # of all other groups. Two different apps = two different group IDs.
    "group.id": "order-processor",

    # auto.offset.reset = what to do when this group has NO stored offset yet
    # "earliest" = start from the very beginning of the topic
    # "latest"   = only read messages that arrive AFTER you start
    "auto.offset.reset": "earliest",
})

TOPIC = "orders"

# Subscribe tells Kafka: "assign me partitions for this topic"
# Kafka will rebalance partitions across all consumers in the group
consumer.subscribe([TOPIC])

print(f"Listening on topic '{TOPIC}'... (Ctrl+C to stop)\n")

# If the topic doesn't exist yet, Kafka returns UNKNOWN_TOPIC_OR_PARTITION.
# This loop will keep retrying until the topic appears (usually when the
# producer first writes to it).
last_unknown_topic_log = 0.0
try:
    while True:
        # poll() asks Kafka: "any new messages for me?"
        # timeout=1.0 means wait up to 1 second before returning None
        msg = consumer.poll(timeout=1.0)

        if msg is None:
            # No message in the last 1 second — that's fine, keep looping
            continue

        if msg.error():
            err = msg.error()
            code = err.code()

            if code == KafkaError._PARTITION_EOF:
                # Reached the end of a partition — not an error, just means
                # you've caught up. More messages may arrive later.
                print(f"  [end of partition {msg.partition()}]")

            elif code == KafkaError.UNKNOWN_TOPIC_OR_PART:
                # Topic may not exist yet (producer hasn't written yet).
                # Log sparingly so we don't spam the console.
                now = time.time()
                if now - last_unknown_topic_log > 5:
                    print(f"  Waiting for topic '{TOPIC}' to be created...")
                    last_unknown_topic_log = now
                time.sleep(1)

            else:
                print(f"  Error: {err}")
            continue

        # Decode the message
        order = json.loads(msg.value().decode("utf-8"))

        print(
            f"Received | partition={msg.partition()} offset={msg.offset()} "
            f"key={msg.key().decode()} | {order}"
        )

        # --- Your business logic goes here ---
        # e.g. validate the order, write to Postgres, trigger a downstream event
        # For now we just print it.

except KeyboardInterrupt:
    print("\nStopping.")
finally:
    # IMPORTANT: always close the consumer.
    # This triggers a graceful rebalance so other consumers in the group
    # can pick up your partitions immediately instead of waiting for a timeout.
    consumer.close()
