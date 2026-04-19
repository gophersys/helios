# libs/typescript

Coming — will host TypeScript/JavaScript libraries shared across all
brain-ecosystem project monorepos.

## Layout (once populated)

Each library lives in its own directory directly under this subtree:

```
typescript/
├── <lib-name>/
│   ├── project.json        # Nx wiring, nx:run-commands only
│   ├── ctl.sh              # bash source of truth, chmod +x
│   ├── package.json        # declared dependencies (no lockfile — parent owns it)
│   ├── tsconfig.json
│   └── src/
```

## Verbs

Every TypeScript library's `ctl.sh` implements, at minimum:

- `build`      — compile to `dist/` (`tsc` or the chosen bundler)
- `test`       — run the unit test suite
- `lint`       — run ESLint / Biome
- `typecheck`  — `tsc --noEmit`
- `publish`    — publish to the configured registry (gated)

Target cache policy:

- `build`, `lint`, `typecheck`, `test` → `cache: true` with appropriate `inputs`
- `publish` → `cache: false` (side-effectful, external)

## Authoring reference

See the skill documentation at:

```
brain/.claude/skills/development-nx-run-command/
├── SKILL.md
├── reference/hard-rules.md
├── reference/verb-catalog.md
└── templates/
```

The `templates/ctl.sh` and `templates/project-no-configurations.json`
files are the canonical starting points. Do not add files beyond
`project.json` + `ctl.sh` at the library root.
