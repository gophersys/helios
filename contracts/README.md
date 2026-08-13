# contracts

The interface between an app and the platform. An app never talks to a
`platform/*` implementation directly. It declares its needs through the contracts
here, and the platform fulfills them.

## Why this exists

`platform/services/` lets an app get a Postgres, an ingress, an observability
hookup and so on, without knowledge of how the platform built them. A contract is
the **stable interface** that lets us change the implementation underneath
without a change to the app.

Example: today `contracts/databases.md` says "declare a `Database` CR; receive a
Secret named `<project>-<app>-db-credentials`." Tomorrow we replace CloudNativePG
with Neon. The CR stays identical and the Secret shape stays identical, so no app
sees a change.

## One file per contract

Each contract names its own implementation in its front-matter. That front-matter
is the source of truth. To print the current set:

```
grep -H '^fulfilled_by:' contracts/*.md
```

A table stood here and listed the same 6 values by hand. It drifted in both
directions. It gave `ingress.md` the paths `platform/core/ingress/` and
`platform/core/cert-manager/`, and neither directory exists. It also gave
`messaging.md` the path `platform/services/messaging/*`, where the contract
itself reads `platform/services/messaging/nats/`.

## What a contract document contains

Every contract `.md` file follows this outline:

1. **Abstract** — one paragraph: what the app gets, and what it must do.
2. **Interface** — the concrete shape: the CRDs used, the env var names, the
   label conventions and the Secret formats. This is the app-facing surface.
3. **Guarantees** — what the platform promises: availability, backup and upgrade
   policy.
4. **Caveats** — what the platform does NOT promise, for example rate limits and
   cross-AZ latency.
5. **Example** — a minimal working example of an app that consumes this contract.

## Rules

- Git history versions the contracts. A breaking change to a contract bumps the
  version in the contract's front-matter and needs a migration note.
- A contract can add a field freely, because that is backward-compatible. Only
  the removal of a field, or a change to the semantics of a field, is a breaking
  change.
- An app reads its contracts once, at scaffold time (through
  `brain/.claude/scripts/scaffold.sh app ...`), and treats them as law.

## Status

Today every contract is a stub. The outline is filled in, but most sections are
marked TBD. They are populated in a later pass, as real apps consume the matching
platform service.
