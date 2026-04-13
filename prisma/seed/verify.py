"""Seed verification — runs after seeding to assert the database matches expectations.

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

    system = db.user.find_first(where={"email": "system@concord.local"})
    check(system is not None, "Missing system user")

    # ── API keys ──
    keys = db.apikey.find_many()
    check(len(keys) >= 1, "No API keys seeded")

    # ── Products ──
    alpha = db.product.find_first(where={"name": "Alpha"})
    check(alpha is not None, "Missing product: Alpha")
    if not alpha:
        return errors

    check(alpha.slug == "alpha", f"Alpha slug wrong: {alpha.slug}")
    check(alpha.status == "ACTIVE", "Alpha product not active")

    # ── Boards ──
    board = db.board.find_first(where={"productId": alpha.id})
    check(board is not None, "Alpha has no board")
    if not board:
        return errors

    # ── Revisions (case-insensitive lookup via ckBoardsName) ──
    a0 = db.boardrevision.find_first(where={"ckBoardsName": "alpha_a0"})
    b0 = db.boardrevision.find_first(where={"ckBoardsName": "alpha_b0"})
    check(a0 is not None, "Missing revision: alpha_a0")
    check(b0 is not None, "Missing revision: alpha_b0")

    if a0:
        a0_targets = db.producttarget.find_many(where={"boardRevisionId": a0.id})
        check(len(a0_targets) >= 2, f"A0 has {len(a0_targets)} targets, expected >= 2")

    if b0:
        check(b0.deviceType == 2, f"B0 deviceType wrong: {b0.deviceType}")
        check(b0.deviceVariant == 3, f"B0 deviceVariant wrong: {b0.deviceVariant}")
        b0_targets = db.producttarget.find_many(where={"boardRevisionId": b0.id})
        check(len(b0_targets) >= 2, f"B0 has {len(b0_targets)} targets, expected >= 2")

    # ── Stage configs (use type field, not stage number ranges) ──
    stages = db.productstageconfig.find_many(
        where={"productId": alpha.id},
        include={"boardRevision": True},
    )
    val_stages = [s for s in stages if s.type == "VALIDATION"]
    mfg_stages = [s for s in stages if s.type == "MANUFACTURING"]

    check(len(val_stages) >= 5, f"Only {len(val_stages)} val stage configs, expected >= 5")
    check(len(mfg_stages) >= 1, f"Only {len(mfg_stages)} mfg stage configs, expected >= 1")

    # Verify B0 has all 5 validation stages
    b0_val_stages = [s for s in val_stages if b0 and s.boardRevisionId == b0.id]
    b0_stage_nums = sorted([s.stage for s in b0_val_stages])
    check(b0_stage_nums == [1, 2, 3, 4, 5], f"B0 val stage numbers: {b0_stage_nums}, expected [1,2,3,4,5]")

    # Verify stage names
    expected_names = {1: "Smoke", 2: "Driver", 3: "Integration", 4: "Regression", 5: "FUOTA"}
    for s in b0_val_stages:
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
            check(rev is not None, f"Stage {s.stage} ({s.name}) references nonexistent boardRevisionId")

    # ── Fixtures ──
    val_fixtures = db.fixture.find_many(where={"productId": alpha.id, "type": "VALIDATION"})
    check(len(val_fixtures) >= 1, f"Only {len(val_fixtures)} validation fixtures, expected >= 1")

    mfg_fixtures = db.fixture.find_many(where={"productId": alpha.id, "type": "MANUFACTURING"})
    check(len(mfg_fixtures) >= 1, f"Only {len(mfg_fixtures)} manufacturing fixtures, expected >= 1")

    for fx in val_fixtures:
        slots = db.fixtureslot.find_many(where={"fixtureId": fx.id})
        check(len(slots) >= 1, f"Fixture {fx.name} has no slots")

    # ── Fixture designs ──
    if b0:
        designs = db.fixturedesign.find_many(where={"boardRevisionId": b0.id})
        check(len(designs) >= 1, f"No fixture designs for B0")

    # ── Build matrix ──
    for s in b0_val_stages:
        if s.enabled:
            matrix = db.stagebuildmatrix.find_many(where={"stageConfigId": s.id})
            check(len(matrix) >= 1, f"Enabled B0 stage {s.stage} ({s.name}) has no build matrix entries")

    # ── Product access ──
    access = db.productaccess.find_many(where={"productId": alpha.id})
    check(len(access) >= 1, "No product access records for Alpha")

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
