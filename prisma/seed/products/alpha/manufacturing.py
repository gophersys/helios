"""Alpha B0 manufacturing seed — fixture designs, fixtures, and stage configs.

Manufacturing fixtures have 4-6 MTIBs per fixture (multi-DUT parallel testing).
3 manufacturing stages: Electrical, Flash, POST.
"""

from database import Json


# ── Fixture profile template ─────────────────────────────────
# Manufacturing profile is similar to validation but optimized for throughput.
# All DUT positions share the same hardware config.

ALPHA_B0_MFG_PROFILE = {
    "station_id": None,
    "product": "alpha",
    "board": "alpha_b0",
    "mtib_revision": "1.2",
    "capabilities": ["button", "jlink"],
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

# ── Manufacturing stages ─────────────────────────────────────
# Manufacturing uses different stages than validation.
# Each maps to a test suite in apps/manufacturing/alpha/.

MFG_STAGES = [
    {"stage": 1, "name": "Electrical", "enabled": True, "triggerTypes": ["manual"]},
    {"stage": 2, "name": "Flash", "enabled": True, "triggerTypes": ["manual"]},
    {"stage": 3, "name": "POST", "enabled": True, "triggerTypes": ["manual"]},
]

# ── Fixture instances ────────────────────────────────────────
# Manufacturing fixtures have multiple slots (one MTIB per DUT position).
# Initially no nodes assigned — operators assign them in the UI.

MFG_FIXTURES = [
    {"stationId": "mfg-fixture-01", "name": "Alpha MFG Fixture 1", "slotCount": 4},
]


def seed_manufacturing(db, product, b0_rev):
    """Seed manufacturing fixture design, fixtures, and stage configs for Alpha B0."""
    print("\n=== Alpha B0: Manufacturing ===")

    # ── Fixture design ──
    design = db.fixturedesign.upsert(
        where={"name": "alpha-mfg-fixture-v1.0"},
        data={
            "create": {
                "name": "alpha-mfg-fixture-v1.0",
                "boardRevisionId": b0_rev.id,
                "revision": "1.0",
                "capabilities": ["button", "jlink"],
                "profileTemplate": Json(ALPHA_B0_MFG_PROFILE),
                "notes": "Alpha B0 manufacturing fixture. 4-slot parallel testing panel.",
            },
            "update": {
                "profileTemplate": Json(ALPHA_B0_MFG_PROFILE),
                "capabilities": ["button", "jlink"],
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

        # Create empty slots (nodes assigned later by operators)
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

    # ── Stage configs ──
    # Manufacturing stages are product-level, not per-revision
    # (same tests run regardless of board rev)
    for sd in MFG_STAGES:
        db.productstageconfig.upsert(
            where={"productId_stage_boardRevisionId": {
                "productId": product.id,
                "stage": sd["stage"] + 100,  # Offset to avoid collision with validation stages
                "boardRevisionId": b0_rev.id,
            }},
            data={
                "create": {
                    "productId": product.id,
                    "boardRevisionId": b0_rev.id,
                    "stage": sd["stage"] + 100,  # 101=Electrical, 102=Flash, 103=POST
                    "name": sd["name"],
                    "enabled": sd["enabled"],
                    "triggerTypes": sd["triggerTypes"],
                },
                "update": {
                    "name": sd["name"],
                    "enabled": sd["enabled"],
                    "triggerTypes": sd["triggerTypes"],
                },
            },
        )
    print(f"  ✓ {len(MFG_STAGES)} manufacturing stages")
