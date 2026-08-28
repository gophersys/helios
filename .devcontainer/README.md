# Eden development environment

Eden has one development container: `.devcontainer/devcontainer.json`, backed
by `ghcr.io/gophersys/cloud`. Start it from the repository root:

```sh
./ctl.sh up
./ctl.sh shell
```

The repository owns only three container artifacts:

- `base` — the smaller shared toolchain image.
- `cloud` — the complete development and CI image.
- `buildkit` — the pinned GHCR mirror used by multi-architecture builds.

Image source lives under `base/` and `cloud/`; BuildKit mirroring lives in
`.ci/mirror-buildkit.sh`. Manage them through `./ctl.sh image ...` from Eden.
