"""Validation test catalog API.

Serves the test catalog (catalog.yaml) for each product. The catalog is the
source of truth for test definitions and is used by both the test runner
and the frontend.

The sync endpoint creates/updates ValidationDesign records from the YAML catalog,
enabling the UI and CI pipeline to reference validated test definitions.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml
from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_auth, require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

# Base path for validation apps (relative to repo root)
VALIDATION_APPS_PATH = Path("/workspaces/concord/apps/validation")


def _load_catalog(product: str) -> dict | None:
    """Load catalog.yaml for a product."""
    catalog_path = VALIDATION_APPS_PATH / product / "catalog.yaml"
    if not catalog_path.exists():
        return None

    with open(catalog_path) as f:
        return yaml.safe_load(f)


def _serialize_catalog(catalog: dict) -> dict:
    """Serialize catalog for API response."""
    return {
        "version": catalog.get("version", "0.0.0"),
        "product": catalog.get("product"),
        "board": catalog.get("board"),
        "stages": catalog.get("stages", {}),
        "hardware": catalog.get("hardware", {}),
        "tests": catalog.get("tests", []),
        "testCount": len(catalog.get("tests", [])),
        "stageCount": len(catalog.get("stages", {})),
    }


def _get_stage_summary(catalog: dict) -> list:
    """Get summary of stages with test counts."""
    stages = catalog.get("stages", {})
    tests = catalog.get("tests", [])

    summaries = []
    for stage_id, stage_def in stages.items():
        stage_tests = [t for t in tests if t.get("stage") == stage_id]
        total_timeout = sum(t.get("timeout_s", 0) for t in stage_tests)

        summaries.append({
            "id": stage_id,
            "name": stage_def.get("name", stage_id),
            "description": stage_def.get("description"),
            "timingBudgetS": stage_def.get("timing_budget_s"),
            "trigger": stage_def.get("trigger"),
            "blocksMerge": stage_def.get("blocks_merge", False),
            "testCount": len(stage_tests),
            "totalTimeoutS": total_timeout,
            "directory": stage_def.get("directory"),
        })

    return summaries


@require_auth
def list_catalogs():
    """GET /v2/validation/catalog — List available test catalogs."""
    catalogs = []

    if VALIDATION_APPS_PATH.exists():
        for product_dir in VALIDATION_APPS_PATH.iterdir():
            if product_dir.is_dir():
                catalog_path = product_dir / "catalog.yaml"
                if catalog_path.exists():
                    catalog = _load_catalog(product_dir.name)
                    if catalog:
                        catalogs.append({
                            "product": product_dir.name,
                            "version": catalog.get("version", "0.0.0"),
                            "board": catalog.get("board"),
                            "testCount": len(catalog.get("tests", [])),
                            "stageCount": len(catalog.get("stages", {})),
                        })

    return jsonify(ApiResponse.ok(catalogs).to_dict()), 200


@require_auth
def get_catalog(product: str):
    """GET /v2/validation/catalog/<product> — Get test catalog for a product."""
    catalog = _load_catalog(product)
    if not catalog:
        return not_found(f"No catalog found for product '{product}'")

    return jsonify(ApiResponse.ok(_serialize_catalog(catalog)).to_dict()), 200


@require_auth
def get_catalog_stages(product: str):
    """GET /v2/validation/catalog/<product>/stages — Get stage summary."""
    catalog = _load_catalog(product)
    if not catalog:
        return not_found(f"No catalog found for product '{product}'")

    return jsonify(ApiResponse.ok(_get_stage_summary(catalog)).to_dict()), 200


@require_auth
def get_catalog_tests(product: str):
    """GET /v2/validation/catalog/<product>/tests — Get tests with filtering."""
    catalog = _load_catalog(product)
    if not catalog:
        return not_found(f"No catalog found for product '{product}'")

    tests = catalog.get("tests", [])

    # Filter by stage
    stage = request.args.get("stage")
    if stage:
        tests = [t for t in tests if t.get("stage") == stage]

    # Filter by category
    category = request.args.get("category")
    if category:
        tests = [t for t in tests if t.get("category") == category]

    # Filter by hardware requirement
    hardware = request.args.get("hardware")
    if hardware:
        tests = [t for t in tests if hardware in t.get("hardware", [])]

    return jsonify(ApiResponse.ok(tests).to_dict()), 200


@require_auth
def get_catalog_test(product: str, test_id: str):
    """GET /v2/validation/catalog/<product>/tests/<test_id> — Get single test."""
    catalog = _load_catalog(product)
    if not catalog:
        return not_found(f"No catalog found for product '{product}'")

    tests = catalog.get("tests", [])
    test = next((t for t in tests if t.get("id") == test_id), None)

    if not test:
        return not_found(f"Test '{test_id}' not found in catalog")

    # Enrich with stage info
    stages = catalog.get("stages", {})
    stage_id = test.get("stage")
    if stage_id and stage_id in stages:
        test["stageInfo"] = {
            "id": stage_id,
            **stages[stage_id],
        }

    return jsonify(ApiResponse.ok(test).to_dict()), 200


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Catalog Sync — create/update ValidationDesign records from YAML
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _build_validation_design_nodes(catalog: Dict[str, Any], stage_id: str) -> List[Dict[str, Any]]:
    """Build flow graph nodes from catalog tests for a specific stage.

    Each test becomes a TEST node in the validation flow graph.
    Position is calculated based on test order within the stage.
    """
    tests = [t for t in catalog.get("tests", []) if t.get("stage") == stage_id]
    nodes = []

    # Grid layout: 3 columns, rows based on test count
    col_width = 300
    row_height = 120
    start_x = 100
    start_y = 100

    for idx, test in enumerate(tests):
        col = idx % 3
        row = idx // 3

        nodes.append({
            "id": test.get("id", f"test_{idx}"),
            "type": "TEST",
            "label": test.get("name", f"Test {idx + 1}"),
            "data": {
                "testId": test.get("id"),
                "testName": test.get("name"),
                "description": test.get("description"),
                "timeout_s": test.get("timeout_s", 60),
                "hardware": test.get("hardware", []),
                "category": test.get("category"),
            },
            "position": {
                "x": start_x + col * col_width,
                "y": start_y + row * row_height,
            },
        })

    return nodes


def _build_validation_design_edges(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build edges connecting nodes in sequence."""
    edges = []
    for i in range(len(nodes) - 1):
        edges.append({
            "id": f"edge_{i}",
            "source": nodes[i]["id"],
            "target": nodes[i + 1]["id"],
        })
    return edges


def _create_slug(product: str, board: str, stage_id: str) -> str:
    """Create URL-safe slug for validation design."""
    return f"{product}-{board}-{stage_id}".lower().replace("_", "-")


@require_permissions(Permissions.VALIDATION_MANAGE)
def sync_catalog(product: str):
    """POST /v2/validation/catalog/<product>/sync — Sync catalog to ValidationDesign records.

    Reads catalog.yaml for the product and creates/updates ValidationDesign records
    for each stage defined in the catalog. This allows:
    - UI to display available validation designs
    - CI pipeline to reference designs when triggering runs
    - Test runner to get design details

    Each stage (gate, nightly, integration) becomes a separate ValidationDesign.
    Tests within each stage become nodes in the design's flow graph.

    Request body (optional):
        {
            "stages": ["gate", "nightly"]  // Optional: sync only specific stages
        }

    Response:
        {
            "synced": [
                {"id": "...", "slug": "alpha-alpha_b0-gate", "stage": "gate", "action": "created"},
                {"id": "...", "slug": "alpha-alpha_b0-nightly", "stage": "nightly", "action": "updated"}
            ],
            "catalogVersion": "1.0.0",
            "totalTests": 32
        }
    """
    catalog = _load_catalog(product)
    if not catalog:
        return not_found(f"No catalog found for product '{product}'")

    db = get_db_client()
    body = request.get_json() or {}
    filter_stages = body.get("stages")  # Optional: only sync specific stages

    catalog_version = catalog.get("version", "0.0.0")
    board = catalog.get("board", f"{product}_b0")
    stages = catalog.get("stages", {})
    all_tests = catalog.get("tests", [])
    hardware = catalog.get("hardware", {})

    synced = []

    try:
        for stage_id, stage_def in stages.items():
            # Skip if filtering and stage not in filter
            if filter_stages and stage_id not in filter_stages:
                continue

            slug = _create_slug(product, board, stage_id)
            name = f"{product.title()} {board.upper()} {stage_def.get('name', stage_id.title())}"

            # Build nodes from tests in this stage
            nodes = _build_validation_design_nodes(catalog, stage_id)
            edges = _build_validation_design_edges(nodes)

            # Stage tests
            stage_tests = [t for t in all_tests if t.get("stage") == stage_id]

            design_data = {
                "name": name,
                "slug": slug,
                "product": product,
                "board": board,
                "description": stage_def.get("description"),
                "nodes": Json(nodes),
                "edges": Json(edges),
                "isDefault": stage_id == "gate",  # Gate is default for PR validation
            }

            # Try to find existing design
            existing = db.validationdesign.find_first(where={"slug": slug})

            if existing:
                # Update existing
                db.validationdesign.update(
                    where={"id": existing.id},
                    data=design_data,
                )
                synced.append({
                    "id": existing.id,
                    "slug": slug,
                    "stage": stage_id,
                    "action": "updated",
                    "testCount": len(stage_tests),
                })
            else:
                # Create new
                design = db.validationdesign.create(data=design_data)
                synced.append({
                    "id": design.id,
                    "slug": slug,
                    "stage": stage_id,
                    "action": "created",
                    "testCount": len(stage_tests),
                })

        log_audit("validation.catalog.sync", "ValidationDesign", None, {
            "product": product,
            "catalogVersion": catalog_version,
            "stagesSynced": [s["stage"] for s in synced],
        })

        return jsonify(ApiResponse.ok({
            "synced": synced,
            "catalogVersion": catalog_version,
            "totalTests": len(all_tests),
            "hardware": hardware,
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to sync catalog for %s: %s", product, e)
        return internal_error("Failed to sync catalog")


@require_permissions(Permissions.VALIDATION_VIEW)
def get_catalog_sync_status(product: str):
    """GET /v2/validation/catalog/<product>/sync — Get sync status for a product.

    Returns the current ValidationDesign records for the product and whether
    they match the catalog.yaml version.

    Response:
        {
            "product": "alpha",
            "catalogVersion": "1.0.0",
            "designs": [
                {"id": "...", "slug": "alpha-alpha_b0-gate", "stage": "gate", "testCount": 10, "synced": true},
                {"id": "...", "slug": "alpha-alpha_b0-nightly", "stage": "nightly", "testCount": 22, "synced": false}
            ],
            "syncRequired": true
        }
    """
    catalog = _load_catalog(product)
    if not catalog:
        return not_found(f"No catalog found for product '{product}'")

    db = get_db_client()
    catalog_version = catalog.get("version", "0.0.0")
    board = catalog.get("board", f"{product}_b0")
    stages = catalog.get("stages", {})
    all_tests = catalog.get("tests", [])

    designs = []
    sync_required = False

    try:
        for stage_id, stage_def in stages.items():
            slug = _create_slug(product, board, stage_id)
            stage_tests = [t for t in all_tests if t.get("stage") == stage_id]
            catalog_test_count = len(stage_tests)

            existing = db.validationdesign.find_first(where={"slug": slug})

            if existing:
                # Check if node count matches test count (rough sync check)
                existing_nodes = existing.nodes if existing.nodes else []
                existing_test_count = len(existing_nodes)
                is_synced = existing_test_count == catalog_test_count

                designs.append({
                    "id": existing.id,
                    "slug": slug,
                    "name": existing.name,
                    "stage": stage_id,
                    "catalogTestCount": catalog_test_count,
                    "designTestCount": existing_test_count,
                    "synced": is_synced,
                    "updatedAt": existing.updatedAt.isoformat(),
                })

                if not is_synced:
                    sync_required = True
            else:
                # Design doesn't exist yet
                designs.append({
                    "id": None,
                    "slug": slug,
                    "name": f"{product.title()} {board.upper()} {stage_def.get('name', stage_id.title())}",
                    "stage": stage_id,
                    "catalogTestCount": catalog_test_count,
                    "designTestCount": 0,
                    "synced": False,
                    "updatedAt": None,
                })
                sync_required = True

        return jsonify(ApiResponse.ok({
            "product": product,
            "board": board,
            "catalogVersion": catalog_version,
            "designs": designs,
            "syncRequired": sync_required,
            "totalCatalogTests": len(all_tests),
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to get sync status for %s: %s", product, e)
        return internal_error("Failed to get sync status")
