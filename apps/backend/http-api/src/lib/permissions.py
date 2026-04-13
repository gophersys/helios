"""
Concord platform permissions.

Format: module:action
Modules: products, builds, validation, fixtures, devices, kubernetes, users, permissions, api-keys, system
Actions: view, manage, trigger, run
"""


class Permissions:
    """Enumeration of all platform permission strings used with @require_permissions.

    Permission strings follow the format module:action.
    """

    # Products & Builds
    PRODUCTS_VIEW = "products:view"
    PRODUCTS_MANAGE = "products:manage"
    BUILDS_VIEW = "builds:view"
    BUILDS_TRIGGER = "builds:trigger"
    BUILDS_MANAGE = "builds:manage"

    # Testing
    VALIDATION_VIEW = "validation:view"
    VALIDATION_RUN = "validation:run"
    VALIDATION_MANAGE = "validation:manage"

    # Manufacturing
    MANUFACTURING_VIEW = "manufacturing:view"
    MANUFACTURING_RUN = "manufacturing:run"
    MANUFACTURING_MANAGE = "manufacturing:manage"

    # Infrastructure
    FIXTURES_VIEW = "fixtures:view"
    FIXTURES_MANAGE = "fixtures:manage"
    DEVICES_VIEW = "devices:view"
    DEVICES_MANAGE = "devices:manage"
    KUBERNETES_VIEW = "kubernetes:view"
    KUBERNETES_MANAGE = "kubernetes:manage"

    # Platform
    USERS_VIEW = "users:view"
    USERS_MANAGE = "users:manage"
    PERMISSIONS_MANAGE = "permissions:manage"
    API_KEYS_VIEW = "api-keys:view"
    API_KEYS_MANAGE = "api-keys:manage"
    SYSTEM_VIEW = "system:view"
    SYSTEM_MANAGE = "system:manage"

    @classmethod
    def all(cls) -> set:
        """Return the set of all permission strings defined on this class.

        Returns:
            Set of permission strings (e.g., {'products:view', 'builds:trigger', ...}).
        """
        return {v for k, v in vars(cls).items() if isinstance(v, str) and ":" in v}


# Permission registry for UI grouping — defines display name & description for each permission
PERMISSION_REGISTRY = {
    # Products & Builds
    "products:view": {"module": "Products & Builds", "label": "View Products", "description": "View product catalog, boards, firmware builds"},
    "products:manage": {"module": "Products & Builds", "label": "Manage Products", "description": "Create, edit, delete products, boards, firmware"},
    "builds:view": {"module": "Products & Builds", "label": "View Builds", "description": "View build runs, build jobs, artifacts"},
    "builds:trigger": {"module": "Products & Builds", "label": "Trigger Builds", "description": "Trigger build runs and build jobs"},
    "builds:manage": {"module": "Products & Builds", "label": "Manage Builds", "description": "Configure build scripts, manage build run settings"},

    # Testing
    "validation:view": {"module": "Testing", "label": "View Validation", "description": "View validation runs, results, test catalog"},
    "validation:run": {"module": "Testing", "label": "Run Validation", "description": "Trigger validation runs and test executions"},
    "validation:manage": {"module": "Testing", "label": "Manage Validation", "description": "Configure validation designs, manage test catalog"},

    # Manufacturing
    "manufacturing:view": {"module": "Manufacturing", "label": "View Manufacturing", "description": "View manufacturing sessions, POST results, and device status"},
    "manufacturing:run": {"module": "Manufacturing", "label": "Run Manufacturing", "description": "Start manufacturing sessions and run POST tests"},
    "manufacturing:manage": {"module": "Manufacturing", "label": "Manage Manufacturing", "description": "Configure manufacturing procedures, manage POST sequences"},

    # Infrastructure
    "fixtures:view": {"module": "Infrastructure", "label": "View Fixtures", "description": "View fixtures, test benches, designs, slots, and assignments"},
    "fixtures:manage": {"module": "Infrastructure", "label": "Manage Fixtures", "description": "Create, configure, and manage fixtures and test benches"},
    "devices:view": {"module": "Infrastructure", "label": "View Devices", "description": "View ICLE devices, MTIB nodes, and edge infrastructure"},
    "devices:manage": {"module": "Infrastructure", "label": "Manage Devices", "description": "Configure, deploy, and manage edge devices"},
    "kubernetes:view": {"module": "Infrastructure", "label": "View Kubernetes", "description": "View K8s cluster status, pods, deployments, services"},
    "kubernetes:manage": {"module": "Infrastructure", "label": "Manage Kubernetes", "description": "Scale deployments, delete pods, manage K8s resources"},

    # Platform
    "users:view": {"module": "Platform", "label": "View Users", "description": "View user accounts and their permission sets"},
    "users:manage": {"module": "Platform", "label": "Manage Users", "description": "Create, edit, deactivate user accounts"},
    "permissions:manage": {"module": "Platform", "label": "Manage Permissions", "description": "Create and edit permission sets (roles)"},
    "api-keys:view": {"module": "Platform", "label": "View API Keys", "description": "View API key metadata and usage"},
    "api-keys:manage": {"module": "Platform", "label": "Manage API Keys", "description": "Create and revoke API keys"},
    "system:view": {"module": "Platform", "label": "View System", "description": "View system info, audit history, storage usage"},
    "system:manage": {"module": "Platform", "label": "Manage System", "description": "Manage system settings, retention policies, deployments"},
}


# Default role definitions for seed.py
# Maps the 4 Role enum values to their permission sets.
DEFAULT_ROLES = {
    "Admin": list(Permissions.all()),  # All permissions (Super Admin = Admin role)
    "Maintainer": [
        p for p in Permissions.all()
        if p not in {"users:manage", "permissions:manage", "system:manage", "kubernetes:manage"}
    ],
    "Developer": [
        "products:view", "builds:view", "builds:trigger", "builds:manage",
        "validation:view", "validation:run",
        "manufacturing:view",
        "fixtures:view", "devices:view",
        "api-keys:view", "api-keys:manage",
    ],
    "Operator": [
        "manufacturing:view", "manufacturing:run", "manufacturing:manage",
    ],
}
