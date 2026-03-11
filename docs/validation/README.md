# Concord Validation Documentation

Hardware/firmware validation system for embedded products. Five stages from software stubs to field monitoring.

## Reading Order (New Engineers)

1. [Stages Overview](architecture/stages-overview.md) -- Quick reference: what each stage tests, hardware, runtime, triggers
2. [Validation Philosophy](architecture/00-validation-philosophy.md) -- Why we validate this way, design principles
3. [Final Architecture](architecture/09-final-architecture.md) -- System-level architecture: runners, pipeline controller, MTIB
4. Stage implementation docs (pick your stage) -- Detailed specs for what to build
5. Alpha examples (pick your stage) -- Concrete walkthroughs with real code

## Folder Guide

| Folder | Contents |
|--------|----------|
| `research/` | Early-phase firmware and subsystem analyses (standalone, no inbound links) |
| `architecture/` | Foundation docs + per-stage implementation specifications |
| `examples/alpha/` | Worked walkthroughs for the Alpha product, one per stage |
| `interfaces/` | Component interface/contract specs (growth area) |
| `reference/` | External-facing lookups: Twister/HIL reference, test case catalogs |
| `project/` | Planning, tracking, and review artifacts |

## Full Index

### research/

| File | Description |
|------|-------------|
| [01-sigma5-firmware-analysis.md](research/01-sigma5-firmware-analysis.md) | Sigma5 firmware codebase analysis |
| [02-alpha-firmware-analysis.md](research/02-alpha-firmware-analysis.md) | Alpha firmware codebase analysis |
| [03-sensor-drivers-analysis.md](research/03-sensor-drivers-analysis.md) | Sensor driver architecture and API analysis |
| [05-mtib-server-analysis.md](research/05-mtib-server-analysis.md) | MTIB server protocol and capabilities analysis |

### architecture/

| File | Description |
|------|-------------|
| [stages-overview.md](architecture/stages-overview.md) | **Start here** — Quick reference for all 5 stages: hardware, runtime, triggers, timing |
| [00-validation-philosophy.md](architecture/00-validation-philosophy.md) | Foundation: five-stage model, design principles, strategy |
| [09-final-architecture.md](architecture/09-final-architecture.md) | System architecture: runners, pipeline controller, MTIB, build service |
| [stage1-software-tests.md](architecture/stage1-software-tests.md) | Stage 1 Smoke: native_sim tests, stubs, CI runner |
| [stage2-driver-hw-tests.md](architecture/stage2-driver-hw-tests.md) | Stage 2 Silicon: driver HW tests, dev-kit fixtures, power profiling |
| [stage3-integration-tests.md](architecture/stage3-integration-tests.md) | Stage 3 Integration: concord_harness, instrumented firmware, MTIB |
| [stage4-product-tests.md](architecture/stage4-product-tests.md) | Stage 4 Nightly: comprehensive black-box product validation |
| [stage5-gate-tests.md](architecture/stage5-gate-tests.md) | Stage 5 Gate: PR validation + FUOTA (< 15 min) |

### examples/alpha/

| File | Description |
|------|-------------|
| [stage1-alpha-example.md](examples/alpha/stage1-alpha-example.md) | Stage 1 walkthrough: LSM6DSO interface tests + VSM app tests on native_sim |
| [stage2-alpha-example.md](examples/alpha/stage2-alpha-example.md) | Stage 2 walkthrough: LSM6DSO driver HW tests on dev-kit fixture |
| [stage3-alpha-example.md](examples/alpha/stage3-alpha-example.md) | Stage 3 walkthrough: instrumented firmware integration tests on product board |
| [stage4-alpha-example.md](examples/alpha/stage4-alpha-example.md) | Stage 4 Nightly: comprehensive black-box validation (30-60 min) |
| [stage5-alpha-example.md](examples/alpha/stage5-alpha-example.md) | **Stage 5 Gate: PR validation + FUOTA (< 15 min)** |

### interfaces/

See [interfaces/README.md](interfaces/README.md) for planned component contract specs.

### reference/

| File | Description |
|------|-------------|
| [twister-hil-reference.md](reference/twister-hil-reference.md) | Twister test runner and HIL testing reference |
| [alpha-prdtst-reference.md](reference/alpha-prdtst-reference.md) | Alpha product test case catalog (PRDTST) |

### project/

| File | Description |
|------|-------------|
| [bom-validation-pipeline.md](project/bom-validation-pipeline.md) | Bill of materials for the validation pipeline |
| [cohesion-review.md](project/cohesion-review.md) | V1 cross-document consistency audit |
| [cohesion-review-v2.md](project/cohesion-review-v2.md) | V2 cross-document consistency audit |
