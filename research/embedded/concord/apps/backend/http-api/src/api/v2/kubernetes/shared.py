"""Shared helpers for cluster/system endpoints."""

import math

from flask import request


def parse_list_params():
    """Parse common list query parameters for K8s endpoints.

    Returns (page, limit, namespace, label_selector, field_selector).
    """
    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 1000)
    namespace = request.args.get("namespace", None)
    label_selector = request.args.get("labelSelector", None)
    field_selector = request.args.get("fieldSelector", None)
    return page, limit, namespace, label_selector, field_selector


def paginate(items: list, page: int, limit: int) -> dict:
    """Paginate a list of items client-side.

    Returns dict with 'data' (page slice) and 'pagination' metadata,
    matching the envelope used by DB-backed list endpoints.
    """
    total = len(items)
    pages = max(1, math.ceil(total / limit))
    page = min(page, pages)
    start = (page - 1) * limit
    end = start + limit
    return {
        "data": items[start:end],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": pages,
        },
    }
