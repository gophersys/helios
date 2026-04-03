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

# Legacy sets kept for backward compatibility
LEGACY_ENGINEER_PERMISSIONS = [
    "products:view",
    "builds:view",
    "builds:trigger",
    "validation:view",
    "validation:run",
    "fixtures:view",
    "devices:view",
    "kubernetes:view",
    "system:view",
    "api-keys:view",
    "api-keys:manage",
]

LEGACY_VIEWER_PERMISSIONS = [
    "products:view",
    "builds:view",
    "validation:view",
    "fixtures:view",
    "devices:view",
    "system:view",
]

# Team members to seed with roles and product access
TEAM = [
    {"email": "mateo@corekinect.com", "name": "Mateo Segura", "role": "ADMIN"},
    {"email": "jared@corekinect.com", "name": "Jared Walton", "role": "ADMIN"},
    {"email": "mitchel@corekinect.com", "name": "Mitchel Kelley", "role": "ADMIN"},
    {"email": "chris@corekinect.com", "name": "Chris Burns", "role": "DEVELOPER"},
    {"email": "christian@corekinect.com", "name": "Christian Cortes", "role": "DEVELOPER"},
    {"email": "gwen@corekinect.com", "name": "Gwen Eging", "role": "OPERATOR"},
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
        # These map 1:1 to the Role enum. The "Super Admin" set is kept as
        # a superset alias for the "Admin" role (same permissions).
        print("=== Seeding Permission Sets ===")

        super_admin_set = db.permissionset.upsert(
            where={"name": "Super Admin"},
            data={
                "create": {
                    "name": "Super Admin",
                    "description": "Unrestricted access — all permissions (alias for Admin role)",
                    "permissions": ALL_PERMISSIONS,
                },
                "update": {
                    "description": "Unrestricted access — all permissions (alias for Admin role)",
                    "permissions": ALL_PERMISSIONS,
                },
            },
        )
        print(f"  Permission set 'Super Admin' ready (id: {super_admin_set.id})")

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

        # Legacy permission sets (kept for backward compat, will be removed after migration)
        db.permissionset.upsert(
            where={"name": "Engineer"},
            data={
                "create": {"name": "Engineer", "description": "[Legacy] Engineering access", "permissions": LEGACY_ENGINEER_PERMISSIONS},
                "update": {"description": "[Legacy] Engineering access", "permissions": LEGACY_ENGINEER_PERMISSIONS},
            },
        )
        db.permissionset.upsert(
            where={"name": "Viewer"},
            data={
                "create": {"name": "Viewer", "description": "[Legacy] Read-only access", "permissions": LEGACY_VIEWER_PERMISSIONS},
                "update": {"description": "[Legacy] Read-only access", "permissions": LEGACY_VIEWER_PERMISSIONS},
            },
        )
        print("  Legacy sets (Engineer, Viewer) updated")

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
                    data={"permissionSetId": super_admin_set.id, "role": "ADMIN"},
                )
                print(f"  Super admin: {existing.email} (updated)")
            else:
                user = db.user.create(
                    data={
                        "email": email.lower(),
                        "name": name,
                        "role": "ADMIN",
                        "permissionSetId": super_admin_set.id,
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
                    "permissionSetId": super_admin_set.id,
                    "active": True,
                },
                "update": {
                    "role": "ADMIN",
                    "permissionSetId": super_admin_set.id,
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
                    "active": True,
                    "buildConfig": Json(alpha_build_config),
                    "metadata": Json(alpha_metadata),
                },
                "update": {
                    "slug": "alpha",
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
                    "notes": "Alpha B0 revision - production board (nRF52840 + nRF9151)",
                },
                "update": {
                    "ckBoardsName": "alpha_b0",
                    "socs": ["nrf9151", "nrf52840"],
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

        # Sigma 5 product with C0 and B0 board revisions
        sigma5_metadata = {
            "device_type": 1,
            "device_variant": 5,
            "app_ids": {"nrf52840": 105, "nrf9160": 104},
            "corecloud_env": "VAL_1_0",
        }
        sigma5_product = db.product.upsert(
            where={"name": "Sigma5"},
            data={
                "create": {
                    "name": "Sigma5",
                    "slug": "sigma5",
                    "description": "Sigma 5 industrial IoT platform",
                    "active": True,
                    "metadata": Json(sigma5_metadata),
                },
                "update": {
                    "slug": "sigma5",
                    "metadata": Json(sigma5_metadata),
                },
            },
        )
        print(f"Product: {sigma5_product.name} (id: {sigma5_product.id})")

        # Sigma 5 board (family: sigma5)
        sigma5_board = db.board.upsert(
            where={"productId": sigma5_product.id},
            data={
                "create": {
                    "productId": sigma5_product.id,
                    "name": "Main Board",
                    "ckBoardsFamily": "sigma5",
                    "vendor": "corekinect",
                    "description": "Sigma 5 main board with nRF52840 + nRF9160",
                    "active": True,
                },
                "update": {
                    "ckBoardsFamily": "sigma5",
                    "vendor": "corekinect",
                },
            },
        )

        # Sigma 5 B0 revision (older)
        sigma5_b0_rev = db.boardrevision.upsert(
            where={"boardId_version": {"boardId": sigma5_board.id, "version": "B0"}},
            data={
                "create": {
                    "boardId": sigma5_board.id,
                    "version": "B0",
                    "ckBoardsName": "sigma5_b0",
                    "socs": ["nrf52840"],
                    "notes": "Sigma5 B0 - previous revision, superseded by C0",
                },
                "update": {
                    "ckBoardsName": "sigma5_b0",
                    "socs": ["nrf52840"],
                },
            },
        )

        # Sigma5 B0 ProductTargets
        for target in [
            {"role": "comms", "soc": "nRF9160", "appId": 104},
            {"role": "app", "soc": "nRF52840", "appId": 105},
        ]:
            db.producttarget.upsert(
                where={"boardRevisionId_role": {"boardRevisionId": sigma5_b0_rev.id, "role": target["role"]}},
                data={
                    "create": {"boardRevisionId": sigma5_b0_rev.id, **target},
                    "update": {"soc": target["soc"], "appId": target["appId"]},
                },
            )

        # Sigma 5 C0 revision (current)
        sigma5_c0_rev = db.boardrevision.upsert(
            where={"boardId_version": {"boardId": sigma5_board.id, "version": "C0"}},
            data={
                "create": {
                    "boardId": sigma5_board.id,
                    "version": "C0",
                    "ckBoardsName": "sigma5_c0",
                    "socs": ["nrf52840"],
                    "notes": "Sigma5 C0 - current production revision",
                },
                "update": {
                    "ckBoardsName": "sigma5_c0",
                    "socs": ["nrf52840"],
                },
            },
        )
        # Sigma5 C0 ProductTargets (current production revision)
        for target in [
            {"role": "comms", "soc": "nRF9160", "appId": 104},
            {"role": "app", "soc": "nRF52840", "appId": 105},
        ]:
            db.producttarget.upsert(
                where={"boardRevisionId_role": {"boardRevisionId": sigma5_c0_rev.id, "role": target["role"]}},
                data={
                    "create": {"boardRevisionId": sigma5_c0_rev.id, **target},
                    "update": {"soc": target["soc"], "appId": target["appId"]},
                },
            )
        print(f"  Board: {sigma5_board.name} / B0, C0")

        # Theta product with C0 board revision (asset tracker)
        theta_metadata = {
            "device_type": 3,
            "device_variant": 1,
            "app_ids": {"nrf52840": 107, "nrf9160": 100},
            "corecloud_env": "VAL_1_0",
        }
        theta_product = db.product.upsert(
            where={"name": "Theta"},
            data={
                "create": {
                    "name": "Theta",
                    "slug": "theta",
                    "description": "Theta asset tracker platform",
                    "active": True,
                    "metadata": Json(theta_metadata),
                },
                "update": {
                    "slug": "theta",
                    "metadata": Json(theta_metadata),
                },
            },
        )
        print(f"Product: {theta_product.name} (id: {theta_product.id})")

        # Theta board (family: theta)
        theta_board = db.board.upsert(
            where={"productId": theta_product.id},
            data={
                "create": {
                    "productId": theta_product.id,
                    "name": "Main Board",
                    "ckBoardsFamily": "theta",
                    "description": "Theta main board with nRF52840 + nRF9160",
                    "active": True,
                },
                "update": {
                    "ckBoardsFamily": "theta",
                },
            },
        )

        # Theta C0 revision (current)
        theta_c0_rev = db.boardrevision.upsert(
            where={"boardId_version": {"boardId": theta_board.id, "version": "C0"}},
            data={
                "create": {
                    "boardId": theta_board.id,
                    "version": "C0",
                    "ckBoardsName": "theta_c0",
                    "socs": ["nrf9160", "nrf52840"],
                    "notes": "Theta C0 - current production revision (nRF52840 + nRF9160)",
                },
                "update": {
                    "ckBoardsName": "theta_c0",
                    "socs": ["nrf9160", "nrf52840"],
                },
            },
        )
        # Theta C0 ProductTargets
        for target in [
            {"role": "comms", "soc": "nRF9160", "appId": 104},
            {"role": "app", "soc": "nRF52840", "appId": 105},
        ]:
            db.producttarget.upsert(
                where={"boardRevisionId_role": {"boardRevisionId": theta_c0_rev.id, "role": target["role"]}},
                data={
                    "create": {"boardRevisionId": theta_c0_rev.id, **target},
                    "update": {"soc": target["soc"], "appId": target["appId"]},
                },
            )
        print(f"  Board: {theta_board.name} / C0")

        # IWSCK product with A1 board revision (BLE-only device)
        iwsck_metadata = {
            "device_type": 4,
            "device_variant": 1,
            "app_ids": {"nrf52840": 110},
            "corecloud_env": None,  # No cloud connectivity
        }
        iwsck_product = db.product.upsert(
            where={"name": "IWSCK"},
            data={
                "create": {
                    "name": "IWSCK",
                    "slug": "iwsck",
                    "description": "IWSCK BLE-only device platform",
                    "active": True,
                    "metadata": Json(iwsck_metadata),
                },
                "update": {
                    "slug": "iwsck",
                    "metadata": Json(iwsck_metadata),
                },
            },
        )
        print(f"Product: {iwsck_product.name} (id: {iwsck_product.id})")

        # IWSCK board (family: iwsck)
        iwsck_board = db.board.upsert(
            where={"productId": iwsck_product.id},
            data={
                "create": {
                    "productId": iwsck_product.id,
                    "name": "Main Board",
                    "ckBoardsFamily": "iwsck",
                    "description": "IWSCK main board with nRF52840 only (no modem)",
                    "active": True,
                },
                "update": {
                    "ckBoardsFamily": "iwsck",
                },
            },
        )

        # IWSCK A1 revision (current)
        iwsck_a1_rev = db.boardrevision.upsert(
            where={"boardId_version": {"boardId": iwsck_board.id, "version": "A1"}},
            data={
                "create": {
                    "boardId": iwsck_board.id,
                    "version": "A1",
                    "ckBoardsName": "iwsck_a1",
                    "socs": ["nrf52840"],
                    "notes": "IWSCK A1 - current revision (nRF52840 only, BLE)",
                },
                "update": {
                    "ckBoardsName": "iwsck_a1",
                    "socs": ["nrf52840"],
                },
            },
        )
        # IWSCK A1 ProductTarget (single SoC)
        db.producttarget.upsert(
            where={"boardRevisionId_role": {"boardRevisionId": iwsck_a1_rev.id, "role": "app"}},
            data={
                "create": {"boardRevisionId": iwsck_a1_rev.id, "role": "app", "soc": "nRF52840", "appId": 110},
                "update": {"soc": "nRF52840", "appId": 110},
            },
        )
        print(f"  Board: {iwsck_board.name} / A1")

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

        alpha_design = db.fixturedesign.upsert(
            where={"name": "alpha-fixture-v1.2"},
            data={
                "create": {
                    "name": "alpha-fixture-v1.2",
                    "product": "alpha",
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

        # Sigma5 fixture profile template (complete structure)
        sigma5_profile_template = {
            "station_id": None,
            "product": "sigma5",
            "board": "sigma5_c0",
            "mtib_revision": "1.2",
            "capabilities": ["button", "motion"],
            "dut": {
                "device_id": None,
                "snr": None,
                "imei": None,
                "iccids": [],
            },
            "power": {
                "battery_installed": False,
                "dut_voltage": 3.7,
                "charger_voltage": 5.0,
                "boot_settle_s": 8,
            },
            "button": {
                "gpio_pin": 2,
                "active_low": True,
            },
            "peltier": None,
            "charger_relay": None,
            "ppg_simulator": None,
            "led_sensor": None,
            "nfc_reader": None,
            "motion": {
                "enabled": True,
                "home_on_startup": True,
                "shake_distance_mm": 30,
                "shake_speed_mm_s": 80,
            },
        }

        sigma5_design = db.fixturedesign.upsert(
            where={"name": "sigma5-fixture-v1.2"},
            data={
                "create": {
                    "name": "sigma5-fixture-v1.2",
                    "product": "sigma5",
                    "revision": "1.2",
                    "capabilities": ["button", "motion"],
                    "profileTemplate": Json(sigma5_profile_template),
                    "notes": "REV 1.2 MTIB carrier for Sigma5 C0 validation. Button + motion enabled. No biometrics.",
                },
                "update": {
                    "profileTemplate": Json(sigma5_profile_template),
                },
            },
        )
        print(f"Fixture design: {sigma5_design.name} (id: {sigma5_design.id})")

        # Theta fixture profile template (complete structure)
        theta_profile_template = {
            "station_id": None,
            "product": "theta",
            "board": "theta_c0",
            "mtib_revision": "1.2",
            "capabilities": ["button", "motion", "gps"],
            "dut": {
                "device_id": None,
                "snr": None,
                "imei": None,
                "iccids": [],
            },
            "power": {
                "battery_installed": True,
                "dut_voltage": 3.7,
                "charger_voltage": 5.0,
                "boot_settle_s": 10,
            },
            "button": {
                "gpio_pin": 2,
                "active_low": True,
            },
            "peltier": None,
            "charger_relay": None,
            "ppg_simulator": None,
            "led_sensor": None,
            "nfc_reader": None,
            "motion": {
                "enabled": True,
                "home_on_startup": True,
                "shake_distance_mm": 50,
                "shake_speed_mm_s": 100,
            },
            "gps": {
                "simulator_enabled": False,
            },
        }

        theta_design = db.fixturedesign.upsert(
            where={"name": "theta-fixture-v1.2"},
            data={
                "create": {
                    "name": "theta-fixture-v1.2",
                    "product": "theta",
                    "revision": "1.2",
                    "capabilities": ["button", "motion", "gps"],
                    "profileTemplate": Json(theta_profile_template),
                    "notes": "REV 1.2 MTIB carrier for Theta C0 validation. Button, motion, GPS supported.",
                },
                "update": {
                    "profileTemplate": Json(theta_profile_template),
                },
            },
        )
        print(f"Fixture design: {theta_design.name} (id: {theta_design.id})")

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
                    "nodeId": "node_mtib_rev12",
                },
                "update": {
                    "dutDeviceId": "70B3D584C01E1FCC",
                    "dutSnr": "0964",
                    "dutImei": "355025931735979",
                    "dutIccids": ["89148000009808558441", "89457300000037582833"],
                    "nodeId": "node_mtib_rev12",
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

        # Sigma5 C0 fixture (MTIB 34)
        fixture_34 = db.fixture.upsert(
            where={"stationId": "bench-34"},
            data={
                "create": {
                    "stationId": "bench-34",
                    "name": "Sigma5 C0 Bench (MTIB 34)",
                    "productId": sigma5_product.id,
                    "designId": sigma5_design.id,
                    "type": "VALIDATION",
                    "status": "AVAILABLE",
                },
                "update": {
                    "productId": sigma5_product.id,
                    "designId": sigma5_design.id,
                },
            },
        )
        db.fixtureslot.upsert(
            where={"fixtureId_slotIndex": {"fixtureId": fixture_34.id, "slotIndex": 0}},
            data={
                "create": {
                    "fixtureId": fixture_34.id,
                    "slotIndex": 0,
                    "label": "Primary",
                    "uartAppPath": "/dev/verdin-uart2",
                    "uartCommsPath": "/dev/verdin-uart1",
                },
                "update": {},
            },
        )
        print(f"Fixture: {fixture_34.stationId} (product: {sigma5_product.name})")

        # Theta C0 fixture (MTIB 35 - placeholder for future deployment)
        fixture_35 = db.fixture.upsert(
            where={"stationId": "bench-35"},
            data={
                "create": {
                    "stationId": "bench-35",
                    "name": "Theta C0 Bench (MTIB 35)",
                    "productId": theta_product.id,
                    "designId": theta_design.id,
                    "type": "VALIDATION",
                    "status": "OFFLINE",
                },
                "update": {
                    "productId": theta_product.id,
                    "designId": theta_design.id,
                },
            },
        )
        db.fixtureslot.upsert(
            where={"fixtureId_slotIndex": {"fixtureId": fixture_35.id, "slotIndex": 0}},
            data={
                "create": {
                    "fixtureId": fixture_35.id,
                    "slotIndex": 0,
                    "label": "Primary",
                    "uartAppPath": "/dev/verdin-uart2",
                    "uartCommsPath": "/dev/verdin-uart1",
                },
                "update": {},
            },
        )
        print(f"Fixture: {fixture_35.stationId} (product: {theta_product.name})")

        # ── Stage Configs ──
        # === Seeding Stage Configs ===
        print("\n=== Seeding Stage Configs ===")

        # Read Alpha build script from repo
        build_script_path = os.path.join(os.path.dirname(__file__), "..", "apps", "firmware", "products", "alpha", "scripts", "build.sh")
        alpha_build_script = ""
        if os.path.exists(build_script_path):
            with open(build_script_path) as f:
                alpha_build_script = f.read()
            print(f"  Loaded build script: {len(alpha_build_script)} bytes")
        else:
            print(f"  WARNING: Build script not found at {build_script_path}")

        alpha_stages = [
            {
                "stage": 1, "name": "Smoke", "enabled": False,
                "priority": 10, "blocksMerge": True, "requiresFuota": False, "requiresBench": False,
                "testTimeout": 120, "maxDurationSec": 300,
                "buildScript": alpha_build_script or None,
                "buildTarget": "alpha_b0",
                "buildVariant": "debug",
                "fwRepoUrl": "git@bitbucket.org:corekinect/alpha_fw.git",
                "fwRepoBranch": "concord-main",
                "description": "Quick smoke build to verify compilation",
                "buildMatrix": Json([
                    {"role": "app", "firmware": "alpha_fw", "source": "head",
                     "description": "Build app firmware from triggering commit"},
                ]),
            },
            {
                "stage": 2, "name": "Silicon", "enabled": False,
                "priority": 20, "blocksMerge": True, "requiresFuota": False, "requiresBench": False,
                "testTimeout": 300, "maxDurationSec": 600,
                "buildTarget": "native_sim",
                "buildVariant": "test",
                "testDirectory": "tests/unit/",
                "testMarker": "-m unit",
                "description": "Native simulator unit tests",
                "buildMatrix": Json([]),
            },
            {
                "stage": 3, "name": "Integration", "enabled": False,
                "priority": 30, "blocksMerge": True, "requiresFuota": False, "requiresBench": True,
                "testTimeout": 600, "maxDurationSec": 1200,
                "buildTarget": "alpha_b0",
                "buildVariant": "debug",
                "testDirectory": "tests/integration/",
                "testMarker": "-m integration",
                "description": "Subsystem integration tests with harness instrumentation",
                "buildMatrix": Json([
                    {"role": "mfg", "firmware": "alpha_mfg_fw", "source": "head",
                     "description": "Manufacturing firmware for J-Link flash + personalization"},
                    {"role": "app", "firmware": "alpha_fw", "source": "head",
                     "description": "Application firmware from triggering commit"},
                ]),
            },
            {
                "stage": 4, "name": "Nightly", "enabled": False,
                "priority": 40, "blocksMerge": False, "requiresFuota": False, "requiresBench": True,
                "testTimeout": 1800, "maxDurationSec": 3600,
                "buildTarget": "alpha_b0",
                "buildVariant": "debug",
                "fwRepoUrl": "git@bitbucket.org:corekinect/alpha_fw.git",
                "fwRepoBranch": "concord-main",
                "mfgRepoUrl": "git@bitbucket.org:corekinect/alpha_mfg_fw.git",
                "mfgRepoBranch": "concord-main",
                "testDirectory": "tests/nightly/",
                "testMarker": "-m nightly",
                "description": "Extended nightly test suite with power profiling",
                "buildMatrix": Json([
                    {"role": "mfg", "firmware": "alpha_mfg_fw", "source": "head",
                     "description": "Manufacturing firmware for J-Link flash + personalization"},
                    {"role": "app", "firmware": "alpha_fw", "source": "head",
                     "description": "Application firmware from triggering commit"},
                ]),
            },
            {
                "stage": 5, "name": "FUOTA", "enabled": True,
                "priority": 100, "blocksMerge": True, "requiresFuota": True, "requiresBench": True,
                "testTimeout": 600, "maxDurationSec": 900,
                "buildScript": alpha_build_script or None,
                "buildTarget": "alpha_b0",
                "buildVariant": "release",
                "fwRepoUrl": "git@bitbucket.org:corekinect/alpha_fw.git",
                "fwRepoBranch": "concord-main",
                "mfgRepoUrl": "git@bitbucket.org:corekinect/alpha_mfg_fw.git",
                "mfgRepoBranch": "concord-main",
                "testDirectory": "tests/fuota/",
                "testMarker": "-m fuota",
                "description": "FUOTA delivery verification and boot confirmation",
                "buildMatrix": Json([
                    {"role": "mfg_flash", "firmware": "alpha_mfg_fw", "source": "latest_prev",
                     "description": "Older MFG firmware to flash via J-Link (FUOTA base, N-1)"},
                    {"role": "mfg_base", "firmware": "alpha_mfg_fw", "source": "latest",
                     "description": "Newer MFG firmware CFW for MFG-to-MFG FUOTA test (N)"},
                    {"role": "flash_base", "firmware": "alpha_fw", "source": "latest",
                     "description": "Previous production firmware (cached baseline)"},
                    {"role": "fuota_target", "firmware": "alpha_fw", "source": "head",
                     "description": "New production firmware CFW for OTA delivery"},
                ]),
            },
        ]

        # Find Alpha product ID
        alpha_product_for_stages = db.product.find_first(where={"slug": {"startswith": "alpha"}})
        if alpha_product_for_stages:
            # Delete existing configs first (idempotent re-seed)
            db.productstageconfig.delete_many(where={"productId": alpha_product_for_stages.id})

            for stage_data in alpha_stages:
                db.productstageconfig.create(data={
                    "productId": alpha_product_for_stages.id,
                    **stage_data,
                })
            print(f"  Alpha: {len(alpha_stages)} stage configs seeded")
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
                    "permissionSetId": super_admin_set.id,
                    "active": True,
                },
                "update": {
                    "permissionSetId": super_admin_set.id,
                },
            },
        )
        print(f"System user ready: {system_user.email}")

        from datetime import datetime, timezone
        ci_api_key = db.apikey.upsert(
            where={"id": "ci_admin_key_001"},
            data={
                "create": {
                    "id": "ci_admin_key_001",
                    "name": "CI Admin Key",
                    "keyHash": ci_key_hash,
                    "keyPrefix": ci_key[:12],
                    "userId": system_user.id,
                    "expiresAt": datetime.now(timezone.utc) + timedelta(days=365),
                },
                "update": {
                    "keyHash": ci_key_hash,
                    "keyPrefix": ci_key[:12],
                    "expiresAt": datetime.now(timezone.utc) + timedelta(days=365),
                },
            },
        )
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

        # ── Product Access for Dev Users ──
        # Give all dev users access to all products for role-based testing
        print("\n=== Seeding Product Access ===")
        all_products = db.product.find_many()
        all_dev_users = db.user.find_many(where={"active": True})

        # Map role to access level
        ROLE_ACCESS_LEVEL = {
            "ADMIN": "admin",
            "MAINTAINER": "admin",
            "DEVELOPER": "develop",
            "OPERATOR": "operate",
        }

        for u in all_dev_users:
            user_role = getattr(u, "role", "DEVELOPER") or "DEVELOPER"
            level = ROLE_ACCESS_LEVEL.get(user_role, "view")
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
