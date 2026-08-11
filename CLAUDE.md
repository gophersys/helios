# CLAUDE.md

This is the **Eden** monorepo. Eden is an agentic-engineering platform. Eden is in the
architecture and bootstrap phase. There is no production code yet. The kernel is the first
build target.

## Read before you act

- `docs/architecture/README.md` — the canonical document set. It gives the reading order, the
  epistemic legend (✅🔶⚠️🧩), the source registry, the Eden invariants E1–E7 and the cohesion
  contract. The cohesion contract says that one concept has one home. Cite that home. Never
  define the concept a second time.
- `docs/README.md` — the documentation scheme (ADR-0010). It says where a new document belongs
  and how to name it.
- `docs/architecture/09-build-execution-plan.md` — the current workstreams and milestones.

## Hard rules

- **Naming:** the system is Eden. Never introduce a `helios` identifier (invariant E7). Use the
  full name per HNS-1 (10 §5): `configuration` not `config`, `kubernetes` not `k8s`,
  `dependencies` not `deps`. Never use the names `util`, `common` and `core`.
- **Decisions:** `docs/architecture/adr/` holds the decisions that are made. Do not open them
  again. Put a decision that is not made in `docs/architecture/open-decisions.md`. Do not put it
  in prose.
- **Documents:** a new document follows the scheme of 4 classes: canonical spec, research note,
  directory README or attic. Use lowercase kebab-case file names. A spec carries a status header
  and epistemic tags. Move a superseded document to `docs/attic/`. Never delete it.
- **Pipeline vocabulary:** "phase" is a step of the SDLC pipeline of 10 phases. "stage" is the
  environment axis (development/test/staging/production). Never mix the 2 words.
- **Commits:** use Conventional Commits. Do not add an AI or LLM attribution line (ratified in
  ADR-0010 — omit the `Co-Authored-By` trailer). Always push after you commit (standing
  directive, 2026-06-12: never lose data; save and push).
- **Go:** the floor is Go 1.26. Write in Go everything that can be Go (ADR-0003). The UI is
  Svelte 5 (ADR-0004).
- `poc/` holds material for reuse. Read it freely, but code enters `main` only through the gates
  (ADR-0009 D). Do not change a PoC artifact in place.
- Never edit a generated artifact by hand, for example `docs/architecture/eden-architecture.html`.
  Generate it again with `node docs/tools/render-html.mjs`.
- **A subagent or a workflow always runs on the Opus model** (standing directive, 2026-06-12).
  The reason is the cost of use. The main loop gives the orders and Opus does the work.

## Workspace facts

- This is an Nx workspace with yarn 4. The canonical pull-request gate is
  `bash .ci/ctl.sh affected-check`. The gate does nothing until you run `yarn install`.
- `libs/`, `infrastructure/` and `.devcontainer/` are git submodules. Each one is a separate
  repository with separate commits.
- Nx Cloud is disabled in `nx.json` (ratified in ADR-0010). Keep it disabled.
- **Secrets (GitOps):** Argo CD drives the cluster from the `infrastructure/` submodule of this
  repository. The single source of truth for secrets is the cloud Vaultwarden at
  `secrets.mateosegura.com`. The secrets flow from Vaultwarden into kubernetes through the
  External Secrets Operator and a `bw-serve` bridge. Only a non-secret `ExternalSecret` CR goes
  in git. Never put a plaintext secret in git.
- To deploy the secrets of an Eden app, add an `ExternalSecret` that references the `vaultwarden`
  ClusterSecretStore. Do not create a kubernetes Secret by hand. Do not add a `.env` file. A
  deploy of our own codebase uses the reserved Argo `apps` AppProject. For the wiring of the
  operator and the bridge, see `infrastructure/platform/core/secrets-operator/` and
  `infrastructure/platform/services/gitops/registry/app-external-secrets.yaml`. See also
  `infrastructure/docs/secrets-guide.md` and `infrastructure/docs/runtime-secrets.md`.
- **User connectors** hold a secret for one user or one organization. The third-party credentials
  of a user (`claude-api`, `github`, `openrouter`) live in the **connectors** domain of
  `platformgateway`. Postgres holds them with envelope encryption: `libs/go/envelope` seals a DEK
  for each secret under a KEK from the platform Vault. You write the value one time. You can never
  read it back. It is never in git. An agent resolves one connector through the
  `eden://connector/<id>` scheme behind the frozen `secrets.Provider`. See ADR-0029 and
  `docs/architecture/19-connectors-and-user-secrets.md`.

## The devcontainer first, and the harness versions

- **Do the development work inside the devcontainer.** `.devcontainer/base` is the substrate for
  development and for CI. The agent pods that Eden starts use the same image. Start the container
  with `bash .devcontainer/base/ctl.sh up`. The command starts a long-lived container, mounts the
  repository at `/workspace`, mounts the docker socket, and installs the pinned harnesses and
  hnslint. Then run `ctl.sh exec -- <cmd>` or `ctl.sh shell`.
- The image contains the gate toolchain of ADR-0020: gofumpt, golangci-lint, govulncheck,
  gosec, gremlins, benchstat, hnslint, k3d, kind, nats and bun. If a tool is absent, the gate
  fails. Do not skip the tool. Do not run the Go gate or the Go tests on the host. Run them in
  the container.
- **hnslint comes from its own repository now.** This sentence claimed the image held it while it
  held nothing of the kind: it was in neither `.devcontainer/base/Dockerfile` nor
  `runner/Dockerfile`. Only `post-create` built it, from the bind-mounted `tools/hnslint`, so a
  developer had it and CI never did, and `gophersys/libs` failed `phase-gate implementation` with
  `missing required tool(s): hnslint`.
  It is now `gophersys/hnslint`, a public repository, pinned by `HNSLINT_VERSION` in the base
  Dockerfile. It is public because an image build cannot authenticate to a private repository,
  which is the same reason `gophersys/cictl` is public. Proven in the pod shape by
  `bash ctl.sh verify-runner-image e0c6bc5`, which asserts `hnslint on PATH`.
- **The harness versions are pinned (ADR-0021).** The versions of `claude`, `omp` and `codex` are
  only in `harnesses/versions.env`. Never install the `latest` version of a harness implicitly.
  The `harness-conformance` CI job gates a change to a pin, and the job uses the real harness and
  the real provider. `harness-upgrade-check` opens the pull request that changes the pin. The pin
  for `bun` is the `BUN_VERSION` ARG in the base Dockerfile. It is built into the image and it is
  not in the manifest.

## Go enforcement (ADR-0018)

- **Git hooks (set them up one time):** the tracked hooks are in `.githooks/`. Point git at them
  with `git config core.hooksPath .githooks`. On the staged Go code, `pre-commit` runs gofumpt,
  golangci-lint for each changed module, and hnslint for each changed `libs/go/<lib>`.
  `pre-push` also runs `go test -race` for each changed module. Use `--no-verify` only in an
  emergency, because CI runs the same gate again.
- **AI authoring (layer 2):** the `project-go` Claude Code plugin is in `libs/plugins/project-go/`
  and is registered in `libs/.claude-plugin/marketplace.json`. It injects `libs/.claude/rules/`
  at the start of a session. It lints every edit of a `*.go` file (PostToolUse). It gates
  `git commit` and `git push` (PreToolUse). Install it with
  `claude plugin marketplace add ./libs && claude plugin install project-go@eden-libs`.
- **`hnslint`** is the structural check for HNS-1. It is at `tools/hnslint`. Install it with
  `(cd tools/hnslint && GOWORK=off go install ./cmd/hnslint)`. The shared configuration of the
  linter is `libs/.golangci.yml`.

## Library pipeline (ADR-0020)

This pipeline extends the ADR-0018 enforcement above. It does not replace it. **Implement every
Go library one phase at a time. Never declare a library complete before
`bash ./ctl.sh phase-gate qa` passes.**

- **There are 4 phases, and 1 gate for each phase.** Run
  `bash ./ctl.sh phase-gate <architecture|implementation|testing|qa|all>` in the library. The
  bodies of the verbs are in `libs/go/_ctl/lib.sh` one time only, and the `ctl.sh` of each library
  only dispatches to them. Each gate must pass before the next gate. `phase-gate all` runs the
  gates 1 to 4 and stops at the first failure. Here "phase" is the SDLC step. It is never the
  environment "stage".
- **The TDD order is mandatory.** Write the fake binding and the conformance cases first, and they
  must fail. Then write the bodies and make the tests pass. A change that breaks the exported
  surface against the frozen `<lib>/.apibaseline` is the most serious error (10 §9), and it aborts
  the gate.
- **The test taxonomy has 8 dimensions.** Each library has verbs for them: `property`
  (rapid), `leak` (goleak), `lifecycle`, `load`, `integration` (real docker, k3d and kind; never a
  mock), `vuln`/`sast`/`secretscan`, `bench-guard`, `maintainability`, `mutate` and
  `cover-floor`. The floor of `cover-floor` applies to each package: 80% for a leaf and 70% for a
  substrate. The devcontainer contains every tool, so an absent tool is a gate FAILURE. Do not
  skip the tool.
- **AI instrumentation:** SessionStart injects the rules in
  `libs/.claude/rules/20-library-pipeline.md` and `21-test-taxonomy.md`. The first file holds the
  sequence of the 4 phases, the rule against a shortcut and the rule for a real substrate. The
  second file holds the Go templates for each dimension. `session-start.sh` knows the current
  phase. `pre-git-gate.sh` enforces the full taxonomy before a commit or a push. The **Stop hook**
  `stop-phase-check.sh` blocks the end of a turn while `phase-gate qa` fails for a changed
  library.
- The canonical spec is `docs/architecture/14-library-engineering-pipeline.md` (ADR-0020).

## Release and home deploy (ADR-0028)

Make a stable release with 1 verb: `bash deploy/ctl.sh release v<semver>`. A `v<semver>` tag
starts `release.yml`, and a byte-identical copy of that workflow is in `.ci/providers/github/`.
The workflow builds the 4 images, pushes them to `ghcr.io/gophersys/eden/*`, and opens a
promotion pull request against `gophersys/infrastructure` that pins the digests. **Argo CD** then
reconciles `apps/eden/` onto the home cluster, in the namespace `eden`, at
`https://eden.mateosegura.com`. Check the status with `deploy/ctl.sh release-status v<semver>`.

The secrets of the app are Vault-native (`vault://eden/production#…`, `token-file` mode). Never
copy the JWT credentials or the harness credentials into kubernetes Secrets. Do not confuse
`deploy demo` with `release`. `deploy demo` is local and runs in the container. `release` deploys
to the home cluster.

The decision is **ADR-0028**. The operational runbook is
`docs/architecture/18-release-and-home-deploy.md`. `infrastructure/apps/eden/README.md` holds the
backing stack, the 4 imperative secrets and the Vault ceremony.
