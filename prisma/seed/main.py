"""Concord database seed — populates a complete development environment.

Usage:
    python3 -m seed.main
    SEED_ADMIN_EMAIL=you@company.com python3 -m seed.main

Structure:
    seed/
    ├── main.py          ← this file (entry point + orchestrator)
    ├── platform.py      ← permissions, signing keys, API keys, users (shared)
    └── products/
        └── alpha/
            ├── __init__.py      ← product + board + revisions + targets
            ├── validation.py    ← val fixture designs, fixtures, stage configs
            └── manufacturing.py ← mfg fixture designs, fixtures, stage configs

Adding a new product: copy products/alpha/ → products/yourproduct/, edit the data.
"""

import os
import sys

# Add libs to path so we can import the Prisma client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "libs", "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "libs"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "libs", "protocols"))

from database import Prisma


def seed():
    db = Prisma()
    db.connect()

    try:
        # ── 1. Platform (shared across all products) ──
        from seed.platform import seed_platform
        perm_sets = seed_platform(db)

        # ── 2. Products (each product module is self-contained) ──
        from seed.products.alpha import seed_product
        alpha = seed_product(db)

        # ── 3. Product-specific validation + manufacturing ──
        from seed.products.alpha.validation import seed_validation
        seed_validation(db, alpha["product"], alpha["b0_rev"])

        from seed.products.alpha.manufacturing import seed_manufacturing
        seed_manufacturing(db, alpha["product"], alpha["b0_rev"])

        # ── 4. Users + product access (depends on products existing) ──
        from seed.platform import seed_users
        seed_users(db, perm_sets, products=[alpha["product"]])

        print("\n✓ Seed complete")

    finally:
        db.disconnect()


if __name__ == "__main__":
    seed()
