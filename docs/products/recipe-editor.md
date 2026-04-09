---
min_role: DEVELOPER
---
# Recipe Editor

Write and edit `build.sh` — the shell script that compiles firmware inside the build container. Embedded in the [Stage Config Wizard](stage-config.md) at Step 3.

## Opening

Product detail → **Validation** tab → configure or edit a stage → **Step 3: Build Recipe**.

Empty recipes show a **Start with template** button that scaffolds a working `build.sh`.

## Editor

CodeMirror with bash syntax highlighting, line numbers, and bracket matching.

Toolbar actions:

- **Check** — validates against SDK requirements
- **Run** — test build with current recipe content (does not save)

Unsaved changes indicator shows when content differs from the saved version.

## Validation rules

Check verifies four things:

- Shebang line (`#!/bin/bash`)
- Error handling (`set -e`)
- SDK initialization (`concord_init` sourced)
- Artifact emission (at least one `concord_emit_hex` or `concord_emit_cfw` call)

## SDK variables

The build service injects these before executing your recipe:

| Variable | Content |
|----------|---------|
| `CONCORD_BOARD` | Zephyr board name from target config |
| `CONCORD_FW_TYPE` | Firmware type identifier |
| `CONCORD_VARIANT` | Build variant string |
| `CONCORD_VERSION` | Firmware version |
| `CONCORD_OUTPUT_DIR` | Output directory path |

## Save vs publish

**Save** — persists as draft. Does not affect running builds.

**Publish** — promotes to active. Next triggered build uses this version.
