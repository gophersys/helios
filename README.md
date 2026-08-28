# Eden

Eden is the product and the organization workspace. Application code, shared
libraries, infrastructure, tools, research, development images, and engineering
instrumentation live in this repository with one Git history.

```text
apps/             deployable applications
libs/             shared libraries
infrastructure/   platform and GitOps configuration
tools/            cictl, hnslint, and repository tools
research/         embedded, hardware, and UI research
.devcontainer/    one development environment; base/cloud/buildkit image sources
```

Start development with `./ctl.sh up`, then enter it with `./ctl.sh shell`.
Run an Nx target with `./ctl.sh run <project> <target>`.

Automatic CI is intentionally disabled during the consolidation. Local
commands remain available; CI will return after the project graph and command
surface are small enough to describe in one place.
