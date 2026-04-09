---
min_role: DEVELOPER
---
# Build Matrix

Defines which firmware variants a stage compiles. Each row is one build job.

## Where it lives

Product detail → **Validation** tab → open a stage config → **Review** step. The matrix table loads at the bottom.

## Reading the table

| Column | Content |
|--------|---------|
| **Label** | Variant identifier combining firmware type, revision, and target |
| **FW Type** | Firmware type name |
| **Variant** | Board revision and target chip |
| **Produces** | Output format — HEX, CFW, or both |
| **Git Ref** | Branch or tag sourcing the build |

## Entry counts

More complex stages produce more variants:

| Stage | Entries |
|-------|---------|
| Smoke | 2 |
| Driver | 3 |
| Integration | 4 |
| Regression | 6 |
| FUOTA | 8 |

## Reset

**Reset to Defaults** restores factory entries for the stage. Visible to admins in the Review step. Does not auto-save — confirm through **Save & Enable**.

## Artifacts

Each matrix entry produces one build job. HEX files are flashed via J-Link/SWD. CFW files go over-the-air through FUOTA. See [Artifacts](../builds/artifacts.md) for storage paths.
