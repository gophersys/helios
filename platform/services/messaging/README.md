# platform/services/messaging

Message brokers — pub/sub, durable queues, request/reply.

## Components

- `nats/` — NATS JetStream (default, covers pub/sub + queues + KV + object).

Do NOT add Kafka until a concrete event-sourcing workload (Debezium CDC,
stream processing) demands it.

## Fulfills
- `contracts/messaging.md` — how apps publish/consume and request NATS
  accounts + credentials.

## Status

STUB.
