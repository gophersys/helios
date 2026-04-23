"""Poller state API — persistent cache for git-poller branch and PR SHAs.

Replaces file-based JSON state with DB-backed storage so poller state
survives pod restarts and works correctly with multiple replicas.
"""

import logging
from database import Json
from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

_VALID_TYPES = {"branch", "pr"}


def _serialize(entry) -> dict:
    """Serialize a PollerState DB record to an API response dict."""
    return {
        "id": entry.id,
        "repoSlug": entry.repoSlug,
        "type": entry.type,
        "refId": entry.refId,
        "commitSha": entry.commitSha,
        "metadata": entry.metadata,
        "createdAt": entry.createdAt.isoformat() if hasattr(entry.createdAt, "isoformat") else entry.createdAt,
        "updatedAt": entry.updatedAt.isoformat() if hasattr(entry.updatedAt, "isoformat") else entry.updatedAt,
    }


@require_permissions(Permissions.SYSTEM_VIEW)
def list_poller_state():
    """GET /v2/system/poller-state

    Returns all cache entries, optionally filtered by repoSlug.
    """
    db = get_db_client()
    repo_slug = (request.args.get("repoSlug") or "").strip()

    where = {}
    if repo_slug:
        where["repoSlug"] = repo_slug

    entries = db.pollcache.find_many(where=where, order={"updatedAt": "desc"})
    return jsonify(ApiResponse.ok([_serialize(e) for e in entries]).to_dict()), 200


@require_permissions(Permissions.SYSTEM_MANAGE)
def upsert_poller_state():
    """PUT /v2/system/poller-state

    Upsert a single cache entry. Body fields:
      repoSlug  (str, required)
      type      ("branch" or "pr", required)
      refId     (str, required)
      commitSha (str, required)
      metadata  (dict, optional)
    """
    db = get_db_client()
    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    repo_slug = (data.get("repoSlug") or "").strip()
    if not repo_slug:
        return bad_request("repoSlug is required")

    entry_type = (data.get("type") or "").strip()
    if entry_type not in _VALID_TYPES:
        return bad_request("type must be 'branch' or 'pr'")

    ref_id = (data.get("refId") or "").strip()
    if not ref_id:
        return bad_request("refId is required")

    commit_sha = (data.get("commitSha") or "").strip()
    if not commit_sha:
        return bad_request("commitSha is required")

    metadata = data.get("metadata")  # optional, may be None

    create_data = {
        "repoSlug": repo_slug,
        "type": entry_type,
        "refId": ref_id,
        "commitSha": commit_sha,
    }
    if metadata is not None:
        create_data["metadata"] = Json(metadata)

    upserted = db.pollcache.upsert(
        where={"repoSlug_type_refId": {
            "repoSlug": repo_slug,
            "type": entry_type,
            "refId": ref_id,
        }},
        data={
            "create": create_data,
            "update": {
                "commitSha": commit_sha,
                **({"metadata": Json(metadata)} if metadata is not None else {}),
            },
        },
    )
    return jsonify(ApiResponse.ok(_serialize(upserted)).to_dict()), 200


@require_permissions(Permissions.SYSTEM_MANAGE)
def delete_poller_state():
    """DELETE /v2/system/poller-state?repoSlug=...&type=...&refId=...

    Delete a specific cache entry identified by (repoSlug, type, refId).
    """
    db = get_db_client()
    repo_slug = (request.args.get("repoSlug") or "").strip()
    entry_type = (request.args.get("type") or "").strip()
    ref_id = (request.args.get("refId") or "").strip()

    if not repo_slug:
        return bad_request("repoSlug query param is required")
    if entry_type not in _VALID_TYPES:
        return bad_request("type must be 'branch' or 'pr'")
    if not ref_id:
        return bad_request("refId query param is required")

    entry = db.pollcache.find_unique(
        where={"repoSlug_type_refId": {
            "repoSlug": repo_slug,
            "type": entry_type,
            "refId": ref_id,
        }}
    )
    if not entry:
        return not_found("Poll cache entry not found")

    db.pollcache.delete(
        where={"repoSlug_type_refId": {
            "repoSlug": repo_slug,
            "type": entry_type,
            "refId": ref_id,
        }}
    )
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
