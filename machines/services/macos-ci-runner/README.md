# macos-ci-runner (PLANNED)

The MacBook in the living room, used as a GitHub Actions runner for the gophersys
org. The consumer is the release workflow of
`gophersys/audiomotion-visualizer`. In that workflow, change the `runs-on` of
`build-mac` from `macos-14` to `[self-hosted, macOS, music-ci]`.

## Why a self-hosted runner instead of the hosted macos-14 runner used today
- It costs 0 Actions minutes. GitHub bills macOS at 10 times the rate on a
  private repo.
- It can run deep tests that only macOS supports and that a hosted runner cannot
  do: the TCC flows for screen recording, and a real capture of loopback audio
  (`--capture-test` while music plays).

## Prerequisites — the owner does these once
1. On the MacBook: System Settings → General → Sharing → set **Remote Login** to
   ON. Record the Computer Name.
2. Stop the machine from sleeping: Settings → Displays → Advanced → prevent sleep
   on power. As an alternative, run `sudo pmset -c sleep 0 displaysleep 10` after
   the enrollment.
3. Create the vault item **`shared/macos-ci-runner/account-credentials`** with
   the admin username and password. Put the machine name or the LAN IP in the
   notes.

## Enrollment runbook — remote, from any enrolled machine
1. Open SSH with the vault credentials, then enroll the machine on the tailnet.
   Use the `tailscale-authkey-*` pattern, or run `tailscale up` interactively.
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
3. The machine must stay logged in, with a GUI session, for the Electron smoke
   tests.
4. Install Node 20 or later. Without it the runner downloads a toolcache.
5. Change the `runs-on` of `build-mac` in the workflow. Keep the hosted runner in
   a comment, as the fallback.
6. Set `status: active` in this identity file, and regenerate the machines index.

## Notes
- The runner user must NOT have the Bitwarden vault unlocked. CI needs no access
  to the vault. It needs `GITHUB_TOKEN` only.
- A deep-test lane in the future: a scheduled workflow that runs
  `--capture-test` against real system audio. That test has a purpose only on
  this machine.
