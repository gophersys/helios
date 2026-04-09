---
min_role: DEVELOPER
---
# Validation System

Schedules and executes firmware tests across the five-stage validation flow. Each stage targets progressively deeper integration — from host-side unit tests (Stage 1) through full FUOTA verification (Stage 5) on physical hardware.

- [System Design](system-design.md) — architecture of the validation engine, job lifecycle, and result aggregation
- [Test Runner](test-runner.md) — how tests are dispatched to fixtures and executed inside K8s Jobs
