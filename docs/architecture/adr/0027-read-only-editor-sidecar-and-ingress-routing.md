# ADR-0027: The read-only editor sidecar and host-per-agent ingress routing

- **Status:** Accepted (the editor-as-sidecar rule + the host-per-agent routing model ratified for
  the kubernetes path; realized phase-by-phase in `libs/go/workspaceprovider` under ADR-0020 — see
  Implementation status)
- **Date:** 2026-06-23
- **Deciders:** Mateo (ratified the sidecar-not-shared-service rule and the host-per-agent routing
  recommendation; grounded in research note 07 §4/§7)

## Context

A user opens a project's live worktree in a **read-only VS Code** from the Eden web app (a reusable
tab) and from the desktop app (their native VS Code, ssh-remote), under **one UI contract** that
resolves identically on docker (local demo) and kubernetes (production). The gateway already owns
that one substrate-agnostic seam: `GET /sessions/{id}/editor` forms `<EditorURLBase>/?folder=<worktree>`
and nothing else (`apps/agentgateway/internal/gateway/editor_handler.go`); an empty `EditorURLBase`
returns 503 (the editor is simply not offered). No field on the wire is a credential. So every
substrate below is just "stand up a read-only code-server that can see the worktree, and point
`EditorURLBase` at it." The local docker path is BUILT and live-verified — a sibling code-server
container shares `/workspace` read-only via `--volumes-from base-devcontainer:ro` (07 §3).

The kubernetes path is the open piece. The per-project editor is a **dynamic per-agent** workload:
it must see *that agent's* worktree. In kubernetes the agent worktree is a writable `emptyDir` in
the agent pod (`workspaceprovider/kubernetesadapter/lifecycle.go` `buildPod`/`buildVolumes`). An
`emptyDir` is pod-scoped: a *separate* code-server Deployment cannot see it without RWX shared
storage (NFS/CephFS). So the editor does **not** belong in the static platform `Catalog()` (the
fixed chart: agentgateway + agent-runtime). Research note 07 §4 designed the faithful analog and
§7 filed three open decisions (OD-EDITOR-1 routing, OD-EDITOR-2 desktop read-only, OD-EDITOR-3 lib
ownership of the local sibling). This ADR rules the kubernetes shape so the library pipeline can
build it: it is an **exported-surface change to a crown-jewel lib** (a new `WorkspaceSpec` field),
which is a contract revision (ADR-0016 §1) and the cardinal sin (10 §9) unless taken through the
full ADR-0020 gate — hence an architecturally significant ruling, not an autonomous edit.

## Decision

### 1. The editor is a read-only SIDECAR in the agent pod, never a shared service

On kubernetes, add a **read-only code-server sidecar container to the agent pod**, mounting the
SAME workdir `emptyDir` with `readOnly: true`. This is the exact analog of the local
`--volumes-from base-devcontainer:ro`: co-located with the worktree, read-only, zero shared-storage
requirement. The workdir `emptyDir` is now mounted **twice** — writable by the workspace container,
read-only by the editor container. Read-only is **structural, not advisory**: the `readOnly: true`
volumeMount means the editor process *cannot* write the worktree (07 §6); it is not "a VS Code told
to behave." The sidecar inherits the agent namespace's default-deny egress NetworkPolicy — it serves
files, it does not dial out. `--auth none` is acceptable ONLY behind the gateway/ingress auth layer;
a naked public ingress MUST add oauth2-proxy / the gateway JWT in front (07 §6).

### 2. The spec surface: `WorkspaceSpec.Editor *EditorSpec`, gated by `CapEditorSidecar`

The sidecar is selected by ONE additive, capability-gated `WorkspaceSpec` field, following the
**exact** precedent of `Entrypoint`/`CapWorkloadPod` (ADR-0022 §4): `WorkspaceSpec.Editor *EditorSpec`,
where `EditorSpec{Image, Port, Resources}` is DATA (the code-server image, the served port, optional
resource caps). **`nil ⇒ byte-identical pods`** — every existing consumer is unaffected; the editor
path is ADDITIVE and spec-selected. `EditorSpec` carries **NO secret** (the canary redaction property
must hold — it is a viewer image + port, never a credential). A new closed-taxonomy capability
`CapEditorSidecar` declares which substrates realize it (kubernetes via the sidecar; docker via the
sibling per §4; a minimal distro may declare it absent and the feature degrades, not breaks — 05 §3).

### 3. Routing — HOST-PER-AGENT ingress (`<agent-id>.editor.<domain>`), wildcard DNS + TLS

OD-EDITOR-1 is **resolved: host-per-agent**. Each agent's editor is exposed by a per-agent `Service`
on the editor port and an `Ingress` routing `<agent-id>.editor.<domain>` to it, backed by a **wildcard
DNS record + wildcard TLS certificate** (`*.editor.<domain>`). The gateway then derives `EditorURLBase`
per agent from the agent's host rather than from one static env. This is the cleanest **origin
isolation** (each agent is its own web origin — cookies, storage, and code-server's same-origin
assumptions are per-agent by construction) and needs **no code-server base-path reconfiguration**.

The rejected alternative — **path-per-agent** (`editor.<domain>/<agent-id>/`) — needs code-server's
base-path / proxy-prefix support and an ingress path-rewrite, which is more fragile: code-server's
asset and websocket URLs must be rewritten consistently, every agent shares one origin (weaker
isolation), and the proxy rewrite is a standing source of subtle breakage. Host-per-agent trades a
wildcard-DNS+TLS setup (a one-time platform cost) for no per-request rewriting and true isolation —
the better trade for a per-agent dynamic workload.

### 4. The library owns BOTH siblings — OD-EDITOR-3 resolved: YES

OD-EDITOR-3 is **resolved: the `workspaceprovider` library owns the local docker sibling too.** The
same `Editor *EditorSpec` drives the dockeradapter to run the read-only sibling editor (the
`--volumes-from … :ro` analog), removing today's asymmetry where the local editor is wired outside
the lib in `deploy/ctl.sh`. One spec field, one capability, both adapters — symmetry across substrates
is the contract, exactly as `Entrypoint` realizes on both. (The dockeradapter realization is a later
phase of this same library workstream; the architecture freezes the surface now.)

### 5. The client seam grows `CreateService` + `CreateIngress`

Exposing the sidecar per agent needs a `Service` and an `Ingress`, which the bounded `kubernetesClient`
seam (`kubernetesadapter/client.go`) does not yet have. Both are ADDED to the seam (the
`k8s.io/api/networkingv1` `Ingress` type is already a direct dependency, used for `NetworkPolicy`).
The existing namespace-cascade rollback already covers them (a `Service`/`Ingress` created in the
workspace namespace is reaped when the namespace is deleted — no new rollback path). The seam is the
**bounded SDK surface**, not a consumer port, so the ≤5-method ceiling does not apply to it (it is
explicitly carved out as the auditable client-go slice); but if the addition is judged to bloat it,
the seam SPLITS along the resource boundary rather than growing unboundedly (10 §10).

### 6. Desktop ssh-remote (OD-EDITOR-2) is referenced, not ruled here

OD-EDITOR-2 (how an ssh-remote VS Code is held read-only) stays **open** and independent: it shares
only the `sshHost` wire field already on the editor contract and can land separately (07 §5). This
ADR does not rule it; it remains in the open-decisions register.

## Consequences

- A user opens a per-agent read-only VS Code on kubernetes exactly as on docker — one UI contract,
  the only difference being the per-agent ingress host vs `localhost`.
- `workspaceprovider` grows ONE additive field + ONE capability + TWO client-seam methods — a
  deliberate, gated surface expansion (a contract revision: un-freeze → extend → re-record
  `.apibaseline` → re-freeze), not scope creep: the editor sidecar is pod lifecycle, which is the
  one place this library owns.
- The platform takes on a wildcard-DNS + wildcard-TLS obligation for `*.editor.<domain>` (the
  host-per-agent cost), in exchange for origin isolation and no code-server base-path rewriting.
- The gateway's editor handler gains a per-agent `EditorURLBase` derivation (resolve the editor
  origin from the agent's host) — a small, separate follow-up on the already-shipped seam.
- OD-EDITOR-1 and OD-EDITOR-3 move to Resolved; OD-EDITOR-2 stays open.

This ADR extends ADR-0016 (the `workspaceprovider` contract it revises) and ADR-0022 §4 (the
`Entrypoint`/`CapWorkloadPod` additive precedent it follows verbatim); it is the parent ruling for
the editor-sidecar library workstream, built phase-by-phase under ADR-0020.

## Implementation status

- **Phase 1 — architecture + ADR + TDD-red (this change):** the ADR ruling; the additive
  `EditorSpec` + `WorkspaceSpec.Editor` + `CapEditorSidecar` surface; `CreateService`/`CreateIngress`
  on the bounded client seam (stubs, filled in implementation); the `.apibaseline` rebaselined
  (additive/neutral, NOT a break); `caseEditorSidecar` added to the conformance suite (RED before
  the real body, mirroring `caseEntrypointWorkloadPod`).
- **Pending:** the kubernetesadapter sidecar + per-agent `Service`/`Ingress` realization (with a REAL
  k3d integration test, no mocks); the dockeradapter sibling realization (§4); the gateway per-agent
  `EditorURLBase` derivation; OD-EDITOR-2 (desktop read-only).
