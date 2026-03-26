# Build System

Architecture documents for the Concord firmware build system — from source code to deployable artifacts.

| Document | Description | Status |
|----------|-------------|--------|
| [Build Service](build-service.md) | Core build orchestrator: gRPC + HTTP, MinIO storage, Bitbucket webhooks | Active |
| [Builder Nodes](builder-nodes.md) | K8s DaemonSet for distributing builds across labeled nodes | Active |
| [Product & Build System](product-build-system.md) | Two-layer build redesign: ck_boards integration, product discovery, runner + hook architecture | Draft |
| [Artifact Contract](artifact-contract.md) | Self-describing build.json manifest, stage input contracts, ArtifactResolver | Draft |
