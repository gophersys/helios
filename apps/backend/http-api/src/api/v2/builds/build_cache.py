import hashlib
import json
from typing import Optional, Dict, Any

def compute_build_fingerprint(
    repo_url: str,
    commit_sha: str,
    board: str,
    variant: str,
    config_flags: Optional[Dict[str, Any]] = None,
) -> str:
    """Compute a deterministic fingerprint for a build configuration."""
    # Normalize and hash
    parts = {
        "repo_url": repo_url or "",
        "commit_sha": commit_sha or "",
        "board": board or "",
        "variant": variant or "",
        "config_flags": json.dumps(config_flags or {}, sort_keys=True),
    }
    canonical = json.dumps(parts, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def find_cached_build(db, fingerprint: str):
    """Find an existing successful build with the same fingerprint."""
    return db.buildjob.find_first(
        where={
            "buildFingerprint": fingerprint,
            "status": "SUCCESS",
        },
        include={"artifacts": True},
        order={"finishedAt": "desc"},
    )
