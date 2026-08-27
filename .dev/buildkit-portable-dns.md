# buildkit-portable-dns

phase:    pr
repo:     gophersys/infrastructure
branch:   fix/buildkit-portable-dns
worktree: ~/code/.worktrees/infrastructure-buildkit-portable-dns
pr:       -
attempt:  0/2
plan:     SELF-APPROVED — public resolver reachability can vary, so two independent anycast providers and a BuildKit-path preflight avoid dependence on one house, ISP, or resolver.

## Goal
The Mac build node resolves registries consistently after Docker restarts and after moving networks, without inheriting a router or ISP DNS server, and operators can prove the configured daemon and its build executor resolve through the intended portable configuration.

## Plan
Add one checked-in BuildKit daemon DNS configuration using independent public anycast resolvers. Add a focused verifier that first fails against the current unconfigured daemon, then validates the checked-in configuration and exercises resolution through a real BuildKit build. Update the reproduction runbook to install and mount the configuration. Deploy only after the active image rehearsal finishes, then prove the live daemon and build path.

Affected project: `machines/services/macos-ci-runner`. Fast test: its focused portable-DNS verifier. Integration: a minimal remote BuildKit build resolving `ghcr.io`. Risk: a network that blocks public port 53 still needs internet policy accommodation; no design can make registry builds independent of internet access. Excluded: router changes, ISP resolvers, DNS-over-HTTPS infrastructure, and unrelated Docker containers/images/volumes. CI agent instrumentation does not change.

## Proven
- `gh run view 33096981929 ...`: cloud and embedded failed with BuildKit executor DNS using `192.168.65.7`; cloud's native smoke had already proven Codex 0.150.1.
- `gh run view 33100408600 ...`: after Docker backend recovery, base and cloud completed successfully with no DNS recurrence while the remaining image jobs continued.
- RED — `bash ctl.sh verify-buildkit-dns`: `FAIL: missing checked-in BuildKit DNS config: machines/services/macos-ci-runner/buildkitd.toml` (exit 1).
- GREEN — `bash ctl.sh verify-buildkit-dns`: `ok: portable BuildKit DNS configuration is wired into daemon reproduction`.
- `shellcheck -S style scripts/verify-buildkit-dns.sh` and `bash -n scripts/verify-buildkit-dns.sh`: exit 0.
- `bash ctl.sh validate`: `lint-shell: linted 36 shell script(s)` and `validate: OK`.
- Live deployment recreated only `eden-buildkitd`, with `eden-bk-config:/etc/buildkit:ro`, `restart=unless-stopped`, and the pinned image digest; `docker exec ... cat /etc/buildkit/buildkitd.toml` showed the checked-in resolver configuration.
- `BUILDKIT_DNS_BUILDER=eden-mini-dns-proof bash ctl.sh verify-buildkit-dns --live`: an uncached remote arm64 build pulled `alpine:3.22`, ran `getent hosts ghcr.io`, and passed.
- Persistence drill — `docker restart eden-buildkitd`, inspect config, then `... verify-buildkit-dns --live`: config remained mounted and a fresh executor `RUN getent hosts ghcr.io` passed.
- Both live proofs loaded mTLS material into owner-only temporary directories, then shredded the files and removed their temporary builders; follow-up `find`/`buildx ls` found no residue.

## Blocked


## Next
Open the PR, read its validation log, and obtain independent review.
