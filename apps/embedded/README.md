# embedded — ephemeral Zephyr dev environments (homelab)

Per-project Zephyr embedded dev environments on the homelab k3s cluster,
pinned to **k3s-w-4** (the Proxmox VM on pve-01 that receives USB
microcontrollers via QEMU passthrough). Each env is an SSH-able devbox with
the Zephyr toolchain, raw USB access for flashing, and its own tailnet
MagicDNS name.

## Architecture

```
apps/embedded/
  namespace/            embedded-lab Namespace (platform-owned, long-lived)
  zephyr-devbox/base/   kustomize base: Deployment+Service+PVCs+ConfigMap
  envs/<name>/          one overlay per ephemeral env  <-- the unit of lifecycle

registry/app-zephyr-envs.yaml        ApplicationSet: envs/* -> Application zephyr-<name>
registry/app-embedded-namespace.yaml owns the namespace (never pruned)
registry/projects/embedded.yaml      AppProject fence: embedded-lab only, namespaced-only

Pod (ns: embedded-lab, pinned k3s-w-4, privileged)
  ├─ /dev/bus/usb + /dev/serial   hostPath — hotplug/re-enumeration-safe flashing
  ├─ /home/dev + /workspace       PVCs (local-path on k3s-w-4)
  └─ sshd :22 ── Service (LoadBalancer, class tailscale) ──▶ tailnet: zephyr-<env>
```

## Spin up an env

```bash
cp -r apps/embedded/envs/nucleo-bringup apps/embedded/envs/<name>
# edit apps/embedded/envs/<name>/kustomization.yaml:
#   - nameSuffix: -<name>
#   - labels pairs: app.kubernetes.io/instance: <name>
#   - tailscale.com/hostname patch value: zephyr-<name>
#   - authorized_keys patch: your SSH public key(s)
kubectl kustomize apps/embedded/envs/<name>   # sanity-check the build
git checkout -b feat/embedded-env-<name> && git add apps/embedded/envs/<name> \
  && git commit -m "feat(embedded): env <name>" && git push
# open PR, merge -> ApplicationSet creates zephyr-<name>; then:
ssh dev@zephyr-<name>   # MagicDNS, from anywhere on the tailnet
```

## Tear down an env

```bash
git rm -r apps/embedded/envs/<name>
git commit -m "chore(embedded): retire env <name>" && git push
# PR, merge -> Argo prunes the Application: pod, PVCs, Service and its
# tailnet node all go away. The embedded-lab namespace stays.
```

## Invariants (do not break)

- Every env overlay MUST set a unique `nameSuffix`, a unique
  `app.kubernetes.io/instance` label **with `includeSelectors: true`**
  (all envs share the namespace — without it Services cross-match pods),
  and a unique `tailscale.com/hostname`.
- Devbox pods are privileged + hostPath by design (USB flashing); that is why
  `embedded-lab` is on both Kyverno exclusion lists. Nothing else belongs in
  this namespace.

## Dependencies / TODOs

- Image `ghcr.io/gophersys/zephyr-devbox:latest` — built by a parallel PR in
  gophersys/zephyr-devbox; pods ImagePullBackOff (harmlessly) until it lands.
- Tailscale operator (`registry/app-tailscale-operator.yaml`) + its imperative
  `operator-oauth` Secret — see
  `platform/services/networking/tailscale-operator/README.md`.
- USB: QEMU passthrough of the microcontrollers into the k3s-w-4 VM, plus the
  node's udev rules for the stable `/dev/mcu-slot-N` symlinks.
