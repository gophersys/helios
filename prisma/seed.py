"""Seed the database with the initial admin user.

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


def seed():
    email = os.environ.get("SEED_ADMIN_EMAIL", "").strip()
    name = os.environ.get("SEED_ADMIN_NAME", "Admin").strip()

    if not email:
        print("SEED_ADMIN_EMAIL not set. Skipping seed.")
        print("Usage: SEED_ADMIN_EMAIL=you@company.com python3 seed.py")
        return

    db = Prisma()
    db.connect()

    try:
        # Check if any admin already exists
        existing = db.user.find_first(where={"role": "ADMIN"})
        if existing:
            print(f"Admin user already exists: {existing.email}")
            return

        user = db.user.create(
            data={
                "email": email.lower(),
                "name": name,
                "role": "ADMIN",
                "active": True,
            }
        )
        print(f"Created admin user: {user.email} (id: {user.id})")
    finally:
        db.disconnect()


if __name__ == "__main__":
    seed()
