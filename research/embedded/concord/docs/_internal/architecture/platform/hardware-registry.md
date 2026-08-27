# Hardware Registry Architecture

## Overview

Concord tracks test hardware through four related models. Each serves a distinct purpose, but together they form a unified registry of physical infrastructure.

## Models

### Node

The lowest-level representation: a compute node (typically an MTIB board) in the K3s cluster.

- **Identity**: `hostname` (K8s node name, unique), `ipAddress`
- **Classification**: `type` (MANUFACTURING | VALIDATION), `hardwareRevision` ("REV1.2")
- **Lifecycle**: `status` (ONLINE | OFFLINE | MAINTENANCE | ERROR)
- **K8s integration**: Auto-deploys MTIB server pod on creation, manages labels/taints
- **API**: `/v2/nodes`

Nodes are infrastructure primitives. They know nothing about what product they test or what fixture they sit in.

### FixtureSlot

The bridge between a Node and a Fixture. A slot is a numbered position in a fixture that can hold one Node.

- **Constraint**: `nodeId` is `@unique` -- a node can only be in one slot at a time
- **Lifecycle**: Slots exist even when empty (`nodeId = null`)
- **Manufacturing use**: A fixture with 8 slots maps 8 MTIBs testing the same product

### Fixture (Manufacturing)

A physical fixture assembly used on the manufacturing floor. Groups multiple Nodes (via FixtureSlots) that test the same Product.

- **Product-scoped**: `productId` FK to Product (required)
- **Multi-slot**: A fixture has N FixtureSlots, each holding one Node
- **Sessions**: Manufacturing Sessions reference a Fixture
- **Deployments**: Software deployments (MTIB server) target fixtures
- **API**: `/v2/fixtures`

Example: "Theta MFG Fixture 1" has 8 slots, each with an MTIB running manufacturing POST tests on Theta boards.

### FixtureDesign (Validation)

A versioned hardware design specification for a validation fixture. Describes the PCB wiring, GPIO mapping, and capabilities of the test jig.

- **Product-scoped**: `product` (string, e.g. "alpha") -- not an FK, just a label
- **Versioned**: `revision` (e.g. "1.2") tracks hardware iterations
- **Profile template**: `profileTemplate` (JSON) is the default fixture profile -- power config, GPIO mapping, UART paths, J-Link SNRs
- **Capabilities**: String array of hardware features: `["button", "peltier", "charger_relay", "ppg_servo"]`
- **API**: `/v2/validation/designs`

Example: "alpha-fixture-v1.2" describes the REV 1.2 MTIB wiring for Alpha B0 DUTs.

### TestBench (Validation)

A specific validation workstation: one MTIB + one DUT + one fixture design. The operational unit for running validation tests.

- **Product link**: `productId` FK to Product (optional, preferred for scheduling)
- **Fixture design**: `fixtureDesignId` FK to FixtureDesign (provides profile template + capabilities)
- **DUT identity**: `dutDeviceId`, `dutSnr`, `dutImei`, `dutIccids` -- the specific device under test
- **Hardware paths**: `mtibAddress`, `uartAppPath`, `uartCommsPath`, `jlinkAppSerial`, `jlinkCommsSerial`
- **Locking**: `status` (AVAILABLE | LOCKED | OFFLINE | MAINTENANCE), `lockedBy` for exclusive access during test runs
- **Profile resolution**: Merges FixtureDesign.profileTemplate + TestBench.profileOverrides + DUT info
- **API**: `/v2/validation/benches`

Example: "Alpha B0 Bench 1" at 10.4.45.33 with DUT 70B3D584C01E1FCC, using alpha-fixture-v1.2 design.

## Relationship Diagram

```
Product
├── Fixture (manufacturing)          TestBench (validation)
│   ├── FixtureSlot[0] → Node        ├── mtibAddress (direct)
│   ├── FixtureSlot[1] → Node        ├── FixtureDesign (profile template)
│   └── FixtureSlot[N] → Node        ├── Product (optional FK)
│                                     └── DUT info (device ID, SNR, etc.)
│
└── ValidationRun
    └── nodeId → Node (NOT TestBench)
```

### Key observations:

1. **Manufacturing path**: Product → Fixture → FixtureSlot → Node. Multi-slot, Node is the compute unit.
2. **Validation path**: Product → TestBench → FixtureDesign. Single-bench, TestBench bundles MTIB + DUT + design.
3. **No link between TestBench and Node**: TestBench stores `mtibAddress` as a string, not a Node FK. ValidationRun references Node directly.
4. **FixtureDesign vs Fixture**: Despite similar names, these are unrelated models. FixtureDesign is a design spec; Fixture is a physical manufacturing assembly.

## Current Gaps

### 1. TestBench has no Node FK

When an MTIB is discovered via K8s, a Node record is created. But TestBench stores the MTIB address as a plain string (`mtibAddress`). There is no FK linking TestBench to Node, so:
- Health status from Node does not propagate to TestBench
- Node discovery (`sync_nodes_from_k8s`) and bench discovery (`discover_mtibs`) are independent operations
- A bench can reference an MTIB that has no Node record, and vice versa

### 2. discover_mtibs() does not create Node records

`discover_mtibs()` in `benches.py` queries K8s for nodes with label `node.corekinect.com/type=mtib` and returns unregistered ones. But it only checks against TestBench records, not Node records. It does not create anything -- it is read-only.

Meanwhile, `sync_nodes_from_k8s()` in `nodes.py` queries K8s for arm64 nodes and compares against Node records. These two discovery functions operate independently.

### 3. get_bench_profile() does not include Product.metadata

The profile resolution merges FixtureDesign.profileTemplate + TestBench.profileOverrides + DUT info, but does not include Product.metadata. Product metadata contains `deviceTypeId`, `deviceVariantId`, `appIds`, and `coreCloudEnv` -- all needed by validation tests.

### 4. Manufacturing Fixtures do not use FixtureDesign

Manufacturing Fixtures have their own `metadata` JSON but no link to FixtureDesign. The profile template concept (GPIO mapping, power config) applies equally to manufacturing, but there is no shared schema.

## Recommendations

### Short-term (no schema changes)

1. **Enhance `get_bench_profile()`** to include Product.metadata when `TestBench.productId` is set. This gives validation tests access to `deviceTypeId`, `appIds`, etc. without additional API calls.

2. **Enhance `discover_mtibs()`** to cross-reference against both TestBench and Node records, and optionally auto-create Node records for discovered MTIBs. This ensures every MTIB in the cluster has a Node record.

3. **Add Node health propagation** to TestBench status. When `check_node_health()` finds a Node offline, any TestBench with a matching `mtibAddress` should be marked OFFLINE.

### Medium-term (schema evolution)

4. **Add `nodeId` FK to TestBench**. This creates an explicit link from TestBench to Node, enabling health propagation and eliminating the string-based `mtibAddress` matching.

5. **Add `fixtureDesignId` FK to Fixture** (manufacturing). Let manufacturing fixtures reference a FixtureDesign for their profile template, unifying the profile resolution pattern across both paths.

### Long-term (full unification)

6. **Consider merging Fixture and TestBench** into a single "TestStation" model that works for both manufacturing (multi-slot) and validation (single-slot). The `type` field already exists on both. The main difference is multi-slot vs single-bench, which could be modeled as a station with 1..N slots.

## Profile Resolution Flow

Current flow for `GET /v2/validation/benches/<id>/profile`:

```
1. Load TestBench (include FixtureDesign)
2. Start with FixtureDesign.profileTemplate (or {})
3. Deep-merge TestBench.profileOverrides
4. Inject DUT info: device_id, snr, imei, iccids
5. Inject hardware paths: uart, jlink
6. Inject capabilities
7. Return merged profile
```

Recommended enhanced flow:

```
1. Load TestBench (include FixtureDesign, Product)
2. Start with FixtureDesign.profileTemplate (or {})
3. Deep-merge TestBench.profileOverrides
4. Inject DUT info: device_id, snr, imei, iccids
5. Inject hardware paths: uart, jlink
6. Inject capabilities
7. If Product exists, inject Product.metadata as "product" key
8. Return merged profile
```
