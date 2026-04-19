# libs/rust

Coming — will host Rust crates shared across all brain-ecosystem project
monorepos.

## Layout (once populated)

Each crate lives in its own directory directly under this subtree:

```
rust/
├── <crate-name>/
│   ├── project.json        # Nx wiring, nx:run-commands only
│   ├── ctl.sh              # bash source of truth, chmod +x
│   ├── Cargo.toml          # crate manifest
│   └── src/
```

The top-level `libs/` repo does NOT define a Cargo workspace. Each crate
stands on its own and is referenced by consumers via path or git
dependency. This matches the submodule model: projects pin a specific
`libs` commit and consume individual crates from it.

## Verbs

Every Rust crate's `ctl.sh` implements, at minimum:

- `build`      — `cargo build --release`
- `test`       — `cargo test`
- `lint`       — `cargo clippy -- -D warnings`
- `check`      — `cargo check` (fast type-only pass)
- `publish`    — `cargo publish` to the configured registry (gated)

Target cache policy:

- `build`, `check`, `lint`, `test` → `cache: true` with `Cargo.toml`,
  `Cargo.lock` (if tracked), and `src/**` as `inputs`
- `publish` → `cache: false`

## Authoring reference

See the skill documentation at:

```
brain/.claude/skills/development-nx-run-command/
```

The project interface is `project.json` + `ctl.sh`. The language-native
manifest (`Cargo.toml`, plus `Cargo.lock` when tracked) is permitted at
the crate root because `cargo` requires it; see the brain skill's
`hard-rules.md` rule 1.
