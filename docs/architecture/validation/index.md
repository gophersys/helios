# Validation

Five-stage firmware validation system. Start with [Stages Overview](stages-overview.md) for the big picture, then [System Architecture](system.md) for implementation details.

| Document | Description |
|----------|-------------|
| [Stages Overview](stages-overview.md) | Quick reference: what each stage tests, hardware, triggers, timing |
| [System Architecture](system.md) | Full system architecture: runners, pipeline controller, MTIB, build service |
| [Stage 1: Software Tests](stage1-software-tests.md) | Stub drivers, native_sim, CI |
| [Stage 2: Driver HW Tests](stage2-driver-hw-tests.md) | Driver hardware tests, dev-kit fixtures |
| [Stage 3: Integration Tests](stage3-integration-tests.md) | concord_harness, instrumented firmware |
| [Stage 4: Product Tests](stage4-product-tests.md) | Black-box product validation, regression |
| [Stage 4: FUOTA Flow](stage4-fuota-flow.md) | FUOTA validation lifecycle (12-step) |
| [Stage 4: PR Flow](stage4-pr-flow.md) | PR validation firmware build matrix |
| [Stage 5: FUOTA Tests](stage5-fuota-tests.md) | PR validation + OTA verification (< 15 min) |
| [Test Runner](test-runner.md) | Test runner architecture + execution stack |
