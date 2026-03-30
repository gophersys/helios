"""Board discovery endpoints — list branches, scan boards, board detail.

Powers the product creation wizard by exposing ck_boards repo data.
"""

import logging
from typing import Optional

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse

logger = logging.getLogger(__name__)

_ck_boards_service = None


def init_ck_boards_service(bare_repo_path: str, worktree_base_path: str):
    """Initialize the ck_boards service singleton (called at app startup)."""
    global _ck_boards_service
    from src.services.ck_boards.service import CkBoardsService
    _ck_boards_service = CkBoardsService(bare_repo_path, worktree_base_path)


def get_ck_boards_service():
    """Get the ck_boards service singleton."""
    return _ck_boards_service


@require_permissions(Permissions.PRODUCTS_VIEW)
def list_board_branches():
    """GET /v2/products/boards/branches — list branches and tags."""
    svc = get_ck_boards_service()
    if svc is None:
        return internal_error("Board discovery service not configured")
    try:
        refs = svc.list_refs()
        return jsonify(ApiResponse.ok(refs).to_dict()), 200
    except Exception as e:
        logger.exception("Failed to list ck_boards branches")
        return internal_error("Failed to list branches")


@require_permissions(Permissions.PRODUCTS_VIEW)
def discover_boards():
    """GET /v2/products/boards/discover?branch=main — scan all boards."""
    branch = request.args.get("branch")
    if not branch:
        return bad_request("branch query parameter is required")

    svc = get_ck_boards_service()
    if svc is None:
        return internal_error("Board discovery service not configured")
    try:
        boards = svc.discover_boards(branch)
        return jsonify(ApiResponse.ok(boards).to_dict()), 200
    except ValueError as e:
        logger.warning("Board discovery validation error on branch %s: %s", branch, e)
        return bad_request("Invalid branch or board configuration")
    except Exception as e:
        logger.exception("Failed to discover boards on branch %s", branch)
        return internal_error("Failed to discover boards")


@require_permissions(Permissions.PRODUCTS_VIEW)
def discover_board_detail(board_name: str):
    """GET /v2/products/boards/discover/<board>?branch=main — deep scan."""
    branch = request.args.get("branch")
    if not branch:
        return bad_request("branch query parameter is required")

    svc = get_ck_boards_service()
    if svc is None:
        return internal_error("Board discovery service not configured")
    try:
        detail = svc.discover_board_detail(board_name, branch)
        return jsonify(ApiResponse.ok(detail).to_dict()), 200
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            logger.warning("Board not found: %s on branch %s: %s", board_name, branch, e)
            return not_found(f"Board '{board_name}' not found on branch '{branch}'")
        logger.warning("Board detail validation error for %s on %s: %s", board_name, branch, e)
        return bad_request("Invalid board or branch configuration")
    except Exception as e:
        logger.exception("Failed to get detail for board %s on %s", board_name, branch)
        return internal_error("Failed to get board detail")
