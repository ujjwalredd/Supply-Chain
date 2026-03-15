---
name: kafka-diagnosis
description: Diagnose Kafka consumer lag, DLQ spikes, and producer silence in the supply chain platform
---

## System Context

Kafka runs as a single broker (container: `supply-chain-kafka`, port 9092 internal).
Zookeeper: `supply-chain-zookeeper`, port 2181.
Schema Registry: `supply-chain-schema-registry`, port 8081.

## Topics

| Topic | Purpose | Normal Lag |
|---|---|---|
| `supply-chain-events` | Order events from OpenBoxes/producer | < 100 messages |
| `supply-chain-dlq` | Dead letter queue — failed messages | Should be 0 |

## Consumer Groups

- `pg-writer` — consumes `supply-chain-events`, writes to PostgreSQL
- `ksqldb-*` — ksqlDB stream processors (tumbling windows)

## Diagnosing Consumer Lag

The `kafka_guardian` heartbeat shows: `lag_check|dlq=<N>|age=<Ns>`

- `dlq=0` → normal
- `dlq > 0` → messages failed processing → check PostgreSQL `pg_writer` container logs
- `age > 60s` → producer is silent (no new events in 60s) → check `supply-chain-producer` container
- Lag > 2000 → CRITICAL, `pg-writer` is stuck or PostgreSQL is slow

## Common Failure Patterns

| Symptom | Root Cause | Fix |
|---|---|---|
| DLQ growing | Schema validation failures | Check Schema Registry compatibility |
| Lag spike + plateau | pg-writer crashed | Check `supply-chain-pg-writer` container logs |
| Producer silence | OpenBoxes connector down | Check `supply-chain-openboxes-connector` |
| Lag growing indefinitely | PostgreSQL connection pool exhausted | Check `database_health` agent for connection count |

## Self-Healing Actions

1. DLQ > 10 → alert HIGH, check pg-writer logs, issue correction to kafka_guardian
2. Lag > 5000 → consider restarting `pg-writer` container (this is handled by kafka_guardian directly)
3. Producer silence > 5min → check if it's expected (no orders) or a crash

## Reading Lag from Heartbeat

The `kafka_guardian` agent writes its findings to the heartbeat `current_task` field.
Format: `lag_check|dlq=<N>|age=<N>s`
- `dlq=0|age=4s` → completely healthy
- `dlq=5|age=120s` → 5 DLQ messages, last event 2 min ago

## Critical Rules

- Kafka lag is EXPECTED during startup (first 2-3 minutes) — do not alert during startup window
- DLQ messages are PERMANENT failures — they will NOT self-resolve without human inspection
- Consumer group rebalancing causes brief lag spikes — wait 30s before escalating
