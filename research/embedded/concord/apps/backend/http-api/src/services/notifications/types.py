"""Notification type registry.

Defines all notification types with their group, label, and description.
The frontend reads this registry via GET /v2/notifications/types to build
the preferences UI dynamically.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationTypeDef:
    key: str
    group: str
    label: str
    description: str


NOTIFICATION_GROUPS = {
    "PLATFORM": "Platform",
    "VALIDATION": "Validation",
    "MANUFACTURING": "Manufacturing",
    "BUILD": "Build",
    "BUG": "Bug Reports",
    "SYSTEM": "System",
}

NOTIFICATION_TYPES: dict[str, NotificationTypeDef] = {}


def _register(key: str, group: str, label: str, description: str) -> None:
    NOTIFICATION_TYPES[key] = NotificationTypeDef(
        key=key, group=group, label=label, description=description,
    )


# ── Platform ───────────────────────────────────────────────────
_register(
    "PLATFORM_RELEASE_PUBLISHED", "PLATFORM",
    "Release published",
    "A new platform version has been deployed to production.",
)
_register(
    "PLATFORM_DEPLOYMENT_COMPLETE", "PLATFORM",
    "Deployment complete",
    "A platform deployment finished successfully.",
)
_register(
    "PLATFORM_DEPLOYMENT_FAILED", "PLATFORM",
    "Deployment failed",
    "A platform deployment encountered an error.",
)

# ── Validation ─────────────────────────────────────────────────
_register(
    "VALIDATION_RUN_COMPLETE", "VALIDATION",
    "Validation run complete",
    "A validation test run finished successfully.",
)
_register(
    "VALIDATION_RUN_FAILED", "VALIDATION",
    "Validation run failed",
    "A validation test run finished with failures.",
)

# ── Manufacturing ──────────────────────────────────────────────
_register(
    "MANUFACTURING_SESSION_COMPLETE", "MANUFACTURING",
    "Manufacturing session complete",
    "A manufacturing panel session finished successfully.",
)
_register(
    "MANUFACTURING_SESSION_FAILED", "MANUFACTURING",
    "Manufacturing session failed",
    "A manufacturing panel session finished with failures.",
)

# ── Build ──────────────────────────────────────────────────────
_register(
    "BUILD_COMPLETE", "BUILD",
    "Build complete",
    "A firmware build finished successfully.",
)
_register(
    "BUILD_FAILED", "BUILD",
    "Build failed",
    "A firmware build encountered an error.",
)

# ── Bug Reports ────────────────────────────────────────────────
_register(
    "BUG_ACKNOWLEDGED", "BUG",
    "Bug acknowledged",
    "Your bug report has been acknowledged by the team.",
)
_register(
    "BUG_RESOLVED", "BUG",
    "Bug resolved",
    "Your bug report has been resolved.",
)
_register(
    "BUG_DISMISSED", "BUG",
    "Bug dismissed",
    "Your bug report has been reviewed and dismissed.",
)

# ── System ─────────────────────────────────────────────────────
_register(
    "SYSTEM_ANNOUNCEMENT", "SYSTEM",
    "System announcement",
    "An administrator broadcast a system-wide message.",
)
_register(
    "SYSTEM_MAINTENANCE", "SYSTEM",
    "Scheduled maintenance",
    "A scheduled maintenance window is approaching.",
)


def get_types_by_group() -> dict[str, list[dict]]:
    """Return notification types grouped for the frontend."""
    groups: dict[str, list[dict]] = {}
    for t in NOTIFICATION_TYPES.values():
        groups.setdefault(t.group, []).append({
            "key": t.key,
            "label": t.label,
            "description": t.description,
        })
    return {
        group_key: {
            "label": NOTIFICATION_GROUPS.get(group_key, group_key),
            "types": types,
        }
        for group_key, types in groups.items()
    }
