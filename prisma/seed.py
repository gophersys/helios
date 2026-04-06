"""Seed the database with default permission sets and initial admin user.

Usage:
    SEED_ADMIN_EMAIL=you@company.com SEED_ADMIN_NAME="Your Name" python3 seed.py

Or via Nx:
    SEED_ADMIN_EMAIL=you@company.com npx nx run database:seed

Build Matrix Labels (documentation only - not stored in DB):
    MFG_BASE     - Manufacturing firmware base (used for personalization)
    FUT_DEBUG    - Debug firmware for validation (logging enabled)
    FUT_RELEASE  - Release firmware for validation (logging disabled)
    PROD         - Production firmware (AP protect enabled)

These labels are used by the build system to identify firmware variants.
The firmware build records in the database use these labels in their metadata.
"""

import os
import sys

# Add libs to path so we can import the Prisma client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "libs", "python"))

from database import Prisma, Json

# Every permission that exists in the system (26 total)
# Organized by functional group for clarity
ALL_PERMISSIONS = [
    # Products & Builds
    "products:view",
    "products:manage",
    "builds:view",
    "builds:trigger",
    "builds:manage",
    # Testing
    "validation:view",
    "validation:run",
    "validation:manage",
    # Manufacturing
    "manufacturing:view",
    "manufacturing:run",
    "manufacturing:manage",
    # Infrastructure
    "fixtures:view",
    "fixtures:manage",
    "devices:view",
    "devices:manage",
    "kubernetes:view",
    "kubernetes:manage",
    # Platform
    "users:view",
    "users:manage",
    "permissions:manage",
    "api-keys:view",
    "api-keys:manage",
    "system:view",
    "system:manage",
]

# Role-based permission sets (maps to Role enum: ADMIN, MAINTAINER, DEVELOPER, OPERATOR)
ADMIN_PERMISSIONS = ALL_PERMISSIONS  # All permissions

MAINTAINER_PERMISSIONS = [
    p for p in ALL_PERMISSIONS
    if p not in ("users:manage", "permissions:manage", "system:manage", "kubernetes:manage")
]

DEVELOPER_PERMISSIONS = [
    "products:view",
    "builds:view",
    "builds:trigger",
    "builds:manage",
    "validation:view",
    "validation:run",
    "manufacturing:view",
    "fixtures:view",
    "devices:view",
    "api-keys:view",
    "api-keys:manage",
]

OPERATOR_PERMISSIONS = [
    "manufacturing:view",
    "manufacturing:run",
    "manufacturing:manage",
]

# Real team members (seeded in staging + production)
TEAM = [
    {"email": "mateo@corekinect.com", "name": "Mateo Segura", "role": "ADMIN"},
    {"email": "jared@corekinect.com", "name": "Jared Walton", "role": "ADMIN"},
    {"email": "mitchel@corekinect.com", "name": "Mitchel Kelley", "role": "ADMIN"},
    {"email": "chris@corekinect.com", "name": "Chris Burns", "role": "DEVELOPER"},
    {"email": "christian@corekinect.com", "name": "Christian Cortes", "role": "DEVELOPER"},
    {"email": "gwen@corekinect.com", "name": "Gwen Eging", "role": "OPERATOR"},
]

# Dev-only sample users (one per role, for local dev login picker)
DEV_USERS = [
    {"email": "admin@concord.dev", "name": "Admin User", "role": "ADMIN"},
    {"email": "maintainer@concord.dev", "name": "Maintainer User", "role": "MAINTAINER"},
    {"email": "developer@concord.dev", "name": "Developer User", "role": "DEVELOPER"},
    {"email": "operator@concord.dev", "name": "Operator User", "role": "OPERATOR"},
]

# Product access level per role
ROLE_ACCESS_LEVEL = {
    "ADMIN": "admin",
    "MAINTAINER": "admin",
    "DEVELOPER": "develop",
    "OPERATOR": "operate",
}


def seed():
    email = os.environ.get("SEED_ADMIN_EMAIL", "").strip()
    name = os.environ.get("SEED_ADMIN_NAME", "Admin").strip()

    db = Prisma()
    db.connect()

    try:
        # ── Permission Sets (role-based) ──
        # 4 permission sets matching the 4 roles
        print("=== Seeding Permission Sets ===")

        admin_set = db.permissionset.upsert(
            where={"name": "Admin"},
            data={
                "create": {
                    "name": "Admin",
                    "description": "Full platform access — all permissions",
                    "permissions": ADMIN_PERMISSIONS,
                },
                "update": {
                    "description": "Full platform access — all permissions",
                    "permissions": ADMIN_PERMISSIONS,
                },
            },
        )
        print(f"  Permission set 'Admin' ready (id: {admin_set.id})")

        maintainer_set = db.permissionset.upsert(
            where={"name": "Maintainer"},
            data={
                "create": {
                    "name": "Maintainer",
                    "description": "Full product access — everything except user/permission/system/cluster management",
                    "permissions": MAINTAINER_PERMISSIONS,
                },
                "update": {
                    "description": "Full product access — everything except user/permission/system/cluster management",
                    "permissions": MAINTAINER_PERMISSIONS,
                },
            },
        )
        print(f"  Permission set 'Maintainer' ready (id: {maintainer_set.id})")

        developer_set = db.permissionset.upsert(
            where={"name": "Developer"},
            data={
                "create": {
                    "name": "Developer",
                    "description": "Build, test, and monitor products — no admin access",
                    "permissions": DEVELOPER_PERMISSIONS,
                },
                "update": {
                    "description": "Build, test, and monitor products — no admin access",
                    "permissions": DEVELOPER_PERMISSIONS,
                },
            },
        )
        print(f"  Permission set 'Developer' ready (id: {developer_set.id})")

        operator_set = db.permissionset.upsert(
            where={"name": "Operator"},
            data={
                "create": {
                    "name": "Operator",
                    "description": "Manufacturing operations — view, run, and manage manufacturing sessions",
                    "permissions": OPERATOR_PERMISSIONS,
                },
                "update": {
                    "description": "Manufacturing operations — view, run, and manage manufacturing sessions",
                    "permissions": OPERATOR_PERMISSIONS,
                },
            },
        )
        print(f"  Permission set 'Operator' ready (id: {operator_set.id})")

        # Map role names to permission set objects
        role_to_perm_set = {
            "ADMIN": admin_set,
            "MAINTAINER": maintainer_set,
            "DEVELOPER": developer_set,
            "OPERATOR": operator_set,
        }

        # Backfill existing users that have no permission set
        users_without_set = db.user.find_many(where={"permissionSetId": None})
        for user in users_without_set:
            db.user.update(
                where={"id": user.id},
                data={"permissionSetId": developer_set.id},
            )
            print(f"  Assigned '{user.email}' to Developer permission set (backfill)")

        # Create super admin user if email provided
        if email:
            existing = db.user.find_unique(where={"email": email.lower()})
            if existing:
                db.user.update(
                    where={"id": existing.id},
                    data={"permissionSetId": admin_set.id, "role": "ADMIN"},
                )
                print(f"  Super admin: {existing.email} (updated)")
            else:
                user = db.user.create(
                    data={
                        "email": email.lower(),
                        "name": name,
                        "role": "ADMIN",
                        "permissionSetId": admin_set.id,
                        "active": True,
                    }
                )
                print(f"  Super admin: {user.email} (created, id: {user.id})")
        else:
            print("  SEED_ADMIN_EMAIL not set. Skipping admin user creation.")

        # Development admin user (admin@concord.local / admin)
        # Available in all environments for seeding, but login only works in development
        dev_admin = db.user.upsert(
            where={"email": "admin@concord.local"},
            data={
                "create": {
                    "email": "admin@concord.local",
                    "name": "Dev Admin",
                    "role": "ADMIN",
                    "permissionSetId": admin_set.id,
                    "active": True,
                },
                "update": {
                    "role": "ADMIN",
                    "permissionSetId": admin_set.id,
                    "active": True,
                },
            },
        )
        print(f"  Dev admin: admin@concord.local (id: {dev_admin.id})")

        # ── Team Members ──
        # Seed all team members with roles, permission sets, and product access.
        # Product access is seeded after products are created (see below).

        # ── Products + Boards ──
        print("\n=== Seeding Products & Boards ===")

        # Alpha product with B0 board revision
        alpha_metadata = {
            "device_type": 2,
            "device_variant": 3,
            "app_ids": {"nrf52840": 109, "nrf9151": 108},
            "corecloud_env": "VAL_1_0",
        }
        alpha_build_config = {
            "board": "alpha_b0",
            "ncsVersion": "v2.9.0",
            "boardRoot": "ck_boards",
            "targets": {
                "app": {"soc": "nrf52840", "appId": 109, "role": "application"},
                "comms": {"soc": "nrf9151", "appId": 108, "role": "communications"},
            },
            "hasVsmMerge": True,
            "hasFips": False,
            "confFiles": {
                "app": ["prj.conf", "boards/alpha_b0_nrf52840.conf"],
                "comms": ["prj.conf", "boards/alpha_b0_nrf9151.conf"],
            },
            "overlays": {
                "app": ["boards/alpha_b0_nrf52840.overlay"],
                "comms": [],
            },
            "postBuild": ["sign_mcuboot", "generate_dfu_package"],
            "cfw": {"deviceType": 2, "deviceVariant": 3},
        }
        alpha_product = db.product.upsert(
            where={"name": "Alpha"},
            data={
                "create": {
                    "name": "Alpha",
                    "slug": "alpha",
                    "description": "Alpha wearable device platform",
                    "fwRepoSlug": "alpha_fw",
                    "mfgFwRepoSlug": "alpha_mfg_fw",
                    "active": True,
                    "buildConfig": Json(alpha_build_config),
                    "metadata": Json(alpha_metadata),
                },
                "update": {
                    "slug": "alpha",
                    "fwRepoSlug": "alpha_fw",
                    "mfgFwRepoSlug": "alpha_mfg_fw",
                    "buildConfig": Json(alpha_build_config),
                    "metadata": Json(alpha_metadata),
                },
            },
        )
        print(f"Product: {alpha_product.name} (id: {alpha_product.id})")

        # Alpha board (family: alpha)
        alpha_board = db.board.upsert(
            where={"productId": alpha_product.id},
            data={
                "create": {
                    "productId": alpha_product.id,
                    "name": "Main Board",
                    "ckBoardsFamily": "alpha",
                    "vendor": "corekinect",
                    "description": "Alpha main board with nRF52840 + nRF9151",
                    "active": True,
                },
                "update": {
                    "ckBoardsFamily": "alpha",
                    "vendor": "corekinect",
                },
            },
        )

        alpha_a0_rev = db.boardrevision.upsert(
            where={"boardId_version": {"boardId": alpha_board.id, "version": "A0"}},
            data={
                "create": {
                    "boardId": alpha_board.id,
                    "version": "A0",
                    "ckBoardsName": "alpha_a0",
                    "socs": ["nrf9160", "nrf52840"],
                    "notes": "Alpha A0 revision - initial board (nRF52840 + nRF9160)",
                },
                "update": {
                    "ckBoardsName": "alpha_a0",
                    "socs": ["nrf9160", "nrf52840"],
                },
            },
        )

        # Alpha A0 targets (nRF9160 comms uses appId 106, nRF52840 app uses appId 109)
        for target in [
            {"role": "comms", "soc": "nRF9160", "appId": 106},
            {"role": "app", "soc": "nRF52840", "appId": 109},
        ]:
            db.producttarget.upsert(
                where={"boardRevisionId_role": {"boardRevisionId": alpha_a0_rev.id, "role": target["role"]}},
                data={
                    "create": {"boardRevisionId": alpha_a0_rev.id, **target},
                    "update": {"soc": target["soc"], "appId": target["appId"]},
                },
            )

        alpha_b0_rev = db.boardrevision.upsert(
            where={"boardId_version": {"boardId": alpha_board.id, "version": "B0"}},
            data={
                "create": {
                    "boardId": alpha_board.id,
                    "version": "B0",
                    "ckBoardsName": "alpha_b0",
                    "socs": ["nrf9151", "nrf52840"],
                    "deviceType": 2,
                    "deviceVariant": 3,
                    "notes": "Alpha B0 - current production (nRF52840 + nRF9151)",
                },
                "update": {
                    "ckBoardsName": "alpha_b0",
                    "socs": ["nrf9151", "nrf52840"],
                    "deviceType": 2,
                    "deviceVariant": 3,
                },
            },
        )

        # Alpha B0 targets (nRF9151 comms uses appId 108, nRF52840 app uses appId 109)
        for target in [
            {"role": "comms", "soc": "nRF9151", "appId": 108},
            {"role": "app", "soc": "nRF52840", "appId": 109},
        ]:
            db.producttarget.upsert(
                where={"boardRevisionId_role": {"boardRevisionId": alpha_b0_rev.id, "role": target["role"]}},
                data={
                    "create": {"boardRevisionId": alpha_b0_rev.id, **target},
                    "update": {"soc": target["soc"], "appId": target["appId"]},
                },
            )
        print(f"  Board: {alpha_board.name} / A0, B0")

        # ── Team Members + Product Access ──
        # Now that products exist, seed team members with their roles and product access.
        print("\n=== Seeding Team Members ===")
        all_products = db.product.find_many()
        product_ids = [p.id for p in all_products]

        for member in TEAM:
            perm_set = role_to_perm_set.get(member["role"], developer_set)
            u = db.user.upsert(
                where={"email": member["email"]},
                data={
                    "create": {
                        "email": member["email"],
                        "name": member["name"],
                        "role": member["role"],
                        "permissionSetId": perm_set.id,
                        "active": True,
                    },
                    "update": {
                        "name": member["name"],
                        "role": member["role"],
                        "permissionSetId": perm_set.id,
                        "active": True,
                    },
                },
            )

            # Create product access for all products
            access_level = ROLE_ACCESS_LEVEL.get(member["role"], "view")
            for pid in product_ids:
                db.productaccess.upsert(
                    where={"userId_productId": {"userId": u.id, "productId": pid}},
                    data={
                        "create": {"userId": u.id, "productId": pid, "level": access_level},
                        "update": {"level": access_level},
                    },
                )
            print(f"  {u.name}: {member['role']} ({perm_set.name}), {len(product_ids)} products ({access_level})")

        # Also grant dev admin access to all products
        for pid in product_ids:
            db.productaccess.upsert(
                where={"userId_productId": {"userId": dev_admin.id, "productId": pid}},
                data={
                    "create": {"userId": dev_admin.id, "productId": pid, "level": "admin"},
                    "update": {"level": "admin"},
                },
            )
        print(f"  Dev Admin: {len(product_ids)} products (admin)")

        # ── Fixture Designs ──
        print("\n=== Seeding Fixture Designs ===")

        # Alpha fixture profile template (complete structure from alpha_b0.json)
        alpha_profile_template = {
            "station_id": None,  # Filled by TestBench
            "product": "alpha",
            "board": "alpha_b0",
            "mtib_revision": "1.2",
            "capabilities": ["button", "peltier", "charger_relay"],
            "dut": {
                "device_id": None,  # Filled by TestBench
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
            "button": {
                "gpio_pin": 2,
                "active_low": True,
            },
            "peltier": {
                "gpio_pin": 4,
                "temp_adc_channel": 7,
            },
            "charger_relay": {
                "gpio_pin": 5,
                "active_high": True,
            },
            "ppg_simulator": None,
            "led_sensor": None,
            "nfc_reader": None,
            "motion": None,
        }

        # Find Alpha B0 revision for fixture design FK
        alpha_b0_rev = db.boardrevision.find_first(
            where={"board": {"product": {"slug": "alpha"}}, "version": "B0"}
        )
        alpha_b0_rev_id = alpha_b0_rev.id if alpha_b0_rev else None

        alpha_design = db.fixturedesign.upsert(
            where={"name": "alpha-fixture-v1.2"},
            data={
                "create": {
                    "name": "alpha-fixture-v1.2",
                    "boardRevisionId": alpha_b0_rev_id,
                    "revision": "1.2",
                    "capabilities": ["button", "peltier", "charger_relay"],
                    "profileTemplate": Json(alpha_profile_template),
                    "notes": "REV 1.2 MTIB carrier for Alpha B0 validation. Button, peltier, charger relay wired.",
                },
                "update": {
                    "profileTemplate": Json(alpha_profile_template),
                },
            },
        )
        print(f"Fixture design: {alpha_design.name} (id: {alpha_design.id})")

        # ── Fixtures (was Test Benches) ──
        print("\n=== Seeding Fixtures ===")
        # Bench-33 DUT: Device 0964 (physical device on MTIB REV 1.2 at 10.4.45.33)
        fixture_33 = db.fixture.upsert(
            where={"stationId": "bench-33"},
            data={
                "create": {
                    "stationId": "bench-33",
                    "name": "Alpha B0 Bench 1 (MTIB 33)",
                    "productId": alpha_product.id,
                    "designId": alpha_design.id,
                    "type": "VALIDATION",
                    "status": "AVAILABLE",
                },
                "update": {
                    "productId": alpha_product.id,
                    "designId": alpha_design.id,
                },
            },
        )
        # Create slot with DUT and hardware info
        db.fixtureslot.upsert(
            where={"fixtureId_slotIndex": {"fixtureId": fixture_33.id, "slotIndex": 0}},
            data={
                "create": {
                    "fixtureId": fixture_33.id,
                    "slotIndex": 0,
                    "label": "Primary",
                    "dutDeviceId": "70B3D584C01E1FCC",
                    "dutSnr": "0964",
                    "dutImei": "355025931735979",
                    "dutIccids": ["89148000009808558441", "89457300000037582833"],
                    "jlinkAppSerial": "821009543",
                    "jlinkCommsSerial": "821009541",
                    "uartAppPath": "/dev/verdin-uart2",
                    "uartCommsPath": "/dev/verdin-uart1",
                                    },
                "update": {
                    "dutDeviceId": "70B3D584C01E1FCC",
                    "dutSnr": "0964",
                    "dutImei": "355025931735979",
                    "dutIccids": ["89148000009808558441", "89457300000037582833"],
                                    },
            },
        )
        print(f"Fixture: {fixture_33.stationId} (product: {alpha_product.name})")

        fixture_32 = db.fixture.upsert(
            where={"stationId": "bench-32"},
            data={
                "create": {
                    "stationId": "bench-32",
                    "name": "Alpha B0 Bench 2 (MTIB 32)",
                    "productId": alpha_product.id,
                    "type": "VALIDATION",
                    "status": "AVAILABLE",
                },
                "update": {
                    "productId": alpha_product.id,
                },
            },
        )
        db.fixtureslot.upsert(
            where={"fixtureId_slotIndex": {"fixtureId": fixture_32.id, "slotIndex": 0}},
            data={
                "create": {
                    "fixtureId": fixture_32.id,
                    "slotIndex": 0,
                    "label": "Primary",
                    "dutDeviceId": "70B3D584C01E20A2",
                    "dutSnr": "097D",
                    "uartAppPath": "/dev/verdin-uart2",
                    "uartCommsPath": "/dev/verdin-uart1",
                },
                "update": {},
            },
        )
        print(f"Fixture: {fixture_32.stationId} (product: {alpha_product.name})")

        # ── Stage Configs (Alpha B0 only) ──
        print("\n=== Seeding Stage Configs ===")

        # Find Alpha B0 board revision for linking stages
        alpha_b0_rev_for_stages = db.boardrevision.find_first(
            where={"board": {"product": {"slug": "alpha"}}, "version": "B0"}
        )
        b0_rev_id = alpha_b0_rev_for_stages.id if alpha_b0_rev_for_stages else None

        if alpha_product:
            # Delete existing build matrix entries first (FK constraint)
            existing_configs = db.productstageconfig.find_many(where={"productId": alpha_product.id})
            for ec in existing_configs:
                db.stagebuildmatrix.delete_many(where={"stageConfigId": ec.id})
            # Delete existing configs (idempotent re-seed)
            db.productstageconfig.delete_many(where={"productId": alpha_product.id})

            stage_defs = [
                {
                    "stage": 1, "name": "Smoke", "enabled": True,
                    "boardRevisionId": b0_rev_id,
                    "watchBranch": "main",
                    "triggerTypes": ["pr_push", "manual"],
                },
                {
                    "stage": 2, "name": "Silicon", "enabled": False,
                    "boardRevisionId": b0_rev_id,
                    "triggerTypes": ["manual"],
                },
                {
                    "stage": 3, "name": "Integration", "enabled": False,
                    "boardRevisionId": b0_rev_id,
                    "triggerTypes": ["manual"],
                },
                {
                    "stage": 4, "name": "Nightly", "enabled": True,
                    "boardRevisionId": b0_rev_id,
                    "watchBranch": "main",
                    "triggerTypes": ["schedule", "manual"],
                },
                {
                    "stage": 5, "name": "FUOTA", "enabled": True,
                    "boardRevisionId": b0_rev_id,
                    "watchBranch": "main",
                    "triggerTypes": ["pr_merge", "manual"],
                },
            ]

            # Import stage build definitions for seeding build matrix
            from corekinect.stages import Stage, get_stage_build_defs
            STAGE_ENUM_MAP = {1: Stage.SMOKE, 2: Stage.SILICON, 3: Stage.INTEGRATION, 4: Stage.NIGHTLY, 5: Stage.FUOTA}

            created_stages = []
            for sd in stage_defs:
                config = db.productstageconfig.create(data={
                    "productId": alpha_product.id,
                    **sd,
                })
                created_stages.append((config, sd["stage"]))

            # Seed build matrix entries for each stage
            for config, stage_num in created_stages:
                stage_enum = STAGE_ENUM_MAP.get(stage_num)
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
                    print(f"    {config.name}: {len(build_defs)} build matrix entries")

            enabled = sum(1 for s in stage_defs if s["enabled"])
            print(f"  Alpha B0: {len(stage_defs)} stages ({enabled} enabled)")
        else:
            print("  WARNING: Alpha product not found, skipping stage config seed")

        # ── CI Test API Key ──
        # Create a deterministic API key for CI testing
        # Key: ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG
        # This is a known key that can be used for testing without login
        import hashlib
        from datetime import timedelta
        ci_key = "ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG"
        ci_key_hash = hashlib.sha256(ci_key.encode()).hexdigest()

        # Find or create system user for API keys
        system_user = db.user.upsert(
            where={"email": "system@concord.local"},
            data={
                "create": {
                    "email": "system@concord.local",
                    "name": "System",
                    "permissionSetId": admin_set.id,
                    "active": True,
                },
                "update": {
                    "permissionSetId": admin_set.id,
                },
            },
        )
        print(f"System user ready: {system_user.email}")

        from datetime import datetime, timezone
        # Upsert by keyHash (unique) — safe for re-seeding
        existing_key = db.apikey.find_first(where={"keyHash": ci_key_hash})
        if existing_key:
            ci_api_key = db.apikey.update(
                where={"id": existing_key.id},
                data={"expiresAt": datetime.now(timezone.utc) + timedelta(days=365)},
            )
        else:
            ci_api_key = db.apikey.create(data={
                "name": "CI Admin Key",
                "keyHash": ci_key_hash,
                "keyPrefix": ci_key[:12],
                "userId": system_user.id,
                "expiresAt": datetime.now(timezone.utc) + timedelta(days=365),
            })
        print(f"CI API key ready: {ci_api_key.keyPrefix}... (id: {ci_api_key.id})")
        print(f"  Use this key for testing: {ci_key}")

        # ── Recipe Templates ──
        print("\n=== Seeding Recipe Templates ===")

        dual_core_template = '''\
#!/bin/bash
# Concord Build Recipe — Dual-Core (nRF52840 + nRF9151)
# Builds both application and communications processor firmware
# using Zephyr west with the Concord Build SDK.
set -eo pipefail

# Source the Concord Build SDK
source /app/sdk/concord-build.sh

# Initialize build environment (parses BOARD, VARIANT, VERSION, etc.)
concord_init

# ── Application Processor (nRF52840) ──
echo "Building application firmware..."
west build -b "${BOARD}/nrf52840" app/ \\
    -d build/app \\
    -- \\
    -DBOARD_ROOT="${BOARD_ROOT}" \\
    -DCONFIG_APP_VERSION="${VERSION}"

concord_collect_hex app build/app/zephyr/merged.hex

# ── Communications Processor (nRF9151) ──
echo "Building comms firmware..."
west build -b "${BOARD}/nrf9151" comms/ \\
    -d build/comms \\
    -- \\
    -DBOARD_ROOT="${BOARD_ROOT}" \\
    -DCONFIG_APP_VERSION="${VERSION}"

concord_collect_hex comms build/comms/zephyr/merged.hex

# Generate CFW packages for FUOTA delivery
if [ "${GENERATE_CFW}" = "true" ]; then
    echo "Generating CFW packages..."
    concord_generate_cfw app build/app/zephyr/app_update.bin
    concord_generate_cfw comms build/comms/zephyr/app_update.bin
fi

# Finalize — upload artifacts, update build status
concord_finalize
'''

        single_core_template = '''\
#!/bin/bash
# Concord Build Recipe — Single-Core (nRF52840)
# Builds a single-processor Zephyr application with the Concord Build SDK.
set -eo pipefail

# Source the Concord Build SDK
source /app/sdk/concord-build.sh

# Initialize build environment
concord_init

# ── Build firmware ──
echo "Building firmware for ${BOARD}..."
west build -b "${BOARD}" app/ \\
    -d build/app \\
    -- \\
    -DBOARD_ROOT="${BOARD_ROOT}" \\
    -DCONFIG_APP_VERSION="${VERSION}"

concord_collect_hex app build/app/zephyr/merged.hex

# Generate CFW if requested
if [ "${GENERATE_CFW}" = "true" ]; then
    echo "Generating CFW package..."
    concord_generate_cfw app build/app/zephyr/app_update.bin
fi

# Finalize
concord_finalize
'''

        cmake_template = '''\
#!/bin/bash
# Concord Build Recipe — CMake Project
# For products that use plain CMake instead of Zephyr west.
# Adapts a standard CMake workflow to the Concord Build SDK.
set -eo pipefail

# Source the Concord Build SDK
source /app/sdk/concord-build.sh

# Initialize build environment
concord_init

# ── Configure ──
echo "Configuring CMake project..."
cmake -B build \\
    -DCMAKE_BUILD_TYPE="${VARIANT:-Release}" \\
    -DAPP_VERSION="${VERSION}" \\
    -DBOARD="${BOARD}" \\
    .

# ── Build ──
echo "Building..."
cmake --build build --parallel "$(nproc)"

# ── Collect artifacts ──
# Adjust the path to match your project output
if [ -f build/firmware.hex ]; then
    concord_collect_hex app build/firmware.hex
elif [ -f build/firmware.bin ]; then
    echo "Converting bin to hex..."
    objcopy -I binary -O ihex build/firmware.bin build/firmware.hex
    concord_collect_hex app build/firmware.hex
else
    echo "ERROR: No firmware output found in build/"
    exit 1
fi

# Finalize
concord_finalize
'''

        for tmpl in [
            {
                "name": "Dual-Core (nRF52840 + nRF9151)",
                "description": "Standard recipe for dual-processor products using Zephyr west. Builds both app and comms targets.",
                "content": dual_core_template,
                "category": "zephyr",
                "sortOrder": 1,
            },
            {
                "name": "Single-Core (nRF52840)",
                "description": "Simplified recipe for single-processor products using Zephyr west.",
                "content": single_core_template,
                "category": "zephyr",
                "sortOrder": 2,
            },
            {
                "name": "CMake Project",
                "description": "Recipe for products that use plain CMake instead of Zephyr west.",
                "content": cmake_template,
                "category": "general",
                "sortOrder": 3,
            },
        ]:
            db.recipetemplate.upsert(
                where={"name": tmpl["name"]},
                data={
                    "create": tmpl,
                    "update": {
                        "description": tmpl["description"],
                        "content": tmpl["content"],
                        "category": tmpl["category"],
                        "sortOrder": tmpl["sortOrder"],
                    },
                },
            )
            print(f"  Recipe template: {tmpl['name']}")

        # ── Signing Keys ──
        # Seed the bench signing keys from the repo (dev/bench only — production keys are never in the DB)
        print("\n=== Seeding Signing Keys ===")
        import base64

        key_files = {
            "Alpha Bench Signing Key (APP)": "apps/firmware/products/alpha/alpha_fw/encryption_key.pem",
            "Alpha Bench Signing Key (COMMS)": "apps/firmware/products/alpha/alpha_fw/comms_encryption_key.pem",
        }

        signing_key_ids = {}
        for key_name, key_path in key_files.items():
            full_path = os.path.join(os.path.dirname(__file__), "..", key_path)
            if os.path.exists(full_path):
                with open(full_path, "r") as f:
                    key_value = base64.b64encode(f.read().encode()).decode()
                secret = db.secret.upsert(
                    where={"name": key_name},
                    data={
                        "create": {
                            "name": key_name,
                            "type": "signing_key",
                            "value": key_value,
                            "description": f"EC P-256 private key for {key_name.split('(')[0].strip()}",
                            "createdById": dev_admin.id,
                        },
                        "update": {
                            "value": key_value,
                        },
                    },
                )
                signing_key_ids[key_name] = secret.id
                print(f"  {key_name}: {secret.id[:16]}...")
            else:
                print(f"  WARNING: {key_path} not found")

        # Link the APP signing key to Alpha stages that need it
        app_key_id = signing_key_ids.get("Alpha Bench Signing Key (APP)")
        if app_key_id and alpha_product:
            stages_needing_key = db.productstageconfig.find_many(
                where={"productId": alpha_product.id, "signingKeyId": None}
            )
            for stage in stages_needing_key:
                db.productstageconfig.update(
                    where={"id": stage.id},
                    data={"signingKeyId": app_key_id},
                )
            print(f"  Linked signing key to {len(stages_needing_key)} Alpha stages")

        # ── Dev Sample Users (development only) ──
        # One user per role for the dev login picker
        is_dev = os.environ.get("ENVIRONMENT", "development") == "development"
        if is_dev:
            print("\n=== Seeding Dev Users ===")
            role_to_perm_set = {
                "ADMIN": admin_set,
                "MAINTAINER": maintainer_set,
                "DEVELOPER": developer_set,
                "OPERATOR": operator_set,
            }
            for dev_user in DEV_USERS:
                perm_set = role_to_perm_set.get(dev_user["role"], developer_set)
                u = db.user.upsert(
                    where={"email": dev_user["email"]},
                    data={
                        "create": {
                            "email": dev_user["email"],
                            "name": dev_user["name"],
                            "role": dev_user["role"],
                            "permissionSetId": perm_set.id,
                            "active": True,
                        },
                        "update": {
                            "name": dev_user["name"],
                            "role": dev_user["role"],
                            "permissionSetId": perm_set.id,
                        },
                    },
                )
                print(f"  {dev_user['role']:12s} {dev_user['name']} ({dev_user['email']})")

        # ── Product Access ──
        # Give all users access to all products based on their role
        print("\n=== Seeding Product Access ===")
        all_products = db.product.find_many()
        all_dev_users = db.user.find_many(where={"active": True})

        role_to_level = {
            "ADMIN": "admin",
            "MAINTAINER": "admin",
            "DEVELOPER": "develop",
            "OPERATOR": "operate",
        }

        for u in all_dev_users:
            user_role = getattr(u, "role", "DEVELOPER") or "DEVELOPER"
            level = role_to_level.get(user_role, "view")
            for p in all_products:
                db.productaccess.upsert(
                    where={
                        "userId_productId": {"userId": u.id, "productId": p.id},
                    },
                    data={
                        "create": {
                            "userId": u.id,
                            "productId": p.id,
                            "level": level,
                        },
                        "update": {"level": level},
                    },
                )
            print(f"Product access: {u.name} -> {len(all_products)} products ({level})")

    finally:
        db.disconnect()


if __name__ == "__main__":
    seed()
