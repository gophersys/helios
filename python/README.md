# libs/python

Coming — will host Python libraries shared across all brain-ecosystem
project monorepos.

## Layout (once populated)

Each library lives in its own directory directly under this subtree:

```
python/
├── <lib-name>/
│   ├── project.json        # Nx wiring, nx:run-commands only
│   ├── ctl.sh              # bash source of truth, chmod +x
│   ├── pyproject.toml      # uv / poetry / hatch metadata
│   └── src/<lib_name>/
```

## Verbs

Every Python library's `ctl.sh` implements, at minimum:

- `build`      — `uv build` (or `poetry build`) → wheel + sdist in `dist/`
- `test`       — `pytest` with the library's test suite
- `lint`       — `ruff check` (or `flake8`)
- `typecheck`  — `mypy` (or `pyright`)
- `publish`    — upload to the configured index (gated)

The package manager (uv vs poetry vs hatch) is chosen per-library and
encapsulated inside its `ctl.sh`. The consumer never calls the tool
directly — everything goes through `nx run <project>:<verb>`.

Target cache policy:

- `build`, `lint`, `typecheck`, `test` → `cache: true` with appropriate `inputs`
- `publish` → `cache: false`

## Authoring reference

See the skill documentation at:

```
brain/.claude/skills/development-nx-run-command/
```

The project interface is `project.json` + `ctl.sh`. The language-native
manifest (`pyproject.toml`) is permitted at the library root because the
Python toolchain requires it; see the brain skill's `hard-rules.md`
rule 1.
