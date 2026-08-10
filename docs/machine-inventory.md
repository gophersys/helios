# Machine inventory

Every machine, where it lives, how you reach it, and whether it is declared.
Verified against the live tailnet and both clusters on 2026-08-09.

> **Access is Tailscale, everywhere.** Every live machine is on the tailnet and
> reachable over **Tailscale SSH** — no key needed, no bastion. The
> `sentinel-00`/`sentinel-01` jumpboxes were deleted on 2026-08-09 precisely
> because Tailscale SSH made them redundant.
> `ssh ubuntu@<tailnet-ip>` (Linux) is the whole procedure.

## Workstation

| Machine | Tailnet | OS | Notes |
| --- | --- | --- | --- |
| `mateos-macbook-air` | `100.89.71.64` | macOS | **The main workstation.** Runs the studio dashboard on `:8737` (launchd `com.mateosegura.studio-dashboard`), holds every kubeconfig, the `bw` CLI and the OCI CLI. |

**Not declared in `machines/development/` — that directory is empty.** The machine
that holds every credential and drives every cluster is the one machine with no
identity file. Tracked as debt D22.

## Homelab — Proxmox hypervisors

| Host | Tailnet | Hardware | Declared |
| --- | --- | --- | --- |
| `pve-00` | `100.77.217.116` | MS-A2 | ❌ no |
| `pve-01` | `100.124.246.39` | ThinkPad P1 | ✅ `clusters/instances/homelab/hypervisors/pve-01/` |
| `pve-03` | `100.126.209.124` | Yoga | ❌ no |

Two of three hypervisors are undeclared. They host all 8 k3s VMs, so their
bootstrap state is load-bearing and invisible. Also D22.

## Homelab — k3s cluster (8 VMs on the above)

| Node | IP | Role |
| --- | --- | --- |
| `k3s-cp-0/1/2` | `10.168.0.211-213` | control-plane + etcd |
| `k3s-w-0` | `10.168.0.221` | platform / devops |
| `k3s-w-1` | `10.168.0.222` | media — NVMe `/mnt/media`, MinIO |
| `k3s-w-2`, `k3s-w-3` | `10.168.0.223-224` | general apps |
| `k3s-w-4` | `10.168.0.225` | embedded — USB passthrough for Zephyr |

All 8 declared under `clusters/instances/homelab/nodes/`. Reached through the
tailnet; services land on the MetalLB VIP `10.168.0.240`.

Not individually on the tailnet — `homelab-ts-operator` (`100.74.135.18`) is the
Tailscale k8s operator, which projects selected Services onto the tailnet.

## Cloud — OCI Phoenix (the root of trust)

| k8s node | OCI instance | Tailnet | Role |
| --- | --- | --- | --- |
| `code-kit-server` | `server-00` | `100.72.160.20` | control-plane + **etcd** |
| `agent-00` | `agent-00` | `100.81.203.110` | worker — **holds Vaultwarden and all storage** |

Both `VM.Standard.A1.Flex` (ARM 2 OCPU / 12 GB), Ubuntu 22.04.5, k3s v1.34.5,
public IP `144.24.23.2`. See `docs/cloud-cluster.md`.

> **Naming is inconsistent by necessity.** OCI, the boot volumes and the OS
> hostnames all say `server-00`. Only the k3s registration still says
> `code-kit-server`, and it cannot be renamed in place — k3s derives its etcd
> member identity from the node name (debt D15). The Tailscale device names still
> say `code-kit-*` too and *can* safely be renamed in the admin console.

`cloud-subnet-router` (`100.88.73.74`) advertises the cloud subnet onto the tailnet.

## Ephemeral

| Device | Tailnet | Notes |
| --- | --- | --- |
| `zephyr-nucleo-bringup` | `100.76.193.42` | Zephyr devbox pod, USB-passthrough on `k3s-w-4` |
| `zephyr-zephyr-libs` | `100.106.109.58` | same |

Created and destroyed by the `zephyr-envs` ApplicationSet — each gets its own
MagicDNS name from the Tailscale operator. Not machines; do not declare them.

## Declared but NOT on the tailnet — verify or retire

| Machine | Declared purpose |
| --- | --- |
| `arm-builder` | On-demand ARM docker builder for ghcr.io pushes |
| `macos-ci-runner` | Self-hosted GitHub Actions runner, macOS |
| `windows-ci-runner` | Self-hosted GitHub Actions runner, Windows |

None appears on the tailnet. `arm-builder`'s stated consumers were **codectl and
fintel** — codectl was deleted 2026-08-09. Either these are powered off
on-demand, or they no longer exist. **Do not assume they work.** Resolve before
relying on any of them for CI.

## Stale tailnet entries — remove in the admin console

| Device | State |
| --- | --- |
| `sentinel-00`, `sentinel-01` | **instances terminated 2026-08-09** — machines are gone |
| `laptop-at1rvdr3`, `laptop-at1rvdr3-1` | offline 153 days |

Every device on a tailnet is a potential ingress. Removing dead ones is
housekeeping *and* hygiene.

## How to reach anything

```sh
tailscale status                     # who is up
ssh ubuntu@100.81.203.110            # any Linux host — Tailscale SSH, no key

KUBECONFIG=~/.kube/homelab.yaml      kubectl get nodes
KUBECONFIG=~/.kube/cloud.yaml        kubectl get nodes    # direct, no tailnet needed
KUBECONFIG=~/.kube/cloud-tailnet.yaml kubectl get nodes   # same cluster via tailnet
```

**True break-glass for the cloud cluster** is the OCI console (Compute →
Instances → Console Connection): serial access needing neither SSH nor network.
That credential must never live in the vault it exists to rescue.

## Gaps (debt D22)

1. `machines/development/` is empty — the MacBook Air is undeclared.
2. `pve-00` and `pve-03` are undeclared.
3. Three declared service machines are unreachable and unverified.
4. Four dead devices still hold tailnet identities.
