# Read-only VS Code editor over a project worktree: a substrate-portable design

> **Class:** research note (docs/README.md §1) · **Research date:** 2026-06-23 · **Status:** PARTIAL —
> the local web path is BUILT + live-verified; the kubernetes sidecar path and the desktop ssh-remote
> path are DESIGNED here, not yet built. Point-in-time findings; never canonical — promoted into specs
> with a citation, not edited here. **Promotes into:** a `workspaceprovider` editor-sidecar capability
> (an ADR + a `WorkspaceSpec` surface change) and the agentgateway editor contract.

**Domain:** how a user opens a project's live worktree in a **read-only VS Code** from the Eden web app
(a reusable tab) and from the desktop app (their native VS Code, ssh-remote), with **one UI contract**
that works identically on docker (local demo) and kubernetes (production). **Audience:** whoever builds
the kubernetes editor sidecar and the desktop ssh path on top of the shipped web foundation.

## 1. Intent

> "I can open a view-only VS Code window running inside an isolated sandbox that lets me view, in real
> time, any branch — but view only — so I can then reuse that window to open the monorepo for that
> project at any point, and the chat window next to it. In web it opens a new tab; in desktop mode it
> opens the user's VS Code app sshd into the right remote environment endpoint. This must also work in
> kubernetes."

Two hard requirements fall out: **read-only** (the editor never mutates the agent's worktree — it is a
viewer, not a second writer racing the supervisor) and **substrate-portable** (the same UI affordance
resolves to a working editor on docker locally and on kubernetes in production).

## 2. The contract (✅ BUILT) — `GET /sessions/{id}/editor`

The gateway owns ONE substrate-agnostic seam. It forms a per-project URL and nothing else:

```
GET /sessions/{id}/editor →
  { "url": "<EditorURLBase>/?folder=<worktree>",   // read-only web VS Code, a new tab
    "worktreePath": "<worktree>",                  // the supervisor's materialized CWD
    "sshHost": "<EditorSSHHost or "">" }            // optional ssh-remote host for the desktop URI
```

- The worktree is resolved through the **same seam the workspace file API uses**
  (`resolveWorkspaceRoot` → the agent's materialized CWD), so the editor opens exactly the directory the
  right-panel file tree renders — no second notion of "the project's files."
- `EditorURLBase` empty → **503** (the editor is simply not offered for that deployment); the UI hides
  or falls back. This is the only knob that differs across substrates.
- No field is a credential: the URL carries no token; `sshHost` is a host alias the user's VS Code
  resolves. (`apps/agentgateway/internal/gateway/editor_handler.go`, `editor_test.go`.)

The frontend (`workspace/+page.svelte`, `ProjectTopBar.svelte`) is network-free presentation: web →
`window.open(url, 'eden-vscode')` (a **named** window, so re-opening another project re-points the same
tab — "reuse this window"); desktop (Tauri, `isDesktop()`) with an `sshHost` →
`vscode://vscode-remote/ssh-remote+<host><worktreePath>`.

**Because the handler only forms `<base>/?folder=<worktree>`, every substrate below is just "stand up a
read-only code-server that can see the worktree, and point `EDEN_EDITOR_URL_BASE` at it."**

## 3. Local docker (✅ BUILT + live-verified)

`deploy/ctl.sh` `start_code_server` runs a read-only code-server **sibling** container:

```
docker run -d --rm --name eden-codeserver \
  --volumes-from base-devcontainer:ro \         # shares /workspace READ-ONLY
  -p 127.0.0.1:8500:8080 codercom/code-server:latest \
  --auth none --bind-addr 0.0.0.0:8080 /workspace
```

`EDEN_EDITOR_URL_BASE=http://localhost:8500`. The supervisor worktrees live under
`/workspace/.eden-runtime/supervisors/<id>` so they fall inside the shared `/workspace` mount; the
`?folder=` path the gateway returns is exactly that path. Read-only is enforced by the `:ro` on
`--volumes-from`. Verified live: `?folder` URL served `200`, the worktree's `README.md` + `.claude/`
visible, no write path. The docker-out-of-docker constraint (the Mac daemon cannot see the
devcontainer's `/tmp`) is why the worktrees moved under `/workspace`, not `/tmp`.

## 4. Kubernetes (🔶 DESIGNED — the faithful analog is a sidecar, NOT a shared service)

**Why not a static platform service.** The per-project editor is a *dynamic per-agent* workload: it must
see *that agent's* worktree. In kubernetes the agent worktree is a **writable `emptyDir`** in the agent
pod (`workspaceprovider/kubernetesadapter/lifecycle.go` `buildPod`/`buildVolumes` — a single
`workspaceContainer` with the spec image; Bind/Inputs mounts become `emptyDir` volumes). An `emptyDir`
is pod-scoped: a *separate* code-server Deployment cannot see it without RWX shared storage
(NFS/CephFS). So the editor does **not** belong in `deploy/servicespec`'s static `Catalog()` (that is the
fixed platform chart: agentgateway + agent-runtime).

**The design:** add a **read-only code-server sidecar container to the agent pod**, mounting the SAME
workdir `emptyDir` with `readOnly: true`. This is the exact analog of the local
`--volumes-from base-devcontainer:ro` — co-located with the worktree, read-only, zero shared-storage
requirement.

```
Pod(agent-<id>):
  containers:
    - name: workspace        # the harness, writes the worktree (unchanged)
      volumeMounts: [{ name: workdir, mountPath: <workDir> }]
    - name: editor           # NEW — read-only code-server
      image: codercom/code-server
      args: [--auth, none, --bind-addr, 0.0.0.0:8080, <workDir>]
      volumeMounts: [{ name: workdir, mountPath: <workDir>, readOnly: true }]
      ports: [{ containerPort: 8080, name: editor }]
  volumes: [{ name: workdir, emptyDir: {} }]      # unchanged; now mounted twice
```

Expose per agent: a `Service` on the editor port + **Ingress routing** so `EditorURLBase` resolves to
that agent. Two routing models (an open decision, §7): **host-per-agent** (`<id>.editor.<domain>`, a
wildcard-DNS + wildcard-TLS ingress — cleanest origin isolation) or **path-per-agent**
(`editor.<domain>/<id>/`, needs code-server's base-path/proxy support). The gateway then forms
`EditorURLBase` per agent rather than from one static env — a small handler change: resolve the editor
origin from the agent's namespace/ingress instead of a single `EDEN_EDITOR_URL_BASE`.

**Why this is a focused session, not an autonomous edit.** The sidecar needs a new `WorkspaceSpec`
field (e.g. `Editor *EditorSpec` / a `Sidecars` slice). That is an **exported-surface change to a
crown-jewel lib → it breaks the frozen `<lib>/.apibaseline`**, which is the cardinal sin (10 §9) and
aborts the gate unless taken through the full ADR-0020 library pipeline (architecture → implementation →
testing → qa, TDD red-before-green, conformance two-binding, deliberate rebaseline) with a **real k3d
integration test** (no mocks — per the standing bar). It also warrants an **ADR** (editor-as-sidecar +
the ingress routing model) and a matching dockeradapter path so the lib — not `deploy/ctl.sh` — owns the
local sibling too (today's asymmetry: local editor is wired outside the lib).

## 5. Desktop ssh-remote (🔶 DESIGNED)

The frontend path already exists (`isDesktop() && sshHost` → `vscode://vscode-remote/ssh-remote+…`).
What's missing is the **endpoint**: `EditorSSHHost` returns `""` today. To light it up:

- Run an **sshd in the sandbox** (or an ssh-accessible bastion that reaches the agent pod), exposing the
  worktree path. Read-only here is a posture decision: an ssh-remote VS Code can write unless the mount
  / the ssh user is constrained read-only (a read-only bind, a restricted shell, or an overlay).
- Resolve `EditorSSHHost` to a reachable `host[:port]` alias the user's `~/.ssh/config` (or a one-shot
  Eden-provisioned config) understands. The OS opens the user's native VS Code via the `vscode://` deep
  link; the Tauri shell must register/allow that scheme.
- This is independent of §4 and can land separately; it shares only the `sshHost` field already on the
  wire contract.

## 6. Security posture (invariant across substrates)

- **Read-only is structural, not advisory:** the `:ro` mount (docker) / `readOnly: true` volumeMount
  (k8s) means the editor process *cannot* write the worktree — it is not "a VS Code told to behave."
- **No credential on the wire:** `--auth none` is acceptable ONLY because access is already gated — the
  URL is reachable only behind the gateway's auth and (k8s) the ingress's auth; the `?folder` URL and
  `sshHost` carry no secret. A public ingress MUST add an auth layer (oauth2-proxy / the gateway JWT) in
  front of code-server; `--auth none` on a naked public ingress would be a regression.
- **Egress:** the editor sidecar inherits the agent namespace's default-deny egress NetworkPolicy
  (07 §3) — it serves files, it does not need to dial out.

## 7. Open decisions to file

- **OD-EDITOR-1 — k8s editor routing:** host-per-agent (wildcard DNS+TLS) vs path-per-agent
  (code-server base-path). Drives the ingress shape and how the gateway derives per-agent `EditorURLBase`.
- **OD-EDITOR-2 — desktop read-only enforcement:** how an ssh-remote VS Code is held read-only
  (read-only bind / restricted user / overlay) vs accepting that desktop ssh is read-write by nature.
- **OD-EDITOR-3 — lib ownership of the local sibling:** fold the docker sibling editor into the
  `workspaceprovider` dockeradapter (symmetry with the k8s sidecar) vs leave it in `deploy/ctl.sh`.

## Sources

- Shipped code: `apps/agentgateway/internal/gateway/{editor_handler.go,editor_test.go,gateway.go,router.go}`,
  `apps/agentgateway/internal/liveserve/liveserve.go`, `apps/frontend/src/lib/{platform/runtime.ts,
  gateway/client.ts,workspace/ProjectTopBar.svelte}`, `apps/frontend/src/routes/(app)/projects/[id]/workspace/+page.svelte`,
  `deploy/ctl.sh` (`start_code_server`). Commit `13d6328`.
- k8s pod model: `libs/go/workspaceprovider/kubernetesadapter/lifecycle.go` (`buildPod`, `buildVolumes`).
- code-server: `codercom/code-server` (`--auth`, `--bind-addr`, `?folder=`, base-path/proxy for path routing).
