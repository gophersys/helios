---
min_role: DEVELOPER
---
# Stage Config Wizard

Configure validation stages. Four steps: target and triggers, signing key, build recipe, review.

## Initialization

Product detail → **Validation** tab. New products show **Initialize Stages**. Creates all five entries:

| Stage | Name | Purpose |
|-------|------|---------|
| 1 | Smoke | Boot check — does firmware start? |
| 2 | Driver | Peripheral and driver validation |
| 3 | Integration | Cross-subsystem, both firmware types |
| 4 | Regression | Full variant permutation |
| 5 | FUOTA | Over-the-air update end-to-end |

Click **Configure** on any stage to open the wizard.

## Step 1: Target & Triggers

- **Board revision** — which revision this stage validates. Active revisions only.
- **Watch branch** — git branch the poller monitors. Defaults to `main`.
- **Triggers** — any combination of:

| Trigger | Behavior |
|---------|----------|
| Pull Request | Build on PR create/update |
| Merge | Build on merge to watch branch |
| Auto | Runs when the previous stage passes |
| Schedule | Cron expression |
| Manual | On-demand via UI or API |

## Step 2: Signing Key

Select a signing key for firmware images. Optional for Smoke/Driver. Required for FUOTA — unsigned CFW files are rejected by the bootloader.

## Step 3: Build Recipe

The [Recipe Editor](recipe-editor.md). Write or edit `build.sh`. Check validates SDK requirements. Run kicks off a test build.

## Step 4: Review & Save

Summary of all configured values: branch, triggers, key, recipe, and [build matrix](build-matrix.md). Click **Save & Enable Stage** to activate.

## Editing

Configured stages show **Edit** instead of Configure. Opens the wizard with fields pre-populated. Edits take effect on the next triggered build.
