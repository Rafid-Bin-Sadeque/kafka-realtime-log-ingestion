"""
Phase 3 — EOD Flag Updater

Runs ONCE at end of day, after the trading server closes the log file.

What it does:
  1. Reads the day's log file ONE time to build a trade IP map
  2. Runs one SQL UPDATE to flip flag = 'trade' for matching rows
  3. Runs one SQL UPDATE to flip remaining 'pending' → 'lilo'
  4. Sends Discord notification (optional, set DISCORD_WEBHOOK_URL in .env)

What it replaces:
  - The entire heavy EOD ETL (no more 7-8GB insert, data is already in DB)
  - This job runs in minutes instead of hours

This is the ONLY step that still requires looking at the raw log file.

Usage:
    python 03_trading_pipeline/eod_flag_updater.py --date 20260318
    python 03_trading_pipeline/eod_flag_updater.py              # defaults to today
"""

import os
import io
import sys
import argparse
import datetime
import time
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

SCHEMA = os.getenv("POSTGRES_SCHEMA", "kafka_learn")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def get_current_time():
    return datetime.datetime.now() + datetime.timedelta(hours=6)


def send_discord_message(message: str):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
    except Exception:
        pass


def build_trade_ip_map(log_file: str) -> dict:
    """
    Single pass over the log file to build {ip: set(logins)} for trade activity.
    """
    ip_login_map = {}

    include_filters = [
        "buy limit:", "order placed", "modify order", "order",
        "request transferred to dealers", "order modified",
        "modify", "position modified", "market sell",
        "order placed for execution", "market buy", "sell limit",
    ]
    exclude_filters = [
        "request from", "confirm for", "received mail",
        "history deals synchronized", "history orders synchronized",
    ]

    print(f"Reading: {log_file}")
    line_count = 0

    try:
        with io.open(log_file, "r", encoding="utf-16", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        with io.open(log_file, "r", errors="ignore") as f:
            lines = f.readlines()

    for line in lines:
        line_count += 1
        if not any(f in line for f in exclude_filters):
            if any(f in line for f in include_filters):
                parts = line.split()
                ip = parts[4] if len(parts) > 4 and parts[4].count(".") == 3 else "unknown"
                login = (
                    parts[5].split(":")[0].strip().split(" ")[-1].replace("'", "")
                    if len(parts) > 5 else "unknown"
                )
                if ip != "unknown" and login != "unknown":
                    if ip not in ip_login_map:
                        ip_login_map[ip] = set()
                    ip_login_map[ip].add(login)

    print(f"  Scanned {line_count:,} lines | Found {len(ip_login_map):,} unique trade IPs")
    return ip_login_map


def update_flags(log_date: str, ip_login_map: dict):
    """
    Two SQL UPDATEs:
      1. flag = 'trade' for rows whose IP is in the trade map
      2. flag = 'lilo'  for all remaining 'pending' rows
    """
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
    cursor = conn.cursor()

    trade_ips = list(ip_login_map.keys())
    print(f"\nUpdating flags for log_date={log_date}, trade IPs={len(trade_ips):,}...")

    # Step 1: mark trade rows
    t1 = time.time()
    cursor.execute(
        f"""
        UPDATE {SCHEMA}.access_log
        SET flag = 'trade'
        WHERE log_date = %s
          AND ip = ANY(%s)
          AND flag = 'pending'
        """,
        (log_date, trade_ips),
    )
    trade_updated = cursor.rowcount
    conn.commit()
    print(f"  'trade' flag set on {trade_updated:,} rows ({time.time()-t1:.1f}s)")

    # Step 2: mark remaining as lilo
    t2 = time.time()
    cursor.execute(
        f"""
        UPDATE {SCHEMA}.access_log
        SET flag = 'lilo'
        WHERE log_date = %s
          AND flag = 'pending'
        """,
        (log_date,),
    )
    lilo_updated = cursor.rowcount
    conn.commit()
    print(f"  'lilo' flag set on {lilo_updated:,} rows ({time.time()-t2:.1f}s)")

    cursor.close()
    conn.close()
    return trade_updated, lilo_updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.date.today().strftime("%Y%m%d"),
                        help="Log file date in YYYYMMDD format (default: today)")
    args = parser.parse_args()

    log_date_str = args.date  # e.g. "20260318"
    log_date_iso = f"{log_date_str[:4]}-{log_date_str[4:6]}-{log_date_str[6:]}"  # "2026-03-18"
    log_file = os.path.join(os.path.dirname(__file__), "..", "logs", f"trading_{log_date_str}.log")

    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        sys.exit(1)

    st = get_current_time()
    print(f"\nEOD Flag Updater — {log_date_iso}")
    print(f"Start: {st}\n")

    # Step 1: one pass over the file to build trade IP map
    ip_login_map = build_trade_ip_map(log_file)

    # Step 2: update flags in DB
    trade_count, lilo_count = update_flags(log_date_iso, ip_login_map)

    et = get_current_time()
    duration = et - st
    print(f"\nDone in {duration}")
    print(f"  trade: {trade_count:,}  |  lilo: {lilo_count:,}")

    send_discord_message(
        f":white_check_mark: EOD flags updated for {log_date_iso} | "
        f"trade: {trade_count:,} | lilo: {lilo_count:,} | duration: {duration}"
    )
