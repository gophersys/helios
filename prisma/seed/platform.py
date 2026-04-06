"""Platform-level seed data — shared across all products.

Seeds: permission sets, signing keys, CI API key, system user,
team members, dev users, recipe templates.
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone

from database import Json


# ── Permissions ──────────────────────────────────────────────

ALL_PERMISSIONS = [
    "products:view", "products:manage",
    "builds:view", "builds:trigger", "builds:manage",
    "validation:view", "validation:run", "validation:manage",
    "manufacturing:view", "manufacturing:run", "manufacturing:manage",
    "fixtures:view", "fixtures:manage",
    "devices:view", "devices:manage",
    "kubernetes:view", "kubernetes:manage",
    "users:view", "users:manage",
    "permissions:manage",
    "api-keys:view", "api-keys:manage",
    "system:view", "system:manage",
]

ROLE_PERMISSIONS = {
    "Admin": {
        "permissions": ALL_PERMISSIONS,
        "description": "Full platform access — all permissions",
    },
    "Maintainer": {
        "permissions": [p for p in ALL_PERMISSIONS if p not in (
            "users:manage", "permissions:manage", "system:manage", "kubernetes:manage",
        )],
        "description": "Full product access — no user/system management",
    },
    "Developer": {
        "permissions": [
            "products:view", "builds:view", "builds:trigger", "builds:manage",
            "validation:view", "validation:run",
            "manufacturing:view", "fixtures:view", "devices:view",
            "api-keys:view", "api-keys:manage",
        ],
        "description": "Build, test, and monitor products — no admin access",
    },
    "Operator": {
        "permissions": [
            "manufacturing:view", "manufacturing:run", "manufacturing:manage",
        ],
        "description": "Manufacturing operations only",
    },
}

# ── Team ─────────────────────────────────────────────────────

TEAM = [
    {"email": "mateo@corekinect.com", "name": "Mateo Segura", "role": "ADMIN"},
    {"email": "jared@corekinect.com", "name": "Jared Walton", "role": "ADMIN"},
    {"email": "mitchel@corekinect.com", "name": "Mitchel Kelley", "role": "ADMIN"},
    {"email": "chris@corekinect.com", "name": "Chris Burns", "role": "DEVELOPER"},
    {"email": "christian@corekinect.com", "name": "Christian Cortes", "role": "DEVELOPER"},
    {"email": "gwen@corekinect.com", "name": "Gwen Eging", "role": "OPERATOR"},
]

DEV_USERS = [
    {"email": "admin@concord.dev", "name": "Admin User", "role": "ADMIN"},
    {"email": "maintainer@concord.dev", "name": "Maintainer User", "role": "MAINTAINER"},
    {"email": "developer@concord.dev", "name": "Developer User", "role": "DEVELOPER"},
    {"email": "operator@concord.dev", "name": "Operator User", "role": "OPERATOR"},
]

ROLE_ACCESS_LEVEL = {
    "ADMIN": "admin", "MAINTAINER": "admin",
    "DEVELOPER": "develop", "OPERATOR": "operate",
}

# ── Recipe templates ─────────────────────────────────────────

RECIPE_TEMPLATES = [
    {
        "name": "Nordic NCS (dual-processor)",
        "description": "Standard build for nRF52840 + nRF9151 dual-processor boards using NCS/Zephyr.",
        "category": "nordic",
        "sortOrder": 0,
        "content": "#!/bin/bash\nset -euo pipefail\n# Template: Nordic NCS dual-processor\necho 'Configure your build here'\n",
    },
    {
        "name": "Single processor",
        "description": "Build for single-SoC boards (ESP32, STM32, single nRF).",
        "category": "general",
        "sortOrder": 1,
        "content": "#!/bin/bash\nset -euo pipefail\n# Template: single processor\necho 'Configure your build here'\n",
    },
]


def seed_platform(db) -> dict:
    """Seed shared platform data. Returns permission set map."""
    print("=== Platform ===")

    # Permission sets
    perm_sets = {}
    for name, cfg in ROLE_PERMISSIONS.items():
        ps = db.permissionset.upsert(
            where={"name": name},
            data={
                "create": {"name": name, "description": cfg["description"], "permissions": cfg["permissions"]},
                "update": {"description": cfg["description"], "permissions": cfg["permissions"]},
            },
        )
        perm_sets[name.upper()] = ps
        print(f"  ✓ Permission set: {name}")

    # Backfill users without permission set
    orphans = db.user.find_many(where={"permissionSetId": None})
    for u in orphans:
        db.user.update(where={"id": u.id}, data={"permissionSetId": perm_sets["DEVELOPER"].id})

    # Dev admin (available in all envs for seeding)
    db.user.upsert(
        where={"email": "admin@concord.local"},
        data={
            "create": {"email": "admin@concord.local", "name": "Dev Admin", "role": "ADMIN", "permissionSetId": perm_sets["ADMIN"].id},
            "update": {"role": "ADMIN", "permissionSetId": perm_sets["ADMIN"].id},
        },
    )

    # Super admin from env
    admin_email = os.environ.get("SEED_ADMIN_EMAIL", "").strip()
    if admin_email:
        db.user.upsert(
            where={"email": admin_email.lower()},
            data={
                "create": {"email": admin_email.lower(), "name": os.environ.get("SEED_ADMIN_NAME", "Admin"), "role": "ADMIN", "permissionSetId": perm_sets["ADMIN"].id},
                "update": {"role": "ADMIN", "permissionSetId": perm_sets["ADMIN"].id},
            },
        )
        print(f"  ✓ Super admin: {admin_email}")

    # System user + CI API key
    system_user = db.user.upsert(
        where={"email": "system@concord.local"},
        data={
            "create": {"email": "system@concord.local", "name": "System", "permissionSetId": perm_sets["ADMIN"].id},
            "update": {"permissionSetId": perm_sets["ADMIN"].id},
        },
    )

    ci_key = "ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG"
    ci_key_hash = hashlib.sha256(ci_key.encode()).hexdigest()
    existing = db.apikey.find_first(where={"keyHash": ci_key_hash})
    if existing:
        db.apikey.update(where={"id": existing.id}, data={"expiresAt": datetime.now(timezone.utc) + timedelta(days=365)})
    else:
        db.apikey.create(data={
            "name": "CI Admin Key", "keyHash": ci_key_hash, "keyPrefix": ci_key[:12],
            "userId": system_user.id, "expiresAt": datetime.now(timezone.utc) + timedelta(days=365),
        })
    print(f"  ✓ CI API key: {ci_key[:16]}...")

    # Signing keys
    for key_name, key_type in [("Bench Signing Key", "signing_key"), ("Engineering Signing Key", "signing_key"), ("Production Signing Key", "signing_key")]:
        existing = db.secret.find_first(where={"name": key_name})
        if not existing:
            db.secret.create(data={"name": key_name, "type": key_type, "value": "", "description": f"Base64-encoded PEM for {key_name.lower()}", "createdById": system_user.id})
    print("  ✓ Signing keys")

    # Recipe templates
    for tmpl in RECIPE_TEMPLATES:
        db.recipetemplate.upsert(
            where={"name": tmpl["name"]},
            data={"create": tmpl, "update": {"content": tmpl["content"], "description": tmpl["description"]}},
        )
    print(f"  ✓ Recipe templates: {len(RECIPE_TEMPLATES)}")

    return perm_sets


def seed_users(db, perm_sets: dict, products: list):
    """Seed team members and dev users with product access."""
    print("\n=== Users ===")

    all_users = TEAM + DEV_USERS
    is_dev = os.environ.get("ENVIRONMENT", "development") == "development"

    for u in all_users:
        if not is_dev and u in DEV_USERS:
            continue

        ps = perm_sets.get(u["role"])
        if not ps:
            continue

        user = db.user.upsert(
            where={"email": u["email"]},
            data={
                "create": {"email": u["email"], "name": u["name"], "role": u["role"], "permissionSetId": ps.id},
                "update": {"name": u["name"], "role": u["role"], "permissionSetId": ps.id},
            },
        )

        # Grant access to all products
        level = ROLE_ACCESS_LEVEL.get(u["role"], "view")
        for product in products:
            db.productaccess.upsert(
                where={"userId_productId": {"userId": user.id, "productId": product.id}},
                data={
                    "create": {"userId": user.id, "productId": product.id, "level": level},
                    "update": {"level": level},
                },
            )

    print(f"  ✓ {len(all_users)} users seeded")
    print(f"  ✓ Product access granted to {len(products)} product(s)")
