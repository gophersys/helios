---
min_role: OPERATOR
---
# Concord

Concord is CoreKinect's platform for building and testing embedded firmware. It compiles firmware from source, validates it on real hardware through automated test fixtures, and manages the full lifecycle from git push to production-ready binary.

## System concepts

**[Products](products/)** are the top-level unit. A product defines a piece of hardware: its board revisions, SoC targets, firmware repositories, and build configuration. Everything else — builds, validation, manufacturing — hangs off a product.

**[Builds](builds/)** compile firmware from source. When code is pushed or a PR is opened against a watched branch, Concord triggers a build run that produces hex files, DFU packages, and composite firmware archives. Each build targets a specific board revision and validation stage.

**[Validation](validation/)** tests firmware on real hardware. Five stages run in sequence — Smoke, Driver, Integration, Regression, and FUOTA — each progressively more thorough. A validation session connects to a physical device through a fixture, runs a test suite, and reports pass/fail with measurements.

**[Manufacturing](manufacturing/)** is the production end. Operators flash validated firmware onto devices using manufacturing fixtures, run POST (power-on self-test), and record serial numbers and test results per unit.

**[Fixtures](fixtures/)** are the physical test stations. Each fixture has slots where devices under test (DUTs) are connected via MTIBs (modular test interface boards). Fixtures are typed — validation fixtures run test suites, manufacturing fixtures run POST.

**[Stages](builds/build-configuration/)** control what gets built and when. Each product can configure up to five validation stages with independent trigger rules (PR push, merge, scheduled, manual) and build recipes.

## Where to start

Your role determines what you see and what you can do. The sidebar navigation adjusts automatically.

If you're setting up the platform, start with [Products](products/) — create a product, link its firmware repositories, and configure its board revisions. The [Administration](administration/) section covers user management and permissions.

If you're running tests, go to [Validation](validation/) for the queue, active sessions, and results. Manufacturing operators start at [Manufacturing](manufacturing/).

For the Python test SDK, REST API reference, and system architecture, see [Reference](reference/) and [Platform](platform/).
