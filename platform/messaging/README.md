# platform/messaging

Message brokers. Primary: NATS (leader) because JetStream covers both
pub/sub and durable queues with a single cluster and very low operational
cost. Optional: Kafka when a real event-sourcing workload arrives.

Status: stub.

TODO:
- Pin NATS helm chart version (nats-io/nats).
- Enable JetStream with persistence.
- Wire NATS accounts per tenant app and emit NATS creds via ExternalSecret.
- Do NOT install Kafka until a concrete use case (Debezium, stream
  processing) demands it.
