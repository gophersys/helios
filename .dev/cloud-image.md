# cloud-image

phase:    wait
repo:     gophersys/.devcontainer
branch:   feat/cloud-image
worktree: ~/code/.worktrees/.devcontainer-cloud-image
pr:       38
attempt:  0/2

## Goal

CLOUD PR1 of the image-consolidation program (task ledger #94, approved; spec:
image-architecture.md, FINAL). This PR is ADDITIVE and amd64-only. It creates
the `cloud` image — the reduced base plus the CI fold — next to the existing
images, and it changes no existing image. It adds: `versions.env` (the one home
for every tool version of the new mechanism), `_delta/components/*.sh` (small
idempotent install scripts, versions via environment), `cloud/Dockerfile` +
`cloud/ctl.sh` + `cloud/project.json` + `cloud/devcontainer.json`, the
`SMOKE_CLOUD` smoke set with the 5.5 GB size gate (R4), and the CI wiring in
all 4 places of the dependency graph. arm64, real-world gate tests, and
consumer migration are later serial PRs.

## Plan

plan: SELF-APPROVED (--auto, inside the approved #94 program; the orchestrator
task cites the ledger). The one risk weighed: the cloud Dockerfile reuses
base's proven RUN blocks, so the main failure mode is a drifted copy — held
down by copying blocks verbatim and asserting content in SMOKE_CLOUD.

1. RED — update the hermetic test expectations to demand the cloud image:
   `publish-order.test.sh` EXPECTED_JOBS += cloud,
   `dockerfile-args.test.sh` DOCKERFILES += cloud/Dockerfile,
   `platform-policy.test.sh` BUILD_PATH_FILES += cloud/ctl.sh +
   cloud/project.json. Prove each fails for the right reason.
2. GREEN — versions.env; _delta/components (db-clients, k9s, comforts, delve,
   protocols, buildx, runner, agents + ready-uninstalled terraform, aws, oci,
   ansible); cloud/Dockerfile (KEEP set, Go-cache cleanup, component calls,
   GOPHERSYS_DEVCONTAINER=cloud, CMD zsh); cloud/ctl.sh thin dispatcher;
   lib.sh gains IMAGE_BUILD_CONTEXT/IMAGE_DOCKERFILE + versions_env_build_args;
   BUILD_ORDER += cloud in ctl.sh and .ci/ctl.sh; cloud job in
   build-and-push.yml (build→smoke→push→verify, smoke BEFORE push) + the
   byte-identical provider copy; SMOKE_CLOUD + size gate in .ci/smoke.sh.
3. Local gates: `bash ./ctl.sh validate` + `bash ./ctl.sh test` green.
4. PR, watch checks up to 30 min, fix once if red. DO NOT MERGE.

## Proven

Only things that RAN, with the command and the result:

- RED: `bash _ctl/tests/publish-order.test.sh` exit=1 —
  `FAIL: ..._declares_the_expected_jobs` naming `cloud` in BOTH workflow
  copies. `bash _ctl/tests/dockerfile-args.test.sh` exit=1 —
  `FAIL: every_named_Dockerfile_exists` naming `cloud/Dockerfile`.
  `bash _ctl/tests/platform-policy.test.sh` exit=1 —
  `FAIL: every_named_build_path_file_exists` naming `cloud/ctl.sh` and
  `cloud/project.json`. All three failed for exactly the feature's reason.
- GREEN: `bash ./ctl.sh validate` exit=0 — `validate: OK` (shellcheck -x -S
  style over every script incl. the 12 components, jq, hadolint 2.14.0 in
  container mode, ARG discipline, all 6 Dockerfiles).
- GREEN: `bash ./ctl.sh test` exit=0 — all 7 suites: build 6, dockerfile-args
  29, guard 11, platform-policy 8, publish-order 28, tripwire 5,
  verify-published 6 checks, 0 failed.
- `bash cloud/ctl.sh help` exit=0 — the dispatcher sources the library and
  prints the cloud usage block.
- versions_env_build_args probe: 47 `--build-arg` pairs generated from
  versions.env (GO_VERSION=1.26.5, CICTL_VERSION=v0.1.0, OMP_VERSION=17.2.5
  spot-checked). BREAK-TEST: a file with the line `BADLINE` made it exit 1
  with "unreadable pin line ... 'BADLINE' — want NAME=value" — the check can
  fail.
- BUILD_ORDER agreement (the validate.yml step, run locally): both greps
  print `BUILD_ORDER=(base base-runner flutter zephyr zephyr-devbox cloud)`
  — AGREE.
- Provider copy: `cmp .github/workflows/build-and-push.yml
  .ci/providers/github/build-and-push.yml` exit=0 — byte-identical.
- Local amd64 image build: RUNNING in the background on this arm64 host
  (emulated; scratchpad cloud-build.log). Result and measured size recorded
  here when it finishes; remote CI is the prover either way.

## Review

Round 1 (REQUEST_CHANGES, 1 finding):

- Finding 1 (Correctness): the buildx call at cloud/Dockerfile:536 passes
  only DOCKER_BUILDX_VERSION of buildx.sh's 3 required pins; claim: the
  build fails there. DISPOSITION: edit applied (ca30aa6 — the call site now
  names its full pin contract), failure claim REFUTED by execution: a
  positive/negative build pair on the branch's real buildx.sh behind the
  byte-identical prefix — positive (all 3 pins as --build-arg) exit 0 with
  sha256 OK + `buildx v0.36.1` proof; negative (SHA args omitted) exit 1 at
  buildx.sh:17 naming DOCKER_BUILDX_SHA256_AMD64. Same-stage valued ARGs
  are RUN environment — the pin gate (Dockerfile:125-166) runs on exactly
  that mechanism. Spec §3.3 unchanged; no check weakened. Evidence posted
  on the PR (comment 5310082039).
- Gates after the change: validate OK, test OK (7 files).

## Blocked

(nothing)

## Next

Watch PR #38 round-2 review (triggered by the ca30aa6 push) up to 25 min.
The local amd64 build runs in the background (attempt 2 after a Docker-VM
disk exhaustion, not a Dockerfile defect); record its size here when done.
