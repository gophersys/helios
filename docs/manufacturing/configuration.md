---
min_role: MAINTAINER
---
# Manufacturing Configuration

You have a product registered in Concord with at least one board revision, and you need to tell the system how to manufacture it. Until you do, the Manufacturing tab on the product detail page shows "Manufacturing not configured." and nothing else.

The configuration wizard walks through four steps. You'll select hardware, map test stages to firmware, define pass criteria, and review everything before it goes live.

## Opening the Wizard

Navigate to the product detail page and switch to the **Manufacturing** tab. Click **Configure Manufacturing** to open the wizard. A step indicator across the top tracks progress -- you'll see **Base Config** highlighted for step 1.

## Step 1 -- Base Config

Select the board revision this manufacturing config targets. The dropdown lists every active revision on the product (e.g., `B0`). Pick one and click **Next**.

Each board revision gets its own manufacturing config. If you ship two board revisions in parallel, configure them separately.

## Step 2 -- Stage Configuration

Three test stages appear: **Electrical**, **Flash**, and **POST**. These map to the physical operations the fixture performs on each board.

The **Firmware Source** section defaults to **Latest Build** -- the fixture pulls the most recent passing build artifact from Concord's build system when it flashes the board. You can pin a specific build version here instead, but most production lines leave it on latest so they're always flashing approved firmware without manual intervention.

Each stage has its own toggle and settings. All three are enabled by default. Disable a stage only if you have a specific reason -- skipping Flash, for example, means the fixture won't program the board at all.

## Step 3 -- Pass Criteria

Two settings control how the line handles failures:

**All stages must pass** -- When checked, a unit must clear Electrical, Flash, and POST to count as passed. Uncheck this only for engineering runs where you want partial results.

**Max retries** -- How many times the fixture should re-attempt a failing stage before marking the unit as failed. Zero means no retries. For production, 1 or 2 retries catches transient failures (bad contact, UART timeout) without masking real defects.

## Step 4 -- Review Configuration

A summary shows the board revision, enabled stages, firmware source, and pass criteria. Read it carefully -- this config drives every manufacturing session for this product going forward.

Click **Create Configuration** to save. The wizard closes and the Manufacturing tab now shows an **Enabled** badge instead of the "not configured" message. Operators can start sessions immediately.

## Editing Later

To change the configuration after creation, return to the Manufacturing tab and click the edit button. The wizard reopens with current values pre-filled. Changing firmware source or pass criteria takes effect on the next session -- it doesn't affect sessions already in progress.

## Related

- [Manufacturing sessions](sessions.md) -- the operator workflow that uses this config
- [Station setup](station-setup.md) -- physical fixture prep before operators start sessions
- [Products](../products/index.md) -- where board revisions and firmware repos are managed
