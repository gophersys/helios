---
name: onboard-mtib
description: Bring a new Verdin MTIB hardware unit from "freshly manufactured" to "available in the platform as a Node, ready to be slotted into a Fixture". Walks cluster join, label/taint apply, and platform Discover-Register.
argument-hint: "<SNR> — <MANUFACTURING|VALIDATION>"
---

# /onboard-mtib

Spawn `deployer` (for the cluster-side label/taint work) and `http-api-eng` (for the platform-side Discover-Register flow). The full reference is in `.claude/knowledge/deploy/verdin-edge.md` — this skill walks the operator path end-to-end.

## Authoritative knowledge to load

- `.claude/knowledge/deploy/verdin-edge.md` — the full Verdin onboarding flow, MTIB Deployment template, common failure modes.
- `.claude/knowledge/product-domains/fixtures.md` — the Node/Fixture/Slot model.
- `.claude/knowledge/infrastructure.md` — where `cluster.yaml` + `labels.yaml` live.
- `.claude/knowledge/apps/backend/http-api.md` — the `/v2/nodes/*` endpoints.

## Pre-flight

- **Manufacturing has finished the Verdin/MTIB board.** SNR (8 digits) is stamped and recorded. The board is flashed with `concord-os-yocto` (the auto-join K3s agent config is baked in).
- **Office network access.** The Verdin connects to the office LAN; DHCP from `10.4.45.0/24` gives it an IP.
- **You have `kubectl` against the cluster.** `KUBECONFIG=~/.kube/config` if on-site, `~/.kube/config-concord-remote` if off-site (see `.claude/knowledge/workflows/credentials.md`).
- **You have `Permissions.DEVICES_MANAGE`** on the platform (the decorator on `register_node`). Granted by default to the ADMIN and MAINTAINER permission sets.

## The flow

### 1. Power the Verdin on; verify K3s join

Within ~60s of power-up, the Verdin's K3s agent registers with `concordserver01-03`. Verify:

```bash
kubectl get nodes
```

Look for `verdin-imx8mm-<SNR>` in the list with status `Ready` and `arch=arm64`. If it doesn't appear:

- Check the Verdin's serial console for K3s agent errors (`journalctl -u k3s-agent` over SSH).
- Confirm DHCP gave it an address in `10.4.45.0/24`.
- Confirm the cluster CA cert is current (concord-os-yocto bakes it in; stale OS images may have an outdated CA).

### 2. Apply cluster-level labels (one-shot)

The Verdin lands in the cluster with no workload labels — nothing schedules on it yet. Apply:

```bash
kubectl label node verdin-imx8mm-<SNR> concord.corekinect.com/workload-edge=true
kubectl label node verdin-imx8mm-<SNR> concord.corekinect.com/workload=edge
```

These are sufficient for the platform's Discover step to surface the node. The taint and the `corekinect.com/purpose=<mfg|validation>` label are added by the platform's Register step (next).

### 3. Add to the static cluster config (so labels survive a re-bootstrap)

Edit two files so the next `bootstrap.sh` re-applies these labels:

- `infrastructure/clusters/office/cluster.yaml` — append a row to `nodes.edge`:
  ```yaml
  nodes:
    edge:
      - hostname: verdin-imx8mm-<SNR>
        ip: 10.4.45.<assigned-IP>
  ```

- `infrastructure/clusters/office/nodes/labels.yaml` — append:
  ```yaml
  nodes:
    edge:
      - hostname: verdin-imx8mm-<SNR>
        workloads: [edge]
  ```

Also update `.claude/knowledge/deploy/verdin-edge.md::Current fleet` and commit. This counts as a code change → the knowledge-freshness hook will require the verdin-edge.md update (it does).

### 4. Platform: Discover

In the UI: **Fixtures → Discover MTIBs**. The wizard calls `POST /v2/devices/mtibs/discover`. The new Verdin appears under "Discovered" (in K8s, not yet in the platform DB).

Programmatically (rare — UI is canonical):

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  https://<host>/v2/devices/mtibs/discover
```

### 5. Platform: Register

Click **Register** next to the discovered node. Pick:

- **Type**: `MANUFACTURING` or `VALIDATION`. This must match the fixture this MTIB will be slotted into. **Picking wrong here is a real source of incidents** — see the v0.9.16 MOTION_ENABLED arch fix; type drives whether motion is enabled on the mtib-server.
- **Friendly name** (optional): defaults to the hostname.

The platform calls `POST /v2/devices/mtibs/<node_id>/register`. The `<node_id>` is the platform's `Node.id` (UUID) — for a never-registered Verdin, this is the row that `POST /v2/devices/mtibs` creates (or that `discover` returns as a "discovered" candidate, which the UI completes server-side). The backend:

1. Patches the K8s Node: adds `corekinect.com/role=edge` label, `corekinect.com/purpose=<mfg|validation>` label, and the `corekinect.com/role=edge:NoSchedule` taint.
2. Inserts a `Node` row in Postgres with hostname, IP, type, hardware revision.
3. Calls `log_audit("node.register", "Node", ...)`.
4. Returns the Node UUID.

### 6. Verify

- `kubectl get node verdin-imx8mm-<SNR> --show-labels` shows all expected labels and the taint.
- `GET /v2/devices/mtibs` returns the new node with `status=ONLINE` (live-derived from K8s).
- The node is now selectable in the slot-assign dropdown of any fixture creation flow.

The MTIB is now part of the platform fleet, but no `mtib-server` Deployment exists yet — that's created when the node is bound to a Fixture slot (`/add-fixture` or the operator UI). Until then, the node is idle.

## Decision points

- **`MANUFACTURING` vs `VALIDATION`**: irreversible without re-registering. The type drives `MOTION_ENABLED` for any mtib-server Deployment this node hosts, and gates which fixtures it can be slotted into. Pick deliberately.
- **Hardware revision**: the registration form may ask for the MTIB hardware revision (B0, C0, C1, …). If unsure, check the silkscreen on the board itself. The platform stores it in `Node.hardwareRevision` for traceability.

## Don't

- Don't register the same Verdin twice. The Discover wizard prevents this, but a direct API call could. Idempotency is enforced by the unique hostname constraint on `Node`.
- Don't apply both `MANUFACTURING` and `VALIDATION` taints/labels. The node has a single role.
- Don't bind the node to a slot of the wrong fixture type. The slot-assign endpoint validates this — but the error message is generic, and the right time to catch it is here, at registration.
- Don't skip the `cluster.yaml` + `labels.yaml` updates. The next `bootstrap.sh --labels-only` (or full re-bootstrap) will strip the labels from any node it doesn't know about.

## Update knowledge

After onboarding, update:

- **`.claude/knowledge/deploy/verdin-edge.md::Current fleet`** — add the new SNR + IP.

That's a code change (infrastructure edit), and the freshness hook will require the verdin-edge knowledge update in the same commit. Bundle both into one commit.

## Common failure modes

(see `.claude/knowledge/deploy/verdin-edge.md::Common failure modes` for the full list — these are the top three)

- **Verdin online, K8s sees it, UI's Discover returns empty** → http-api isn't reaching the K8s API (egress NetworkPolicy or in-cluster ServiceAccount permissions). Check the http-api pod logs for `K8S_AVAILABLE` at startup.
- **`gRPC connection failed` in fixture health** → MTIB pod isn't pulling (registry creds for ARM64). `kubectl describe pod mtib-<hostname>-s0 -n <env>`.
- **Verdin lost its labels after a cluster bounce** → re-bootstrap: `./infrastructure/ctl.sh office bootstrap`. Confirm the static `labels.yaml` and `cluster.yaml` carry the entry first.

## Related

- `/add-fixture` — what to do once the MTIB is registered and ready to slot.
- `/deploy-staging` / `/deploy-production` — if the MTIB image itself needs an update.
- `/debug-prod` — if a registered MTIB starts misbehaving in production.
