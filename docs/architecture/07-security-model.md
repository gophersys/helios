# 07 — Security Model

> Status: Draft · 2026-06-12 · Canonical home for: threat model, credential handling, agent
> sandboxing, clean-room verification, supply chain, tenancy, audit.

## 1. Threat model (what we defend against, ranked)

| # | Threat | Primary defense |
|---|---|---|
| 1 | **Exfiltration of user cloud credentials** (the crown jewels) | vault + never-in-agent-context rule (§2) |
| 2 | **Reward hacking** — agents gaming gates (planted test fixtures, doctored evidence) | clean-room verification (§4) |
| 3 | **Agent-introduced supply-chain compromise** (malicious/typosquatted dependencies) | locked dependency sets, SBOM, provenance (§5) |
| 4 | **Sandbox escape / lateral movement from an agent pod** | pod isolation + egress policy + dial-out-only (§3) |
| 5 | **Out-of-band tampering** with repos/infrastructure | drift detection (05 §5) + server-side gates |
| 6 | **Cross-tenant access** (hosted tier) | tenancy boundaries designed now, enforced later (§6) |
| 7 | **Secret leakage via logs/telemetry/transcripts** | un-printable Secret type + redaction by construction (§2) |

## 2. Credentials & secrets

- Connector credentials are vaulted at rest (KMS-backed), bound to their credential profile's
  declared scopes (05 §1), and reachable only through the `secrets` port.
- **Never in agent context.** Credentials are not serialized into prompts, configuration files in
  agent workspaces, or transcripts. Agents and workloads receive **short-lived, scoped tokens** minted
  per use; the vault is the only minting path and every mint is audit-logged.
- The enforcement is in the type (10 §4 ✅): `SecretReference` is the loggable handle;
  `Secret` is constructed un-printable — String/Debug/JSON/log all redact; `Use(fn)` scopes
  exposure; `Zeroize()` wipes. Telemetry and transcripts therefore redact by construction, not by
  filter lists.
- Transcripts are first-class stored objects (P9) — they are also a leak surface; transcript
  storage gets the same redaction guarantees plus retention policy per project.

## 3. Agent sandboxing

- One sandbox per agent execution: container/pod with the workspace mounted, nothing else.
- **Dial-out only** (the `management` pattern): pods open no listening sockets; they connect out
  to the broker over mTLS, receive commands, stream telemetry. ✅ prototyped in `poc/agents`.
- Egress policy per pod: model-provider endpoints + explicitly granted tool endpoints; default
  deny. Tool grants are part of the agent connector contract (F4) and recorded per Run.
- Workspace isolation: agents work in worktrees with FileLeases (02 §2); the authoritative repo
  accepts merges only through gates — an agent cannot push to `main` even from a compromised pod.
- In-app AssistantSessions (02 §1) are read-scoped F4 sessions: their tool grants cover project
  data (runs, dashboards, FinOps, drift events) but no write paths and no credential access;
  their transcripts get the same redaction-by-construction and retention treatment as Run
  transcripts (§2).

## 4. Clean-room verification (anti-reward-hack)

The verifier never runs in an environment the author wrote to (build-system invariant I5 ✅):

- Exercise (phase 6) provisions a **fresh environment**, copies only declared inputs (source +
  pinned dependencies), and runs the held-out verification suite the implementing agent never saw
  where the cell affords it (`poc/knowledge` pattern: `_verify/` suites ✅).
- Evidence carries provenance (artifact hash, environment fingerprint); gates reject evidence
  whose provenance doesn't match the artifact under decision.
- Known attack from the benchmark literature — planting `conftest.py`-style auto-discovered
  fixtures — is neutralized by fresh-environment provisioning plus declared-inputs-only copying.

## 5. Supply chain

- **Locked dependency sets per archetype**: agents may not introduce dependencies outside the
  blessed set without an `approve`-gated exception; lockfiles are gate-verified.
- SBOM emitted at Package (phase 7); license scanning gates; provenance attestation links
  artifact → Run → Spec → transcript (the full chain, 03 §5).
- Internal APIs are hardened like public ones (Bender mode 10): the Connect gateway authenticates
  and authorizes every caller including Eden's own agents — agents will find and call anything
  reachable, so nothing unauthenticated is reachable.
- Library publishing: release builds run `GOWORK=off`; the ADOPTED-only merge invariant prevents
  unpublished source from masking published versions (10 §8).

## 6. Tenancy

v1 is local-first single-tenant (ADR-0006): the user's machine/cluster is the trust boundary, and
the dominant risks are §1–§5, not cross-tenant. The hosted tier's requirements are **designed in
now**: Organization/RBAC entities exist from day 1 (02 §1), all data rows carry tenancy keys, the
vault is namespaced per organization, and per-tenant encryption is an adapter concern of the vault
port — so multi-tenancy is policy + deployment work, not a remodel. 🔶 (claim to be validated when
the hosted milestone is scoped).

## 7. Audit

Append-only audit log (S1) for: credential mints/uses, gate decisions (with evidence refs and the
signing identity — agent or human), drift remediations, policy changes, workspace access, and
admin actions. Audit events ride plane (a) telemetry but are durably stored independently of the
observability stack's retention.
