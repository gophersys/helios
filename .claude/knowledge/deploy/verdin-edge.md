# Deploy — Verdin edge nodes

Every MTIB fixture is built on a Toradex Verdin iMX8MM ARM64 SoM running concord-os-yocto. The Verdin joins the office K3s cluster as a K8s agent and hosts a per-fixture `mtib-server` Deployment. Bringing a new MTIB online is a coordinated dance between manufacturing of the Verdin/MTIB hardware, cluster onboarding, and platform registration.

Refresh this file when: the Verdin onboarding flow changes, the workload labels change, the MTIB deployment template changes, the `Node` Prisma model gains or loses fields used by the discover/register flow, or the K8s API used to discover edge nodes (`list_node`) is wrapped differently.

## What a Verdin edge node is

| Attribute | Value |
|---|---|
| Hardware | Toradex Verdin iMX8MM SoM on a CoreKinect carrier board |
| OS | concord-os-yocto (custom Yocto distro in `concord/concord-os-yocto/`) |
| Architecture | `arm64` |
| K8s role | Agent (no etcd, no control-plane) |
| Hostname convention | `verdin-imx8mm-<8-digit-SNR>` — the SNR stamped on the SoM |
| IP | DHCP from the office subnet `10.4.45.0/24` |
| Workload label | `concord.corekinect.com/workload-edge=true` (plus `concord.corekinect.com/workload=edge` for nodeSelector) |
| Taint | `corekinect.com/role=edge:NoSchedule` (only pods tolerating this run here) |
| Purpose label (post-registration) | `corekinect.com/purpose=manufacturing` or `=validation` |

Current fleet (from `infrastructure/clusters/office/cluster.yaml`):

```
verdin-imx8mm-15005696   10.4.45.33
verdin-imx8mm-15005670   10.4.45.34
verdin-imx8mm-15005721   10.4.45.36
verdin-imx8mm-15005714   10.4.45.37
verdin-imx8mm-15005668   10.4.45.39
```

These are also listed in `infrastructure/clusters/office/nodes/labels.yaml`, which `bootstrap.sh` reads to apply the workload labels.

## End-to-end onboarding flow

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. MFG: Manufacturing builds the Verdin/MTIB board                    │
│    - Flash concord-os-yocto                                          │
│    - SNR (8 digits) is stamped + recorded                            │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 2. CLUSTER: Verdin powers on in the office, joins K3s                 │
│    - Pre-baked K3s agent config in concord-os-yocto                  │
│    - Node appears in `kubectl get nodes` with `arch=arm64`           │
│    - No labels yet → no pods scheduled                               │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 3. CLUSTER: bootstrap.sh or manual `kubectl label`                    │
│    - Adds `concord.corekinect.com/workload-edge=true`                │
│    - For static cluster config, add to                                │
│      `infrastructure/clusters/office/nodes/labels.yaml`              │
│      and `cluster.yaml` `nodes.edge`                                  │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 4. PLATFORM: GET /v2/nodes/sync (the "Discover MTIBs" wizard)         │
│    - http-api calls k8s.list_node() filtered on `arch=arm64` + Ready  │
│    - Returns `discovered` list (in K8s but not in DB)                │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 5. PLATFORM: POST /v2/nodes/:k8sName/register                         │
│    - Operator picks type: MANUFACTURING | VALIDATION                  │
│    - _apply_edge_labels patches the K8s Node:                         │
│       labels[corekinect.com/role]=edge                                │
│       labels[corekinect.com/purpose]=<mfg|validation>                 │
│       taint  corekinect.com/role=edge:NoSchedule                      │
│    - Inserts row in `Node` table (Prisma model) with hostname, ip,    │
│      type, hardwareRevision                                           │
│    - log_audit("node.register", "Node", ...)                          │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 6. PLATFORM: POST /v2/fixtures/:id/slots/:slotId/assign               │
│    - Binds the Node to a FixtureSlot                                  │
│    - Triggers _deploy_mtib_for_node():                                │
│        create_mtib_deployment(node_hostname, fixture_id, slot, cfg)   │
│        renders apps/backend/http-api/assets/templates/                │
│                mtib_server_deployment.yaml                            │
│        applies into the matching namespace (staging/production/dev)   │
│    - Node.metadata.deployment_name is set                             │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 7. RUNTIME: mtib-server pod lands on the Verdin                       │
│    - nodeSelector: kubernetes.io/hostname=<verdin host>               │
│    - tolerations: corekinect.com/role=edge:NoSchedule                 │
│    - Container binds port 50053 on host networking                    │
│    - http-api polls it via gRPC                                       │
└──────────────────────────────────────────────────────────────────────┘
```

Step 4 endpoint: `GET /v2/nodes/sync` (the handler is `sync_nodes_from_k8s` in `apps/backend/http-api/src/api/v2/nodes/nodes.py`).

Step 5 endpoint: `POST /v2/nodes/<id>/register` (handler `register_node`, same file).

## MTIB Deployment template

`apps/backend/http-api/assets/templates/mtib_server_deployment.yaml` is a templated YAML rendered by `services/kubernetes/mtib_deployments.py::create_mtib_deployment`. The substitutions:

| Placeholder | Source | Notes |
|---|---|---|
| `{{DEPLOYMENT_NAME}}` | `mtib-<hostname>-s<slot_index>` | Truncated to 63 chars (RFC 1123). |
| `{{NODE_HOSTNAME}}` | the Verdin's K8s hostname | Used in `nodeSelector: kubernetes.io/hostname`. |
| `{{FIXTURE_ID}}` | UUID of the bound fixture (or `"standalone"`) | Stored as label for queries. |
| `{{DEPLOYMENT_ID}}` | UUID per deployment | Distinguishes redeploys. |
| `{{IMAGE}}` | `containers.ad.corekinect.com/concord-mtib-server:latest` (override per fixture config) | ARM64 image, built separately from the platform. |
| `{{MOTION_ENABLED}}` | derived: `VALIDATION` → `true`, anything else → `false` | The "fixture purpose" rule: only validation fixtures drive FluidNC linear rails. |
| `{{METRICS_ENABLED}}` | from fixture config (default `false`) | |
| `{{LOG_LEVEL}}` | from fixture config (default `4`) | |
| `{{CPU_REQUEST}}` / `{{MEMORY_REQUEST}}` / `{{CPU_LIMIT}}` / `{{MEMORY_LIMIT}}` | from fixture config | Defaults: 250m/256Mi req, 2000m/1Gi limit. |

The Deployment carries `corekinect.com/managed-by: concord` label so `ctl.sh::_verify_rollout` knows to skip it (see [`helm.md`](helm.md)). It also carries `app.kubernetes.io/name: concord-mtib-server` so the NetworkPolicy egress rule on http-api can target it (though in practice the egress allows the whole `10.4.45.0/24:50053` block — see [`network.md`](network.md)).

## How `mtib_host` ends up everywhere

Several different things mean "MTIB host" depending on context:

| Term | Where | What |
|---|---|---|
| `Node.hostname` | DB column | The Verdin's K8s hostname, e.g. `verdin-imx8mm-15005696`. |
| `Node.ipAddress` | DB column | The Verdin's InternalIP, fetched at register time from K8s. |
| `mtib_host` env var | runner pod env (set by `services/kubernetes/runner_env.py`) | The IP:port string `10.4.45.33:50053` for a single MTIB. |
| `MTIB_HOSTS` env var | runner pod env | Comma-separated `ip:port,…` for all slots in a panel run. |
| node selector `kubernetes.io/hostname` | the MTIB Deployment | Pins the mtib-server pod onto that specific Verdin. |
| label `concord.corekinect.com/workload-edge=true` | the Verdin node | Lets schedulers find edge nodes. |
| label `corekinect.com/purpose=<mfg|validation>` | the Verdin node | Lets fixture-config UIs filter. |

The runner pod gets the IP+port from http-api's `slot_infos`, which `services/kubernetes/mtib_deployments.py::get_slot_health` enriches with `nodeIp` after looking each Verdin up by hostname.

## What "discovery" actually does

`sync_nodes_from_k8s`:

1. `core_v1.list_node()` — every K8s node.
2. Filter by `labels["kubernetes.io/arch"] == "arm64"`.
3. Filter by `status.conditions[type=Ready, status=True]`.
4. Cross-reference against `db.node.find_many()` (matching on `hostname`).
5. Bucket into three lists:
   - `registered`: in K8s **and** DB.
   - `discovered`: in K8s, not in DB — needs `POST /v2/nodes/register`.
   - `offline`: in DB, not in K8s (Ready) — likely powered off or unjoined.

It does **not** rely on the `workload-edge` label, since a freshly-joined Verdin may not yet have it. Operators see "discovered" Verdins as soon as they appear in K8s, regardless of labels.

## Registering a new MTIB end-to-end

The realistic operator flow:

1. **Manufacturing finishes a Verdin** → boards goes in the rack, power on.
2. **Verdin joins K3s** (automatic — concord-os-yocto has the agent config). Verify: `kubectl get nodes` shows `verdin-imx8mm-<SNR>` Ready.
3. **Operator opens the platform UI → Fixtures → "Discover MTIBs"**. The wizard calls `GET /v2/nodes/sync`; the new Verdin appears under "Discovered".
4. **Operator clicks Register**, picks Type = MANUFACTURING or VALIDATION, names it. UI calls `POST /v2/nodes/<id>/register`. http-api labels + taints the K8s node and inserts the DB row.
5. **Operator binds the Node to a FixtureSlot** in the UI. http-api spawns the MTIB Deployment via `create_mtib_deployment`.
6. **Within ~30 s** the mtib-server pod is Ready on the Verdin. `Node.status` flips to `ONLINE` (computed live by `_serialize_node`, not stored as a column).

To onboard a *static* fleet entry (so `bootstrap.sh` re-applies labels after a cluster reset), edit:

- `infrastructure/clusters/office/cluster.yaml` — add the node under `nodes.edge`.
- `infrastructure/clusters/office/nodes/labels.yaml` — add `workloads: [edge]`.

## How to add a new Verdin to the fleet

1. Build the hardware; record the SNR (`SNR=15005xxx`).
2. Flash concord-os-yocto. K3s agent config should auto-join.
3. Verify `kubectl get node verdin-imx8mm-<SNR>` shows Ready.
4. Append the entry to `infrastructure/clusters/office/cluster.yaml::nodes.edge` and to `nodes/labels.yaml`.
5. Apply labels (one-shot, since the static file is for re-bootstrap only):
   ```
   kubectl label node verdin-imx8mm-<SNR> concord.corekinect.com/workload-edge=true
   kubectl label node verdin-imx8mm-<SNR> concord.corekinect.com/workload=edge
   ```
6. Update this file's fleet list.
7. Operator runs the Discover & Register flow in the UI to add it to `Node`.

## Common failure modes

- **Verdin online, K8s sees it, but UI's Discover returns empty** — http-api isn't reaching the K8s API server (egress NetworkPolicy or kubeconfig). Check `K8S_AVAILABLE` log line at startup; if false, the import failed and http-api falls back to an empty result. Likely cause: missing in-cluster ServiceAccount permissions, or missing `kubeconfig` mount in dev compose.
- **`gRPC connection failed`** in health check — the Verdin booted but mtib-server didn't. Most often: the MTIB image isn't pulled (registry creds missing for ARM64). `kubectl describe pod mtib-<hostname>-s0 -n <env>`.
- **Verdin shows OFFLINE in `Node.status` even though K8s sees it Ready** — `Node.metadata.deployment_name` is set but the Deployment doesn't exist (deleted manually). The serializer reports OFFLINE because `readyReplicas != replicas`. Recreate via the slot-assign endpoint.
- **`MOTION_ENABLED=true` ended up on a manufacturing fixture** — the fixture config or `node_type` got crossed. The canonical rule is `_mtib_env_for_fixture` in `apps/backend/http-api/src/api/v2/fixtures/fixtures.py`; the standalone-node path uses `_deploy_mtib_for_node`. Both must agree. Tests live at `apps/backend/http-api/tests/api/fixtures/test_mtib_env.py`.
- **DHCP renews → Verdin IP changes → http-api can't reach MTIB** — `Node.ipAddress` is stamped at register time. Re-resolve via `services/kubernetes/client.py::resolve_node_ips` or operator triggers a "re-register" in the UI.
- **Pod stays Pending with `no nodes match selector`** — the Verdin lost its `workload-edge` label after a cluster bounce. Rerun `bash infrastructure/ctl.sh office bootstrap` or re-label manually.

## Related knowledge

- [`overview.md`](overview.md) — cluster topology including the Verdin fleet.
- [`helm.md`](helm.md) — why MTIB Deployments are excluded from rollout verification.
- [`network.md`](network.md) — port 50053 routing and NetworkPolicy boundaries.
- [`../apps/edge/mtib-server.md`](../apps/edge/mtib-server.md) — what runs on the Verdin.
- [`../apps/backend/http-api.md`](../apps/backend/http-api.md) — `/v2/nodes/*` endpoints and the K8s client.
- [`../glossary.md`](../glossary.md) — MTIB, Verdin, Fixture, Slot, Node definitions.
