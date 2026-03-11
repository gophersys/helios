"""
Concord platform permissions.

Format: module:action
Modules: products, builds, validation, manufacturing, fixtures, benches, devices, cluster, users, permissions, api-keys, system
Actions: view, manage, trigger, run
"""


class Permissions:
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
    MANUFACTURING_VIEW = "manufacturing:view"
    MANUFACTURING_RUN = "manufacturing:run"
    MANUFACTURING_MANAGE = "manufacturing:manage"

    # Infrastructure
    FIXTURES_VIEW = "fixtures:view"
    FIXTURES_MANAGE = "fixtures:manage"
    BENCHES_VIEW = "benches:view"
    BENCHES_MANAGE = "benches:manage"
    DEVICES_VIEW = "devices:view"
    DEVICES_MANAGE = "devices:manage"
    CLUSTER_VIEW = "cluster:view"
    CLUSTER_MANAGE = "cluster:manage"

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
        return {v for k, v in vars(cls).items() if isinstance(v, str) and ":" in v}


# Permission registry for UI grouping — defines display name & description for each permission
PERMISSION_REGISTRY = {
    # Products & Builds
    "products:view": {"module": "Products & Builds", "label": "View Products", "description": "View product catalog, boards, chipsets, firmware builds"},
    "products:manage": {"module": "Products & Builds", "label": "Manage Products", "description": "Create, edit, delete products, boards, chipsets, firmware"},
    "builds:view": {"module": "Products & Builds", "label": "View Builds", "description": "View CI pipelines, build jobs, artifacts"},
    "builds:trigger": {"module": "Products & Builds", "label": "Trigger Builds", "description": "Trigger CI pipelines and build jobs"},
    "builds:manage": {"module": "Products & Builds", "label": "Manage Builds", "description": "Configure build scripts, manage pipeline settings"},

    # Testing
    "validation:view": {"module": "Testing", "label": "View Validation", "description": "View validation runs, results, test catalog"},
    "validation:run": {"module": "Testing", "label": "Run Validation", "description": "Trigger validation runs and test executions"},
    "validation:manage": {"module": "Testing", "label": "Manage Validation", "description": "Configure validation designs, manage test catalog"},
    "manufacturing:view": {"module": "Testing", "label": "View Manufacturing", "description": "View manufacturing sessions and device status"},
    "manufacturing:run": {"module": "Testing", "label": "Run Manufacturing", "description": "Execute manufacturing tests and sessions"},
    "manufacturing:manage": {"module": "Testing", "label": "Manage Manufacturing", "description": "Configure manufacturing fixtures and test definitions"},

    # Infrastructure
    "fixtures:view": {"module": "Infrastructure", "label": "View Fixtures", "description": "View manufacturing fixtures, slots, and assignments"},
    "fixtures:manage": {"module": "Infrastructure", "label": "Manage Fixtures", "description": "Create, configure, and manage manufacturing fixtures"},
    "benches:view": {"module": "Infrastructure", "label": "View Benches", "description": "View validation test benches, designs, and profiles"},
    "benches:manage": {"module": "Infrastructure", "label": "Manage Benches", "description": "Create, configure, and manage validation benches"},
    "devices:view": {"module": "Infrastructure", "label": "View Devices", "description": "View ICLE devices, MTIB nodes, and edge infrastructure"},
    "devices:manage": {"module": "Infrastructure", "label": "Manage Devices", "description": "Configure, deploy, and manage edge devices"},
    "cluster:view": {"module": "Infrastructure", "label": "View Cluster", "description": "View K8s cluster status, pods, deployments, services"},
    "cluster:manage": {"module": "Infrastructure", "label": "Manage Cluster", "description": "Scale deployments, delete pods, manage K8s resources"},

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
DEFAULT_ROLES = {
    "Super Admin": list(Permissions.all()),
    "Admin": [
        p for p in Permissions.all()
        if p not in {"cluster:manage", "system:manage", "permissions:manage"}
    ],
    "Engineer": [
        "products:view", "builds:view", "builds:trigger",
        "validation:view", "validation:run",
        "manufacturing:view", "manufacturing:run",
        "fixtures:view", "benches:view", "devices:view",
        "cluster:view", "system:view",
        "api-keys:view", "api-keys:manage",
    ],
    "Operator": [
        "products:view", "builds:view",
        "validation:view", "manufacturing:view", "manufacturing:run",
        "fixtures:view", "benches:view", "devices:view",
        "system:view",
    ],
    "Viewer": [
        "products:view", "builds:view",
        "validation:view", "manufacturing:view",
        "fixtures:view", "benches:view", "devices:view",
        "system:view",
    ],
}
