# The component process — how anything enters the system

Status: v0, depth D0–D1. This is the process Mateo asked for by name: adding
a new component to the system comes FIRST; part numbers come LAST. The
process is enforced by the `sfd` tool (`tools/sfd`), not by discipline.

## The identity rule

A component's identity is its **Zephyr `compatible` string** (for example
`bosch,bme280`). An SoC's identity is its **Zephyr SoC name** (for example
`esp32c6`, `mimxrt1052`).

An orderable part number (`MIMXRT1052CVL5B`) is a **late binding** made in
P4, per product. Before that moment, part numbers do not exist in this
system. This is what lets the process be proven before any purchasing
question can distort it.

## The state machine

```
PROPOSED ─▸ SOURCED ─▸ EXERCISED ─▸ SELECTABLE ─▸ BOUND (per product, P4)
    │           │           │
    └── every transition is a tool run with recorded evidence ──┘
```

| State | Meaning | Evidence | Depth |
|---|---|---|---|
| PROPOSED | someone named a capability need | none yet | D0 |
| SOURCED | Zephyr carries a binding (and ideally a driver) for it | `sfd component add` succeeded: binding path(s) + driver path(s) @ SHA | D1–D2 |
| EXERCISED | it builds/runs in this repo's workspace | a `west build`/twister run recorded against the record | D3 |
| SELECTABLE | eligible for P4 part selection | record at D2+ and `sfd verify` green | — |
| BOUND | a part number attached, for one product | P4 fit-matrix decision, recorded in the product's SDHR | — |

Transitions only move forward. A Zephyr pin bump can DEMOTE: `sfd verify`
red on drift drops a record out of SELECTABLE until re-proven.

## The tool runs that enforce it

All runs happen inside the devcontainer, against the pinned workspace
(`ws/`). The catalog (`catalog/`) is the output — versioned, reviewed,
cited.

```
sfd component add <compatible> --zephyr ws/zephyr   # PROPOSED → SOURCED
sfd soc add <soc-name>         --zephyr ws/zephyr   # same, for SoCs
sfd verify                     --zephyr ws/zephyr   # gate: catalog vs tree
```

`component add` refuses when no binding exists upstream. That refusal is the
process working: the component is flagged as **driver-work**, costed, and
either a driver gets written or the component is not used. It is never
hidden.

## Eden seam

The `sfd` core is a library: pure transforms from a Zephyr tree to typed
YAML records. The CLI is a thin shell. Eden later imports the library (Go)
or shells the CLI; the records are the API. Nothing in the core reads
interactive input or global state.
