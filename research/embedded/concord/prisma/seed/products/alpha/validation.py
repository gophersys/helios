"""Alpha B0 validation seed — fixture designs, fixtures, stage configs, and build recipe.

Validation fixtures have 1 MTIB per slot (single-DUT testing).
5 validation stages: Smoke, Driver, Integration, Regression, FUOTA.
"""

import os

from database import Json

from seed.helpers import upsert_by_non_unique


# ── Fixture profile template ─────────────────────────────────
# This JSON is passed to the test runner and interpreted by
# apps/validation/alpha/fixtures/. Concord stores it but never reads it.

ALPHA_B0_VAL_PROFILE = {
    "station_id": None,
    "product": "alpha",
    "board": "alpha_b0",
    "mtib_revision": "1.2",
    "capabilities": ["power", "button", "peltier", "charger_relay"],
    "dut": {
        "device_id": None,
        "snr": None,
        "imei": None,
        "iccids": [],
    },
    "power": {
        "battery_installed": False,
        "dut_voltage": 4.5,
        "charger_voltage": 5.0,
        "boot_settle_s": 10,
    },
    "button": {"gpio_pin": 2, "active_low": True},
    "peltier": {"gpio_pin": 4, "temp_adc_channel": 7},
    "charger_relay": {"gpio_pin": 5, "active_high": True},
    "ppg_simulator": None,
    "led_sensor": None,
    "nfc_reader": None,
    "motion": None,
}

# ── Validation stages ────────────────────────────────────────

VALIDATION_STAGES = [
    {"type": "VALIDATION", "stage": 1, "name": "Smoke", "enabled": False, "triggerTypes": ["pr_push", "manual"]},
    {"type": "VALIDATION", "stage": 2, "name": "Driver", "enabled": False, "triggerTypes": ["manual"]},
    {"type": "VALIDATION", "stage": 3, "name": "Integration", "enabled": False, "triggerTypes": ["manual"]},
    {"type": "VALIDATION", "stage": 4, "name": "Regression", "enabled": False, "triggerTypes": ["schedule", "manual"]},
    {"type": "VALIDATION", "stage": 5, "name": "FUOTA", "enabled": True, "watchBranch": "concord-main", "triggerTypes": ["pr_push", "pr_merge", "manual"]},
]

# ── Fixture instances ────────────────────────────────────────
# Each validation fixture has 1 slot (1 MTIB, 1 DUT).

VAL_FIXTURES = [
    {"stationId": "bench-33", "name": "Alpha B0 Bench 33", "slots": [
        {"slotIndex": 0, "label": "DUT", "dutSnr": "0964", "dutDeviceId": "70B3D584C01E1FCC"},
    ]},
    {"stationId": "bench-32", "name": "Alpha B0 Bench 32", "slots": [
        {"slotIndex": 0, "label": "DUT", "dutSnr": "097D", "dutDeviceId": "70B3D584C01E20A2"},
    ]},
]


def seed_validation(db, product, b0_rev):
    """Seed validation fixture design, fixtures, and stage configs."""
    print("\n=== Alpha: Validation ===")

    # ── Fixture design ──
    # FixtureDesign.name isn't @unique — see helpers.upsert_by_non_unique.
    design = upsert_by_non_unique(
        db.fixturedesign,
        where={"name": "alpha-val-fixture-v1.2"},
        create={
            "name": "alpha-val-fixture-v1.2",
            "boardRevisionId": b0_rev.id,
            "revision": "1.2",
            "capabilities": ["power", "button", "peltier", "charger_relay"],
            "profileTemplate": Json(ALPHA_B0_VAL_PROFILE),
            "notes": "REV 1.2 MTIB carrier for Alpha B0 validation. Single-DUT bench.",
        },
        update={
            "profileTemplate": Json(ALPHA_B0_VAL_PROFILE),
            "capabilities": ["power", "button", "peltier", "charger_relay"],
        },
    )
    print(f"  ✓ Design: {design.name}")

    # ── Fixtures ──
    for fx in VAL_FIXTURES:
        fixture = db.fixture.upsert(
            where={"stationId": fx["stationId"]},
            data={
                "create": {
                    "name": fx["name"],
                    "stationId": fx["stationId"],
                    "productId": product.id,
                    "boardRevisionId": b0_rev.id,
                    "type": "VALIDATION",
                    "designId": design.id,
                },
                "update": {
                    "name": fx["name"],
                    "designId": design.id,
                    "boardRevisionId": b0_rev.id,
                },
            },
        )

        # Create slots
        for slot_def in fx["slots"]:
            db.fixtureslot.upsert(
                where={"fixtureId_slotIndex": {"fixtureId": fixture.id, "slotIndex": slot_def["slotIndex"]}},
                data={
                    "create": {
                        "fixtureId": fixture.id,
                        "slotIndex": slot_def["slotIndex"],
                        "label": slot_def.get("label"),
                        "dutSnr": slot_def.get("dutSnr"),
                        "dutDeviceId": slot_def.get("dutDeviceId"),
                    },
                    "update": {
                        "label": slot_def.get("label"),
                        "dutSnr": slot_def.get("dutSnr"),
                        "dutDeviceId": slot_def.get("dutDeviceId"),
                    },
                },
            )
        print(f"  ✓ Fixture: {fx['name']} ({len(fx['slots'])} slots)")

    # ── Stage configs + build matrix ──
    # Clear existing validation configs (idempotent re-seed, preserves manufacturing)
    existing = db.productstageconfig.find_many(where={"productId": product.id, "type": "VALIDATION"})
    for ec in existing:
        db.stagebuildmatrix.delete_many(where={"stageConfigId": ec.id})
        db.productstageconfig.delete(where={"id": ec.id})

    try:
        from corekinect.stages import Stage, get_stage_build_defs
        STAGE_MAP = {1: Stage.SMOKE, 2: Stage.DRIVER, 3: Stage.INTEGRATION, 4: Stage.REGRESSION, 5: Stage.FUOTA}
    except ImportError:
        STAGE_MAP = {}

    for sd in VALIDATION_STAGES:
        config = db.productstageconfig.create(data={
            "productId": product.id,
            "boardRevisionId": b0_rev.id,
            **sd,
        })

        # Seed build matrix from stage definitions
        stage_enum = STAGE_MAP.get(sd["stage"])
        if stage_enum:
            build_defs = get_stage_build_defs(stage_enum)
            for i, bd in enumerate(build_defs):
                db.stagebuildmatrix.create(data={
                    "stageConfigId": config.id,
                    "sortOrder": i,
                    "label": bd.label,
                    "fwType": bd.fw_type,
                    "variant": bd.variant,
                    "configLog": bd.config_log,
                    "producesHex": bd.produces_hex,
                    "producesCfw": bd.produces_cfw,
                    "gitRef": bd.git_ref,
                    "isVersionBump": bd.is_version_bump,
                    "baseLabel": bd.base_label,
                    "description": bd.description,
                })
            print(f"  ✓ Stage {sd['name']}: {len(build_defs)} matrix entries")
        else:
            print(f"  ✓ Stage {sd['name']}: no matrix (stages lib not available)")

    # No A0 stage configs — A0 is legacy, validation runs on B0 only

    # ── Build recipes ──
    # Recipes live alongside the seed data at:
    #   recipes/{boardName}/{domain}/{stageName}/build.sh
    # Seeded to both DB (RecipeVersion) and MinIO at:
    #   firmware/recipes/{slug}/{boardName}/{domain}/{stageName}/build.sh
    from seed.storage import get_seed_storage, seed_recipe_to_minio

    recipes_dir = os.path.join(os.path.dirname(__file__), "recipes")
    db.recipeversion.delete_many(where={"productId": product.id})
    system_user = db.user.find_first(where={"email": "system@concord.local"})
    minio_client, minio_bucket = get_seed_storage()
    slug = product.slug or product.name.lower().replace(" ", "_")
    version_counter = 0

    stage_name_map = {1: "smoke", 2: "driver", 3: "integration", 4: "regression", 5: "fuota"}
    for sd in VALIDATION_STAGES:
        stage_name = stage_name_map.get(sd["stage"], f"stage-{sd['stage']}")
        recipe_path = os.path.join(recipes_dir, b0_rev.ckBoardsName, "validation", stage_name, "build.sh")
        if not os.path.isfile(recipe_path):
            continue

        with open(recipe_path) as f:
            content = f.read()

        version_counter += 1
        rv = db.recipeversion.create(data={
            "productId": product.id,
            "version": version_counter,
            "content": content,
            "status": "published",
            "changeNote": f"Seed recipe for {sd['name']} ({b0_rev.version})",
            "createdById": system_user.id if system_user else None,
        })

        # Link stage config to this recipe
        cfg = db.productstageconfig.find_first(
            where={"productId": product.id, "stage": sd["stage"], "boardRevisionId": b0_rev.id}
        )
        if cfg:
            db.productstageconfig.update(where={"id": cfg.id}, data={"recipeVersionId": rv.id})

        # Write to MinIO
        minio_key = f"firmware/recipes/{slug}/{b0_rev.ckBoardsName}/validation/{stage_name}/build.sh"
        if minio_client:
            seed_recipe_to_minio(minio_client, minio_bucket, minio_key, content)

        print(f"  ✓ Recipe: {minio_key} v{rv.version} ({len(content)} bytes)")

    if version_counter == 0:
        print(f"  ⚠ No recipes found in {recipes_dir}")

    enabled = sum(1 for s in VALIDATION_STAGES if s["enabled"])
    print(f"  ✓ {len(VALIDATION_STAGES)} stage configs ({enabled} enabled)")
