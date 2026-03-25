# kafka-trading-log-pipeline

A hands-on Kafka learning project that simulates a **real-time trading server log pipeline** — from log generation through Kafka to Postgres.

Built in three phases, each layering more complexity. Phase 3 replicates a production-grade pattern: high-volume log ingestion, producer-side filtering, parallel consumers, and an EOD batch flag update.

## What's inside

```
Zookeeper    → Kafka broker coordination
Kafka        → message broker (3-partition topic, ~110 messages/sec)
Kafka UI     → web interface to inspect topics and consumer groups
Postgres     → destination database for parsed log rows
```

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker Desktop | 4.x+ | https://www.docker.com/products/docker-desktop |
| Python | 3.10+ | https://www.python.org/downloads |

---

## Quickstart

### 1. Clone the repo
```bash
git clone <repo-url>
cd kafka-trading-log-pipeline
```

### 2. Configure environment
```bash
cp .env.example .env
```
Edit `.env` with your Postgres credentials (defaults match `docker-compose.yml`).

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the infrastructure
```bash
docker compose up -d
```

### 5. Run Phase 3 — trading log pipeline

Open 5 terminals from the project root:

| Terminal | Command | What it does |
|----------|---------|--------------|
| T1 | `python 03_trading_pipeline/topic_setup.py` | Create Kafka topic (run once) |
| T2 | `python 03_trading_pipeline/db_setup.py` | Create Postgres table (run once) |
| T3 | `python 03_trading_pipeline/log_consumer.py` | Consumer — partition 0 |
| T4 | `python 03_trading_pipeline/log_consumer.py` | Consumer — partition 1 |
| T5 | `python 03_trading_pipeline/log_consumer.py` | Consumer — partition 2 |
| T6 | `python 03_trading_pipeline/log_producer.py` | Producer (start after generator) |
| T7 | `python 03_trading_pipeline/log_generator.py` | Log generator — start this first |

### 6. End of day (optional)
```bash
python 03_trading_pipeline/eod_flag_updater.py --date YYYYMMDD
```
Flips `flag` from `pending` → `trade` or `lilo` based on a single pass over the log file.

---

## URLs

| URL | What it is |
|-----|-----------|
| http://localhost:8080 | Kafka UI — inspect topics, messages, consumer lag |
| http://localhost:9092 | Kafka broker |
| http://localhost:5432 | Postgres |

---

## Project structure

```
kafka/
├── 01_basics/                  ← Phase 1: producer/consumer fundamentals
│   ├── producer.py
│   ├── consumer.py
│   └── inspect_topics.py
├── 02_log_pipeline/            ← Phase 2: generic log file → Kafka → Postgres
│   ├── log_generator.py
│   ├── log_producer.py
│   ├── log_consumer.py
│   ├── db_setup.py
│   └── monitor_lag.py
├── 03_trading_pipeline/        ← Phase 3: high-volume trading log pipeline
│   ├── log_generator.py        ← simulates ~550 lines/sec log output
│   ├── log_producer.py         ← tails file, filters to cid: lines, sends to Kafka
│   ├── log_consumer.py         ← parses + bulk-inserts to Postgres (batch=500)
│   ├── topic_setup.py          ← creates topic with 3 partitions
│   ├── db_setup.py             ← creates table in POSTGRES_SCHEMA
│   ├── eod_flag_updater.py     ← EOD job: flips pending → trade/lilo
│   └── monitor_lag.py          ← shows per-partition consumer lag
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── generate_doc.py             ← generates kafka_explained.docx
```

---

## Key design decisions

**Filter at the producer, not the consumer**
Only `cid:` login lines (~20% of total volume) are sent to Kafka. This reduces broker load and consumer work by 80%, which matters at ~550 lines/sec.

**Partition key = login number**
All messages for the same login always go to the same partition. This guarantees ordering per user and allows 3 consumers to work in parallel without stepping on each other.

**Pending → trade/lilo at EOD**
Rows are inserted with `flag='pending'`. The trade flag can only be determined after seeing whether an IP placed a trade later in the day — a look-ahead problem. The EOD updater solves this with two SQL UPDATEs instead of re-processing the entire file.

---

## Monitor consumer lag

```bash
python 03_trading_pipeline/monitor_lag.py
```

```
=== Lag Report ===
Topic : trading-access-logs
Group : log-to-postgres

  Partition 0 | committed=14,823  latest=14,823  lag=0    [OK]
  Partition 1 | committed=14,901  latest=14,901  lag=0    [OK]
  Partition 2 | committed=14,876  latest=14,876  lag=0    [OK]

  Total lag: 0 messages
```

---

## Tips

- **Kafka UI** at http://localhost:8080 is the easiest way to see messages flowing through topics
- Start the generator before the producer — the producer tails the file and waits if it doesn't exist yet
- Run 3 consumer instances to match the 3 partitions; a 4th consumer will sit idle
- `POSTGRES_SCHEMA` in `.env` controls which schema the table is created in — set it to anything you like
- Phase 1 and 2 are self-contained — you can run them independently without Phase 3 infrastructure
