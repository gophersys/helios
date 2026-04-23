"""Board discovery endpoints — list branches, scan boards, board detail.

Powers the product creation wizard by exposing ck_boards repo data.
Uses Bitbucket REST API (HTTPS) — no SSH or git required.
"""

import logging

import requests
from flask import jsonify, request
from requests.auth import HTTPBasicAuth

from config.env import env_config
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.ck_boards.service import CkBoardsService

logger = logging.getLogger(__name__)

_ck_boards_service = None

_API_BASE = "https://api.bitbucket.org/2.0"


def init_ck_boards_service(config) -> None:
    """Initialize the ck_boards service from AppConfig (called at app startup)."""
    global _ck_boards_service

    # Extract workspace from the repo URL: git@bitbucket.org:corekinect/ck_boards.git → corekinect
    repo_url = config.CK_BOARDS_REPO_URL
    workspace = config.BITBUCKET_WORKSPACE
    # Extract repo slug from URL
    repo_slug = "ck_boards"
    if "/" in repo_url:
        repo_slug = repo_url.split("/")[-1].replace(".git", "")

    try:
        _ck_boards_service = CkBoardsService(
            workspace=workspace,
            repo_slug=repo_slug,
            email=config.BITBUCKET_EMAIL,
            api_token=config.BITBUCKET_API_TOKEN,
            fetch_interval=config.CK_BOARDS_FETCH_INTERVAL,
            environment=config.ENVIRONMENT,
        )
    except RuntimeError as e:
        logging.getLogger(__name__).warning("CkBoards disabled: %s", e)


def get_ck_boards_service():
    """Return the global CkBoardsService instance (or None if not initialized)."""
    return _ck_boards_service


@require_permissions(Permissions.PRODUCTS_VIEW)
def list_board_branches():
    """GET /v2/products/boards/branches"""
    svc = get_ck_boards_service()
    if svc is None or not svc.is_ready:
        return internal_error("Board discovery service not configured")
    try:
        refs = svc.list_refs()
        return jsonify(ApiResponse.ok(refs).to_dict()), 200
    except Exception:
        logger.exception("Failed to list ck_boards branches")
        return internal_error("Failed to list branches")


@require_permissions(Permissions.PRODUCTS_VIEW)
def discover_boards():
    """GET /v2/products/boards/discover?branch=main"""
    branch = request.args.get("branch")
    if not branch:
        return bad_request("branch query parameter is required")

    svc = get_ck_boards_service()
    if svc is None or not svc.is_ready:
        return internal_error("Board discovery service not configured")
    try:
        boards = svc.discover_boards(branch)
        return jsonify(ApiResponse.ok(boards).to_dict()), 200
    except ValueError as e:
        logger.warning("Board discovery validation error on branch %s: %s", branch, e)
        return bad_request("Invalid branch or board configuration")
    except Exception:
        logger.exception("Failed to discover boards on branch %s", branch)
        return internal_error("Failed to discover boards")


@require_permissions(Permissions.PRODUCTS_VIEW)
def discover_board_detail(board_name: str):
    """GET /v2/products/boards/discover/<board>?branch=main"""
    branch = request.args.get("branch")
    if not branch:
        return bad_request("branch query parameter is required")

    svc = get_ck_boards_service()
    if svc is None or not svc.is_ready:
        return internal_error("Board discovery service not configured")
    try:
        detail = svc.discover_board_detail(board_name, branch)
        return jsonify(ApiResponse.ok(detail).to_dict()), 200
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            return not_found(f"Board '{board_name}' not found on branch '{branch}'")
        return bad_request("Invalid board or branch configuration")
    except Exception:
        logger.exception("Failed to get detail for board %s on %s", board_name, branch)
        return internal_error("Failed to get board detail")


@require_permissions(Permissions.PRODUCTS_VIEW)
def check_repo():
    """GET /v2/products/repos/check?slug=alpha_fw — verify Bitbucket repo exists."""
    slug = request.args.get("slug", "").strip()
    if not slug:
        return bad_request("slug query parameter is required")

    result = {"exists": False, "slug": slug}
    try:
        resp = requests.get(
            f"{_API_BASE}/repositories/{env_config.BITBUCKET_WORKSPACE}/{slug}",
            auth=HTTPBasicAuth(env_config.BITBUCKET_EMAIL, env_config.BITBUCKET_API_TOKEN),
            timeout=10,
        )
        result["exists"] = resp.status_code == 200
    except Exception as e:
        logger.debug("Failed to check repo %s: %s", slug, e)

    return jsonify(ApiResponse.ok(result).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_VIEW)
def list_repo_branches():
    """GET /v2/products/repos/branches?slug=alpha_fw — list branches for a Bitbucket repo."""
    slug = request.args.get("slug", "").strip()
    if not slug:
        return bad_request("slug query parameter is required")

    branches = []
    try:
        url = f"{_API_BASE}/repositories/{env_config.BITBUCKET_WORKSPACE}/{slug}/refs/branches"
        while url:
            resp = requests.get(
                url,
                auth=HTTPBasicAuth(env_config.BITBUCKET_EMAIL, env_config.BITBUCKET_API_TOKEN),
                timeout=15,
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            branches.extend(b["name"] for b in data.get("values", []))
            url = data.get("next")
    except Exception as e:
        logger.debug("Failed to list branches for repo %s: %s", slug, e)

    return jsonify(ApiResponse.ok({"slug": slug, "branches": sorted(branches)}).to_dict()), 200
