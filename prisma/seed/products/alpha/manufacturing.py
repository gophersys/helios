"""Alpha B0 manufacturing seed — fixture designs, fixtures, and stage config.

Manufacturing fixtures have 4-6 MTIBs per fixture (multi-DUT parallel testing).
Single manufacturing stage with type=MANUFACTURING.
"""

from database import Json


# ── Fixture profile template ─────────────────────────────────

ALPHA_B0_MFG_PROFILE = {
    "station_id": None,
    "product": "alpha",
    "board": "alpha_b0",
    "mtib_revision": "1.2",
    "capabilities": ["power", "button", "jlink"],
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
    "peltier": None,
    "charger_relay": None,
    "ppg_simulator": None,
}

MFG_SLOT_DEFS = [
    {"index": 0, "label": "Slot 1"},
    {"index": 1, "label": "Slot 2"},
    {"index": 2, "label": "Slot 3"},
    {"index": 3, "label": "Slot 4"},
]

MFG_FIXTURES = [
    {"stationId": "mfg-fixture-01", "name": "Alpha MFG Fixture 1", "slotCount": 4},
]


def seed_manufacturing(db, product, b0_rev):
    """Seed manufacturing fixture design, fixtures, and stage config for Alpha B0."""
    print("\n=== Alpha B0: Manufacturing ===")

    # ── Fixture design ──
    design = db.fixturedesign.upsert(
        where={"name": "alpha-mfg-fixture-v1.0"},
        data={
            "create": {
                "name": "alpha-mfg-fixture-v1.0",
                "boardRevisionId": b0_rev.id,
                "revision": "1.0",
                "capabilities": ["power", "button", "jlink"],
                "profileTemplate": Json(ALPHA_B0_MFG_PROFILE),
                "notes": "Alpha B0 manufacturing fixture. 4-slot parallel testing panel.",
            },
            "update": {
                "profileTemplate": Json(ALPHA_B0_MFG_PROFILE),
                "capabilities": ["power", "button", "jlink"],
            },
        },
    )
    print(f"  ✓ Design: {design.name}")

    # ── Fixtures ──
    for fx in MFG_FIXTURES:
        fixture = db.fixture.upsert(
            where={"stationId": fx["stationId"]},
            data={
                "create": {
                    "name": fx["name"],
                    "stationId": fx["stationId"],
                    "productId": product.id,
                    "boardRevisionId": b0_rev.id,
                    "type": "MANUFACTURING",
                    "designId": design.id,
                },
                "update": {
                    "name": fx["name"],
                    "designId": design.id,
                    "boardRevisionId": b0_rev.id,
                },
            },
        )

        for i in range(fx["slotCount"]):
            db.fixtureslot.upsert(
                where={"fixtureId_slotIndex": {"fixtureId": fixture.id, "slotIndex": i}},
                data={
                    "create": {
                        "fixtureId": fixture.id,
                        "slotIndex": i,
                        "label": f"Slot {i + 1}",
                    },
                    "update": {"label": f"Slot {i + 1}"},
                },
            )
        print(f"  ✓ Fixture: {fx['name']} ({fx['slotCount']} slots)")

    # ── Manufacturing stage config (single stage, type=MANUFACTURING) ──
    # Use the new StageType-aware unique constraint
    db.productstageconfig.upsert(
        where={"productId_type_stage_boardRevisionId": {
            "productId": product.id,
            "type": "MANUFACTURING",
            "stage": 1,
            "boardRevisionId": b0_rev.id,
        }},
        data={
            "create": {
                "productId": product.id,
                "boardRevisionId": b0_rev.id,
                "type": "MANUFACTURING",
                "stage": 1,
                "name": "Manufacturing",
                "enabled": True,
                "triggerTypes": ["manual"],
            },
            "update": {
                "name": "Manufacturing",
                "enabled": True,
                "triggerTypes": ["manual"],
            },
        },
    )
    print("  ✓ Manufacturing stage config")
