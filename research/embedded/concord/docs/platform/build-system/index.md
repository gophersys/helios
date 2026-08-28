---
min_role: DEVELOPER
---
# Build System

Compiles firmware from source, produces flashable hex files, and stores artifacts in MinIO. The build service orchestrates compilation across worker nodes using a two-layer product build system.

- [Build Service](build-service.md) — the orchestration engine that dispatches builds to workers
- [Product Builds](product-builds.md) — how the two-layer build system (base + variant) works
- [Artifact Contract](artifact-contract.md) — what a build produces and where it lands in MinIO
