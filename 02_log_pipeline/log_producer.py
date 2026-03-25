"""
Phase 2 — Log Producer (File Tailer)

Reads new lines from a growing log file in real-time (like `tail -f` in a terminal)
and sends each line as a message to a Kafka topic.

This is the bridge between the file system and Kafka.

How file tailing works:
  - Opens the file and jumps to the END (so we don't re-send old lines on restart)
  - Checks for new content every 0.1 seconds
  - When a new line appears, sends it to Kafka immediately

Run this in Terminal 2, after log_generator.py has started.
"""

import os
import time
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "app.log")
TOPIC = "app-logs"

producer = Producer({
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
})


def delivery_report(err, msg):
    if err:
        print(f"  ✗ Delivery failed: {err}")
    else:
        print(f"  ✓ Sent → partition={msg.partition()} offset={msg.offset()}")


def tail_file(filepath: str):
    """
    Generator that yields new lines from a file as they are appended.

    seek(0, 2) means: go to position 0 bytes from the END of the file.
    This ensures we only pick up lines written AFTER this script starts.
    In production, this means you never re-process old logs on restart
    (though for a full restart-safe solution you'd save the file offset — Phase 3).
    """
    # Wait for the file to be created by the generator
    while not os.path.exists(filepath):
        print(f"Waiting for log file to appear: {filepath}")
        time.sleep(1)

    with open(filepath, "r") as f:
        f.seek(0, 2)  # jump to end of file
        print(f"Tailing: {os.path.abspath(filepath)}")
        print(f"Sending to Kafka topic: '{TOPIC}'\n")

        while True:
            line = f.readline()
            if line:
                # readline() includes the newline — strip it before sending
                yield line.strip()
            else:
                # No new content yet — sleep briefly and check again
                time.sleep(0.1)


print("Log Producer starting...")

try:
    for log_line in tail_file(LOG_FILE):
        # Show a preview in the console (first 90 chars)
        print(f"Sending: {log_line[:90]}...")

        producer.produce(
            topic=TOPIC,
            value=log_line.encode("utf-8"),
            callback=delivery_report,
        )
        # poll(0) = process any pending delivery callbacks without blocking
        producer.poll(0)

except KeyboardInterrupt:
    print("\nFlushing remaining messages...")
    producer.flush()
    print("Done.")
