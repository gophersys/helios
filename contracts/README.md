# contracts

The app–platform interface. Apps never talk to `platform/*` implementations
directly — they declare their needs via the contracts here, and the platform
fulfills them.

## Why this exists

The point of `platform/services/` is to let apps get a Postgres, an ingress,
an observability hookup, and so on, without knowing how the platform built
them. Contracts are the **stable interface** that lets us swap the
implementation underneath without touching the apps.

Example: today `contracts/databases.md` says "declare a `Database` CR; receive
a Secret named `<project>-<app>-db-credentials`." Tomorrow we swap
CloudNativePG for Neon — the CR stays identical, the Secret shape stays
identical, apps notice nothing.

## One file per contract

| Contract              | Fulfilled by                                                 |
|-----------------------|--------------------------------------------------------------|
| `observability.md`    | `platform/services/observability/`                           |
| `secrets.md`          | `platform/core/secrets-operator/`                            |
| `databases.md`        | `platform/services/databases/*`                              |
| `ingress.md`          | `platform/core/ingress/` + `platform/core/cert-manager/`     |
| `identity.md`         | `platform/services/identity-sso/`                            |
| `messaging.md`        | `platform/services/messaging/*`                              |

## What a contract document contains

Every contract .md follows this outline:

1. **Abstract** — one paragraph: what the app gets, what it has to do.
2. **Interface** — the concrete shape: CRDs used, env var names, label
   conventions, Secret formats. This is the app-facing surface.
3. **Guarantees** — what the platform promises (availability, backup,
   upgrade policy).
4. **Caveats** — what the platform does NOT promise (rate limits, cross-AZ
   latency, etc.).
5. **Example** — minimal working example of an app consuming this contract.

## Rules

- Contracts are versioned in the repo via git history. Breaking changes to
  a contract bump the contract's front-matter version and require a
  migration note.
- A contract can add fields freely (backward-compatible); only removing or
  changing a field's semantics is a breaking change.
- An app reads its contracts once at scaffold time (via
  `brain/.claude/scripts/scaffold.sh app ...`) and treats them as law.

## Status

Today: every contract is a stub with the outline filled in but most
sections marked TBD. Populated in a later pass as real apps consume the
corresponding platform service.
