"""Integration tests for the Products API."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tests.conftest import make_obj


def _product_defaults() -> dict:
    """Common product fields for test mocks."""
    return {
        "slug": None,
        "buildConfig": None,
    }


def test_list_products(authed_client, mock_db):
    """Test listing products with pagination."""
    mock_db.product.count.return_value = 2
    mock_db.product.find_many.return_value = [
        make_obj(
            id="prod-1",
            name="Product Alpha",
            description="First product",
            status="ACTIVE",
            metadata={},
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            boards=[],
            firmwareSets=[],
            **_product_defaults(),
        ),
        make_obj(
            id="prod-2",
            name="Product Beta",
            description="Second product",
            status="ARCHIVED",
            metadata={"key": "value"},
            createdAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            boards=[],
            firmwareSets=[],
            **_product_defaults(),
        ),
    ]

    response = authed_client.get("/v2/products")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert "errors" in data
    assert len(data["errors"]) == 0

    # Check nested structure
    assert "data" in data["data"]
    assert "pagination" in data["data"]
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2
    assert data["data"]["pagination"]["page"] == 1


def test_list_products_unauthorized(client):
    """Test listing products without auth returns 401."""
    response = client.get("/v2/products")
    assert response.status_code == 401


def test_create_product(authed_client, mock_db):
    """Test creating a new product."""
    mock_db.product.find_unique.return_value = None

    mock_db.product.create.return_value = make_obj(
        id="prod-new",
        name="New Product",
        description="A new product",
        status="ACTIVE",
        metadata={},
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
        **_product_defaults(),
    )

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.post(
            "/v2/products",
            data=json.dumps({
                "name": "New Product",
                "description": "A new product",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["name"] == "New Product"
    assert data["data"]["id"] == "prod-new"


def test_create_product_duplicate_name(authed_client, mock_db):
    """Test creating a product with duplicate name returns 409."""
    mock_db.product.find_unique.return_value = make_obj(
        id="existing-prod",
        name="Existing Product",
        description="",
        status="ACTIVE",
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )

    response = authed_client.post(
        "/v2/products",
        data=json.dumps({
            "name": "Existing Product",
        }),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_create_product_missing_name(authed_client, mock_db):
    """Test creating product with missing name returns 400."""
    response = authed_client.post(
        "/v2/products",
        data=json.dumps({}),
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_get_product(authed_client, mock_db):
    """Test getting a single product with children."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-123",
        name="Test Product",
        description="A test product",
        status="ACTIVE",
        metadata={"foo": "bar"},
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
        boards=[
            make_obj(
                id="board-1",
                productId="prod-123",
                name="Main Board",
                description=None,
                active=True,
                createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                revisions=[
                    make_obj(
                        id="rev-1",
                        boardId="board-1",
                        version="1.0",
                        ckBoardsName="main_board_v1",
                        peripherals=None,
                        status="ACTIVE",
                        notes="First revision",
                        targets=[],
                        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                        updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                    ),
                ],
            ),
        ],
        firmwareSets=[],
        **_product_defaults(),
    )

    response = authed_client.get("/v2/products/prod-123")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["id"] == "prod-123"
    assert data["data"]["name"] == "Test Product"
    assert "boards" in data["data"]
    assert len(data["data"]["boards"]) == 1
    assert "firmwareSets" in data["data"]


def test_get_product_not_found(authed_client, mock_db):
    """Test getting a non-existent product returns 404."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.get("/v2/products/nonexistent")
    assert response.status_code == 404


def test_update_product(authed_client, mock_db):
    """Test updating an existing product."""
    existing = make_obj(
        id="prod-update",
        name="Old Name",
        description="Old description",
        status="ACTIVE",
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )
    mock_db.product.find_unique.return_value = existing

    mock_db.product.update.return_value = make_obj(
        id="prod-update",
        name="Old Name",
        description="New description",
        status="ACTIVE",
        metadata={"updated": True},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
        **_product_defaults(),
    )

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-update",
            data=json.dumps({
                "description": "New description",
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["description"] == "New description"
    assert data["data"]["status"] == "ACTIVE"


def test_update_product_not_found(authed_client, mock_db):
    """Test updating a non-existent product returns 404."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.put(
        "/v2/products/nonexistent",
        data=json.dumps({"name": "New Name"}),
    )

    assert response.status_code == 404


def test_delete_product(authed_client, mock_db):
    """Test deleting an archived product with no test runs."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-delete",
        name="Product to Delete",
        description="",
        status="ARCHIVED",
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )

    # Mock test run check returns None
    mock_db.testrun.find_first.return_value = None

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.delete("/v2/products/prod-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_delete_product_with_runs(authed_client, mock_db):
    """Test deleting an archived product with test runs returns 409."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-has-runs",
        name="Product with Runs",
        description="",
        status="ARCHIVED",
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )

    # Mock test run check returns a run
    mock_db.testrun.find_first.return_value = make_obj(
        id="run-1",
        productId="prod-has-runs",
    )

    response = authed_client.delete("/v2/products/prod-has-runs")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_update_product_duplicate_name(authed_client, mock_db):
    """Test updating a product to a duplicate name returns 409."""
    existing = make_obj(
        id="prod-update",
        name="Old Name",
        description="",
        status="ACTIVE",
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )
    dup = make_obj(
        id="prod-other",
        name="Taken Name",
        **_product_defaults(),
    )

    mock_db.product.find_unique.side_effect = [existing, dup]

    with patch("src.api.v2.products.products.log_audit"):
        response = authed_client.put(
            "/v2/products/prod-update",
            data=json.dumps({"name": "Taken Name"}),
        )

    assert response.status_code == 409


def test_delete_product_no_runs_succeeds(authed_client, mock_db):
    """Test deleting an archived product with no test runs succeeds."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-no-runs",
        name="Product No Runs",
        description="",
        status="ARCHIVED",
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )

    mock_db.testrun.find_first.return_value = None

    with patch("api.v2.products.products.log_audit"):
        response = authed_client.delete("/v2/products/prod-no-runs")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


# ── Target tests ───────────────────────────────────────────


def test_create_product_no_targets_in_product_create(authed_client, mock_db):
    """Product create no longer includes targets — targets live on BoardRevision."""
    mock_db.product.find_unique.return_value = None

    created = make_obj(
        id="prod-t1",
        name="Alpha",
        description="",
        status="ACTIVE",
        metadata={},
        slug=None,
        buildConfig=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
    )
    mock_db.product.create.return_value = created

    with patch("api.v2.products.products.log_audit"):
        authed_client.post(
            "/v2/products",
            data=json.dumps({
                "name": "Alpha",
            }),
        )

    call_kwargs = mock_db.product.create.call_args[1]
    assert "targets" not in call_kwargs["data"]


def test_get_product_includes_targets_in_response(authed_client, mock_db):
    """GET /v2/products/<id> includes targets collected from board revisions."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-with-targets",
        name="Alpha",
        description="",
        status="ACTIVE",
        metadata={},
        slug=None,
        buildConfig=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[
            make_obj(
                id="board-1",
                productId="prod-with-targets",
                name="Main Board",
                description=None,
                active=True,
                createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                revisions=[
                    make_obj(
                        id="rev-1",
                        boardId="board-1",
                        version="B0",
                        ckBoardsName="alpha_b0",
                        status="ACTIVE",
                        notes=None,
                        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                        targets=[
                            make_obj(id="tgt-1", role="app", soc="nrf52840", appId=109),
                        ],
                    ),
                ],
            ),
        ],
        firmwareSets=[],
    )

    response = authed_client.get("/v2/products/prod-with-targets")
    assert response.status_code == 200

    data = json.loads(response.data)
    targets = data["data"]["targets"]
    assert len(targets) == 1
    assert targets[0]["role"] == "app"
    assert targets[0]["soc"] == "nrf52840"
    assert targets[0]["appId"] == 109


def test_get_product_empty_targets_returns_empty_list(authed_client, mock_db):
    """GET /v2/products/<id> returns targets=[] when no board revisions have targets."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-no-targets",
        name="Alpha",
        description="",
        status="ACTIVE",
        metadata={},
        slug=None,
        buildConfig=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
    )

    response = authed_client.get("/v2/products/prod-no-targets")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["targets"] == []


def test_delete_product_with_board_targets_succeeds(authed_client, mock_db):
    """Products with board revision targets can be deleted — Prisma cascade handles cleanup."""
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-cascade",
        name="Alpha",
        description="",
        status="ARCHIVED",
        metadata={},
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **_product_defaults(),
    )
    mock_db.testrun.find_first.return_value = None

    with patch("api.v2.products.products.log_audit"):
        response = authed_client.delete("/v2/products/prod-cascade")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True
    mock_db.product.delete.assert_called_once_with(where={"id": "prod-cascade"})


# ── Default-access tests (r5ayeu) ─────────────────────────
#
# Newly-created products grant access only to admins. Maintainers,
# Developers and Operators must be granted access via ProductAccess.


def _build_token_headers(role: str, user_id: str = "test-user-id") -> dict:
    """Generate JWT auth headers for a specific role, bypassing the
    superadmin permission-set wiring used by ``authed_client``.

    The catalog access tests need to exercise the *role*-based gate and
    therefore require a token whose ``role`` claim is something other than
    ADMIN. ``authed_client`` always uses DEVELOPER, but the test setup
    layers an "all permissions" permission set on top so the
    require_permissions check still passes — exactly what we want for
    these tests.
    """
    from src.services.auth.jwt import create_token
    token = create_token(
        user_id=user_id,
        email=f"{role.lower()}@example.com",
        name=f"{role.title()} User",
        permission_set_id="test-perm-set-id",
        role=role,
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _stub_perm_set(mock_db) -> None:
    """Wire the per-set permission cache so role-only tests don't 403."""
    from src.lib.permissions import Permissions
    mock_db.permissionset.find_unique.return_value = make_obj(
        id="test-perm-set-id",
        name="Stub",
        permissions=list(Permissions.all()),
    )


def test_list_products_admin_sees_newly_created_product(client, mock_db):
    """A newly-created product (no ProductAccess entries) is visible to ADMIN."""
    _stub_perm_set(mock_db)
    new_prod = make_obj(
        id="prod-new",
        name="Fresh Product",
        description="",
        status="ACTIVE",
        metadata={},
        createdAt=datetime(2026, 4, 30, tzinfo=timezone.utc),
        updatedAt=datetime(2026, 4, 30, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
        **_product_defaults(),
    )
    mock_db.product.find_many.return_value = [new_prod]
    mock_db.product.count.return_value = 1
    mock_db.productaccess.find_many.return_value = []

    response = client.get("/v2/products", headers=_build_token_headers("ADMIN"))
    assert response.status_code == 200
    payload = json.loads(response.data)["data"]
    names = [p["name"] for p in payload["data"]]
    assert "Fresh Product" in names
    # Admin path must NOT consult ProductAccess at all.
    assert mock_db.productaccess.find_many.called is False


def test_list_products_developer_does_not_see_newly_created_product(client, mock_db):
    """A newly-created product (no ProductAccess entries) is hidden from non-admins.

    This is the contract for r5ayeu: products start invisible to everyone
    except ADMIN until access is explicitly granted.
    """
    _stub_perm_set(mock_db)
    mock_db.product.find_many.return_value = []
    mock_db.product.count.return_value = 0
    mock_db.productaccess.find_many.return_value = []  # No grants yet

    response = client.get("/v2/products", headers=_build_token_headers("DEVELOPER"))
    assert response.status_code == 200
    payload = json.loads(response.data)["data"]
    assert payload["data"] == []
    # The find_many call must have been scoped to an empty allowlist.
    where = mock_db.product.find_many.call_args.kwargs["where"]
    assert where["id"] == {"in": []}


def test_list_products_maintainer_does_not_see_newly_created_product(client, mock_db):
    """Maintainer must also be granted explicit access — they no longer bypass."""
    _stub_perm_set(mock_db)
    mock_db.product.find_many.return_value = []
    mock_db.product.count.return_value = 0
    mock_db.productaccess.find_many.return_value = []

    response = client.get("/v2/products", headers=_build_token_headers("MAINTAINER"))
    assert response.status_code == 200
    payload = json.loads(response.data)["data"]
    assert payload["data"] == []
    where = mock_db.product.find_many.call_args.kwargs["where"]
    assert where["id"] == {"in": []}


def test_list_products_developer_sees_product_after_explicit_grant(client, mock_db):
    """After a ProductAccess entry is created, the developer sees the product."""
    _stub_perm_set(mock_db)
    granted_product = make_obj(
        id="prod-granted",
        name="Granted Product",
        description="",
        status="ACTIVE",
        metadata={},
        createdAt=datetime(2026, 4, 30, tzinfo=timezone.utc),
        updatedAt=datetime(2026, 4, 30, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
        **_product_defaults(),
    )
    mock_db.product.find_many.return_value = [granted_product]
    mock_db.product.count.return_value = 1
    mock_db.productaccess.find_many.return_value = [
        make_obj(productId="prod-granted", level="view"),
    ]

    response = client.get("/v2/products", headers=_build_token_headers("DEVELOPER"))
    assert response.status_code == 200
    payload = json.loads(response.data)["data"]
    assert [p["name"] for p in payload["data"]] == ["Granted Product"]
    where = mock_db.product.find_many.call_args.kwargs["where"]
    assert where["id"] == {"in": ["prod-granted"]}


def test_get_product_developer_without_access_returns_404(client, mock_db):
    """Direct GET for a product the developer hasn't been granted returns 404.

    404 (not 403) deliberately hides existence — we don't want non-admins
    probing the ID space.
    """
    _stub_perm_set(mock_db)
    mock_db.productaccess.find_first.return_value = None

    response = client.get(
        "/v2/products/prod-secret", headers=_build_token_headers("DEVELOPER"),
    )
    assert response.status_code == 404
    # The product itself must not have been fetched — the access check
    # short-circuits before any product DB hit.
    mock_db.product.find_unique.assert_not_called()


def test_get_product_developer_with_access_returns_product(client, mock_db):
    """A developer with an explicit ProductAccess entry can fetch the product."""
    _stub_perm_set(mock_db)
    mock_db.productaccess.find_first.return_value = make_obj(
        userId="test-user-id", productId="prod-shared", level="view",
    )
    mock_db.product.find_unique.return_value = make_obj(
        id="prod-shared",
        name="Shared Product",
        description="",
        status="ACTIVE",
        metadata={},
        createdAt=datetime(2026, 4, 30, tzinfo=timezone.utc),
        updatedAt=datetime(2026, 4, 30, tzinfo=timezone.utc),
        boards=[],
        firmwareSets=[],
        **_product_defaults(),
    )

    response = client.get(
        "/v2/products/prod-shared", headers=_build_token_headers("DEVELOPER"),
    )
    assert response.status_code == 200
    payload = json.loads(response.data)["data"]
    assert payload["id"] == "prod-shared"
