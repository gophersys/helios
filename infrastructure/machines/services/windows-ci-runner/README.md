# windows-ci-runner (PLANNED)

Windows VM on pve-00 as a gophersys org Actions runner. Consumer:
`gophersys/audiomotion-visualizer` `build-win` job (swap
`runs-on: windows-latest` → `[self-hosted, Windows, music-ci]`).

## Build runbook (Proxmox side)
1. pve-00: create VM (4 vCPU / 8G / 80G thin LV, q35, OVMF/UEFI + TPM 2.0
   for Win11). Attach Windows 11 ISO + VirtIO drivers ISO.
2. Install Windows 11 Pro (eval license initially; license decision before
   `status: active`). Load VirtIO storage/net drivers during setup.
3. Install qemu-guest-agent + VirtIO tools; enable RDP; static DHCP lease.
4. Tailscale for Windows; join tailnet as `windows-ci-runner`.
5. Debloat + disable sleep; auto-login for the runner user (GUI session
   needed for Electron smoke tests).

## Runner install (PowerShell, as runner user)
```powershell
mkdir C:\actions-runner; cd C:\actions-runner
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/latest/download/actions-runner-win-x64-<ver>.zip -OutFile runner.zip
Expand-Archive runner.zip .
$TOKEN = gh api -X POST orgs/gophersys/actions/runners/registration-token -q .token
./config.cmd --url https://github.com/gophersys --token $TOKEN --labels self-hosted,Windows,music-ci --runasservice --unattended
```
Node 20+ via winget; git via winget.

## Notes
- Electron GUI smoke tests need an interactive session; if the service
  session can't open windows, run the runner as a startup app in the
  auto-logged-in session instead of a Windows service.
- Keep hosted `windows-latest` in the workflow as a commented fallback.
