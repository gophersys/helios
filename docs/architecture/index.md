# Architecture

System design for the Concord platform. Three domains: platform infrastructure, validation system, and build system.

## Reading Order

For validation (the largest domain):

1. [stages-overview.md](validation/stages-overview.md) — Quick reference for all 5 stages
2. [system.md](validation/system.md) — Comprehensive system architecture
3. Pick a stage file for deep-dive

## Platform

Cross-cutting infrastructure and shared services.

| Document | Description |
|----------|-------------|
| [unified-platform.md](platform/unified-platform.md) | System unification spec: manufacturing + validation + build integration |
| [hardware-registry.md](platform/hardware-registry.md) | Node, Fixture, TestBench model relationships and gaps |
| [log-streaming.md](platform/log-streaming.md) | Log capture: K8s Job → Reporter → MinIO → WebSocket → Frontend |
| [ci-pipeline.md](platform/ci-pipeline.md) | CI pipeline flow: trigger → K8s Job → result reporting |
| [corecloud-library.md](platform/corecloud-library.md) | CoreCloud Python SDK restructuring (v0.9 → v1.0) |

## Validation

Five-stage firmware validation system.

| Document | Description |
|----------|-------------|
| [stages-overview.md](validation/stages-overview.md) | Quick reference: what each stage tests, hardware, triggers, timing |
| [system.md](validation/system.md) | Full system architecture: runners, pipeline controller, MTIB, build service |
| [stage1-software-tests.md](validation/stage1-software-tests.md) | Stage 1 Smoke: native_sim tests, stubs |
| [stage2-driver-hw-tests.md](validation/stage2-driver-hw-tests.md) | Stage 2 Silicon: driver HW tests, dev-kit fixtures |
| [stage3-integration-tests.md](validation/stage3-integration-tests.md) | Stage 3 Integration: concord_harness, instrumented firmware |
| [stage4-product-tests.md](validation/stage4-product-tests.md) | Stage 4 Nightly: black-box product validation |
| [stage4-fuota-flow.md](validation/stage4-fuota-flow.md) | FUOTA validation lifecycle (12-step) |
| [stage4-pr-flow.md](validation/stage4-pr-flow.md) | PR validation firmware build matrix (8 builds) |
| [stage5-gate-tests.md](validation/stage5-gate-tests.md) | Stage 5 Gate: PR validation + FUOTA (< 15 min) |
| [test-runner.md](validation/test-runner.md) | Test runner architecture + execution stack |

## Build

Firmware build orchestrator.

| Document | Description |
|----------|-------------|
| [build-service.md](build/build-service.md) | BuildEngine library, gRPC + HTTP interfaces, MinIO storage |
| [builder-nodes.md](build/builder-nodes.md) | DaemonSet-based build worker deployment on WSL/K3s nodes |
| [product-build-system.md](build/product-build-system.md) | Two-layer build redesign: ck_boards integration, product discovery, runner + hook |
| [artifact-contract.md](build/artifact-contract.md) | Self-describing build.json manifest, stage input contracts, ArtifactResolver |
