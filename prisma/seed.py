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

from database import Prisma

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

    finally:
        db.disconnect()


if __name__ == "__main__":
    seed()
