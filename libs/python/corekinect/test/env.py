"""Shared environment helpers for the corekinect test framework."""

import os


def get_run_id() -> str:
    """Get the run ID from environment, preferring new name.

    Checks CONCORD_SESSION_ID first (new convention), falls back to
    CONCORD_RUN_ID (legacy) for backward compatibility.
    """
    return os.environ.get("CONCORD_SESSION_ID") or os.environ.get("CONCORD_RUN_ID") or ""
