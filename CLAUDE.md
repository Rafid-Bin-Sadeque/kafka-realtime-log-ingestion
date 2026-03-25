# CLAUDE.md — Kafka Learning Project

## What this project is
A hands-on Kafka learning project built by a data engineer. The goal is to understand real-time log ingestion using Kafka, simulating a trading server log pipeline with real-world volume and parsing logic.

---

## Project structure

```
kafka/
├── 01_basics/          # Phase 1 — basic producer/consumer with orders topic
├── 02_log_pipeline/    # Phase 2 — generic log file → Kafka → Postgres
├── 03_trading_pipeline/    # Phase 3 — trading server log replica pipeline
├── logs/               # Generated log files (gitignored)
├── docker-compose.yml  # Zookeeper + Kafka + Kafka UI + Postgres
├── .env                # Credentials — copy from .env.example (gitignored)
└── requirements.txt
```

---

## Infrastructure

- **Kafka:** confluentinc/cp-kafka:7.4.0, port 9092
- **Kafka UI:** port 8080
- **Postgres:** local Docker service (see docker-compose.yml), or point to your own instance via `.env`
- `POSTGRES_SCHEMA` (set in `.env`) is a schema inside the target database — not a separate DB

---

## Phase 3 — Trading Log Pipeline (main focus)

**Topic:** `trading-access-logs`, 3 partitions
**Consumer group:** `log-to-postgres`
**DB table:** `<POSTGRES_SCHEMA>.access_log_realtime`
**Partition key:** login number (guarantees ordering per user)

**Run order:**
1. `python 03_trading_pipeline/topic_setup.py` (once)
2. `python 03_trading_pipeline/db_setup.py` (once)
3. Start 3 consumer instances (Terminals 3, 4, 5): `python 03_trading_pipeline/log_consumer.py`
4. Start producer (Terminal 2): `python 03_trading_pipeline/log_producer.py`
5. Start generator (Terminal 1): `python 03_trading_pipeline/log_generator.py`
6. EOD: `python 03_trading_pipeline/eod_flag_updater.py --date YYYYMMDD`

**Key design decisions:**
- Producer filters to `cid:` lines only (~20% of total volume) — reduces Kafka load by 80%
- All rows inserted with `flag='pending'`, flipped to `trade`/`lilo` at EOD by `eod_flag_updater.py`
- This solves the look-ahead problem: trade flag requires knowing if an IP traded later in the day

---

## Conventions

- Use `execute_values` (psycopg2) for all bulk inserts
- Batch size: 500 rows or 3-second flush interval in consumers
- Always add comments explaining WHY, not just what the code does
- Log file encoding: generator writes **UTF-8**; real production files are **UTF-16**

---

## What NOT to do

- Do not create a new `monitor_lag.py` inside `01_basics/inspect_topics.py` — each phase has its own monitor

---

## Log format (for reference)

- Line types: `cid:` (login), logout, trade/order, system/monitor — only `cid:` lines go to the DB
- Format: tab + comma delimited
- Mix: ~20% cid login lines, 15% logout, 5% trade/order, 60% system/monitor
