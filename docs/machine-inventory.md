# Machine inventory

Every machine, where it lives, how you reach it, and whether it is declared.
Verified against the live tailnet and both clusters on 2026-08-09.
`macos-ci-runner` was measured on the machine on 2026-08-13.

> **Access is Tailscale, everywhere, with 1 exception.** Every live machine is
> on the tailnet and reachable over **Tailscale SSH**. You need no key and no
> bastion. The `sentinel-00` and `sentinel-01` jumpboxes were deleted on
> 2026-08-09 because Tailscale SSH made them unnecessary.
> On Linux the whole procedure is `ssh ubuntu@<tailnet-ip>`.
> The exception is `macos-ci-runner`. Tailscale is not installed on it, so you
> reach it on the LAN with a dedicated key. See the section below.

## Workstation

| Machine | Tailnet | OS | Notes |
| --- | --- | --- | --- |
| `mateos-macbook-air` | `100.89.71.64` | macOS | **The main workstation.** It runs the studio dashboard on `:8737` (launchd `com.mateosegura.studio-dashboard`) and holds every kubeconfig, the `bw` CLI and the OCI CLI. |

**It is not declared in `machines/development/`, because that directory is
empty.** The machine that holds every credential and drives every cluster is the
one machine with no identity file. Tracked as debt D22.

## Homelab — Proxmox hypervisors

| Host | Tailnet | Hardware | Declared |
| --- | --- | --- | --- |
| `pve-00` | `100.77.217.116` | MS-A2 | ❌ no |
| `pve-01` | `100.124.246.39` | ThinkPad P1 | ✅ `clusters/instances/homelab/hypervisors/pve-01/` |
| `pve-03` | `100.126.209.124` | Yoga | ❌ no |

2 of the 3 hypervisors are undeclared. They host all 8 k3s VMs, so their
bootstrap state is load-bearing and invisible. This is also D22.

**`pve-01` is the sole Tailscale subnet router for `10.168.0.0/24`** as of
2026-08-19. pve-00 advertised the same prefix until Mateo single-homed the
advertisement (`tailscale set --advertise-routes=` on pve-00); pve-00 is now a
host-only tailnet node, and it also carries `--accept-routes=false` so it does
not route its own LAN over the tailnet. Neither pref is in git, because pve-00
has no identity file — D22 again.

## Homelab — k3s cluster (8 VMs on the hosts above)

| Node | IP | Role |
| --- | --- | --- |
| `k3s-cp-0/1/2` | `10.168.0.211-213` | control-plane + etcd |
| `k3s-w-0` | `10.168.0.221` | platform / devops |
| `k3s-w-1` | `10.168.0.222` | media — NVMe `/mnt/media`, MinIO |
| `k3s-w-2`, `k3s-w-3` | `10.168.0.223-224` | general apps |
| `k3s-w-4` | `10.168.0.225` | embedded — USB passthrough for Zephyr |

All 8 are declared under `clusters/instances/homelab/nodes/`. You reach them
through the tailnet, and the services land on the MetalLB VIP `10.168.0.240`.

They are not individually on the tailnet. `homelab-ts-operator`
(`100.74.135.18`) is the Tailscale k8s operator, and it projects selected
Services onto the tailnet.

## Cloud — OCI Phoenix (the root of trust)

| k8s node | OCI instance | Tailnet | Role |
| --- | --- | --- | --- |
| `code-kit-server` | `server-00` | `100.72.160.20` | control-plane + **etcd** |
| `agent-00` | `agent-00` | `100.81.203.110` | worker — **holds Vaultwarden and all storage** |

Both are `VM.Standard.A1.Flex` (ARM, 2 OCPU / 12 GB), Ubuntu 22.04.5, k3s
v1.34.5, public IP `144.24.23.2`. See `docs/cloud-cluster.md`.

> **The naming is inconsistent, and it must stay that way for now.** OCI, the
> boot volumes and the OS hostnames all say `server-00`. Only the k3s
> registration still says `code-kit-server`, and you cannot rename it in place,
> because k3s derives its etcd member identity from the node name (debt D15). The
> Tailscale device names also still say `code-kit-*`, and you *can* rename those
> safely in the admin console.

`cloud-subnet-router` (`100.88.73.74`) advertises the cloud subnet onto the
tailnet.

## Temporary devices

None today. The two Zephyr devbox pods (`zephyr-nucleo-bringup`,
`zephyr-zephyr-libs`) were removed 2026-08-18 with the whole `embedded-lab`
stack; their tailnet nodes died with their Services. The pattern stands: a
pod the Tailscale operator exposes gets its own MagicDNS name, is not a
machine, and is never declared here.

## Declared but NOT on the tailnet

| Machine | Declared purpose | State on 2026-08-13 |
| --- | --- | --- |
| `macos-ci-runner` | macOS CI host, and later a self-hosted GitHub Actions runner | **The machine exists and it is reachable.** It is a Mac mini: `Macmini9,1` (M1, 2020), arm64, 8 cores, 8 GB, macOS 15.5, full Xcode. `sshd` answers on the LAN at `10.168.0.92:22` and accepts the key `~/.ssh/macos-ci-runner`. It is **not** on the tailnet, it has **no** container runtime, and the Actions runner is **not** registered. |
| `windows-ci-runner` | Self-hosted GitHub Actions runner, Windows | **Not seen.** It is powered off, or it does not exist. **Do not assume that it works.** |

Neither appears on the tailnet. `macos-ci-runner` is measured and reachable, so
it is no longer a machine you must "verify or retire". It is a half-enrolled
machine, and the 3 open items above are the rest of its enrollment.
`windows-ci-runner` is still unverified. Resolve it before you depend on it
for CI.

`arm-builder` was the third machine in this list. It was terminated on 2026-08-10
and its volume was deleted. It billed $4.00 a month to run 0 builds, and a
t4g.small with 2 GiB of memory could not build these images. GitHub's
`ubuntu-24.04-arm` runner replaces it: native arm64, and no machine to manage.

## Stale tailnet entries — remove them in the admin console

| Device | State |
| --- | --- |
| `sentinel-00`, `sentinel-01` | **instances terminated 2026-08-09** — the machines are gone |
| `laptop-at1rvdr3`, `laptop-at1rvdr3-1` | offline 153 days |

Every device on a tailnet is a possible entry point. Removing the dead ones is
housekeeping *and* security.

## How to reach anything

```sh
tailscale status                     # who is up
ssh ubuntu@100.81.203.110            # any Linux host — Tailscale SSH, no key

KUBECONFIG=~/.kube/homelab.yaml      kubectl get nodes
KUBECONFIG=~/.kube/cloud.yaml        kubectl get nodes    # direct, no tailnet needed
KUBECONFIG=~/.kube/cloud-tailnet.yaml kubectl get nodes   # same cluster via tailnet
```

The **true break-glass path for the cloud cluster** is the OCI console (Compute →
Instances → Console Connection). It gives serial access and needs neither SSH nor
the network. That credential must never live in the vault it exists to rescue.

## Gaps (debt D22)

1. `machines/development/` is empty, so the MacBook Air is undeclared.
2. `pve-00` and `pve-03` are undeclared.
3. 1 declared service machine is unreachable and unverified: `windows-ci-runner`.
   `macos-ci-runner` was measured on 2026-08-13 and it is reachable, but it is
   not on the tailnet yet.
4. 4 dead devices still hold tailnet identities.
