"""Seed verification — runs after seeding to assert the database matches expectations.

Usage:
    python3 -m seed.verify          # standalone
    Called automatically by seed.main when SEED_VERIFY=1

Catches:
    - Missing records (seed didn't create what it should)
    - Wrong field values (seed wrote stale field names or values)
    - Broken relationships (FK references that don't resolve)
    - Constraint violations (enabled stage on deprecated revision)
    - Count mismatches (wrong number of stage configs, targets, etc.)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "libs", "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "libs"))

from database import Prisma


class SeedVerificationError(Exception):
    pass


def verify(db) -> list[str]:
    """Verify seeded data. Returns list of errors (empty = all good)."""
    errors: list[str] = []

    def check(condition: bool, msg: str):
        if not condition:
            errors.append(msg)

    # ── Permission sets ──
    for name in ("Admin", "Maintainer", "Developer", "Operator"):
        ps = db.permissionset.find_first(where={"name": name})
        check(ps is not None, f"Missing permission set: {name}")
        if ps:
            check(len(ps.permissions) > 0, f"Permission set {name} has no permissions")

    # ── Users ──
    admin = db.user.find_first(where={"email": "admin@concord.local"})
    check(admin is not None, "Missing dev admin user (admin@concord.local)")
    if admin:
        check(admin.permissionSetId is not None, "Dev admin has no permission set")

    system = db.user.find_first(where={"email": "system@concord.local"})
    check(system is not None, "Missing system user")

    # ── API keys ──
    keys = db.apikey.find_many()
    check(len(keys) >= 1, "No API keys seeded")

    # ── Products ──
    alpha = db.product.find_first(where={"name": "Alpha"})
    check(alpha is not None, "Missing product: Alpha")
    if not alpha:
        return errors  # Can't verify anything else

    check(alpha.slug == "alpha", f"Alpha slug wrong: {alpha.slug}")
    check(alpha.fwRepoSlug == "alpha_fw", f"Alpha fwRepoSlug wrong: {alpha.fwRepoSlug}")
    check(alpha.mfgFwRepoSlug == "alpha_mfg_fw", f"Alpha mfgFwRepoSlug wrong: {alpha.mfgFwRepoSlug}")
    check(alpha.active is True, "Alpha product not active")

    # ── Boards ──
    board = db.board.find_first(where={"productId": alpha.id})
    check(board is not None, "Alpha has no board")
    if not board:
        return errors

    # ── Revisions ──
    revisions = db.boardrevision.find_many(
        where={"boardId": board.id},
        order={"version": "asc"},
    )
    rev_versions = [r.version for r in revisions]
    for expected in ("A0", "B0"):
        check(expected in rev_versions, f"Missing revision: {expected}")

    rev_map = {r.version: r for r in revisions}

    # A0 checks
    a0 = rev_map.get("A0")
    if a0:
        check(a0.ckBoardsName == "alpha_a0", f"A0 ckBoardsName wrong: {a0.ckBoardsName}")
        check(a0.status == "ACTIVE", f"A0 status wrong: {a0.status} (expected ACTIVE)")
        a0_targets = db.producttarget.find_many(where={"boardRevisionId": a0.id})
        check(len(a0_targets) >= 2, f"A0 has {len(a0_targets)} targets, expected >= 2")

    # B0 checks
    b0 = rev_map.get("B0")
    if b0:
        check(b0.ckBoardsName == "alpha_b0", f"B0 ckBoardsName wrong: {b0.ckBoardsName}")
        check(b0.status == "ACTIVE", f"B0 status wrong: {b0.status} (expected ACTIVE)")
        check(b0.deviceType == 2, f"B0 deviceType wrong: {b0.deviceType}")
        check(b0.deviceVariant == 3, f"B0 deviceVariant wrong: {b0.deviceVariant}")
        b0_targets = db.producttarget.find_many(where={"boardRevisionId": b0.id})
        check(len(b0_targets) >= 2, f"B0 has {len(b0_targets)} targets, expected >= 2")

    # ── Stage configs ──
    stages = db.productstageconfig.find_many(
        where={"productId": alpha.id},
        include={"boardRevision": True},
    )
    val_stages = [s for s in stages if s.stage <= 100]
    mfg_stages = [s for s in stages if s.stage > 100]

    check(len(val_stages) >= 5, f"Only {len(val_stages)} val stage configs, expected >= 5 (5 for B0 minimum)")
    check(len(mfg_stages) >= 3, f"Only {len(mfg_stages)} mfg stage configs, expected >= 3")

    # Verify B0 has all 5 stages
    b0_stages = [s for s in val_stages if b0 and s.boardRevisionId == b0.id]
    b0_stage_nums = sorted([s.stage for s in b0_stages])
    check(b0_stage_nums == [1, 2, 3, 4, 5], f"B0 stage numbers: {b0_stage_nums}, expected [1,2,3,4,5]")

    # Verify stage names match expected
    expected_names = {1: "Smoke", 2: "Driver", 3: "Integration", 4: "Regression", 5: "FUOTA"}
    for s in val_stages:
        if s.stage in expected_names:
            check(s.name == expected_names[s.stage], f"Stage {s.stage} name: '{s.name}', expected '{expected_names[s.stage]}'")

    # ── CONSTRAINT: no enabled stages on deprecated/EOL revisions ──
    for s in stages:
        if s.enabled and s.boardRevision:
            check(
                s.boardRevision.status not in ("DEPRECATED", "EOL"),
                f"CONSTRAINT VIOLATION: Stage {s.stage} ({s.name}) is ENABLED but revision "
                f"{s.boardRevision.version} is {s.boardRevision.status}"
            )

    # ── CONSTRAINT: every stage config has a valid boardRevisionId ──
    for s in stages:
        if s.boardRevisionId:
            rev = db.boardrevision.find_unique(where={"id": s.boardRevisionId})
            check(rev is not None, f"Stage {s.stage} ({s.name}) references nonexistent boardRevisionId: {s.boardRevisionId}")

    # ── Fixtures ──
    val_fixtures = db.fixture.find_many(where={"productId": alpha.id, "type": "VALIDATION"})
    check(len(val_fixtures) >= 1, f"Only {len(val_fixtures)} validation fixtures, expected >= 1")

    mfg_fixtures = db.fixture.find_many(where={"productId": alpha.id, "type": "MANUFACTURING"})
    check(len(mfg_fixtures) >= 1, f"Only {len(mfg_fixtures)} manufacturing fixtures, expected >= 1")

    # Verify fixtures have slots
    for fx in val_fixtures:
        slots = db.fixtureslot.find_many(where={"fixtureId": fx.id})
        check(len(slots) >= 1, f"Fixture {fx.name} has no slots")

    # ── Fixture designs ──
    val_designs = db.fixturedesign.find_many(where={"boardRevisionId": b0.id if b0 else ""})
    check(len(val_designs) >= 1, f"No fixture designs for B0")

    # ── Build matrix ──
    for s in b0_stages:
        if s.enabled:
            matrix = db.stagebuildmatrix.find_many(where={"stageConfigId": s.id})
            check(len(matrix) >= 1, f"Enabled B0 stage {s.stage} ({s.name}) has no build matrix entries")

    # ── Product access ──
    access = db.productaccess.find_many(where={"productId": alpha.id})
    check(len(access) >= 1, f"No product access records for Alpha")

    # ── Signing keys ──
    secrets = db.secret.find_many(where={"type": "signing_key"})
    check(len(secrets) >= 1, "No signing keys seeded")

    # ── Recipe templates ──
    templates = db.recipetemplate.find_many()
    check(len(templates) >= 1, "No recipe templates seeded")

    return errors


def main():
    db = Prisma()
    db.connect()
    try:
        errors = verify(db)
        if errors:
            print(f"\n✗ Seed verification FAILED — {len(errors)} error(s):")
            for e in errors:
                print(f"  ✗ {e}")
            sys.exit(1)
        else:
            print("\n✓ Seed verification passed")
    finally:
        db.disconnect()


if __name__ == "__main__":
    main()
