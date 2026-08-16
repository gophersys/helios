"""Unit tests for auth types validation in src/api/v2/auth/types.py."""


# ── LoginRequest ──────────────────────────────────────


def test_login_valid():
    from src.api.v2.auth.types import LoginRequest

    data = {"email": "user@example.com", "password": "secret123"}
    req, err = LoginRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.email == "user@example.com"
    assert req.password == "secret123"


def test_login_email_normalized():
    from src.api.v2.auth.types import LoginRequest

    data = {"email": "  User@Example.COM  ", "password": "secret"}
    req, err = LoginRequest.from_json(data)

    assert err is None
    assert req.email == "user@example.com"


def test_login_missing_email():
    from src.api.v2.auth.types import LoginRequest

    data = {"password": "secret123"}
    req, err = LoginRequest.from_json(data)

    assert req is None
    assert err == "Email is required"


def test_login_missing_password():
    from src.api.v2.auth.types import LoginRequest

    data = {"email": "user@example.com"}
    req, err = LoginRequest.from_json(data)

    assert req is None
    assert err == "Password is required"


def test_login_empty_body():
    from src.api.v2.auth.types import LoginRequest

    req, err = LoginRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = LoginRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_login_empty_email():
    from src.api.v2.auth.types import LoginRequest

    data = {"email": "   ", "password": "secret"}
    req, err = LoginRequest.from_json(data)

    assert req is None
    assert err == "Email is required"


def test_login_empty_password():
    from src.api.v2.auth.types import LoginRequest

    data = {"email": "user@example.com", "password": ""}
    req, err = LoginRequest.from_json(data)

    assert req is None
    assert err == "Password is required"


# ── UserCreateRequest ─────────────────────────────────


def test_user_create_valid():
    from src.api.v2.auth.types import UserCreateRequest

    data = {
        "email": "new@example.com",
        "name": "New User",
        "role": "ADMIN",
        "permissionSetId": "perm-1",
    }
    req, err = UserCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.email == "new@example.com"
    assert req.name == "New User"
    assert req.role == "ADMIN"
    assert req.permissionSetId == "perm-1"


def test_user_create_minimal():
    from src.api.v2.auth.types import UserCreateRequest

    data = {"email": "min@example.com", "name": "Min User"}
    req, err = UserCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.role is None
    assert req.permissionSetId is None


def test_user_create_missing_name():
    from src.api.v2.auth.types import UserCreateRequest

    data = {"email": "user@example.com"}
    req, err = UserCreateRequest.from_json(data)

    assert req is None
    assert err == "Name is required"


def test_user_create_missing_email():
    from src.api.v2.auth.types import UserCreateRequest

    data = {"name": "Some User"}
    req, err = UserCreateRequest.from_json(data)

    assert req is None
    assert err == "Email is required"


def test_user_create_empty_body():
    from src.api.v2.auth.types import UserCreateRequest

    req, err = UserCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = UserCreateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_user_create_email_normalized():
    from src.api.v2.auth.types import UserCreateRequest

    data = {"email": "  USER@Example.COM  ", "name": "User"}
    req, err = UserCreateRequest.from_json(data)

    assert err is None
    assert req.email == "user@example.com"


def test_user_create_role_normalized():
    from src.api.v2.auth.types import UserCreateRequest

    data = {"email": "u@x.com", "name": "User", "role": "  admin  "}
    req, err = UserCreateRequest.from_json(data)

    assert err is None
    assert req.role == "ADMIN"


def test_user_create_empty_role_becomes_none():
    from src.api.v2.auth.types import UserCreateRequest

    data = {"email": "u@x.com", "name": "User", "role": "   "}
    req, err = UserCreateRequest.from_json(data)

    assert err is None
    assert req.role is None


# ── UserUpdateRequest ─────────────────────────────────


def test_user_update_valid():
    from src.api.v2.auth.types import UserUpdateRequest

    data = {"name": "Updated Name", "active": False}
    req, err = UserUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Updated Name"
    assert req.active is False


def test_user_update_empty_body():
    from src.api.v2.auth.types import UserUpdateRequest

    req, err = UserUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = UserUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_user_update_no_fields():
    from src.api.v2.auth.types import UserUpdateRequest

    # A dict with only unknown keys -> no recognized fields
    data = {"unknownField": "value"}
    req, err = UserUpdateRequest.from_json(data)

    assert req is None
    assert err == "No fields to update"


def test_user_update_empty_name():
    from src.api.v2.auth.types import UserUpdateRequest

    data = {"name": "   "}
    req, err = UserUpdateRequest.from_json(data)

    assert req is None
    assert err == "Name cannot be empty"


def test_user_update_active_non_bool():
    from src.api.v2.auth.types import UserUpdateRequest

    data = {"active": "true"}
    req, err = UserUpdateRequest.from_json(data)

    assert req is None
    assert err == "Active must be a boolean"


def test_user_update_to_update_data_includes_only_set_fields():
    from src.api.v2.auth.types import UserUpdateRequest

    data = {"name": "New Name"}
    req, err = UserUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert update_data == {"name": "New Name"}
    assert "role" not in update_data
    assert "permissionSetId" not in update_data
    assert "active" not in update_data


def test_user_update_role_can_be_set_to_none():
    """Role can be explicitly set to None (cleared) when 'role' key is present."""
    from src.api.v2.auth.types import UserUpdateRequest

    data = {"role": None}
    req, err = UserUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.role is None
    assert req._has_role is True

    update_data = req.to_update_data()
    assert "role" in update_data
    assert update_data["role"] is None


def test_user_update_role_omitted_not_in_update():
    """When 'role' key is absent, it should NOT appear in to_update_data()."""
    from src.api.v2.auth.types import UserUpdateRequest

    data = {"name": "Just Name"}
    req, err = UserUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "role" not in update_data


def test_user_update_permission_set_id_set_to_none():
    from src.api.v2.auth.types import UserUpdateRequest

    data = {"permissionSetId": None}
    req, err = UserUpdateRequest.from_json(data)

    assert err is None
    assert req._has_permission_set_id is True

    update_data = req.to_update_data()
    assert "permissionSetId" in update_data
    assert update_data["permissionSetId"] is None


# ── PermissionSetCreateRequest ────────────────────────


def test_permission_set_create_valid():
    from src.api.v2.auth.types import PermissionSetCreateRequest

    data = {
        "name": "Operator",
        "description": "Can operate devices",
        "permissions": ["Concord.Admin.Products.View", "Concord.Admin.Fixtures.Manage"],
    }
    req, err = PermissionSetCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Operator"
    assert req.description == "Can operate devices"
    assert len(req.permissions) == 2


def test_permission_set_create_missing_name():
    from src.api.v2.auth.types import PermissionSetCreateRequest

    data = {"permissions": ["Concord.Admin.Products.View"]}
    req, err = PermissionSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Name is required"


def test_permission_set_create_missing_permissions():
    from src.api.v2.auth.types import PermissionSetCreateRequest

    data = {"name": "Empty"}
    req, err = PermissionSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Permissions must be a non-empty list"


def test_permission_set_create_permissions_not_list():
    from src.api.v2.auth.types import PermissionSetCreateRequest

    data = {"name": "Bad", "permissions": "not-a-list"}
    req, err = PermissionSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Permissions must be a non-empty list"


def test_permission_set_create_permissions_empty_strings():
    from src.api.v2.auth.types import PermissionSetCreateRequest

    data = {"name": "Bad", "permissions": ["", "  "]}
    req, err = PermissionSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Permissions must contain valid strings"


def test_permission_set_create_empty_body():
    from src.api.v2.auth.types import PermissionSetCreateRequest

    req, err = PermissionSetCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


# ── PermissionSetUpdateRequest ────────────────────────


def test_permission_set_update_valid():
    from src.api.v2.auth.types import PermissionSetUpdateRequest

    data = {"name": "Renamed", "permissions": ["Concord.Admin.Products.View"]}
    req, err = PermissionSetUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Renamed"
    assert req.permissions == ["Concord.Admin.Products.View"]


def test_permission_set_update_no_fields():
    from src.api.v2.auth.types import PermissionSetUpdateRequest

    req, err = PermissionSetUpdateRequest.from_json({"unknownField": 1})
    assert req is None
    assert err == "No fields to update"


def test_permission_set_update_empty_name():
    from src.api.v2.auth.types import PermissionSetUpdateRequest

    data = {"name": "   "}
    req, err = PermissionSetUpdateRequest.from_json(data)

    assert req is None
    assert err == "Name cannot be empty"


def test_permission_set_update_permissions_not_list():
    from src.api.v2.auth.types import PermissionSetUpdateRequest

    data = {"permissions": "not-a-list"}
    req, err = PermissionSetUpdateRequest.from_json(data)

    assert req is None
    assert err == "Permissions must be a list"


def test_permission_set_update_to_update_data():
    from src.api.v2.auth.types import PermissionSetUpdateRequest

    data = {"description": None}
    req, err = PermissionSetUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "description" in update_data
    assert update_data["description"] is None
    assert "name" not in update_data
    assert "permissions" not in update_data


def test_permission_set_update_empty_body():
    from src.api.v2.auth.types import PermissionSetUpdateRequest

    req, err = PermissionSetUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


# ── ApiKeyCreateRequest ───────────────────────────────


def test_api_key_create_valid():
    from src.api.v2.auth.types import ApiKeyCreateRequest

    data = {"name": "CI Key", "expiresAt": "2026-12-31T00:00:00Z"}
    req, err = ApiKeyCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "CI Key"
    assert req.expiresAt == "2026-12-31T00:00:00Z"


def test_api_key_create_missing_name():
    from src.api.v2.auth.types import ApiKeyCreateRequest

    data = {"expiresAt": "2026-12-31T00:00:00Z"}
    req, err = ApiKeyCreateRequest.from_json(data)

    assert req is None
    assert err == "Name is required"


def test_api_key_create_no_expiry():
    from src.api.v2.auth.types import ApiKeyCreateRequest

    data = {"name": "Permanent Key"}
    req, err = ApiKeyCreateRequest.from_json(data)

    assert err is None
    assert req.expiresAt is None


def test_api_key_create_empty_body():
    from src.api.v2.auth.types import ApiKeyCreateRequest

    req, err = ApiKeyCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


# ── ProductAccessSetRequest ───────────────────────────


def test_product_access_set_valid():
    from src.api.v2.auth.types import ProductAccessSetRequest

    data = {
        "access": [
            {"productId": "prod-1", "level": "admin"},
            {"productId": "prod-2", "level": "view"},
        ]
    }
    req, err = ProductAccessSetRequest.from_json(data)

    assert err is None
    assert req is not None
    assert len(req.access) == 2
    assert req.access[0]["level"] == "admin"
    assert req.access[1]["level"] == "view"


def test_product_access_set_missing_access():
    from src.api.v2.auth.types import ProductAccessSetRequest

    data = {}
    req, err = ProductAccessSetRequest.from_json(data)

    assert req is None
    assert err == "Request body must contain JSON data"


def test_product_access_set_access_not_list():
    from src.api.v2.auth.types import ProductAccessSetRequest

    data = {"access": "not-a-list"}
    req, err = ProductAccessSetRequest.from_json(data)

    assert req is None
    assert err == "'access' must be an array"


def test_product_access_set_invalid_level():
    from src.api.v2.auth.types import ProductAccessSetRequest

    data = {"access": [{"productId": "prod-1", "level": "superadmin"}]}
    req, err = ProductAccessSetRequest.from_json(data)

    assert req is None
    assert "level must be one of" in err


def test_product_access_set_missing_product_id():
    from src.api.v2.auth.types import ProductAccessSetRequest

    data = {"access": [{"level": "admin"}]}
    req, err = ProductAccessSetRequest.from_json(data)

    assert req is None
    assert "productId is required" in err


def test_product_access_set_entry_not_object():
    from src.api.v2.auth.types import ProductAccessSetRequest

    data = {"access": ["not-an-object"]}
    req, err = ProductAccessSetRequest.from_json(data)

    assert req is None
    assert "must be an object" in err


def test_product_access_set_empty_body():
    from src.api.v2.auth.types import ProductAccessSetRequest

    req, err = ProductAccessSetRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"
