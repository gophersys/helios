# macos-ci-runner (ENROLLED — the runner is not registered yet)

The Mac mini in the living room. It is the macOS CI host for the gophersys org.
The planned consumer is the release workflow of
`gophersys/audiomotion-visualizer`. In that workflow, change the `runs-on` of
`build-mac` from `macos-14` to `[self-hosted, macOS, music-ci]`. Do not make
that change yet. The runner is not registered.

## What is true today (measured on 2026-08-13)

| Fact | Value |
| --- | --- |
| Model | `Macmini9,1` — Mac mini (M1, 2020). It is not a MacBook. |
| CPU | arm64, 8 cores |
| Memory | 8 GB |
| macOS | 15.5 |
| Free disk | 42 GiB |
| Remote Login | ON. `sshd` answers at `10.168.0.92:22` (OpenSSH 9.9). |
| Access | The dedicated key `~/.ssh/macos-ci-runner` (ed25519, no passphrase). |
| Xcode | Full Xcode at `/Applications/Xcode.app/Contents/Developer`. |
| HostName | `macos-ci-runner`. `scutil --get HostName` and `hostname` both give it. |

Prove the access from the workstation:

```sh
ssh -i ~/.ssh/macos-ci-runner -o BatchMode=yes -o IdentitiesOnly=yes \
    mateo@10.168.0.92 'echo OK'
```

## The HostName was unset until 2026-08-13

`scutil --get HostName` gave `HostName: not set`, and `hostname` gave
`Mateos-Mac-mini.local`. The machine therefore did not answer with the name it
is declared under. This command set it:

```sh
sudo scutil --set HostName macos-ci-runner
```

The identity assertion in `scripts/verify-access.sh` was always correct. The
machine was wrong. Read a `FAIL ... answered as <other name>` line that way.

`LocalHostName` stays `Mateos-Mac-mini`. It is the Bonjour name on the LAN, not
the fleet identity, so we leave it alone.

## What is NOT true yet

Do not depend on any item below. None of them is done.

1. **The tailnet.** Tailscale is not installed, so the machine does not appear
   in `tailscale status`. The machine is on the LAN only. The name
   `macos-ci-runner` is reserved in the tailnet, not live.
2. **Homebrew and Go.** Both are absent.
3. **The GitHub Actions runner.** It is not configured against the org. Until it
   is, the release workflow keeps the hosted `macos-14` runner.

A container builder WAS on this list. It is not any more: Docker Desktop is
installed and it serves builds. Read the next section.

## The arm64 buildkitd node

The cluster uses this machine to build `linux/arm64` images natively. The k3s
nodes are amd64, so they must emulate arm64, and emulation is slow. Measured on
2026-08-13, same Dockerfile, images pulled first, `--no-cache`: arm64 native
4.02s against amd64 emulated 13.8s, so 3.44 times faster.

A build in the cluster reaches this machine through a standalone `buildkitd`
container, over mutual TLS. The machine never becomes an Actions runner. The two
paths are independent. The design and the workflow step are in
`docs/ci-substrate.md`; the setup is reproducible from `buildkitd-runbook.md` in
this directory.

`buildkitd` runs as the container `eden-buildkitd`. It listens on
`tcp://10.168.0.92:1234` and exposes the BUILD API only — no Docker Engine API.
It survives a reboot with `--restart unless-stopped` and the Docker-autostart
chain below.

### The credential — a client certificate, over mTLS

`buildkitd` authenticates its clients with mutual TLS. The mini holds the server
certificate; the cluster holds a client certificate, as the three vault items
`shared/eden/buildkit-client-{ca,cert,key}`. Proven on 2026-08-14:

| test | result |
| --- | --- |
| a native arm64 build through the node | exit 0, 9.3s |
| a client with no certificate | refused — mTLS enforced |
| `docker -H tcp://10.168.0.92:1234` | error — no Engine API on the port |
| `docker run --privileged --pid=host` | error, NOT root — the escape is dead |
| `docker buildx build --allow security.insecure` | refused — the entitlement is not allowed |

The client can submit a sandboxed build and nothing else. This replaces an SSH
key that reached the Docker Engine API — root on this machine's Docker VM. That
key is REVOKED from `~/.ssh/authorized_keys`, and its vault item
`shared/eden/macos-buildx-key` is deleted.

The admin key `~/.ssh/macos-ci-runner` is a different key. It stays unrestricted,
`verify-access` uses it, and it never enters the cluster.

### Three things are necessary after a reboot

Each one was proven necessary by removing it and measuring the result.

1. Docker Desktop `AutoStart=True`.
2. macOS auto-login. Docker Desktop is a GUI application, so it cannot start
   without a user session.
3. The LaunchAgent `com.gophersys.docker-autostart`. The `AutoStart` flag never
   registered a login item, so the flag alone does not start Docker.

| configuration | Docker answers |
| --- | --- |
| items 1 and 2 only | not at 422s after the reboot |
| all 3 items | at 41s after the reboot |

Item 3 is the one that is easy to miss, because item 1 looks like it should be
enough. It is not.

## Why a self-hosted runner instead of the hosted macos-14 runner used today
- It costs 0 Actions minutes. GitHub bills macOS at 10 times the rate on a
  private repo.
- It can run deep tests that only macOS supports and that a hosted runner cannot
  do: the TCC flows for screen recording, and a real capture of loopback audio
  (`--capture-test` while music plays).

## The work that remains — in order
1. Stop the machine from sleeping: Settings → Displays → Advanced → prevent
   sleep on power. As an alternative, run `sudo pmset -c sleep 0 displaysleep 10`.
2. Join the tailnet. Use the `tailscale-authkey-*` pattern, or run
   `tailscale up` interactively. Then change `address:` in
   `contracts/access.yaml` from the LAN address to the tailnet address.
3. Install the runner (as the login user, NOT root):
   ```sh
   mkdir ~/actions-runner && cd ~/actions-runner
   curl -o runner.tar.gz -L https://github.com/actions/runner/releases/latest/download/actions-runner-osx-arm64-<ver>.tar.gz
   tar xzf runner.tar.gz
   TOKEN=$(gh api -X POST orgs/gophersys/actions/runners/registration-token -q .token)
   ./config.sh --url https://github.com/gophersys --token "$TOKEN" \
       --labels self-hosted,macOS,music-ci --unattended
   ./svc.sh install && ./svc.sh start    # launchd agent, GUI session
   ```
4. The machine must stay logged in, with a GUI session, for the Electron smoke
   tests.
5. Install Node 20 or later. Without it the runner downloads a toolcache.
6. Change the `runs-on` of `build-mac` in the workflow. Keep the hosted runner
   in a comment, as the fallback.
7. Set `runner.registered: true` in `identity.yaml`, then regenerate the
   machines index with `bash machines/ctl.sh generate-index`.

## Notes
- The runner user should NOT have the Bitwarden vault unlocked. CI needs no access
  to the vault. It needs `GITHUB_TOKEN` only.
- The vault item `shared/ssh/macos-ci-runner` holds the account password. It is
  the break-glass path. The happy path is the key. The name follows the fleet
  convention `shared/ssh/<machine>`, the same as `shared/ssh/macbook-air`.
- A deep-test lane in the future: a scheduled workflow that runs
  `--capture-test` against real system audio. That test has a purpose only on
  this machine.
