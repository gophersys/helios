class Permissions:
    # Firmware
    FIRMWARE_APPID_CREATE = "Concord.Firmware.AppID.Create"
    FIRMWARE_APPID_VIEW = "Concord.Firmware.AppID.View"
    FIRMWARE_APPID_UPDATE = "Concord.Firmware.AppID.Update"
    FIRMWARE_APPID_DELETE = "Concord.Firmware.AppID.Delete"

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

    # Admin - Hardware
    ADMIN_HARDWARE_VIEW = "Concord.Admin.Hardware.View"
    ADMIN_HARDWARE_MANAGE = "Concord.Admin.Hardware.Manage"

    @classmethod
    def all(cls) -> list[dict]:
        """Return all permissions as a list for the /permissions endpoint."""
        return [
            {"key": v, "name": k}
            for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, str)
        ]
