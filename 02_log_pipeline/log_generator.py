"""
Phase 2 — Log Generator

Simulates a live application server writing logs to a file every 0.5 seconds.
This replaces your real server's log file for the demo.

In production, your actual server writes this file — you'd skip this script entirely.

Run this in Terminal 1. It writes to: logs/app.log
"""

import os
import time
import random
from datetime import datetime
from faker import Faker

fake = Faker()

# Log file lives at the project root in a logs/ folder
LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "app.log")

ENDPOINTS = [
    "/api/orders",
    "/api/users",
    "/api/checkout",
    "/api/products",
    "/api/login",
    "/api/logout",
]
METHODS = ["GET", "POST", "PUT", "DELETE"]

# Status codes — weighted: most requests succeed (200/201), some fail
STATUS_CODES = [200, 200, 200, 200, 200, 201, 400, 401, 404, 500]
ERROR_MESSAGES = ["database_timeout", "connection_refused", "null_pointer", "out_of_memory"]


def generate_log_line() -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    endpoint = random.choice(ENDPOINTS)
    method = random.choice(METHODS)
    status = random.choice(STATUS_CODES)
    user_id = random.randint(1000, 9999)
    ip = fake.ipv4()

    # Errors take longer
    duration_ms = random.randint(500, 5000) if status == 500 else random.randint(5, 300)

    level = "ERROR" if status >= 500 else "WARN" if status >= 400 else "INFO"

    line = (
        f"{timestamp} | {level:<5} | user_id={user_id} | endpoint={endpoint} "
        f"| method={method} | status={status} | duration_ms={duration_ms} | ip={ip}"
    )

    if status >= 500:
        line += f" | error={random.choice(ERROR_MESSAGES)}"

    return line


# Create the logs/ directory if it doesn't exist
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

print(f"Writing logs to: {os.path.abspath(LOG_FILE)}")
print("Press Ctrl+C to stop.\n")

try:
    with open(LOG_FILE, "a") as f:
        while True:
            line = generate_log_line()
            f.write(line + "\n")
            # flush() forces the line to disk immediately so the producer can see it.
            # Without this, Python buffers writes and the producer would see nothing.
            f.flush()
            print(line)
            time.sleep(0.5)
except KeyboardInterrupt:
    print("\nStopped.")
