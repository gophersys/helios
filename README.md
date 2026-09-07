# Eden

Eden is an opinionated Nx monorepo for building, operating, and evolving a
software platform with human and AI contributors. It provides one reproducible
development environment and one task interface without prescribing an
application framework.

## Start developing

### Prerequisites

- Git
- Docker Desktop or a compatible Docker engine
- The [Dev Container CLI](https://github.com/devcontainers/cli)

Clone Eden and enter its cloud development container:

```bash
git clone git@github.com:gophersys/eden.git ~/code/eden
cd ~/code/eden
devcontainer cloud
```

The host command stops at the container boundary. Run development actions with
Nx from inside the container:

```bash
nx check workspace
nx run-many -t check
codex
```

Use the shared command shape `nx <verb> <project> [-c <configuration>]`.
Projects expose small verbs such as `start`, `check`, `test`, `build`, `review`,
`publish`, and `deploy`.

## Credentials

Eden supports any Bitwarden-compatible server. Select one in the host
environment before starting the container:

```bash
export EDEN_SECRETS_SERVER=https://vault.example.com
devcontainer cloud
```

Inside the container, authenticate the Bitwarden CLI once and unlock only the
shell that needs access:

```bash
bw login
export BW_SESSION="$(bw unlock --raw)"
nx status devcontainer
```

Login state persists in a Docker volume. Unlock sessions remain ephemeral.
Secrets, session tokens, and credentials must never enter Git.

## Work with an agent

Eden supports Codex, Claude Code, and OMP from one canonical configuration in
`.agents`. Harness-specific files under `.codex`, `.claude`, and `.omp` are
generated adapters.

Use two high-level commands when working with an agent:

- `/request <work>` routes work through the research or software practice.
- `/question <topic>` routes a read-only question to the responsible project
  agents.

Project ownership lives in `.agents/ownership.json`. The lifecycle model lives in
`.eden/` and is rendered by tools rather than copied into documentation. Verify
the system and agent instrumentation with:

```bash
nx run agents:sync
nx check agents
nx check eden
nx review agents
nx check docs
```

`nx check agents` is deterministic and runs from the Git hook. `nx review
agents` adds a bounded Codex review for duplicated instructions, vague prose,
unnecessary scaffolding, and comments that do not improve the code.

## Repository map

```text
.agents/        canonical commands, agents, skills, ownership, and policy
.devcontainer/  reproducible local and remote development environment
.claude/        generated Claude Code adapters
.codex/         generated Codex adapters
.omp/           generated OMP adapters
docs/           concise human guidance
.eden/          research and software lifecycle definitions
```

Read [Documentation](docs/README.md) for the human guidance map and
[Operating model](docs/explanation/operating-model.md) for the lifecycle design.
