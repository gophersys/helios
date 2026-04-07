# Platform

Cross-cutting infrastructure and shared services that support manufacturing, validation, and build systems.

| Document | Description |
|----------|-------------|
| [Unified Platform](unified-platform.md) | System unification spec: manufacturing + validation + build integration |
| [Hardware Registry](hardware-registry.md) | Node, Fixture, TestBench model relationships |
| [Log Streaming](log-streaming.md) | Log capture: K8s Job to Reporter to MinIO to WebSocket to Frontend |
| [CI Pipeline](ci-pipeline.md) | CI pipeline flow: trigger to K8s Job to result reporting |
| [CoreCloud Library](corecloud-library.md) | CoreCloud Python SDK restructuring |
| [Zero-Downtime Updates](zero-downtime.md) | Graceful drain, heartbeat recovery, atomic deploys, PDBs |
