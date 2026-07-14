# macos-ci-runner (PLANNED)

The living-room MacBook as a gophersys org GitHub Actions runner.
Consumer: `gophersys/audiomotion-visualizer` release workflow (swap
`build-mac`'s `runs-on: macos-14` → `[self-hosted, macOS, music-ci]`).

## Why self-hosted (vs the hosted macos-14 currently in use)
- $0 Actions minutes (macOS is billed at 10× on private repos).
- Can run macOS-only deep tests hosted runners can't: screen-recording TCC
  flows, real loopback-audio capture (`--capture-test` with music playing).

## Prerequisites (owner, one-time)
1. On the MacBook: System Settings → General → Sharing → **Remote Login ON**.
   Note the Computer Name.
2. Keep-awake: Settings → Displays → Advanced → prevent sleep on power
   (or `sudo pmset -c sleep 0 displaysleep 10` after enrollment).
3. Vault item **`shared/macos-ci-runner/account-credentials`**: admin
   username/password; machine name or LAN IP in notes.

## Enrollment runbook (remote, from any enrolled machine)
1. SSH in with the vault credentials; enroll on the tailnet
   (`tailscale-authkey-*` pattern or interactive `tailscale up`).
2. Install runner (as the login user, NOT root):
   ```sh
   mkdir ~/actions-runner && cd ~/actions-runner
   curl -o runner.tar.gz -L https://github.com/actions/runner/releases/latest/download/actions-runner-osx-arm64-<ver>.tar.gz
   tar xzf runner.tar.gz
   TOKEN=$(gh api -X POST orgs/gophersys/actions/runners/registration-token -q .token)
   ./config.sh --url https://github.com/gophersys --token "$TOKEN" \
       --labels self-hosted,macOS,music-ci --unattended
   ./svc.sh install && ./svc.sh start    # launchd agent, GUI session
   ```
3. The machine must stay logged in (GUI session) for Electron smoke tests.
4. Node 20+ present (runner downloads toolcache otherwise).
5. Flip the workflow's `build-mac` runs-on; keep hosted as fallback comment.
6. Update this identity to `status: active`; regenerate the machines index.

## Notes
- Runner user should NOT have the Bitwarden vault unlocked; CI needs no
  vault access (GITHUB_TOKEN only).
- Deep-test lane (future): a scheduled workflow with `--capture-test`
  against real system audio — only meaningful on this box.
