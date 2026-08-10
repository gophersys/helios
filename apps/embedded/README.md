# embedded — ephemeral Zephyr dev environments (homelab)

Zephyr embedded dev environments, 1 per project, on the homelab k3s cluster. They
are pinned to **k3s-w-4**, the Proxmox VM on pve-01 that receives the USB
microcontrollers through QEMU passthrough. Each env is a devbox that you reach
over SSH. It carries the Zephyr toolchain, raw USB access for flashing, and its
own MagicDNS name on the tailnet.

## Architecture

```
apps/embedded/
  namespace/            embedded-lab Namespace (platform-owned, long-lived)
  zephyr-devbox/base/   kustomize base: Deployment+Service+PVCs+ConfigMap
  envs/<name>/          one overlay per ephemeral env  <-- the unit of lifecycle

registry/app-zephyr-envs.yaml        ApplicationSet: envs/* -> Application zephyr-<name>
registry/app-embedded-namespace.yaml owns the namespace (never pruned)
registry/projects/embedded.yaml      AppProject limit: embedded-lab only, namespaced-only

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

## Invariants — do not break these

- Every env overlay MUST set a unique `nameSuffix`, a unique
  `app.kubernetes.io/instance` label **with `includeSelectors: true`**, and a
  unique `tailscale.com/hostname`. All the envs share the namespace, so without
  `includeSelectors: true` a Service matches the pods of another env.
- A devbox pod is privileged and uses a hostPath by design, because it flashes
  over USB. That is why `embedded-lab` is on both Kyverno exclusion lists.
  Nothing else belongs in this namespace.

## Dependencies and TODOs

- The image `ghcr.io/gophersys/zephyr-devbox:latest`. A parallel PR in
  gophersys/zephyr-devbox builds it. Until that PR lands, the pods stay in
  ImagePullBackOff, and that causes no other problem.
- The Tailscale operator (`registry/app-tailscale-operator.yaml`) and its
  imperative `operator-oauth` Secret. See
  `platform/services/networking/tailscale-operator/README.md`.
- USB: the QEMU passthrough of the microcontrollers into the k3s-w-4 VM, plus the
  udev rules on the node for the stable `/dev/mcu-slot-N` symlinks.
