class Permissions:
    # Cluster / MTIB
    MTIB_READ = "Concord.Cluster.Read"
    MTIB_MANAGE = "Concord.Cluster.Manage"

    # Validation
    VALIDATION_TESTS_RUN = "Concord.Validation.Tests.Run"

    # Admin - Users
    ADMIN_USERS_VIEW = "Concord.Admin.Users.View"
    ADMIN_USERS_MANAGE = "Concord.Admin.Users.Manage"

    # Admin - Permission Sets
    ADMIN_PERMISSION_SETS_VIEW = "Concord.Admin.PermissionSets.View"
    ADMIN_PERMISSION_SETS_MANAGE = "Concord.Admin.PermissionSets.Manage"

    # Admin - API Keys
    ADMIN_API_KEYS_VIEW = "Concord.Admin.ApiKeys.View"
    ADMIN_API_KEYS_MANAGE = "Concord.Admin.ApiKeys.Manage"

    # Admin - Inventory
    ADMIN_INVENTORY_VIEW = "Concord.Admin.Inventory.View"
    ADMIN_INVENTORY_MANAGE = "Concord.Admin.Inventory.Manage"

    # Admin - Codebases
    ADMIN_CODEBASES_VIEW = "Concord.Admin.Codebases.View"
    ADMIN_CODEBASES_MANAGE = "Concord.Admin.Codebases.Manage"

    # Admin - History
    ADMIN_HISTORY_VIEW = "Concord.Admin.History.View"

    # Admin - Catalog
    ADMIN_CATALOG_VIEW = "Concord.Admin.Catalog.View"
    ADMIN_CATALOG_MANAGE = "Concord.Admin.Catalog.Manage"

    # Admin - System
    ADMIN_SYSTEM_VIEW = "Concord.Admin.System.View"
    ADMIN_SYSTEM_MANAGE = "Concord.Admin.System.Manage"

    # Admin - Nodes
    ADMIN_NODES_VIEW = "Concord.Admin.Nodes.View"
    ADMIN_NODES_MANAGE = "Concord.Admin.Nodes.Manage"

    # Admin - Fixtures
    ADMIN_FIXTURES_VIEW = "Concord.Admin.Fixtures.View"
    ADMIN_FIXTURES_MANAGE = "Concord.Admin.Fixtures.Manage"

    # Admin - Deployments
    ADMIN_DEPLOYMENTS_VIEW = "Concord.Admin.Deployments.View"
    ADMIN_DEPLOYMENTS_MANAGE = "Concord.Admin.Deployments.Manage"

    @classmethod
    def all(cls) -> list[dict]:
        """Return all permissions as a list for the /permissions endpoint."""
        return [
            {"key": v, "name": k}
            for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, str)
        ]
