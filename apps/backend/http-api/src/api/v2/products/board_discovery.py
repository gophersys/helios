"""Board discovery endpoints — list branches, scan boards, board detail.

Powers the product creation wizard by exposing ck_boards repo data.
"""

import logging

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse

logger = logging.getLogger(__name__)

_ck_boards_service = None


def init_ck_boards_service(config) -> None:
    """Initialize the ck_boards service from AppConfig (called at app startup)."""
    global _ck_boards_service
    from src.services.ck_boards.service import CkBoardsService
    _ck_boards_service = CkBoardsService(
        repo_url=config.CK_BOARDS_REPO_URL,
        base_path="/tmp/ck_boards",
        ssh_key_b64=config.BITBUCKET_SSH_KEY,
        fetch_interval=config.CK_BOARDS_FETCH_INTERVAL,
        environment=config.ENVIRONMENT,
    )


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
    import base64
    import os
    import stat
    import subprocess

    from config import env_config

    slug = request.args.get("slug", "").strip()
    if not slug:
        return bad_request("slug query parameter is required")

    repo_url = f"git@bitbucket.org:corekinect/{slug}.git"
    result = {"exists": False, "slug": slug}

    try:
        env = dict(os.environ)
        ssh_key_b64 = env_config.BITBUCKET_SSH_KEY
        if ssh_key_b64:
            key_path = f"/tmp/.ssh_check_{os.getpid()}"
            with open(key_path, "wb") as f:
                f.write(base64.b64decode(ssh_key_b64))
            os.chmod(key_path, stat.S_IRUSR)
            env["GIT_SSH_COMMAND"] = f"ssh -i {key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

        proc = subprocess.run(
            ["git", "ls-remote", "--exit-code", repo_url],
            timeout=10, capture_output=True, env=env,
        )
        result["exists"] = proc.returncode == 0

        if ssh_key_b64:
            os.unlink(key_path)
    except Exception:
        pass

    return jsonify(ApiResponse.ok(result).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_VIEW)
def list_repo_branches():
    """GET /v2/products/repos/branches?slug=alpha_fw — list branches for a Bitbucket repo."""
    import base64
    import os
    import stat
    import subprocess

    from config import env_config

    slug = request.args.get("slug", "").strip()
    if not slug:
        return bad_request("slug query parameter is required")

    repo_url = f"git@bitbucket.org:corekinect/{slug}.git"
    branches = []

    try:
        env = dict(os.environ)
        ssh_key_b64 = env_config.BITBUCKET_SSH_KEY
        key_path = None
        if ssh_key_b64:
            key_path = f"/tmp/.ssh_branches_{os.getpid()}"
            with open(key_path, "wb") as f:
                f.write(base64.b64decode(ssh_key_b64))
            os.chmod(key_path, stat.S_IRUSR)
            env["GIT_SSH_COMMAND"] = f"ssh -i {key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

        proc = subprocess.run(
            ["git", "ls-remote", "--heads", repo_url],
            timeout=15, capture_output=True, text=True, env=env,
        )
        if proc.returncode == 0:
            for line in proc.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) == 2:
                    ref = parts[1].replace("refs/heads/", "")
                    branches.append(ref)

        if key_path:
            os.unlink(key_path)
    except Exception:
        pass

    return jsonify(ApiResponse.ok({"slug": slug, "branches": sorted(branches)}).to_dict()), 200
