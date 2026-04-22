---
min_role: OPERATOR
---

# Glossary

Terms used throughout Concord, defined precisely.

## Core Concepts

**Product**
A hardware platform managed end-to-end by Concord. One product = one board family with one or more revisions. Everything else (builds, validation, manufacturing) hangs off a product.

**Board Revision**
A specific hardware version of a product's PCB (e.g., A0, B0, B1). Each revision can have different firmware targets, different validation configs, different manufacturing procedures.

**Product Target**
A single processor on a board revision that receives firmware. Defined by role (`app`, `comms`), SoC (`nrf52840`, `nrf9151`), and a CoreCloud Application ID.

**Stage**
A phase in the validation lifecycle. Concord defines five stages in order: Smoke, Driver, Integration, Regression, FUOTA. Each stage answers a different question about firmware quality.

**Stage Config**
Per-product configuration that maps a validation stage to a specific board revision, Git branch to watch, and signing key. Controls what gets validated, when, and how.

## Firmware & Builds

**Asset Set**
A bundle of compiled firmware files (one per product target) that represents a single buildable version. An asset set is the atomic unit that gets flashed during manufacturing or validation.

**Firmware Build**
A single compiled artifact (hex, cfw, or manifest) for one product target within an asset set.

**Build Run**
A triggered compilation job — either from a Git push (automatic), an external CI upload, or a manual trigger. Produces an asset set on success.

## Testing

**Test Package**
A versioned archive of Python test code uploaded to Concord via `corectl`. Can be type VALIDATION or MANUFACTURING. Contains one or more stage modules.

**Test Run**
A single execution of a test package against one or more DUTs. Created automatically by validation scheduling or manually by manufacturing operators.

**Run Target**
One DUT (device under test) within a test run. Maps to a physical fixture slot. Has its own pass/fail status independent of other targets in the same run.

**Test Execution**
A single test function executed on a single run target. The most granular unit of pass/fail tracking.

## Manufacturing

**Manufacturing Session**
An operator-managed production testing session bound to a specific fixture. Stays active until explicitly ended. Panels are scanned into the session one at a time.

**Panel**
A group of DUTs (typically 4) tested simultaneously in one manufacturing run. Identified by a QR code scan.

**Fixture**
A physical test rig with multiple slots. Connected to Concord via MTIB hardware. Managed by system admins.

**Fixture Slot**
A single DUT position within a fixture. Maps 1:1 to an MTIB address. Each slot independently powers, flashes, and communicates with one device.

## Hardware

**MTIB (Manufacturing Test Interface Board)**
Custom hardware that provides power control, UART communication, GPIO, ADC, and J-Link mux for one DUT slot. Connected to Concord's edge nodes via gRPC.

**DUT (Device Under Test)**
The actual hardware board being tested or manufactured. Sits in a fixture slot, controlled by an MTIB.

## Infrastructure

**Runner**
A container (K8s pod) that executes test packages against hardware. Dynamically deployed per manufacturing session or validation run.

**corectl**
CLI tool for interacting with Concord. Used to upload test packages, trigger runs, and manage local development workflows.

**Fixture Config**
A YAML file (`fixture.yaml` or `concord.yaml`) that describes the hardware setup — which MTIBs, which probes, which UARTs, which firmware to flash.

## Roles

**Operator**
Runs manufacturing sessions. Scans panels, monitors results, escalates failures. Cannot configure products or stages.

**Developer**
Writes firmware and test packages. Uploads test code via corectl. Views validation results. Cannot start manufacturing sessions or modify stage configs.

**Maintainer**
Configures products, stage configs, and test packages. Manages fixture assignments. Can do everything a developer can plus configuration.

**System Admin**
Full access. Manages users, permissions, API keys, fixtures, asset sets. Starts/stops manufacturing sessions. Deploys platform updates.
