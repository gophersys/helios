"""Alpha product seed — product definition, board, revisions, targets.

Alpha is a wearable IoT device with:
- Board family: alpha (ck_boards repo)
- Revisions: A0 (nRF9160+nRF52840), B0 (nRF9151+nRF52840, current production)
- Two firmware repos: alpha_fw (production), alpha_mfg_fw (manufacturing)
"""

from database import Json


def seed_product(db) -> dict:
    """Seed the Alpha product. Returns dict with product + revision refs."""
    print("\n=== Product: Alpha ===")

    metadata = {
        "device_type": 2,
        "device_variant": 3,
        "app_ids": {"nrf52840": 109, "nrf9151": 108},
        "corecloud_env": "VAL_1_0",
    }

    build_config = {
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

    product = db.product.upsert(
        where={"name": "Alpha"},
        data={
            "create": {
                "name": "Alpha", "slug": "alpha",
                "description": "Alpha wearable device platform",
                "fwRepoSlug": "alpha_fw", "mfgFwRepoSlug": "alpha_mfg_fw",
                "active": True,
                "buildConfig": Json(build_config), "metadata": Json(metadata),
            },
            "update": {
                "slug": "alpha", "fwRepoSlug": "alpha_fw", "mfgFwRepoSlug": "alpha_mfg_fw",
                "buildConfig": Json(build_config), "metadata": Json(metadata),
            },
        },
    )
    print(f"  ✓ Product: {product.name}")

    # Board
    board = db.board.upsert(
        where={"productId": product.id},
        data={
            "create": {
                "productId": product.id, "name": "Main Board",
                "ckBoardsFamily": "alpha", "vendor": "corekinect",
                "description": "Alpha main board with nRF52840 + nRF9151",
            },
            "update": {"ckBoardsFamily": "alpha"},
        },
    )

    # A0 revision (legacy)
    a0_rev = db.boardrevision.upsert(
        where={"boardId_version": {"boardId": board.id, "version": "A0"}},
        data={
            "create": {
                "boardId": board.id, "version": "A0", "ckBoardsName": "alpha_a0",
                "socs": ["nrf9160", "nrf52840"],
                "deviceType": 2, "deviceVariant": 1,
                "notes": "Alpha A0 — initial board (nRF9160 + nRF52840)",
                "status": "ACTIVE",
            },
            "update": {"ckBoardsName": "alpha_a0", "socs": ["nrf9160", "nrf52840"], "deviceType": 2, "deviceVariant": 1, "status": "ACTIVE"},
        },
    )
    for t in [{"role": "comms", "soc": "nRF9160", "appId": 102}, {"role": "app", "soc": "nRF52840", "appId": 103}]:
        db.producttarget.upsert(
            where={"boardRevisionId_role": {"boardRevisionId": a0_rev.id, "role": t["role"]}},
            data={"create": {"boardRevisionId": a0_rev.id, **t}, "update": {"soc": t["soc"], "appId": t["appId"]}},
        )

    # B0 revision (current production)
    b0_rev = db.boardrevision.upsert(
        where={"boardId_version": {"boardId": board.id, "version": "B0"}},
        data={
            "create": {
                "boardId": board.id, "version": "B0", "ckBoardsName": "alpha_b0",
                "socs": ["nrf9151", "nrf52840"],
                "deviceType": 2, "deviceVariant": 3,
                "modemVersion": "2.0.2",
                "notes": "Alpha B0 — current production (nRF52840 + nRF9151)",
            },
            "update": {
                "ckBoardsName": "alpha_b0", "socs": ["nrf9151", "nrf52840"],
                "deviceType": 2, "deviceVariant": 3, "modemVersion": "2.0.2",
                "status": "ACTIVE",
            },
        },
    )
    for t in [{"role": "comms", "soc": "nRF9151", "appId": 108}, {"role": "app", "soc": "nRF52840", "appId": 109}]:
        db.producttarget.upsert(
            where={"boardRevisionId_role": {"boardRevisionId": b0_rev.id, "role": t["role"]}},
            data={"create": {"boardRevisionId": b0_rev.id, **t}, "update": {"soc": t["soc"], "appId": t["appId"]}},
        )
    print(f"  ✓ Board: {board.name} (A0, B0)")

    return {"product": product, "board": board, "a0_rev": a0_rev, "b0_rev": b0_rev}
