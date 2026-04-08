---
min_role: DEVELOPER
---
# Build Matrix

You have a product with two firmware types and three board targets. You need to know exactly which combinations produce hex files, which produce CFW files, and which do both. The build matrix is that table.

## Where to find it

The build matrix lives on the product detail page, inside the Validation tab. It appears in two places:

1. **Step 4 (Review)** of the [Stage Config Wizard](stage-config.md) when you configure or edit a stage.
2. **The stage detail panel** for any stage that is already configured.

Open the product, switch to the Validation tab, and either click **Edit** on a configured stage or **Configure** on a new one. Navigate through to the Review step. The Build Matrix section loads at the bottom.

## Reading the table

Each row is a firmware variant that the stage will build. Five columns:

| Column | Content |
|--------|---------|
| **Label** | Monospace identifier for the variant, e.g. `alpha_mfg_fw_b0_nrf52840`. Combines firmware type, board revision, and target. |
| **FW Type** | The firmware type name — `alpha_mfg_fw`, `alpha_fw`, etc. |
| **Variant** | Board revision and target chip (`b0 / nRF52840`). |
| **Produces** | Badges indicating output format: **HEX** (Intel hex for J-Link flashing), **CFW** (composite firmware for FUOTA), or both. |
| **Git Ref** | The branch or tag that sources the build. |

HEX and CFW badges are color-coded. A row with both badges means the build produces a flashable hex and a FUOTA-capable composite in a single pass.

## Entry counts per stage

The number of matrix entries grows with stage complexity. Default counts after initialization:

| Stage | Entries | Rationale |
|-------|---------|-----------|
| Smoke | 2 | Quick boot check, minimal variants |
| Driver | 3 | Adds driver-specific config overlays |
| Integration | 4 | Both firmware types, both protocol stacks |
| Regression | 6 | Full permutation of types and Kconfig variants |
| FUOTA | 8 | Every CFW variant, both targets, both tracks |

The entry count label (e.g. "2 builds") updates as you add or remove entries from the matrix. If the matrix is empty, the table is replaced with a "No build matrix entries" message.

## Reset to Defaults

Customized the matrix and regret it? The **Reset to Defaults** button restores the factory entries for the current stage. This button is visible to admin users in the Build Matrix section of the Review step. It does not save automatically  -- you still need to confirm through Save & Enable.

## How entries map to artifacts

Each matrix entry produces one build job. When the job completes, the resulting artifacts land in MinIO at the standard path. A hex file gets flashed via J-Link/SWD. A CFW file gets delivered over-the-air through the FUOTA pipeline.

For artifact storage paths and download mechanics, see [Build Artifacts](../builds/artifacts.md). For how recipes control the compilation step, see [Build Configuration](../builds/build-configuration.md).
