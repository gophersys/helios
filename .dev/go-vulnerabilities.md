# go-vulnerabilities

phase:    plan
repo:     gophersys/libs
branch:   fix/go-vulnerabilities
worktree: ~/code/.worktrees/libs-vulns
pr:       -
attempt:  0/2

## Goal

Clear the 2 govulncheck advisories that block gophersys/eden#7:
  GO-2026-5856  reported in forge, objectstorage, secrets
  GO-2026-5668  reported in orchestrator, workspaceprovider

When this is done, the vuln verb passes for those 5 libraries and eden#7 loses 1
of its 3 blockers.

## Plan

Phase 1 running.

## Proven

- The advisories come from eden's affected-gate on gophersys/eden#7, where the
  failed tasks were forge:vuln, secrets:vuln, platformgateway:vuln,
  orchestrator:vuln and objectstorage:vuln.
- Nothing else is proven yet. The planner was told to run govulncheck itself and
  not to trust that second-hand summary, including whether each advisory is
  REACHABLE rather than merely present in a dependency.

## Blocked

Nothing.

## Next

Phase 2 once the plan lands.
