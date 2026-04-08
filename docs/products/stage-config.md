---
min_role: DEVELOPER
---
# Stage Config Wizard

Every product in Concord runs firmware through a five-stage validation pipeline: Smoke, Driver, Integration, Regression, and FUOTA. Each stage needs to know what hardware to target, which branches to watch, how to sign the output, and what recipe to build with. The Stage Config Wizard walks you through all of that in four steps.

## Initialization

Before configuring individual stages, you need to create them. Open **Products > [your product] > Validation** tab. A fresh product shows "No validation stages configured" with an **Initialize Stages** button. Click it. Concord creates all five stage entries:

| Stage | Name | Purpose |
|-------|------|---------|
| 1 | Smoke | Quick boot check -- does the firmware start and respond? |
| 2 | Driver | Peripheral and driver-level validation |
| 3 | Integration | Cross-subsystem tests, both firmware types |
| 4 | Regression | Full permutation across all variants and overlays |
| 5 | FUOTA | Over-the-air update verification end-to-end |

After initialization, each stage shows a **Configure** button. Once configured, that button changes to **Edit**.

## Opening the wizard

Click **Configure** (or **Edit**) on any stage row in the Validation tab. The wizard opens as a modal dialog with a step indicator at the top. The header shows the stage number: "Configure Stage 1", "Configure Stage 2", etc.

Four steps, in order:

## Step 1: Target & Triggers

Three sections on this step.

**Target Hardware Revision** -- select which board revision this stage validates against. The dropdown lists active revisions only; draft or deprecated revisions do not appear. If you only have one active revision, it is pre-selected.

**Watch Branch** -- the git branch the build system polls for new commits. Defaults to `main`. Change it to `develop`, `release/v1.0`, or whatever branch feeds this stage.

**Triggers** -- five options, any combination:

| Trigger | Behavior |
|---------|----------|
| Pull Request | Build on PR creation and updates |
| Merge | Build when a PR merges to the watched branch |
| Auto (after previous) | Automatically run when the preceding stage passes |
| Schedule | Run on a cron expression (e.g. `0 2 * * *` for nightly at 2am) |
| Manual | On-demand from the UI or API |

Selecting **Schedule** reveals a **Cron Expression** input field with placeholder `0 2 * * *`. Standard five-field cron syntax.

Click **Next** to proceed.

## Step 2: Signing Key

Select which signing key to use for firmware images produced by this stage. If you have keys configured at the product level, they appear in a list. Pick one.

If no signing keys exist, the step shows a warning. You can proceed without a key -- unsigned builds are valid for Smoke and Driver stages. For FUOTA, you will need one eventually (unsigned CFW files are rejected by the bootloader).

Click **Next** to proceed.

## Step 3: Build Recipe

The [Recipe Editor](recipe-editor.md) loads here. Write or edit the `build.sh` script that compiles firmware for this stage.

Two toolbar actions matter at this step:

- **Check** -- validates the recipe against SDK requirements (shebang, error handling, `concord_init`, artifact emission).
- **Run** -- kicks off a test build with the current recipe content. Useful for catching toolchain errors before committing to the stage config.

If the recipe is empty, you see "No build recipe configured" with a **Start with template** option that scaffolds a working `build.sh`.

Click **Next** to proceed to the final step.

## Step 4: Review & Save

The Review Configuration screen summarizes everything:

- **Watch Branch** -- the branch you selected in Step 1.
- **Triggers** -- which trigger types are enabled.
- **Signing Key** -- the selected key, or "None" if skipped.
- **Build Recipe** -- recipe status (configured, empty, or with validation warnings).
- **Build Matrix** -- the table of firmware variants this stage will produce (see [Build Matrix](build-matrix.md)).

Review the summary. When satisfied, click **Save & Enable Stage**. The wizard closes. Back on the Validation tab, the stage status changes to **ACTIVE** and the Configure button becomes **Edit**.

## Editing a configured stage

Configured stages show an **Edit** button instead of Configure. Clicking it re-opens the wizard with all fields pre-populated. Make changes, navigate through the steps, and save again. The stage remains ACTIVE throughout -- edits take effect on the next triggered build.

## Related

- [Build Matrix](build-matrix.md) -- what firmware variants each stage produces
- [Recipe Editor](recipe-editor.md) -- the `build.sh` editor in detail
- [Validation overview](../validation/index.md) -- how stages fit into the pipeline
- [Stages Overview](../validation/stages-overview.md) -- stage execution order and dependencies
