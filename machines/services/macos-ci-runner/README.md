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
2. **A container builder.** Docker, Colima and Podman are all absent. Homebrew,
   Go and Tailscale are absent too. When the Linux VM is added, give it 4 GB of
   swap, because the host has only 8 GB of memory.
3. **The GitHub Actions runner.** It is not configured against the org. Until it
   is, the release workflow keeps the hosted `macos-14` runner.

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
