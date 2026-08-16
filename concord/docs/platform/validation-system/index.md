---
min_role: DEVELOPER
---
# Validation System

Schedules and executes firmware tests across the five-stage validation flow. Each stage targets progressively deeper integration — from host-side unit tests (Stage 1) through full FUOTA verification (Stage 5) on physical hardware.

## Components

- **Test runner** — `libs/python/corekinect/test/runner.py`. Drives the per-stage test execution lifecycle (preflight, pytest, reporting).
- **autoconf plugin** — `libs/python/corekinect/test/autoconf.py`. The pytest plugin that reads `concord.yaml`, imports the `Fixture` subclass referenced by `fixture.module`, and binds it to the live MTIB client.
- **Fixture lib** — `libs/python/corekinect/fixture/`. The typed fixture-declaration framework — `Fixture` base class, `ADC`/`GPIO`/`UART`/`JLink`/`Power` declarative wrappers, AST extractor, MTIB topology limits.
- **Scheduler** — `apps/backend/http-api/src/api/v2/runs/scheduler.py`. Picks up build runs and dispatches K8s Jobs.
- **Validation Job template** — `apps/backend/http-api/assets/templates/validation_job.yaml`. The K8s Job spec rendered per validation run.

## Related docs

- [Fixture designs](../../fixtures/designs.md) — per-package fixture metadata extracted from the test app
- [Manufacturing system](../../manufacturing/index.md) — sister system for production-line testing
