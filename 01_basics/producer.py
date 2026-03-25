"""
Phase 1 — Basic Producer

A producer writes messages to a Kafka topic.

Run this first, then run consumer.py in another terminal.
"""

import json
import time
from confluent_kafka import Producer
from dotenv import load_dotenv
import os

load_dotenv()

# --- Config ---
# bootstrap.servers = the address of your Kafka broker
# This is the only required setting for a producer.
producer = Producer({
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
})

TOPIC = "orders"


def delivery_report(err, msg):
    """
    Kafka calls this function after each message is either:
    - successfully written to the broker (err=None)
    - failed to be written (err=something)

    Without this, you're fire-and-forget with no confirmation.
    """
    if err:
        print(f"  ✗ Delivery failed: {err}")
    else:
        # msg.partition() = which partition it landed in
        # msg.offset()    = its position in that partition (permanent)
        print(f"  ✓ Delivered to partition={msg.partition()} offset={msg.offset()}")


# --- Send 5 messages ---
for i in range(1, 60):
    order = {
        "order_id": i,
        "customer": f"customer_{i}",
        "item": "widget",
        "quantity": i * 2,
    }

    print(f"Sending: {order}")

    producer.produce(
        topic=TOPIC,
        # Kafka messages are raw bytes — we serialize to JSON manually here
        value=json.dumps(order).encode("utf-8"),
        # key is optional but important: messages with the same key always go
        # to the same partition (guarantees ordering per customer)
        key=str(order["order_id"]).encode("utf-8"),
        callback=delivery_report,
    )

    # poll() lets the producer process delivery callbacks
    # Without this, delivery_report never fires
    producer.poll(0)
    time.sleep(0.5)

# flush() blocks until all messages are confirmed delivered
# Always call this before your program exits
print("\nFlushing...")
producer.flush()
print("Done.")
