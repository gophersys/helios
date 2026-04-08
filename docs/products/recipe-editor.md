---
min_role: DEVELOPER
---
# Recipe Editor

The recipe editor is a CodeMirror-based IDE embedded in the [Stage Config Wizard](stage-config.md). It edits `build.sh` -- the shell script that compiles your firmware. You write the recipe once per stage, and the build service executes it inside a containerized toolchain every time a build triggers.

## Opening the editor

Navigate to **Products > [your product] > Validation** tab, then open the wizard for any stage (Configure or Edit). The editor loads at **Step 3: Build Recipe**.

If no recipe exists yet, the editor shows a "No build recipe configured" message with a **Start with template** button. Click it to scaffold a working recipe.

## Editor layout

The editor mimics a standalone IDE:

**Status bar** -- shows the filename (`build.sh`) on the left and cursor position (`line:col`) on the right. The position updates as you navigate.

**Editor pane** -- full CodeMirror instance with syntax highlighting for bash. Line numbers, bracket matching, and standard keyboard shortcuts work as expected.

**Toolbar** -- three actions sit above the editor:

- **Check** -- validates the recipe against the SDK requirements (see below).
- **Run** -- executes a test build using the current recipe content. Does not save first.
- **Save** / **Publish** -- persists the recipe to the API.

An **Unsaved changes** indicator appears in the toolbar whenever you modify the editor content. It clears after a successful save.

## Template scaffold

The default template includes:

```bash
#!/bin/bash
set -e

# Source Concord SDK
source concord_init

# Build firmware
west build -b ${CONCORD_BOARD} ...

# Emit artifacts
concord_emit_hex build/zephyr/zephyr.hex
concord_emit_cfw build/zephyr/app_update.bin
```

The template gives you a working starting point. The shebang (`#!/bin/bash`), error handling (`set -e`), and SDK function calls are all required. Delete them and the Check validator will flag it.

## Validation

Click **Check** to run recipe validation. The validator inspects the script for:

- **Shebang line** -- must start with `#!/bin/bash`.
- **Error handling** -- `set -e` or equivalent.
- **SDK initialization** -- `concord_init` must be sourced.
- **Artifact emission** -- at least one `concord_emit_hex` or `concord_emit_cfw` call.

Results appear in a checklist panel next to the editor. Each item shows pass/fail status. Fix the failures, re-check, and proceed to the Review step.

## SDK substitution variables

The build service injects environment variables before executing your recipe. Use them instead of hardcoding board names or paths:

| Variable | Value | Example |
|----------|-------|---------|
| `CONCORD_BOARD` | Zephyr board name from the target config | `corekinect_alpha_b0` |
| `CONCORD_FW_TYPE` | Firmware type identifier | `alpha_mfg_fw` |
| `CONCORD_VARIANT` | Build variant string | `debug`, `release` |
| `CONCORD_VERSION` | Firmware version from the product config | `0.8.3` |
| `CONCORD_OUTPUT_DIR` | Where to write build outputs | `/build/output` |

These variables are available in the sidebar checklist and as hover tooltips in the editor. Reference them with `${}` syntax in your script.

## Save and publish

**Save** persists the recipe as a draft. The draft is only visible in the wizard and does not affect running builds.

**Publish** promotes the draft to the active recipe. The next build triggered for this stage will use the published version.

Both actions require passing validation first. If the Check step has failures, Save and Publish remain available but the Review step will warn about unresolved issues.

For how recipes fit into the broader build pipeline, see [Build Configuration](../builds/build-configuration.md). For stage-level settings around the recipe, see [Stage Config](stage-config.md).
