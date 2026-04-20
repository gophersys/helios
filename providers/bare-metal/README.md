# providers/bare-metal

No-op provider for machines the cloud does NOT provision — on-prem,
homelab, NUCs, Raspberry Pi, colocated hardware, etc.

## When to use

- Homelab clusters.
- Physical edge devices.
- Any host where you yourself are responsible for "turning it on" — this
  provider skips the "create compute" step entirely.

## What it does

Given a `compute_unit` request with `provider: bare-metal`, this module:
1. Does **not** create any cloud resource.
2. Verifies the host is reachable on the tailnet under the expected
   `tailscale_hostname`.
3. Runs the bootstrap Ansible playbook against the already-running host.
4. Outputs: `tailnet_ip`, `ssh_key_path`.

## Status

STUB. Real use begins when the first homelab node is enrolled.
