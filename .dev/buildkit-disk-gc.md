# buildkit-disk-gc

phase:    fix
repo:     gophersys/infrastructure
branch:   fix/buildkit-disk-gc
worktree: ~/code/.worktrees/infrastructure-buildkit-disk-gc
pr:       -
attempt:  1/2

## Goal
Keep the persistent ARM64 BuildKit worker from exhausting its Docker VM disk, while retaining a useful warm cache and the portable DNS configuration already deployed.

## Plan
plan: SELF-APPROVED — the risk is pruning reusable build cache too aggressively; bound it at 20 GB while reserving 8 GB and targeting 12 GB free on the 58.4 GB Docker VM.

1. Extend the checked-in BuildKit configuration contract with explicit OCI-worker GC limits and regression fixtures.
2. Update the reproducible runbook and machine documentation with the storage contract and live verification commands.
3. Validate locally, deploy the checked-in config to the mini, recreate only the BuildKit daemon while preserving credentials, and prove its advertised GC policy and free space.
4. Open, review, and merge the infrastructure PR before retrying the failed image publication.

## Proven
- `ssh ... 'df -h /; docker system df; docker inspect eden-buildkitd ...'`: Docker VM was 98% full with 1.1 GiB available; local volumes used 36.07 GB and 26.07 GB was reclaimable; daemon config had DNS only and no GC policy.
- GitHub Actions run `33118737619`, base job `98679983255`: ARM64 agent installation failed with `ENOSPC` in npm cache.
- Red: `bash scripts/test-verify-buildkit-dns.sh` reported both `missing GC policy fails unexpectedly passed` and `unbounded cache fails unexpectedly passed`.
- Green: `bash scripts/test-verify-buildkit-dns.sh && bash scripts/verify-buildkit-dns.sh && git diff --check` passed all fixture cases and the static live contract.
- Live repair: the daemon reports `status=running state=eden-bk-state`, reads the checked-in GC thresholds, and its filesystem changed from 1.1 GiB free (98% used) to 36.3 GiB free (34% used). Exactly the six anonymous BuildKit cache volumes were removed.
- Devcontainer gate: `docker run --rm ... ghcr.io/gophersys/cloud:latest bash ctl.sh validate` passed and linted 39 shell scripts. The first run caught SC2015; the corrected run is green.
- Codex review round 1 requested the missing existing-daemon repair path and explicit verification. Accepted: the setup-only procedure would collide with the live container and did not identify the six removed volumes.

## Blocked


## Next
Re-run the fixture and devcontainer gates, then push review round 2.
