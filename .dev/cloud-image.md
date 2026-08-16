# cloud-image

phase:    intake
repo:     gophersys/.devcontainer
branch:   feat/cloud-image
worktree: ~/code/.worktrees/.devcontainer-cloud-image
pr:       -
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

(nothing yet)

## Blocked

(nothing)

## Next

Write the red test expectations and prove them failing.
