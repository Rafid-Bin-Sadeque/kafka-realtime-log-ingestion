"""
Phase 3 — Trading Log Generator

Simulates a live trading server writing logs at realistic speed.

Real-world stats (based on production volumes):
  - 8 GB/day ÷ ~180 bytes avg/line = ~47 million lines/day
  - 47M ÷ 86,400 seconds = ~550 lines/second

Mix we generate (matches real log ratio):
  - 20% cid: login lines   → these get parsed and inserted to DB
  - 15% logout lines        → filtered out by producer
  - 5%  trade/order lines   → used at EOD for trade flag
  - 60% system/monitor      → filtered out by producer

Run this in Terminal 1:
    python 03_trading_pipeline/log_generator.py
"""

import os
import time
import random
import uuid
import datetime
from faker import Faker

fake = Faker()

# Output file — named like production (YYYYMMDD.log)
TODAY = datetime.date.today().strftime("%Y%m%d")
LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", f"trading_{TODAY}.log")

LINES_PER_SECOND = 550  # matches 8GB/day pace
SLEEP_INTERVAL = 1 / LINES_PER_SECOND

# Two-character server codes (prefix on every line)
SERVER_CODES = ["XA", "BT", "KZ", "RV", "WP", "JN", "YC", "TG", "SL", "OF",
                "UE", "MQ", "DH", "FI", "LX", "ZB", "GW", "NR", "VJ", "CK"]

# Access server points
ACCESS_POINTS = [
    "Access Server Asia 1",
    "Access Server Asia 2",
    "Access Server Europe 1",
    "Access Server Europe 2",
    "Access Server Americas",
]

# Client builds
CLIENT_BUILDS = [
    "Client iPhone build 5545",
    "Client iPhone build 5432",
    "Client iPhone build 5100",
    "Client Android build 5676",
    "Client Android build 5660",
    "Client Web build 5660",
    "Client build 5660",
]

# Instruments for trade lines
INSTRUMENTS = ["XAUUSD", "EURUSD", "GER30", "US2000", "GBPUSD", "BTCUSD", "NASDAQ"]
TRADE_ACTIONS = ["buy", "sell", "buy limit", "sell limit", "buy stop"]

# Pre-generate a pool of logins and IPs that will appear in both login AND trade lines
# (so the EOD flag updater will correctly mark some connections as 'trade')
TRADER_POOL = [
    (fake.ipv4(), str(random.randint(11000000, 11999999)))
    for _ in range(200)
]

# Internal execution server IP — replace with your own
EXECUTION_SERVER_IP = "10.0.0.1"

# Geo data pool
GEO_POOL = [
    "IN, Chennai, Atria Convergence Technologies",
    "NG, Lagos, MTN NIGERIA Communication limited, MTN Nigeria",
    "GB, London, British Telecommunications PLC, BT",
    "ZA, Johannesburg, Vodacom-VB, Vodacom Business",
    "PK, Karachi, Pakistan Telecommunication Company, PTCL",
    "EG, Cairo, Telecom Egypt, TE Data",
    "MA, Casablanca, MT-MPLS, Maroc Telecom",
    "DE, Frankfurt am Main, Deutsche Telekom AG",
    "FR, Paris, Free SAS, Free",
    "IT, Milan, Wind Tre S.p.A, Wind Tre",
    "PY, Asunción, Telecel S.A, Tigo Paraguay",
    "ID, Jakarta, PT. Telekomunikasi Selular, Telkomsel",
]


def random_code():
    return random.choice(SERVER_CODES)


def random_ts():
    """Random timestamp in HH:MM:SS.mmm format (not real-time, just realistic)"""
    h = random.randint(0, 23)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    ms = random.randint(0, 999)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def make_login_line():
    """cid: login line — the ones that get parsed and inserted to DB"""
    ip, login = random.choice(TRADER_POOL)
    client = random.choice(CLIENT_BUILDS)
    point = random.choice(ACCESS_POINTS)
    cid = uuid.uuid4().hex
    ping = round(random.uniform(5, 1500), 2)
    geo = random.choice(GEO_POOL)
    flags = ", flags: datacenter" if random.random() < 0.1 else ""
    investor = ", investor" if random.random() < 0.05 else ""

    # Format must match exactly what access_log.py parses (comma-separated fields after first tab-section)
    return (
        f"{random_code()}\t4\t3\t{random_ts()}\t{ip}\t"
        f"'{login}': login ({client}{investor}, "
        f"cid: {cid}, "
        f"point: {point}, "
        f"ping: {ping} ms, "
        f"geo: {geo}{flags})"
    )


def make_logout_line():
    """Logout line — filtered out (no cid:)"""
    ip, login = random.choice(TRADER_POOL)
    client = random.choice(CLIENT_BUILDS)
    return f"{random_code()}\t4\t3\t{random_ts()}\t{ip}\t'{login}': logout ({client})"


def make_trade_line():
    """
    Trade/order line — used by EOD flag updater to build trade IP map.
    Uses IPs from TRADER_POOL so they match connection lines.
    """
    ip, login = random.choice(TRADER_POOL)
    instrument = random.choice(INSTRUMENTS)
    action = random.choice(TRADE_ACTIONS)
    volume = round(random.choice([0.01, 0.02, 0.05, 0.1, 0.5, 1.0]), 2)
    price = round(random.uniform(1.0, 5200.0), 2)
    order_id = random.randint(160000000, 169999999)
    ms = round(random.uniform(50, 500), 2)

    return (
        f"{random_code()}\t0\t6\t{random_ts()}\t{ip}\t"
        f"'{login}': order placed for execution for '{login}' "
        f"[#{order_id} {action} {volume} {instrument} at {price}], time {ms} ms"
    )


def make_system_line():
    """System/monitor line — filtered out entirely"""
    templates = [
        f"{random_code()}\t0\t2\t{random_ts()}\tMonitor\t"
        f"connections: {random.randint(1000,3000)}, blocked: 0, cpu: {random.randint(5,40)}%, "
        f"process cpu: {random.randint(5,25)}%, threads: {random.randint(1000,2500)}",

        f"{random_code()}\t0\t2\t{random_ts()}\tMonitor\t"
        f"users: {random.randint(100000,200000)}, real: {random.randint(50000,100000)}, "
        f"online: {random.randint(1000,5000)}, errors: 0",

        f"{random_code()}\t0\t6\t{random_ts()}\tEnd of Day\t"
        f"group 'REAL_B\\LTE' completed [{random.randint(5000,90000)} account(s)]",

        f"{random_code()}\t0\t3\t{random_ts()}\t{EXECUTION_SERVER_IP}\tconnection accepted",
    ]
    return random.choice(templates)


# Line type weights: login 20%, logout 15%, trade 5%, system 60%
LINE_TYPES = (
    [make_login_line] * 20 +
    [make_logout_line] * 15 +
    [make_trade_line] * 5 +
    [make_system_line] * 60
)

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

print(f"Trading Log Generator")
print(f"Output: {os.path.abspath(LOG_FILE)}")
print(f"Speed: ~{LINES_PER_SECOND} lines/sec (~{int(LINES_PER_SECOND * 0.20)} cid: lines/sec)")
print(f"Simulates: 8 GB/day trading server log")
print(f"Press Ctrl+C to stop.\n")

count = 0
start = time.time()

try:
    with open(LOG_FILE, "a") as f:
        while True:
            line = random.choice(LINE_TYPES)()
            f.write(line + "\n")
            f.flush()
            count += 1

            # Print stats every 1000 lines
            if count % 1000 == 0:
                elapsed = time.time() - start
                print(f"  {count:,} lines written | {count/elapsed:.0f} lines/sec")

            time.sleep(SLEEP_INTERVAL)

except KeyboardInterrupt:
    print(f"\nStopped. Total lines written: {count:,}")
