# ADR-0006: Local-first hosting posture; hosted tier later on the same ports

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo

## Context

Where do the control plane and user project monorepos live in v1? Options: local-first
(`eden up`); Eden-hosted SaaS from day 1; desktop-first. Hosted-first front-loads tenancy,
billing, and liability work before the platform has proven itself on itself; the corpus's
substrate design (`workspaceprovider`, environment ≠ platform) was built for run-anywhere.

## Decision

v1 is **local-first**: `eden up` runs the full platform on the user's machine (docker-compose
substrate) or cluster (kubernetes substrate). Projects, monorepos, and credentials live with the
user. The Eden-hosted multi-tenant SaaS is a later milestone running the **same artifact** on the
same ports — staging≡production proof of P6 at product scale.

## Consequences

- Dogfooding is unblocked immediately (L2 registers the eden repo as project #1 on a local
  deployment).
- Tenancy entities and keys exist from day 1 but enforcement is deferred (07 §6) — hosted tier
  becomes policy + deployment work, not a remodel. 🔶 to be validated at that milestone.
- Stripe/F3 charging scope deferred (OD-6); v1 FinOps is provider-spend + token metering only.
- The desktop app remains a shell over the same bundle, not a separate posture.
