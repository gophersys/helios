# libs/zephyr

Coming — will host Zephyr RTOS modules and subsystems shared across
embedded firmware projects in the brain ecosystem.

## Layout (once populated)

Each Zephyr module lives in its own directory directly under this subtree:

```
zephyr/
├── <module-name>/
│   ├── project.json        # Nx wiring, nx:run-commands only
│   ├── ctl.sh              # bash source of truth, chmod +x
│   ├── zephyr/
│   │   └── module.yml      # Zephyr module manifest
│   ├── CMakeLists.txt
│   ├── Kconfig
│   └── src/
```

## Integration model

Zephyr modules here are consumed by firmware projects (which live in
`projects/<p>/apps/firmware/`) via their `west.yml` manifests. The
firmware project pulls this `libs/` submodule and references individual
modules by path.

## Verbs

Every Zephyr module's `ctl.sh` implements, at minimum:

- `build`      — build the module's twister test applications (if any)
- `test`       — run twister against the module's test suites
- `lint`       — run the project's code formatter (clang-format, etc.)
- `check`      — static analysis (cppcheck, coccinelle) where applicable

Modules are typically not "published" — they are consumed by git
reference from the firmware project's `west.yml`. No `publish` verb is
required unless a module is explicitly released externally.

Target cache policy:

- `build`, `check`, `lint`, `test` → `cache: true` with `CMakeLists.txt`,
  `Kconfig`, `zephyr/module.yml`, and `src/**` as `inputs`

## Authoring reference

See the skill documentation at:

```
brain/.claude/skills/development-nx-run-command/
```

The project interface is `project.json` + `ctl.sh`. Zephyr's build
system and module plumbing (`CMakeLists.txt`, `Kconfig`,
`zephyr/module.yml`) are permitted at the module root because the
Zephyr / west toolchain requires them; see the brain skill's
`hard-rules.md` rule 1.
