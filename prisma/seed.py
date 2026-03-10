"""Seed the database with default permission sets and initial admin user.

Usage:
    SEED_ADMIN_EMAIL=you@company.com SEED_ADMIN_NAME="Your Name" python3 seed.py

Or via Nx:
    SEED_ADMIN_EMAIL=you@company.com npx nx run database:seed
"""

import os
import sys

# Add libs to path so we can import the Prisma client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "libs", "python"))

from database import Prisma, Json

# Every permission that exists in the system
ALL_PERMISSIONS = [
    "Concord.Cluster.Read",
    "Concord.Cluster.Manage",
    "Concord.Validation.Tests.Run",
    "Concord.Admin.Users.View",
    "Concord.Admin.Users.Manage",
    "Concord.Admin.PermissionSets.View",
    "Concord.Admin.PermissionSets.Manage",
    "Concord.Admin.ApiKeys.View",
    "Concord.Admin.ApiKeys.Manage",
    "Concord.Admin.Inventory.View",
    "Concord.Admin.Inventory.Manage",
    "Concord.Admin.Codebases.View",
    "Concord.Admin.Codebases.Manage",
    "Concord.Admin.Catalog.View",
    "Concord.Admin.Catalog.Manage",
    "Concord.Admin.History.View",
    "Concord.Admin.System.View",
    "Concord.Admin.System.Manage",
    "Concord.Admin.Nodes.View",
    "Concord.Admin.Nodes.Manage",
    "Concord.Admin.Fixtures.View",
    "Concord.Admin.Fixtures.Manage",
    "Concord.Admin.Deployments.View",
    "Concord.Admin.Deployments.Manage",
    "Concord.Admin.Validation.View",
    "Concord.Admin.Validation.Manage",
    "Concord.Admin.CI.View",
    "Concord.Admin.CI.Manage",
]

# Default permission sets
ADMIN_PERMISSIONS = [
    "Concord.Cluster.Read",
    "Concord.Cluster.Manage",
    "Concord.Validation.Tests.Run",
    "Concord.Admin.Users.View",
    "Concord.Admin.Users.Manage",
    "Concord.Admin.Inventory.View",
    "Concord.Admin.Inventory.Manage",
    "Concord.Admin.Codebases.View",
    "Concord.Admin.Codebases.Manage",
    "Concord.Admin.Catalog.View",
    "Concord.Admin.Catalog.Manage",
    "Concord.Admin.History.View",
    "Concord.Admin.System.View",
    "Concord.Admin.Nodes.View",
    "Concord.Admin.Nodes.Manage",
    "Concord.Admin.Fixtures.View",
    "Concord.Admin.Fixtures.Manage",
    "Concord.Admin.Deployments.View",
    "Concord.Admin.Deployments.Manage",
    "Concord.Admin.Validation.View",
    "Concord.Admin.Validation.Manage",
    "Concord.Admin.CI.View",
    "Concord.Admin.CI.Manage",
]

OPERATOR_PERMISSIONS = [
    "Concord.Cluster.Read",
    "Concord.Cluster.Manage",
    "Concord.Validation.Tests.Run",
]

VIEWER_PERMISSIONS = [
    "Concord.Cluster.Read",
]


def seed():
    email = os.environ.get("SEED_ADMIN_EMAIL", "").strip()
    name = os.environ.get("SEED_ADMIN_NAME", "Admin").strip()

    db = Prisma()
    db.connect()

    try:
        # Create default permission sets
        super_admin_set = db.permissionset.upsert(
            where={"name": "Super Admin"},
            data={
                "create": {
                    "name": "Super Admin",
                    "description": "Unrestricted access — all permissions",
                    "permissions": ALL_PERMISSIONS,
                },
                "update": {
                    "description": "Unrestricted access — all permissions",
                    "permissions": ALL_PERMISSIONS,
                },
            },
        )
        print(f"Permission set 'Super Admin' ready (id: {super_admin_set.id})")

        admin_set = db.permissionset.upsert(
            where={"name": "Admin"},
            data={
                "create": {
                    "name": "Admin",
                    "description": "Admin access to users and day-to-day operations",
                    "permissions": ADMIN_PERMISSIONS,
                },
                "update": {
                    "description": "Admin access to users and day-to-day operations",
                    "permissions": ADMIN_PERMISSIONS,
                },
            },
        )
        print(f"Permission set 'Admin' ready (id: {admin_set.id})")

        operator_set = db.permissionset.upsert(
            where={"name": "Operator"},
            data={
                "create": {
                    "name": "Operator",
                    "description": "Operational access without admin capabilities",
                    "permissions": OPERATOR_PERMISSIONS,
                },
                "update": {
                    "description": "Operational access without admin capabilities",
                    "permissions": OPERATOR_PERMISSIONS,
                },
            },
        )
        print(f"Permission set 'Operator' ready (id: {operator_set.id})")

        viewer_set = db.permissionset.upsert(
            where={"name": "Viewer"},
            data={
                "create": {
                    "name": "Viewer",
                    "description": "Read-only access",
                    "permissions": VIEWER_PERMISSIONS,
                },
                "update": {
                    "description": "Read-only access",
                    "permissions": VIEWER_PERMISSIONS,
                },
            },
        )
        print(f"Permission set 'Viewer' ready (id: {viewer_set.id})")

        # Seed default chipsets
        default_chipsets = [
            {"name": "nRF52840", "manufacturer": "Nordic Semiconductor", "isModem": False},
            {"name": "nRF9151", "manufacturer": "Nordic Semiconductor", "isModem": True},
            {"name": "nRF9160", "manufacturer": "Nordic Semiconductor", "isModem": True},
        ]
        for chip in default_chipsets:
            chipset = db.chipset.upsert(
                where={"name": chip["name"]},
                data={
                    "create": {
                        "name": chip["name"],
                        "manufacturer": chip["manufacturer"],
                        "isModem": chip["isModem"],
                    },
                    "update": {
                        "manufacturer": chip["manufacturer"],
                        "isModem": chip["isModem"],
                    },
                },
            )
            print(f"Chipset '{chip['name']}' ready (id: {chipset.id})")

        # Backfill existing users that have no permission set
        users_without_set = db.user.find_many(where={"permissionSetId": None})
        for user in users_without_set:
            # Default unassigned users to Viewer
            db.user.update(
                where={"id": user.id},
                data={"permissionSetId": viewer_set.id},
            )
            print(f"Assigned '{user.email}' to Viewer permission set")

        # Create super admin user if email provided
        if email:
            existing = db.user.find_unique(where={"email": email.lower()})
            if existing:
                if existing.permissionSetId != super_admin_set.id:
                    db.user.update(
                        where={"id": existing.id},
                        data={"permissionSetId": super_admin_set.id},
                    )
                    print(f"Updated '{existing.email}' to Super Admin permission set")
                else:
                    print(f"Super admin user already exists: {existing.email}")
            else:
                user = db.user.create(
                    data={
                        "email": email.lower(),
                        "name": name,
                        "permissionSetId": super_admin_set.id,
                        "active": True,
                    }
                )
                print(f"Created super admin user: {user.email} (id: {user.id})")
        else:
            print("SEED_ADMIN_EMAIL not set. Skipping admin user creation.")
            print("Usage: SEED_ADMIN_EMAIL=you@company.com python3 seed.py")

        # ── Products + Boards ──
        print("\n=== Seeding Products & Boards ===")

        # Alpha product with B0 board revision
        alpha_product = db.product.upsert(
            where={"name": "Alpha"},
            data={
                "create": {
                    "name": "Alpha",
                    "slug": "alpha_b0",
                    "description": "Alpha wearable device platform",
                    "active": True,
                    # Firmware repo config (git poller watches this)
                    "repoSlug": "alpha_fw",
                    "repoSshUrl": "git@bitbucket.org:corekinect/alpha_fw.git",
                    "repoBranch": "concord-main",
                    # Manufacturing firmware repo (cloned during build)
                    "mfgRepoSlug": "alpha_mfg_fw",
                    "mfgRepoSshUrl": "git@bitbucket.org:corekinect/alpha_mfg_fw.git",
                    # Build config (build worker uses this)
                    "buildBoard": "alpha_b0",
                    "buildWestDir": "apps/firmware/products/alpha/alpha_fw",
                    "buildMfgDir": "apps/firmware/products/alpha/alpha_mfg_fw",
                    "metadata": Json({
                        "device_type": 2,
                        "device_variant": 3,
                    }),
                },
                "update": {
                    "slug": "alpha_b0",
                    "repoSlug": "alpha_fw",
                    "repoSshUrl": "git@bitbucket.org:corekinect/alpha_fw.git",
                    "repoBranch": "concord-main",
                    "mfgRepoSlug": "alpha_mfg_fw",
                    "mfgRepoSshUrl": "git@bitbucket.org:corekinect/alpha_mfg_fw.git",
                    "buildBoard": "alpha_b0",
                    "buildWestDir": "apps/firmware/products/alpha/alpha_fw",
                    "buildMfgDir": "apps/firmware/products/alpha/alpha_mfg_fw",
                },
            },
        )
        print(f"Product: {alpha_product.name} (id: {alpha_product.id})")

        # Alpha B0 board
        alpha_board = db.board.upsert(
            where={"productId_name": {"productId": alpha_product.id, "name": "Main Board"}},
            data={
                "create": {
                    "productId": alpha_product.id,
                    "name": "Main Board",
                    "description": "Alpha main board with nRF52840 + nRF9151",
                    "active": True,
                },
                "update": {},
            },
        )

        db.boardrevision.upsert(
            where={"boardId_version": {"boardId": alpha_board.id, "version": "B0"}},
            data={
                "create": {
                    "boardId": alpha_board.id,
                    "version": "B0",
                    "notes": "Alpha B0 revision - production board (nRF52840 + nRF9151)",
                },
                "update": {},
            },
        )
        print(f"  Board: {alpha_board.name} / B0")

        # Sigma 5 product with C0 and B0 board revisions
        sigma5_product = db.product.upsert(
            where={"name": "Sigma5"},
            data={
                "create": {
                    "name": "Sigma5",
                    "slug": "sigma5_c0",
                    "description": "Sigma 5 industrial IoT platform",
                    "active": True,
                    # Firmware repo config (git poller watches this)
                    "repoSlug": "sigma5_fw",
                    "repoSshUrl": "git@bitbucket.org:corekinect/sigma5_fw.git",
                    "repoBranch": "concord-main",
                    # Manufacturing firmware repo (cloned during build)
                    "mfgRepoSlug": "sigma5_mfg_fw",
                    "mfgRepoSshUrl": "git@bitbucket.org:corekinect/sigma5_mfg_fw.git",
                    # Build config (build worker uses this)
                    "buildBoard": "sigma5_b0",
                    "buildWestDir": "apps/firmware/products/sigma5/sigma5_fw",
                    "buildMfgDir": "apps/firmware/products/sigma5/sigma5_mfg_fw",
                    "metadata": Json({
                        "device_type": 1,
                        "device_variant": 5,
                    }),
                },
                "update": {
                    "slug": "sigma5_c0",
                    "repoSlug": "sigma5_fw",
                    "repoSshUrl": "git@bitbucket.org:corekinect/sigma5_fw.git",
                    "repoBranch": "concord-main",
                    "mfgRepoSlug": "sigma5_mfg_fw",
                    "mfgRepoSshUrl": "git@bitbucket.org:corekinect/sigma5_mfg_fw.git",
                    "buildBoard": "sigma5_b0",
                    "buildWestDir": "apps/firmware/products/sigma5/sigma5_fw",
                    "buildMfgDir": "apps/firmware/products/sigma5/sigma5_mfg_fw",
                },
            },
        )
        print(f"Product: {sigma5_product.name} (id: {sigma5_product.id})")

        # Sigma 5 board
        sigma5_board = db.board.upsert(
            where={"productId_name": {"productId": sigma5_product.id, "name": "Main Board"}},
            data={
                "create": {
                    "productId": sigma5_product.id,
                    "name": "Main Board",
                    "description": "Sigma 5 main board with nRF52840 + nRF9160",
                    "active": True,
                },
                "update": {},
            },
        )

        # Sigma 5 B0 revision (older)
        db.boardrevision.upsert(
            where={"boardId_version": {"boardId": sigma5_board.id, "version": "B0"}},
            data={
                "create": {
                    "boardId": sigma5_board.id,
                    "version": "B0",
                    "notes": "Sigma5 B0 - legacy revision (deprecated)",
                },
                "update": {},
            },
        )
        print(f"  Board: {sigma5_board.name} / B0")

        # Sigma 5 C0 revision (current)
        db.boardrevision.upsert(
            where={"boardId_version": {"boardId": sigma5_board.id, "version": "C0"}},
            data={
                "create": {
                    "boardId": sigma5_board.id,
                    "version": "C0",
                    "notes": "Sigma5 C0 - current production revision",
                },
                "update": {},
            },
        )
        print(f"  Board: {sigma5_board.name} / C0")

        # Theta product with C0 board revision (asset tracker)
        theta_product = db.product.upsert(
            where={"name": "Theta"},
            data={
                "create": {
                    "name": "Theta",
                    "slug": "theta_c0",
                    "description": "Theta asset tracker platform",
                    "active": True,
                    # Firmware repo config (git poller watches this)
                    "repoSlug": "theta_fw",
                    "repoSshUrl": "git@bitbucket.org:corekinect/theta_fw.git",
                    "repoBranch": "main",
                    # Manufacturing firmware repo (cloned during build)
                    "mfgRepoSlug": "theta_mfg_fw",
                    "mfgRepoSshUrl": "git@bitbucket.org:corekinect/theta_mfg_fw.git",
                    # Build config (build worker uses this)
                    "buildBoard": "theta_c0",
                    "buildWestDir": "apps/firmware/products/theta/theta_fw",
                    "buildMfgDir": "apps/firmware/products/theta/theta_mfg_fw",
                    "metadata": Json({
                        "device_type": 3,
                        "device_variant": 1,
                        "app_ids": {"nrf52840": 107, "nrf9160": 100},
                    }),
                },
                "update": {
                    "slug": "theta_c0",
                    "repoSlug": "theta_fw",
                    "repoSshUrl": "git@bitbucket.org:corekinect/theta_fw.git",
                    "repoBranch": "main",
                    "mfgRepoSlug": "theta_mfg_fw",
                    "mfgRepoSshUrl": "git@bitbucket.org:corekinect/theta_mfg_fw.git",
                    "buildBoard": "theta_c0",
                    "buildWestDir": "apps/firmware/products/theta/theta_fw",
                    "buildMfgDir": "apps/firmware/products/theta/theta_mfg_fw",
                },
            },
        )
        print(f"Product: {theta_product.name} (id: {theta_product.id})")

        # Theta board
        theta_board = db.board.upsert(
            where={"productId_name": {"productId": theta_product.id, "name": "Main Board"}},
            data={
                "create": {
                    "productId": theta_product.id,
                    "name": "Main Board",
                    "description": "Theta main board with nRF52840 + nRF9160",
                    "active": True,
                },
                "update": {},
            },
        )

        # Theta C0 revision (current)
        db.boardrevision.upsert(
            where={"boardId_version": {"boardId": theta_board.id, "version": "C0"}},
            data={
                "create": {
                    "boardId": theta_board.id,
                    "version": "C0",
                    "notes": "Theta C0 - current production revision (nRF52840 + nRF9160)",
                },
                "update": {},
            },
        )
        print(f"  Board: {theta_board.name} / C0")

        # ── Fixture Designs ──
        print("\n=== Seeding Fixture Designs ===")
        alpha_design = db.fixturedesign.upsert(
            where={"name": "alpha-fixture-v1.2"},
            data={
                "create": {
                    "name": "alpha-fixture-v1.2",
                    "product": "alpha",
                    "revision": "1.2",
                    "capabilities": ["button", "peltier", "charger_relay"],
                    "profileTemplate": Json({
                        "product": "alpha",
                        "board": "alpha_b0",
                        "mtib_revision": "1.2",
                        "power": {
                            "battery_installed": True,
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
                    }),
                    "notes": "REV 1.2 MTIB carrier for Alpha B0 validation. Button, peltier, charger relay wired.",
                },
                "update": {},
            },
        )
        print(f"Fixture design: {alpha_design.name} (id: {alpha_design.id})")

        # Sigma5 fixture design (asset tracker - no biometrics)
        sigma5_design = db.fixturedesign.upsert(
            where={"name": "sigma5-fixture-v1.2"},
            data={
                "create": {
                    "name": "sigma5-fixture-v1.2",
                    "product": "sigma5",
                    "revision": "1.2",
                    "capabilities": ["button", "motion"],
                    "profileTemplate": Json({
                        "product": "sigma5",
                        "board": "sigma5_c0",
                        "mtib_revision": "1.2",
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
                        "motion": {
                            "enabled": True,
                            "home_on_startup": True,
                            "shake_distance_mm": 30,
                            "shake_speed_mm_s": 80,
                        },
                    }),
                    "notes": "REV 1.2 MTIB carrier for Sigma5 C0 validation. Button + motion enabled. No biometrics.",
                },
                "update": {},
            },
        )
        print(f"Fixture design: {sigma5_design.name} (id: {sigma5_design.id})")

        # Theta fixture design (asset tracker - GPS, motion, battery)
        theta_design = db.fixturedesign.upsert(
            where={"name": "theta-fixture-v1.2"},
            data={
                "create": {
                    "name": "theta-fixture-v1.2",
                    "product": "theta",
                    "revision": "1.2",
                    "capabilities": ["button", "motion", "gps"],
                    "profileTemplate": Json({
                        "product": "theta",
                        "board": "theta_c0",
                        "mtib_revision": "1.2",
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
                        "motion": {
                            "enabled": True,
                            "home_on_startup": True,
                            "shake_distance_mm": 50,
                            "shake_speed_mm_s": 100,
                        },
                        "gps": {
                            "simulator_enabled": False,
                        },
                    }),
                    "notes": "REV 1.2 MTIB carrier for Theta C0 validation. Button, motion, GPS supported.",
                },
                "update": {},
            },
        )
        print(f"Fixture design: {theta_design.name} (id: {theta_design.id})")

        # ── Test Benches ──
        print("\n=== Seeding Test Benches ===")
        bench_33 = db.testbench.upsert(
            where={"stationId": "station-33"},
            data={
                "create": {
                    "stationId": "station-33",
                    "name": "Alpha B0 Bench 1 (MTIB 33)",
                    "mtibAddress": "10.4.45.33:50053",
                    "mtibRevision": "REV1.2",
                    "productId": alpha_product.id,  # FK to Product
                    "fixtureDesignId": alpha_design.id,
                    "capabilities": ["button", "peltier", "charger_relay"],
                    "dutProduct": "alpha",
                    "dutRevision": "b0",
                    "dutDeviceId": "70B3D584C01E1FCC",
                    "dutSnr": "0964",
                    "dutImei": "355025931735979",
                    "dutIccids": ["89148000009808558441", "89457300000037582833"],
                    "jlinkAppSerial": "821009546",
                    "jlinkCommsSerial": "821009537",
                    "uartAppPath": "/dev/verdin-uart2",
                    "uartCommsPath": "/dev/verdin-uart1",
                    "status": "AVAILABLE",
                },
                "update": {
                    "productId": alpha_product.id,
                    "fixtureDesignId": alpha_design.id,
                },
            },
        )
        print(f"Test bench: {bench_33.stationId} -> {bench_33.mtibAddress} (product: {alpha_product.name})")

        bench_32 = db.testbench.upsert(
            where={"stationId": "station-32"},
            data={
                "create": {
                    "stationId": "station-32",
                    "name": "Alpha B0 Bench 2 (MTIB 32)",
                    "mtibAddress": "10.4.45.32:50053",
                    "mtibRevision": "REV1.1",
                    "productId": alpha_product.id,  # FK to Product
                    "capabilities": ["button", "peltier", "charger_relay"],
                    "dutProduct": "alpha",
                    "dutRevision": "b0",
                    "dutDeviceId": "70B3D584C01E20A2",
                    "dutSnr": "097D",
                    "uartAppPath": "/dev/verdin-uart2",
                    "uartCommsPath": "/dev/verdin-uart1",
                    "status": "AVAILABLE",
                },
                "update": {
                    "productId": alpha_product.id,
                },
            },
        )
        print(f"Test bench: {bench_32.stationId} -> {bench_32.mtibAddress} (product: {alpha_product.name})")

        # Sigma5 C0 bench (MTIB 34 - IWSCK-A1)
        bench_34 = db.testbench.upsert(
            where={"stationId": "station-34"},
            data={
                "create": {
                    "stationId": "station-34",
                    "name": "Sigma5 C0 Bench (MTIB 34)",
                    "mtibAddress": "10.4.45.34:50053",
                    "mtibRevision": "REV1.2",
                    "productId": sigma5_product.id,  # FK to Product
                    "fixtureDesignId": sigma5_design.id,
                    "capabilities": ["button", "motion"],
                    "dutProduct": "sigma5",
                    "dutRevision": "c0",
                    "uartAppPath": "/dev/verdin-uart2",
                    "uartCommsPath": "/dev/verdin-uart1",
                    "status": "AVAILABLE",
                },
                "update": {
                    "productId": sigma5_product.id,
                    "fixtureDesignId": sigma5_design.id,
                },
            },
        )
        print(f"Test bench: {bench_34.stationId} -> {bench_34.mtibAddress} (product: {sigma5_product.name})")

        # Theta C0 bench (MTIB 35 - placeholder for future deployment)
        bench_35 = db.testbench.upsert(
            where={"stationId": "station-35"},
            data={
                "create": {
                    "stationId": "station-35",
                    "name": "Theta C0 Bench (MTIB 35)",
                    "mtibAddress": "10.4.45.35:50053",
                    "mtibRevision": "REV1.2",
                    "productId": theta_product.id,
                    "fixtureDesignId": theta_design.id,
                    "capabilities": ["button", "motion", "gps"],
                    "dutProduct": "theta",
                    "dutRevision": "c0",
                    "uartAppPath": "/dev/verdin-uart2",
                    "uartCommsPath": "/dev/verdin-uart1",
                    "status": "OFFLINE",  # Placeholder - not deployed yet
                },
                "update": {
                    "productId": theta_product.id,
                    "fixtureDesignId": theta_design.id,
                },
            },
        )
        print(f"Test bench: {bench_35.stationId} -> {bench_35.mtibAddress} (product: {theta_product.name})")

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

    finally:
        db.disconnect()


if __name__ == "__main__":
    seed()
