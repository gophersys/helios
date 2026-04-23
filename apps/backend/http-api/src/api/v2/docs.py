from apispec import APISpec
from flask import jsonify

# ── Spec singleton ────────────────────────────────────────────
_spec: APISpec | None = None


def _build_spec() -> APISpec:
    """Build the OpenAPI 3.0.3 specification for the Concord API."""
    spec = APISpec(
        title="Concord API",
        version="2.0.0",
        openapi_version="3.0.3",
        info={
            "description": (
                "Concord platform API for managing products, builds, test benches, and device validation.\n\n"
                "All responses use a standard envelope:\n"
                '```json\n{ "data": <payload>, "errors": [] }\n```\n'
                "Error responses set `data` to `null` and populate `errors`."
            ),
        },
    )

    # ── Security schemes ────────────────────────────────────────
    spec.components.security_scheme("BearerAuth", {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"})
    spec.components.security_scheme("ApiKeyAuth", {
        "type": "apiKey", "in": "header", "name": "Authorization",
        "description": 'Use format: ApiKey <key>',
    })

    # ── Reusable schemas ────────────────────────────────────────
    spec.components.schema("ErrorDetail", {
        "type": "object",
        "required": ["message"],
        "properties": {
            "message": {"type": "string"},
            "field": {"type": "string"},
            "code": {"type": "string"},
        },
    })
    spec.components.schema("ErrorResponse", {
        "type": "object",
        "properties": {
            "data": {"nullable": True, "example": None},
            "errors": {"type": "array", "items": {"$ref": "#/components/schemas/ErrorDetail"}, "minItems": 1},
        },
    })
    spec.components.schema("ApiEnvelope", {
        "type": "object",
        "properties": {
            "data": {},
            "errors": {"type": "array", "items": {"$ref": "#/components/schemas/ErrorDetail"}, "default": []},
        },
    })
    spec.components.schema("UserBasic", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "email": {"type": "string", "format": "email"},
            "name": {"type": "string"},
            "permissionSetId": {"type": "string", "nullable": True},
            "permissionSetName": {"type": "string", "nullable": True},
        },
    })
    spec.components.schema("UserProfile", {
        "allOf": [
            {"$ref": "#/components/schemas/UserBasic"},
            {"type": "object", "properties": {
                "permissions": {"type": "array", "items": {"type": "string"}},
                "active": {"type": "boolean"},
                "lastSeenAt": {"type": "string", "format": "date-time", "nullable": True},
                "createdAt": {"type": "string", "format": "date-time"},
            }},
        ],
    })
    spec.components.schema("FullUser", {
        "allOf": [
            {"$ref": "#/components/schemas/UserProfile"},
            {"type": "object", "properties": {
                "updatedAt": {"type": "string", "format": "date-time"},
            }},
        ],
    })
    spec.components.schema("PermissionSet", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string", "nullable": True},
            "permissions": {"type": "array", "items": {"type": "string"}},
            "userCount": {"type": "integer"},
            "users": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string"}, "name": {"type": "string"}, "email": {"type": "string"},
            }}},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("PermissionSetDetail", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string", "nullable": True},
            "permissions": {"type": "array", "items": {"type": "string"}},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("ApiKey", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "keyPrefix": {"type": "string"},
            "userId": {"type": "string"},
            "userName": {"type": "string", "nullable": True},
            "expiresAt": {"type": "string", "format": "date-time", "nullable": True},
            "lastUsedAt": {"type": "string", "format": "date-time", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("Product", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string", "nullable": True},
            "status": {"type": "string", "enum": ["ACTIVE", "ARCHIVED"]},
            "metadata": {"type": "object", "nullable": True},
            "boardCount": {"type": "integer"},
            "firmwareBuildCount": {"type": "integer"},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("Board", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "productId": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string", "nullable": True},
            "active": {"type": "boolean"},
            "revisionCount": {"type": "integer"},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("BoardRevision", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "boardId": {"type": "string"},
            "version": {"type": "string"},
            "peripherals": {"type": "object", "nullable": True},
            "status": {"type": "string", "enum": ["ACTIVE", "DEPRECATED", "EOL"]},
            "notes": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("FirmwareBuild", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "productId": {"type": "string"},
            "targetId": {"type": "string", "nullable": True},
            "target": {"type": "object", "nullable": True, "properties": {
                "id": {"type": "string"}, "role": {"type": "string"}, "soc": {"type": "string"}, "appId": {"type": "integer"},
            }},
            "version": {"type": "string"},
            "isManufacturing": {"type": "boolean"},
            "storageKey": {"type": "string"},
            "filename": {"type": "string"},
            "sizeBytes": {"type": "string"},
            "checksum": {"type": "string"},
            "contentType": {"type": "string", "nullable": True},
            "status": {"type": "string", "enum": ["DRAFT", "RELEASED", "DEPRECATED"]},
            "notes": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("AuditLogEntry", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "userId": {"type": "string"},
            "action": {"type": "string"},
            "entityType": {"type": "string"},
            "entityId": {"type": "string"},
            "details": {"type": "object"},
            "ipAddress": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "user": {"nullable": True, "type": "object", "properties": {
                "id": {"type": "string"}, "name": {"type": "string"}, "email": {"type": "string"},
            }},
        },
    })
    spec.components.schema("ConcordNode", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "hostname": {"type": "string"},
            "type": {"type": "string", "enum": ["MANUFACTURING", "VALIDATION"]},
            "status": {"type": "string", "enum": ["ONLINE", "OFFLINE", "MAINTENANCE", "ERROR"]},
            "ipAddress": {"type": "string", "nullable": True},
            "hardwareRevision": {"type": "string", "nullable": True},
            "metadata": {"type": "object", "nullable": True},
            "fixtureSlot": {"nullable": True, "type": "object", "properties": {
                "id": {"type": "string"}, "fixtureId": {"type": "string"},
                "slotIndex": {"type": "integer"}, "label": {"type": "string", "nullable": True},
                "fixtureName": {"type": "string"},
            }},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("FixtureSlot", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "fixtureId": {"type": "string"},
            "slotIndex": {"type": "integer"},
            "label": {"type": "string", "nullable": True},
            "nodeId": {"type": "string", "nullable": True},
            "active": {"type": "boolean"},
            "node": {"nullable": True, "type": "object", "properties": {
                "id": {"type": "string"}, "name": {"type": "string"},
                "hostname": {"type": "string"}, "type": {"type": "string"}, "status": {"type": "string"},
            }},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("Fixture", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "productId": {"type": "string"},
            "type": {"type": "string", "enum": ["MANUFACTURING", "VALIDATION"]},
            "description": {"type": "string", "nullable": True},
            "active": {"type": "boolean"},
            "metadata": {"type": "object", "nullable": True},
            "slotCount": {"type": "integer"},
            "productName": {"type": "string"},
            "slots": {"type": "array", "items": {"$ref": "#/components/schemas/FixtureSlot"}},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("ConcordDeployment", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "productId": {"type": "string", "nullable": True},
            "fixtureId": {"type": "string", "nullable": True},
            "status": {"type": "string", "enum": ["PENDING", "RUNNING", "STOPPED", "FAILED"]},
            "config": {"type": "object", "nullable": True},
            "version": {"type": "string", "nullable": True},
            "fixtureName": {"type": "string"},
            "productName": {"type": "string"},
            "createdBy": {"nullable": True, "type": "object", "properties": {
                "id": {"type": "string"}, "name": {"type": "string"},
            }},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("DashboardFixture", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "type": {"type": "string", "enum": ["MANUFACTURING", "VALIDATION"]},
            "active": {"type": "boolean"},
            "productName": {"type": "string", "nullable": True},
            "productId": {"type": "string"},
            "slotCount": {"type": "integer"},
            "assignedCount": {"type": "integer"},
            "nodesOnline": {"type": "integer"},
            "nodesOffline": {"type": "integer"},
            "nodesError": {"type": "integer"},
            "health": {"type": "string", "enum": ["HEALTHY", "DEGRADED", "ERROR", "UNASSIGNED", "EMPTY", "UNKNOWN"]},
            "hasActiveDeployment": {"type": "boolean"},
            "activeDeploymentStatus": {"type": "string", "nullable": True},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })

    spec.components.schema("ValidationRun", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "productId": {"type": "string"},
            "fixtureId": {"type": "string", "nullable": True},
            "status": {"type": "string", "enum": ["ACTIVE", "COMPLETED", "CANCELLED", "PAUSED"]},
            "config": {"type": "object", "nullable": True},
            "targetCount": {"type": "integer"},
            "completedCount": {"type": "integer"},
            "passedCount": {"type": "integer"},
            "failedCount": {"type": "integer"},
            "startedAt": {"type": "string", "format": "date-time", "nullable": True},
            "finishedAt": {"type": "string", "format": "date-time", "nullable": True},
            "notes": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
            "product": {"type": "object", "nullable": True, "properties": {
                "id": {"type": "string"}, "name": {"type": "string"},
            }},
            "createdBy": {"type": "object", "nullable": True, "properties": {
                "id": {"type": "string"}, "name": {"type": "string"}, "email": {"type": "string"},
            }},
            "devices": {"type": "array", "items": {"$ref": "#/components/schemas/ValidationDevice"}, "nullable": True},
            "executions": {"type": "array", "items": {"$ref": "#/components/schemas/ValidationExecution"}, "nullable": True},
        },
    })
    spec.components.schema("ValidationDevice", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "serialNumber": {"type": "string"},
            "status": {"type": "string"},
            "metadata": {"type": "object", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("ValidationExecution", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "testId": {"type": "string"},
            "nodeId": {"type": "string"},
            "deviceId": {"type": "string"},
            "status": {"type": "string", "enum": ["QUEUED", "RUNNING", "PASSED", "FAILED", "CANCELLED"]},
            "startedAt": {"type": "string", "format": "date-time", "nullable": True},
            "finishedAt": {"type": "string", "format": "date-time", "nullable": True},
            "durationMs": {"type": "integer", "nullable": True},
            "errorMessage": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "test": {"type": "object", "nullable": True, "properties": {
                "id": {"type": "string"}, "name": {"type": "string"}, "category": {"type": "string"},
            }},
            "resultCount": {"type": "integer", "nullable": True},
            "resultsPassed": {"type": "integer", "nullable": True},
        },
    })
    spec.components.schema("ValidationResult", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "executionId": {"type": "string"},
            "stepIndex": {"type": "integer"},
            "groupIndex": {"type": "integer"},
            "passed": {"type": "boolean"},
            "result": {"type": "object", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
        },
    })

    # ── Reusable responses ──────────────────────────────────────
    def _err_resp(desc):
        """Build an error response schema reference for the given description."""
        return {"description": desc, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}

    _deleted_resp = {"description": "Resource deleted", "content": {"application/json": {"schema": {
        "type": "object", "properties": {
            "data": {"nullable": True, "example": None},
            "errors": {"type": "array", "items": {"$ref": "#/components/schemas/ErrorDetail"}, "example": []},
        },
    }}}}

    def _ok(ref_or_schema, *, array=False):
        """Build a success response schema, optionally wrapping in an array."""
        if isinstance(ref_or_schema, str):
            inner = {"$ref": f"#/components/schemas/{ref_or_schema}"}
        else:
            inner = ref_or_schema
        if array:
            inner = {"type": "array", "items": inner}
        return {"description": "Success", "content": {"application/json": {"schema": {
            "allOf": [{"$ref": "#/components/schemas/ApiEnvelope"}, {"type": "object", "properties": {"data": inner}}],
        }}}}

    _400 = _err_resp("Bad request")
    _401 = _err_resp("Unauthorized")
    _403 = _err_resp("Forbidden")
    _404 = _err_resp("Not found")
    _409 = _err_resp("Conflict")
    _500 = _err_resp("Internal server error")
    _auth_security: list = [{"BearerAuth": []}, {"ApiKeyAuth": []}]

    # ── Pagination helpers ──────────────────────────────────────
    _pagination_params = [
        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50, "maximum": 100}},
    ]

    def _paginated(ref):
        """Build a paginated success response schema for the given ref."""
        return _ok({"type": "object", "properties": {
            "data": {"type": "array", "items": {"$ref": f"#/components/schemas/{ref}"}},
            "pagination": {"type": "object", "properties": {
                "page": {"type": "integer"},
                "limit": {"type": "integer"},
                "total": {"type": "integer"},
                "pages": {"type": "integer"},
            }},
        }})

    # ── Tags ────────────────────────────────────────────────────
    for tag in [
        "Auth", "Users", "Permissions", "API Keys",
        "Products", "Boards", "Board Revisions", "Firmware Builds",
        "Builds", "Cluster", "Devices",
        "Benches", "Nodes", "Fixtures", "Fixture Slots", "Managed Deployments",
        "Validation", "System", "Dashboard", "Health",
    ]:
        spec.tag({"name": tag})

    # ── Helper to add paths ─────────────────────────────────────
    def path(url, **kwargs):
        """Register an API path with its operations in the spec."""
        parameters = kwargs.pop("parameters", None)
        spec.path(path=url, operations=kwargs, parameters=parameters)

    # ── Auth ────────────────────────────────────────────────────
    path("/auth/login", post={
        "tags": ["Auth"], "summary": "Login with Google credential", "security": [],
        "requestBody": {"required": True, "content": {"application/json": {"schema": {
            "type": "object", "required": ["credential"],
            "properties": {"credential": {"type": "string", "description": "Google ID token"}},
        }}}},
        "responses": {
            "200": _ok({"type": "object", "properties": {
                "token": {"type": "string"},
                "user": {"$ref": "#/components/schemas/UserBasic"},
            }}),
            "400": _400, "401": _401, "403": _403,
        },
    })
    path("/auth/me", get={
        "tags": ["Auth"], "summary": "Get current user profile", "security": _auth_security,
        "responses": {"200": _ok("UserProfile"), "401": _401, "404": _404},
    })

    # ── Users ───────────────────────────────────────────────────
    path("/users",
        get={
            "tags": ["Users"], "summary": "List all users", "security": _auth_security,
            "responses": {"200": _ok("FullUser", array=True), "401": _401, "403": _403},
        },
        post={
            "tags": ["Users"], "summary": "Create a new user", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["email", "name"],
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "name": {"type": "string"},
                    "permissionSetId": {"type": "string", "nullable": True},
                },
            }}}},
            "responses": {"201": _ok("FullUser"), "400": _400, "409": _409},
        },
    )
    path("/users/{user_id}",
        parameters=[{"name": "user_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        put={
            "tags": ["Users"], "summary": "Update a user", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"},
                    "permissionSetId": {"type": "string", "nullable": True},
                    "active": {"type": "boolean"},
                },
            }}}},
            "responses": {"200": _ok("FullUser"), "400": _400, "404": _404},
        },
        delete={
            "tags": ["Users"], "summary": "Deactivate a user (soft delete)", "security": _auth_security,
            "responses": {"200": _deleted_resp, "400": _400, "404": _404},
        },
    )

    # ── Permissions ───────────────────────────────────────────────
    path("/permissions",
        get={
            "tags": ["Permissions"], "summary": "List all permission sets", "security": _auth_security,
            "responses": {"200": _ok("PermissionSet", array=True), "401": _401, "403": _403},
        },
        post={
            "tags": ["Permissions"], "summary": "Create a permission set", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name", "permissions"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string", "nullable": True},
                    "permissions": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                },
            }}}},
            "responses": {"201": _ok("PermissionSetDetail"), "400": _400, "409": _409},
        },
    )
    path("/permissions/{set_id}",
        parameters=[{"name": "set_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        put={
            "tags": ["Permissions"], "summary": "Update a permission set", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string", "nullable": True},
                    "permissions": {"type": "array", "items": {"type": "string"}},
                },
            }}}},
            "responses": {"200": _ok("PermissionSetDetail"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Permissions"], "summary": "Delete a permission set", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )

    # ── API Keys ────────────────────────────────────────────────
    path("/api-keys",
        get={
            "tags": ["API Keys"], "summary": "List API keys",
            "description": "Users see their own keys. Admins with api-keys:view see all.",
            "security": _auth_security,
            "responses": {"200": _ok("ApiKey", array=True), "401": _401},
        },
        post={
            "tags": ["API Keys"], "summary": "Create a new API key",
            "description": "Returns the full key once. Store it securely.",
            "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "expiresAt": {"type": "string", "format": "date-time", "nullable": True},
                },
            }}}},
            "responses": {"201": _ok({"allOf": [
                {"$ref": "#/components/schemas/ApiKey"},
                {"type": "object", "properties": {"key": {"type": "string", "description": "Full API key (shown only once)"}}},
            ]}), "400": _400},
        },
    )
    path("/api-keys/{key_id}",
        parameters=[{"name": "key_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        delete={
            "tags": ["API Keys"], "summary": "Delete an API key", "security": _auth_security,
            "responses": {"200": _deleted_resp, "403": _403, "404": _404},
        },
    )

    # ── Available Permissions ─────────────────────────────────────
    path("/permissions/available", get={
        "tags": ["Permissions"], "summary": "List all available permissions", "security": _auth_security,
        "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
            "key": {"type": "string"}, "name": {"type": "string"},
        }}}), "401": _401, "403": _403},
    })

    # ── Products ─────────────────────────────────────────────────

    # Products
    path("/products",
        get={
            "tags": ["Products"], "summary": "List all products", "security": _auth_security,
            "parameters": _pagination_params,
            "responses": {"200": _paginated("Product")},
        },
        post={
            "tags": ["Products"], "summary": "Create a product", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name"],
                "properties": {
                    "name": {"type": "string"}, "description": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("Product"), "400": _400, "409": _409},
        },
    )
    path("/products/{product_id}",
        parameters=[{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Products"], "summary": "Get a product with children", "security": _auth_security,
            "responses": {"200": _ok({"allOf": [
                {"$ref": "#/components/schemas/Product"},
                {"type": "object", "properties": {
                    "boards": {"type": "array", "items": {"$ref": "#/components/schemas/Board"}},
                    "firmwareBuilds": {"type": "array", "items": {"$ref": "#/components/schemas/FirmwareBuild"}},
                }},
            ]}), "404": _404},
        },
        put={
            "tags": ["Products"], "summary": "Update a product", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"}, "description": {"type": "string"},
                },
            }}}},
            "responses": {"200": _ok("Product"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Products"], "summary": "Delete a product (must be archived first)", "security": _auth_security,
            "responses": {"200": _deleted_resp, "400": _400, "404": _404, "409": _409},
        },
    )
    path("/products/{product_id}/archive",
        parameters=[{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Products"], "summary": "Archive a product", "security": _auth_security,
            "responses": {"200": _ok("Product"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/products/{product_id}/unarchive",
        parameters=[{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Products"], "summary": "Unarchive a product", "security": _auth_security,
            "responses": {"200": _ok("Product"), "400": _400, "404": _404},
        },
    )
    path("/products/{product_id}/export",
        parameters=[{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Products"], "summary": "Export product data (not yet implemented)", "security": _auth_security,
            "responses": {"501": {"description": "Not implemented"}, "404": _404},
        },
    )

    # ── Boards ───────────────────────────────────────────────────
    path("/products/{product_id}/boards",
        parameters=[{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Boards"], "summary": "List boards for a product", "security": _auth_security,
            "responses": {"200": _ok("Board", array=True), "404": _404},
        },
        post={
            "tags": ["Boards"], "summary": "Create a board", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name"],
                "properties": {
                    "name": {"type": "string"}, "description": {"type": "string"},
                    "active": {"type": "boolean", "default": True},
                },
            }}}},
            "responses": {"201": _ok("Board"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/products/{product_id}/boards/{board_id}",
        parameters=[
            {"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "board_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        get={
            "tags": ["Boards"], "summary": "Get a board with revisions", "security": _auth_security,
            "responses": {"200": _ok({"allOf": [
                {"$ref": "#/components/schemas/Board"},
                {"type": "object", "properties": {
                    "revisions": {"type": "array", "items": {"$ref": "#/components/schemas/BoardRevision"}},
                }},
            ]}), "404": _404},
        },
        put={
            "tags": ["Boards"], "summary": "Update a board", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"}, "description": {"type": "string"},
                    "active": {"type": "boolean"},
                },
            }}}},
            "responses": {"200": _ok("Board"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Boards"], "summary": "Delete a board", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )

    # ── Board Revisions (nested under boards) ────────────────────
    path("/products/{product_id}/boards/{board_id}/revisions",
        parameters=[
            {"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "board_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        post={
            "tags": ["Board Revisions"], "summary": "Create a board revision", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["version"],
                "properties": {
                    "version": {"type": "string"},
                    "status": {"type": "string", "enum": ["ACTIVE", "DEPRECATED", "EOL"], "default": "ACTIVE"},
                    "notes": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("BoardRevision"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/products/{product_id}/boards/{board_id}/revisions/{revision_id}",
        parameters=[
            {"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "board_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "revision_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        put={
            "tags": ["Board Revisions"], "summary": "Update a board revision", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "version": {"type": "string"},
                    "status": {"type": "string", "enum": ["ACTIVE", "DEPRECATED", "EOL"]},
                    "notes": {"type": "string"},
                },
            }}}},
            "responses": {"200": _ok("BoardRevision"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Board Revisions"], "summary": "Delete a board revision", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404},
        },
    )

    # ── Firmware Builds ──────────────────────────────────────────
    path("/products/{product_id}/firmware-builds",
        parameters=[{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Firmware Builds"], "summary": "List firmware builds for a product", "security": _auth_security,
            "parameters": [
                {"name": "targetId", "in": "query", "schema": {"type": "string"}},
                {"name": "status", "in": "query", "schema": {"type": "string", "enum": ["DRAFT", "RELEASED", "DEPRECATED"]}},
                {"name": "isManufacturing", "in": "query", "schema": {"type": "boolean"}},
            ] + _pagination_params,
            "responses": {"200": _ok("FirmwareBuild", array=True), "404": _404},
        },
    )
    path("/products/{product_id}/firmware-builds/upload",
        parameters=[{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Firmware Builds"], "summary": "Upload a firmware build", "security": _auth_security,
            "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                "type": "object", "required": ["file", "targetId", "version"],
                "properties": {
                    "file": {"type": "string", "format": "binary"},
                    "modemFile": {"type": "string", "format": "binary"},
                    "targetId": {"type": "string"}, "version": {"type": "string"},
                    "isManufacturing": {"type": "boolean"},
                    "status": {"type": "string", "enum": ["DRAFT", "RELEASED", "DEPRECATED"]},
                    "notes": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("FirmwareBuild"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/products/{product_id}/firmware-builds/{build_id}",
        parameters=[
            {"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "build_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        put={
            "tags": ["Firmware Builds"], "summary": "Update a firmware build", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "status": {"type": "string", "enum": ["DRAFT", "RELEASED", "DEPRECATED"]},
                    "notes": {"type": "string"},
                },
            }}}},
            "responses": {"200": _ok("FirmwareBuild"), "400": _400, "404": _404},
        },
        delete={
            "tags": ["Firmware Builds"], "summary": "Delete a firmware build", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404},
        },
    )
    path("/products/firmware-builds/{build_id}/download",
        parameters=[{"name": "build_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Firmware Builds"], "summary": "Get firmware build download URL", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {
                "url": {"type": "string", "format": "uri"},
                "filename": {"type": "string"},
            }}), "404": _404},
        },
    )

    # ── Cluster ─────────────────────────────────────────────────
    _ns_param = {"name": "namespace", "in": "query", "schema": {"type": "string"}, "description": "Filter by namespace"}
    _k8s_limit_param = {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 500, "maximum": 1000}}
    _ns_path_param = {"name": "namespace", "in": "path", "required": True, "schema": {"type": "string"}}
    _name_path_param = {"name": "name", "in": "path", "required": True, "schema": {"type": "string"}}

    path("/cluster", get={
        "tags": ["Cluster"], "summary": "Get cluster overview", "security": _auth_security,
        "responses": {"200": _ok({"type": "object", "properties": {
            "kubernetesVersion": {"type": "string"},
            "platforms": {"type": "array", "items": {"type": "string"}},
            "nodeCount": {"type": "integer"},
            "namespaceCount": {"type": "integer"},
            "resources": {"type": "object", "properties": {
                "pods": {"type": "object", "properties": {
                    "running": {"type": "integer"}, "pending": {"type": "integer"},
                    "failed": {"type": "integer"}, "succeeded": {"type": "integer"},
                    "total": {"type": "integer"},
                }},
                "deployments": {"type": "object", "properties": {
                    "available": {"type": "integer"}, "progressing": {"type": "integer"},
                    "total": {"type": "integer"},
                }},
                "services": {"type": "object", "properties": {
                    "total": {"type": "integer"},
                }},
                "jobs": {"type": "object", "properties": {
                    "active": {"type": "integer"}, "succeeded": {"type": "integer"},
                    "failed": {"type": "integer"}, "total": {"type": "integer"},
                }},
            }},
        }}), "401": _401, "403": _403},
    })
    path("/kubernetes/namespaces", get={
        "tags": ["Cluster"], "summary": "List namespaces", "security": _auth_security,
        "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "status": {"type": "string"},
            "createdAt": {"type": "string", "format": "date-time"},
            "age": {"type": "string"},
        }}}), "401": _401, "403": _403},
    })
    path("/kubernetes/nodes",
        get={
            "tags": ["Cluster"], "summary": "List nodes", "security": _auth_security,
            "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"},
                "status": {"type": "string"},
                "roles": {"type": "array", "items": {"type": "string"}},
                "internalIp": {"type": "string"},
                "osImage": {"type": "string"},
                "kubeletVersion": {"type": "string"},
                "containerRuntime": {"type": "string"},
                "architecture": {"type": "string"},
                "capacity": {"type": "object"},
                "allocatable": {"type": "object"},
                "conditions": {"type": "array", "items": {"type": "object"}},
                "labels": {"type": "object"},
                "annotations": {"type": "object"},
                "taints": {"type": "array", "items": {"type": "object"}},
                "unschedulable": {"type": "boolean"},
                "createdAt": {"type": "string", "format": "date-time"},
                "age": {"type": "string"},
            }}}), "401": _401, "403": _403},
        },
    )
    path("/kubernetes/nodes/{node_name}",
        parameters=[{"name": "node_name", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Cluster"], "summary": "Get node details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Node detail object"}), "404": _404},
        },
    )
    path("/kubernetes/events", get={
        "tags": ["Cluster"], "summary": "List cluster events", "security": _auth_security,
        "parameters": [
            _ns_param,
            {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 500, "maximum": 1000}},
        ],
        "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
            "type": {"type": "string"},
            "reason": {"type": "string"},
            "message": {"type": "string"},
            "object": {"type": "string"},
            "namespace": {"type": "string"},
            "count": {"type": "integer"},
            "firstSeen": {"type": "string", "format": "date-time", "nullable": True},
            "lastSeen": {"type": "string", "format": "date-time", "nullable": True},
            "source": {"type": "string"},
        }}}), "401": _401, "403": _403},
    })
    path("/kubernetes/pods",
        get={
            "tags": ["Cluster"], "summary": "List pods", "security": _auth_security,
            "parameters": [_ns_param, _k8s_limit_param],
            "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"},
                "namespace": {"type": "string"},
                "status": {"type": "string"},
                "ready": {"type": "string"},
                "restarts": {"type": "integer"},
                "nodeName": {"type": "string"},
                "podIp": {"type": "string"},
                "containers": {"type": "array", "items": {"type": "object"}},
                "createdAt": {"type": "string", "format": "date-time"},
                "age": {"type": "string"},
            }}}), "401": _401, "403": _403},
        },
    )
    path("/kubernetes/pods/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["Cluster"], "summary": "Get pod details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Pod detail object"}), "404": _404},
        },
        delete={
            "tags": ["Cluster"], "summary": "Delete a pod", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {"deleted": {"type": "boolean"}}}), "404": _404},
        },
    )
    path("/kubernetes/deployments",
        get={
            "tags": ["Cluster"], "summary": "List deployments", "security": _auth_security,
            "parameters": [_ns_param, _k8s_limit_param],
            "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"},
                "namespace": {"type": "string"},
                "replicas": {"type": "object", "properties": {
                    "desired": {"type": "integer"}, "ready": {"type": "integer"},
                    "available": {"type": "integer"}, "updated": {"type": "integer"},
                }},
                "strategy": {"type": "string"},
                "containers": {"type": "array", "items": {"type": "object", "properties": {
                    "name": {"type": "string"}, "image": {"type": "string"},
                }}},
                "conditions": {"type": "array", "items": {"type": "object"}},
                "labels": {"type": "object"},
                "annotations": {"type": "object"},
                "selector": {"type": "object"},
                "createdAt": {"type": "string", "format": "date-time"},
                "age": {"type": "string"},
            }}}), "401": _401, "403": _403},
        },
    )
    path("/kubernetes/deployments/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["Cluster"], "summary": "Get deployment details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Deployment detail object"}), "404": _404},
        },
    )
    path("/kubernetes/deployments/{namespace}/{name}/scale",
        parameters=[_ns_path_param, _name_path_param],
        post={
            "tags": ["Cluster"], "summary": "Scale a deployment", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["replicas"],
                "properties": {"replicas": {"type": "integer", "minimum": 0, "maximum": 100}},
            }}}},
            "responses": {
                "200": _ok({"type": "object", "properties": {
                    "scaled": {"type": "boolean"}, "replicas": {"type": "integer"},
                }}),
                "400": _400, "404": _404,
            },
        },
    )
    path("/kubernetes/deployments/{namespace}/{name}/restart",
        parameters=[_ns_path_param, _name_path_param],
        post={
            "tags": ["Cluster"], "summary": "Restart a deployment", "security": _auth_security,
            "responses": {
                "200": _ok({"type": "object", "properties": {"restarted": {"type": "boolean"}}}),
                "404": _404,
            },
        },
    )
    path("/kubernetes/services",
        get={
            "tags": ["Cluster"], "summary": "List services", "security": _auth_security,
            "parameters": [_ns_param, _k8s_limit_param],
            "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"},
                "namespace": {"type": "string"},
                "type": {"type": "string"},
                "clusterIp": {"type": "string"},
                "externalIps": {"type": "array", "items": {"type": "string"}},
                "loadBalancerIp": {"type": "string", "nullable": True},
                "ports": {"type": "array", "items": {"type": "object", "properties": {
                    "name": {"type": "string"}, "port": {"type": "integer"},
                    "targetPort": {"type": "string"}, "protocol": {"type": "string"},
                    "nodePort": {"type": "integer", "nullable": True},
                }}},
                "selector": {"type": "object"},
                "createdAt": {"type": "string", "format": "date-time"},
                "age": {"type": "string"},
            }}}), "401": _401, "403": _403},
        },
    )
    path("/kubernetes/services/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["Cluster"], "summary": "Get service details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Service detail object"}), "404": _404},
        },
    )
    path("/kubernetes/jobs",
        get={
            "tags": ["Cluster"], "summary": "List jobs", "security": _auth_security,
            "parameters": [_ns_param, _k8s_limit_param],
            "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"},
                "namespace": {"type": "string"},
                "completions": {"type": "string"},
                "parallelism": {"type": "integer"},
                "active": {"type": "integer"},
                "succeeded": {"type": "integer"},
                "failed": {"type": "integer"},
                "status": {"type": "string"},
                "duration": {"type": "string"},
                "backoffLimit": {"type": "integer"},
                "conditions": {"type": "array", "items": {"type": "object"}},
                "labels": {"type": "object"},
                "createdAt": {"type": "string", "format": "date-time"},
                "age": {"type": "string"},
            }}}), "401": _401, "403": _403},
        },
    )
    path("/kubernetes/jobs/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["Cluster"], "summary": "Get job details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Job detail object"}), "404": _404},
        },
        delete={
            "tags": ["Cluster"], "summary": "Delete a job", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {"deleted": {"type": "boolean"}}}), "404": _404},
        },
    )
    path("/kubernetes/configmaps",
        get={
            "tags": ["Cluster"], "summary": "List ConfigMaps", "security": _auth_security,
            "parameters": [_ns_param, _k8s_limit_param],
            "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"},
                "namespace": {"type": "string"},
                "dataKeys": {"type": "array", "items": {"type": "string"}},
                "dataCount": {"type": "integer"},
                "createdAt": {"type": "string", "format": "date-time"},
                "age": {"type": "string"},
            }}}), "401": _401, "403": _403},
        },
    )
    path("/kubernetes/configmaps/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["Cluster"], "summary": "Get ConfigMap details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {
                "name": {"type": "string"},
                "namespace": {"type": "string"},
                "dataKeys": {"type": "array", "items": {"type": "string"}},
                "dataCount": {"type": "integer"},
                "data": {"type": "object"},
                "createdAt": {"type": "string", "format": "date-time"},
                "age": {"type": "string"},
            }}), "404": _404},
        },
    )
    path("/kubernetes/secrets",
        get={
            "tags": ["Cluster"], "summary": "List Secrets", "security": _auth_security,
            "parameters": [_ns_param, _k8s_limit_param],
            "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"},
                "namespace": {"type": "string"},
                "type": {"type": "string"},
                "dataKeys": {"type": "array", "items": {"type": "string"}},
                "dataCount": {"type": "integer"},
                "createdAt": {"type": "string", "format": "date-time"},
                "age": {"type": "string"},
            }}}), "401": _401, "403": _403},
        },
    )
    path("/kubernetes/secrets/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["Cluster"], "summary": "Get Secret details (values masked)", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {
                "name": {"type": "string"},
                "namespace": {"type": "string"},
                "type": {"type": "string"},
                "dataKeys": {"type": "array", "items": {"type": "string"}},
                "dataCount": {"type": "integer"},
                "data": {"type": "object", "description": "Values are masked (first 4 chars + ****)"},
                "createdAt": {"type": "string", "format": "date-time"},
                "age": {"type": "string"},
            }}), "404": _404},
        },
    )
    path("/kubernetes/resources/{kind}/{namespace}/{name}",
        parameters=[
            {"name": "kind", "in": "path", "required": True, "schema": {"type": "string"}, "description": "Resource kind (e.g. pod, deployment, service, job, configmap, secret)"},
            _ns_path_param, _name_path_param,
        ],
        get={
            "tags": ["Cluster"], "summary": "Get resource YAML", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Raw resource YAML as object"}), "400": _400, "404": _404},
        },
        put={
            "tags": ["Cluster"], "summary": "Apply resource YAML", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["yaml"],
                "properties": {"yaml": {"type": "string", "description": "YAML string (max 100KB)"}},
            }}}},
            "responses": {"200": _ok({"type": "object", "description": "Updated resource object"}), "400": _400, "404": _404},
        },
        delete={
            "tags": ["Cluster"], "summary": "Delete a resource", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {"deleted": {"type": "boolean"}}}), "400": _400, "404": _404},
        },
    )
    path("/kubernetes/rbac/roles", get={
        "tags": ["Cluster"], "summary": "List Roles", "security": _auth_security,
        "parameters": [_ns_param, _k8s_limit_param],
        "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "namespace": {"type": "string"},
            "rules": {"type": "array", "items": {"type": "object", "properties": {
                "apiGroups": {"type": "array", "items": {"type": "string"}},
                "resources": {"type": "array", "items": {"type": "string"}},
                "verbs": {"type": "array", "items": {"type": "string"}},
                "resourceNames": {"type": "array", "items": {"type": "string"}},
            }}},
            "labels": {"type": "object"},
            "createdAt": {"type": "string", "format": "date-time"},
            "age": {"type": "string"},
        }}}), "401": _401, "403": _403},
    })
    path("/kubernetes/rbac/clusterroles", get={
        "tags": ["Cluster"], "summary": "List ClusterRoles", "security": _auth_security,
        "parameters": [_k8s_limit_param],
        "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "namespace": {"type": "string"},
            "rules": {"type": "array", "items": {"type": "object"}},
            "labels": {"type": "object"},
            "createdAt": {"type": "string", "format": "date-time"},
            "age": {"type": "string"},
        }}}), "401": _401, "403": _403},
    })
    path("/kubernetes/rbac/bindings", get={
        "tags": ["Cluster"], "summary": "List RoleBindings", "security": _auth_security,
        "parameters": [_ns_param, _k8s_limit_param],
        "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "namespace": {"type": "string"},
            "roleRef": {"type": "object", "properties": {
                "kind": {"type": "string"}, "name": {"type": "string"},
            }},
            "subjects": {"type": "array", "items": {"type": "object", "properties": {
                "kind": {"type": "string"}, "name": {"type": "string"}, "namespace": {"type": "string"},
            }}},
            "createdAt": {"type": "string", "format": "date-time"},
            "age": {"type": "string"},
        }}}), "401": _401, "403": _403},
    })
    path("/kubernetes/rbac/clusterrolebindings", get={
        "tags": ["Cluster"], "summary": "List ClusterRoleBindings", "security": _auth_security,
        "parameters": [_k8s_limit_param],
        "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "namespace": {"type": "string"},
            "roleRef": {"type": "object", "properties": {
                "kind": {"type": "string"}, "name": {"type": "string"},
            }},
            "subjects": {"type": "array", "items": {"type": "object", "properties": {
                "kind": {"type": "string"}, "name": {"type": "string"}, "namespace": {"type": "string"},
            }}},
            "createdAt": {"type": "string", "format": "date-time"},
            "age": {"type": "string"},
        }}}), "401": _401, "403": _403},
    })
    path("/kubernetes/rbac/serviceaccounts", get={
        "tags": ["Cluster"], "summary": "List ServiceAccounts", "security": _auth_security,
        "parameters": [_ns_param, _k8s_limit_param],
        "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "namespace": {"type": "string"},
            "secrets": {"type": "array", "items": {"type": "string"}},
            "labels": {"type": "object"},
            "createdAt": {"type": "string", "format": "date-time"},
            "age": {"type": "string"},
        }}}), "401": _401, "403": _403},
    })

    # ── System / Audit History ──────────────────────────────────
    path("/system/history", get={
        "tags": ["System"], "summary": "List audit log entries", "security": _auth_security,
        "parameters": [
            {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
            {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50, "maximum": 100}},
            {"name": "userId", "in": "query", "schema": {"type": "string"}},
            {"name": "entityType", "in": "query", "schema": {"type": "string"}},
            {"name": "action", "in": "query", "schema": {"type": "string"}},
            {"name": "from", "in": "query", "schema": {"type": "string", "format": "date-time"}},
            {"name": "to", "in": "query", "schema": {"type": "string", "format": "date-time"}},
        ],
        "responses": {"200": _ok({"type": "object", "properties": {
            "entries": {"type": "array", "items": {"$ref": "#/components/schemas/AuditLogEntry"}},
            "pagination": {"type": "object", "properties": {
                "page": {"type": "integer"}, "limit": {"type": "integer"},
                "total": {"type": "integer"}, "pages": {"type": "integer"},
            }},
        }}), "401": _401, "403": _403},
    })
    path("/system/history/{entry_id}",
        parameters=[{"name": "entry_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["System"], "summary": "Get a single audit log entry", "security": _auth_security,
            "responses": {"200": _ok("AuditLogEntry"), "404": _404},
        },
    )

    # ── Nodes ──────────────────────────────────────────────────
    path("/nodes",
        get={
            "tags": ["Nodes"], "summary": "List registered nodes", "security": _auth_security,
            "parameters": _pagination_params + [
                {"name": "type", "in": "query", "schema": {"type": "string", "enum": ["MANUFACTURING", "VALIDATION"]}},
            ],
            "responses": {"200": _paginated("ConcordNode"), "401": _401, "403": _403},
        },
        post={
            "tags": ["Nodes"], "summary": "Create a node", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name", "hostname", "type"],
                "properties": {
                    "name": {"type": "string"}, "hostname": {"type": "string"},
                    "type": {"type": "string", "enum": ["MANUFACTURING", "VALIDATION"]},
                    "ipAddress": {"type": "string"}, "hardwareRevision": {"type": "string"},
                    "metadata": {"type": "object"},
                },
            }}}},
            "responses": {"201": _ok("ConcordNode"), "400": _400, "409": _409},
        },
    )
    path("/nodes/sync", post={
        "tags": ["Nodes"], "summary": "Sync nodes from K8s cluster", "security": _auth_security,
        "responses": {"200": _ok({"type": "object", "properties": {
            "registered": {"type": "array", "items": {"type": "object"}},
            "discovered": {"type": "array", "items": {"type": "object", "properties": {
                "hostname": {"type": "string"}, "ip": {"type": "string"},
                "arch": {"type": "string"}, "labels": {"type": "object"},
            }}},
            "offline": {"type": "array", "items": {"type": "object"}},
        }}), "401": _401, "403": _403},
    })
    path("/nodes/{node_id}",
        parameters=[{"name": "node_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Nodes"], "summary": "Get a node", "security": _auth_security,
            "responses": {"200": _ok("ConcordNode"), "404": _404},
        },
        put={
            "tags": ["Nodes"], "summary": "Update a node", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["MANUFACTURING", "VALIDATION"]},
                    "status": {"type": "string", "enum": ["ONLINE", "OFFLINE", "MAINTENANCE", "ERROR"]},
                    "ipAddress": {"type": "string", "nullable": True},
                    "hardwareRevision": {"type": "string", "nullable": True},
                    "metadata": {"type": "object", "nullable": True},
                },
            }}}},
            "responses": {"200": _ok("ConcordNode"), "400": _400, "404": _404},
        },
        delete={
            "tags": ["Nodes"], "summary": "Delete a node", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )
    path("/nodes/{node_id}/health",
        parameters=[{"name": "node_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Nodes"], "summary": "Check node health via gRPC", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {
                "nodeId": {"type": "string"}, "healthy": {"type": "boolean"},
                "status": {"type": "string"}, "details": {"type": "object"},
            }}), "404": _404},
        },
    )
    path("/nodes/{node_id}/register",
        parameters=[{"name": "node_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Nodes"], "summary": "Register a discovered node (apply K8s labels)", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["hostname", "type"],
                "properties": {
                    "hostname": {"type": "string"},
                    "type": {"type": "string", "enum": ["MANUFACTURING", "VALIDATION"]},
                    "name": {"type": "string"}, "ip": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("ConcordNode"), "400": _400, "409": _409},
        },
    )

    # ── Fixtures ───────────────────────────────────────────────
    path("/fixtures",
        get={
            "tags": ["Fixtures"], "summary": "List fixtures", "security": _auth_security,
            "parameters": _pagination_params + [
                {"name": "type", "in": "query", "schema": {"type": "string", "enum": ["MANUFACTURING", "VALIDATION"]}},
                {"name": "productId", "in": "query", "schema": {"type": "string"}},
            ],
            "responses": {"200": _paginated("Fixture"), "401": _401, "403": _403},
        },
        post={
            "tags": ["Fixtures"], "summary": "Create a fixture", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name", "productId", "type"],
                "properties": {
                    "name": {"type": "string"}, "productId": {"type": "string"},
                    "type": {"type": "string", "enum": ["MANUFACTURING", "VALIDATION"]},
                    "description": {"type": "string"}, "metadata": {"type": "object"},
                    "slots": {"type": "array", "items": {"type": "object", "properties": {
                        "slotIndex": {"type": "integer"}, "label": {"type": "string"},
                    }}},
                },
            }}}},
            "responses": {"201": _ok("Fixture"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/fixtures/{fixture_id}",
        parameters=[{"name": "fixture_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Fixtures"], "summary": "Get a fixture with slots", "security": _auth_security,
            "responses": {"200": _ok("Fixture"), "404": _404},
        },
        put={
            "tags": ["Fixtures"], "summary": "Update a fixture", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"}, "description": {"type": "string", "nullable": True},
                    "active": {"type": "boolean"}, "metadata": {"type": "object", "nullable": True},
                },
            }}}},
            "responses": {"200": _ok("Fixture"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Fixtures"], "summary": "Delete a fixture", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )
    path("/fixtures/{fixture_id}/slots",
        parameters=[{"name": "fixture_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Fixture Slots"], "summary": "Create a slot", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["slotIndex"],
                "properties": {
                    "slotIndex": {"type": "integer", "minimum": 0},
                    "label": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("FixtureSlot"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/fixtures/{fixture_id}/slots/{slot_id}",
        parameters=[
            {"name": "fixture_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "slot_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        put={
            "tags": ["Fixture Slots"], "summary": "Update a slot", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "label": {"type": "string", "nullable": True},
                    "active": {"type": "boolean"},
                },
            }}}},
            "responses": {"200": _ok("FixtureSlot"), "400": _400, "404": _404},
        },
        delete={
            "tags": ["Fixture Slots"], "summary": "Delete a slot", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )
    path("/fixtures/{fixture_id}/slots/{slot_id}/assign",
        parameters=[
            {"name": "fixture_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "slot_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        post={
            "tags": ["Fixture Slots"], "summary": "Assign or unassign a node to a slot", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "nodeId": {"type": "string", "nullable": True, "description": "Node ID to assign, or null to unassign"},
                },
            }}}},
            "responses": {"200": _ok("FixtureSlot"), "400": _400, "404": _404, "409": _409},
        },
    )

    # ── Dashboard ──────────────────────────────────────────────
    path("/dashboard/overview", get={
        "tags": ["Dashboard"], "summary": "Get dashboard overview with all fixtures and computed health", "security": _auth_security,
        "responses": {"200": _ok("DashboardFixture", array=True), "401": _401, "403": _403},
    })

    # ── Managed Deployments ──────────────────────────────────────
    path("/kubernetes/managed-deployments",
        get={
            "tags": ["Managed Deployments"], "summary": "List managed deployments", "security": _auth_security,
            "parameters": _pagination_params + [
                {"name": "fixtureId", "in": "query", "schema": {"type": "string"}, "description": "Filter by fixture ID"},
            ],
            "responses": {"200": _paginated("ConcordDeployment"), "401": _401, "403": _403},
        },
        post={
            "tags": ["Managed Deployments"], "summary": "Create a deployment", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name", "fixtureId"],
                "properties": {
                    "name": {"type": "string"}, "fixtureId": {"type": "string"},
                    "config": {"type": "object"}, "version": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("ConcordDeployment"), "400": _400, "404": _404},
        },
    )
    path("/kubernetes/managed-deployments/{deployment_id}",
        parameters=[{"name": "deployment_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Managed Deployments"], "summary": "Get a deployment", "security": _auth_security,
            "responses": {"200": _ok("ConcordDeployment"), "404": _404},
        },
        delete={
            "tags": ["Managed Deployments"], "summary": "Delete a deployment", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )
    path("/kubernetes/managed-deployments/{deployment_id}/deploy",
        parameters=[{"name": "deployment_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Managed Deployments"], "summary": "Deploy a fixture to K8s", "security": _auth_security,
            "responses": {"200": _ok("ConcordDeployment"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/kubernetes/managed-deployments/{deployment_id}/stop",
        parameters=[{"name": "deployment_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Managed Deployments"], "summary": "Stop a running deployment", "security": _auth_security,
            "responses": {"200": _ok("ConcordDeployment"), "404": _404, "409": _409},
        },
    )
    path("/kubernetes/managed-deployments/{deployment_id}/restart",
        parameters=[{"name": "deployment_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Managed Deployments"], "summary": "Restart a running deployment", "security": _auth_security,
            "responses": {"200": _ok("ConcordDeployment"), "404": _404, "409": _409},
        },
    )
    path("/kubernetes/managed-deployments/{deployment_id}/status",
        parameters=[{"name": "deployment_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Managed Deployments"], "summary": "Get deployment status with K8s pod info", "security": _auth_security,
            "responses": {"200": _ok({"allOf": [
                {"$ref": "#/components/schemas/ConcordDeployment"},
                {"type": "object", "properties": {
                    "k8sStatus": {"type": "array", "items": {"type": "object", "properties": {
                        "name": {"type": "string"}, "slotIndex": {"type": "integer"},
                        "status": {"nullable": True, "type": "object", "properties": {
                            "name": {"type": "string"}, "replicas": {"type": "integer"},
                            "readyReplicas": {"type": "integer"}, "availableReplicas": {"type": "integer"},
                            "pods": {"type": "array", "items": {"type": "object", "properties": {
                                "name": {"type": "string"}, "nodeName": {"type": "string"},
                                "status": {"type": "string"}, "ready": {"type": "boolean"},
                                "restarts": {"type": "integer"},
                            }}},
                        }},
                    }}},
                }},
            ]}), "404": _404},
        },
    )

    # ── Validation ──────────────────────────────────────────────
    path("/validation/tests/run", post={
        "tags": ["Validation"], "summary": "Run validation tests", "security": _auth_security,
        "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
            "type": "object", "required": ["product", "file"],
            "properties": {
                "product": {"type": "string"},
                "file": {"type": "string", "format": "binary", "description": "ZIP file with firmware"},
            },
        }}}},
        "responses": {"201": _ok({"type": "object", "properties": {
            "message": {"type": "string"}, "product": {"type": "string"},
            "build_job_id": {"type": "string"}, "firmware_path": {"type": "string"},
            "jobs": {"type": "array", "items": {"type": "object", "properties": {
                "job_id": {"type": "string"}, "test_type": {"type": "string"},
                "status": {"type": "string", "enum": ["CREATED", "FAILED"]}, "k8s_job_name": {"type": "string"},
            }}},
        }}), "400": _400},
    })

    # ── Validation Runs ──────────────────────────────────────────
    path("/sessions",
        get={
            "tags": ["Validation"], "summary": "List validation runs", "security": _auth_security,
            "parameters": _pagination_params + [
                {"name": "status", "in": "query", "schema": {"type": "string", "enum": ["ACTIVE", "COMPLETED", "CANCELLED", "PAUSED"]}},
            ],
            "responses": {"200": _paginated("ValidationRun"), "401": _401, "403": _403},
        },
        post={
            "tags": ["Validation"], "summary": "Create a validation run", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name", "productId", "nodeId", "serialNumber"],
                "properties": {
                    "name": {"type": "string"},
                    "productId": {"type": "string"},
                    "nodeId": {"type": "string"},
                    "serialNumber": {"type": "string"},
                    "firmwareVariant": {"type": "string", "nullable": True},
                    "config": {"type": "object", "nullable": True},
                    "notes": {"type": "string", "nullable": True},
                    "testFilter": {"type": "array", "items": {"type": "string"}, "nullable": True},
                },
            }}}},
            "responses": {"201": _ok("ValidationRun"), "400": _400, "404": _404},
        },
    )
    path("/sessions/{run_id}",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Validation"], "summary": "Get a validation run", "security": _auth_security,
            "responses": {"200": _ok("ValidationRun"), "401": _401, "404": _404},
        },
    )
    path("/sessions/{run_id}/cancel",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Validation"], "summary": "Cancel a validation run", "security": _auth_security,
            "responses": {"200": _ok("ValidationRun"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/sessions/{run_id}/trigger",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Validation"], "summary": "Trigger a K8s validation job", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["firmwareVersion"],
                "properties": {
                    "firmwareVersion": {"type": "string", "description": "Firmware version to validate"},
                    "firmwarePath": {"type": "string", "nullable": True, "description": "MinIO path if already uploaded"},
                    "config": {"type": "object", "nullable": True, "description": "Override job config"},
                },
            }}}},
            "responses": {
                "200": _ok({"type": "object", "properties": {
                    "jobName": {"type": "string"},
                    "runId": {"type": "string"},
                }}),
                "400": _400, "404": _404, "500": _500,
            },
        },
    )
    path("/sessions/{run_id}/executions",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Validation"], "summary": "List executions for a run", "security": _auth_security,
            "parameters": _pagination_params,
            "responses": {"200": _paginated("ValidationExecution"), "401": _401, "404": _404},
        },
    )
    path("/sessions/{run_id}/executions/{execution_id}/results",
        parameters=[
            {"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "execution_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        get={
            "tags": ["Validation"], "summary": "List results for an execution", "security": _auth_security,
            "responses": {"200": _ok("ValidationResult", array=True), "401": _401, "404": _404},
        },
    )
    path("/sessions/{run_id}/artifacts",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Validation"], "summary": "List artifacts for a run", "security": _auth_security,
            "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"},
                "sizeBytes": {"type": "integer"},
                "lastModified": {"type": "string", "format": "date-time", "nullable": True},
            }}}), "401": _401, "404": _404},
        },
    )
    path("/sessions/{run_id}/artifacts/{name}",
        parameters=[
            {"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "name", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        get={
            "tags": ["Validation"], "summary": "Download a run artifact", "security": _auth_security,
            "responses": {"302": {"description": "Redirect to presigned download URL"}, "404": _404},
        },
    )

    # ── Validation Reporter (internal, API-key auth) ─────────
    path("/sessions/{run_id}/report/start",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Validation"], "summary": "Report run started (pytest reporter)", "security": [{"ApiKeyAuth": []}],
            "responses": {"200": _ok({"type": "object", "properties": {"status": {"type": "string"}}}), "404": _404},
        },
    )
    path("/sessions/{run_id}/report/test-start",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Validation"], "summary": "Report test started (pytest reporter)", "security": [{"ApiKeyAuth": []}],
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["testName"],
                "properties": {
                    "testName": {"type": "string"},
                    "module": {"type": "string", "nullable": True},
                },
            }}}},
            "responses": {"200": _ok({"type": "object", "properties": {"executionId": {"type": "string"}, "status": {"type": "string"}}}), "400": _400, "404": _404},
        },
    )
    path("/sessions/{run_id}/report/test-result",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Validation"], "summary": "Report test result (pytest reporter)", "security": [{"ApiKeyAuth": []}],
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["testName", "passed"],
                "properties": {
                    "testName": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "durationS": {"type": "number", "nullable": True},
                    "errorMessage": {"type": "string", "nullable": True},
                    "measurements": {"type": "object", "nullable": True},
                },
            }}}},
            "responses": {"200": _ok({"type": "object", "properties": {"resultId": {"type": "string"}, "status": {"type": "string"}}}), "400": _400, "404": _404},
        },
    )
    path("/sessions/{run_id}/report/finish",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Validation"], "summary": "Report run finished (pytest reporter)", "security": [{"ApiKeyAuth": []}],
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["total", "passed", "failed"],
                "properties": {
                    "total": {"type": "integer", "minimum": 0},
                    "passed": {"type": "integer", "minimum": 0},
                    "failed": {"type": "integer", "minimum": 0},
                    "errors": {"type": "integer", "minimum": 0, "default": 0},
                    "durationS": {"type": "number", "nullable": True},
                },
            }}}},
            "responses": {"200": _ok({"type": "object", "properties": {"status": {"type": "string"}}}), "400": _400, "404": _404},
        },
    )
    path("/sessions/{run_id}/report/log-chunk",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Validation"], "summary": "Report log chunk (pytest reporter)", "security": [{"ApiKeyAuth": []}],
            "description": "Receive log chunks from test runner, store in MinIO, and broadcast via WebSocket.",
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["file", "offset", "data"],
                "properties": {
                    "file": {"type": "string", "description": "Relative log file path (e.g., tests/test_boot/output.log)"},
                    "offset": {"type": "integer", "minimum": 0, "description": "Byte offset for this chunk"},
                    "data": {"type": "string", "description": "Base64-encoded log data"},
                    "timestamp": {"type": "integer", "nullable": True, "description": "Unix timestamp in milliseconds"},
                },
            }}}},
            "responses": {"200": _ok({"type": "object", "properties": {"received": {"type": "boolean"}}}), "400": _400, "404": _404},
        },
    )
    path("/sessions/{run_id}/logs/{file_path}",
        parameters=[
            {"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "file_path", "in": "path", "required": True, "schema": {"type": "string"}, "description": "Relative log file path"},
            {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}, "description": "Byte offset for partial read"},
        ],
        get={
            "tags": ["Validation"], "summary": "Get log file with offset support",
            "description": "Fetch log file with optional offset for reconnection scenarios. Returns raw bytes with X-Offset and X-Total-Size headers.",
            "responses": {
                "200": {"description": "Log file content", "content": {"text/plain": {"schema": {"type": "string", "format": "binary"}}},
                    "headers": {
                        "X-Offset": {"schema": {"type": "integer"}, "description": "Byte offset of returned content"},
                        "X-Total-Size": {"schema": {"type": "integer"}, "description": "Total file size in bytes"},
                    }},
                "404": _404,
            },
        },
    )
    path("/sessions/{run_id}/download",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Validation"], "summary": "Download run as ZIP",
            "description": "Generate ZIP archive on-demand (if not cached) and return presigned URL for download.",
            "responses": {"200": _ok({"type": "object", "properties": {"url": {"type": "string", "format": "uri"}}}), "404": _404},
        },
    )
    path("/sessions/{run_id}/manifest",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Validation"], "summary": "Get run manifest",
            "description": "Return the manifest.json for the run, containing metadata about configuration, tests, and artifacts.",
            "responses": {"200": _ok({"type": "object", "properties": {
                "runId": {"type": "string"},
                "name": {"type": "string"},
                "status": {"type": "string"},
                "productId": {"type": "string"},
                "config": {"type": "object"},
                "startedAt": {"type": "string", "format": "date-time", "nullable": True},
                "finishedAt": {"type": "string", "format": "date-time", "nullable": True},
                "device": {"type": "object", "nullable": True, "properties": {
                    "id": {"type": "string"},
                    "serialNumber": {"type": "string"},
                    "status": {"type": "string"},
                }},
                "executions": {"type": "array", "items": {"type": "object", "properties": {
                    "testId": {"type": "string"},
                    "testName": {"type": "string"},
                    "status": {"type": "string"},
                }}},
                "passedCount": {"type": "integer"},
                "failedCount": {"type": "integer"},
                "completedCount": {"type": "integer"},
            }}), "404": _404},
        },
    )

    # ── Benches ─────────────────────────────────────────────────
    spec.components.schema("TestBench", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "stationId": {"type": "string"},
            "name": {"type": "string"},
            "mtibAddress": {"type": "string"},
            "mtibRevision": {"type": "string", "nullable": True},
            "fixtureDesignId": {"type": "string", "nullable": True},
            "profileOverrides": {"type": "object", "nullable": True},
            "capabilities": {"type": "array", "items": {"type": "string"}},
            "dutProduct": {"type": "string"},
            "dutRevision": {"type": "string"},
            "dutDeviceId": {"type": "string", "nullable": True},
            "dutSnr": {"type": "string", "nullable": True},
            "dutImei": {"type": "string", "nullable": True},
            "dutIccids": {"type": "array", "items": {"type": "string"}},
            "jlinkAppSerial": {"type": "string", "nullable": True},
            "jlinkCommsSerial": {"type": "string", "nullable": True},
            "uartAppPath": {"type": "string", "nullable": True},
            "uartCommsPath": {"type": "string", "nullable": True},
            "status": {"type": "string", "enum": ["AVAILABLE", "LOCKED", "OFFLINE", "MAINTENANCE"]},
            "lockedBy": {"type": "string", "nullable": True},
            "lockedAt": {"type": "string", "format": "date-time", "nullable": True},
            "lastHealthCheck": {"type": "string", "format": "date-time", "nullable": True},
            "metadata": {"type": "object", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
            "fixtureDesign": {"type": "object", "nullable": True, "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "product": {"type": "string"},
                "revision": {"type": "string"},
                "capabilities": {"type": "array", "items": {"type": "string"}},
            }},
            "profilePath": {"type": "string", "description": "Computed path for K8s job profile loading"},
        },
    })
    spec.components.schema("FixtureProfile", {
        "type": "object",
        "description": "Merged fixture profile for validation tests, combining design template + bench overrides + DUT info",
        "properties": {
            "station_id": {"type": "string", "description": "Test bench station identifier"},
            "capabilities": {"type": "array", "items": {"type": "string"}},
            "dut": {"type": "object", "properties": {
                "device_id": {"type": "string"},
                "snr": {"type": "string"},
                "imei": {"type": "string"},
                "iccids": {"type": "array", "items": {"type": "string"}},
            }},
            "uart_app_path": {"type": "string", "nullable": True},
            "uart_comms_path": {"type": "string", "nullable": True},
            "jlink_app_serial": {"type": "string", "nullable": True},
            "jlink_comms_serial": {"type": "string", "nullable": True},
        },
        "additionalProperties": True,
    })

    path("/fixtures/benches",
        get={
            "tags": ["Benches"], "summary": "List test benches", "security": _auth_security,
            "parameters": _pagination_params + [
                {"name": "product", "in": "query", "schema": {"type": "string"}, "description": "Filter by DUT product"},
                {"name": "status", "in": "query", "schema": {"type": "string", "enum": ["AVAILABLE", "LOCKED", "OFFLINE", "MAINTENANCE"]}},
                {"name": "capability", "in": "query", "schema": {"type": "array", "items": {"type": "string"}}, "description": "Filter by required capabilities"},
            ],
            "responses": {"200": _paginated("TestBench"), "401": _401, "403": _403},
        },
        post={
            "tags": ["Benches"], "summary": "Create a test bench", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["stationId", "name", "mtibAddress", "dutProduct", "dutRevision"],
                "properties": {
                    "stationId": {"type": "string"},
                    "name": {"type": "string"},
                    "mtibAddress": {"type": "string"},
                    "mtibRevision": {"type": "string"},
                    "fixtureDesignId": {"type": "string"},
                    "profileOverrides": {"type": "object"},
                    "capabilities": {"type": "array", "items": {"type": "string"}},
                    "dutProduct": {"type": "string"},
                    "dutRevision": {"type": "string"},
                    "dutDeviceId": {"type": "string"},
                    "dutSnr": {"type": "string"},
                    "dutImei": {"type": "string"},
                    "dutIccids": {"type": "array", "items": {"type": "string"}},
                    "jlinkAppSerial": {"type": "string"},
                    "jlinkCommsSerial": {"type": "string"},
                    "uartAppPath": {"type": "string"},
                    "uartCommsPath": {"type": "string"},
                    "metadata": {"type": "object"},
                },
            }}}},
            "responses": {"201": _ok("TestBench"), "400": _400, "409": _409},
        },
    )
    path("/fixtures/benches/discover",
        get={
            "tags": ["Benches"], "summary": "Discover unregistered MTIBs", "security": _auth_security,
            "description": "Find K8s nodes with MTIB label that are not yet registered as test benches.",
            "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
                "hostname": {"type": "string"},
                "ip": {"type": "string"},
                "mtibAddress": {"type": "string"},
                "labels": {"type": "object"},
                "hardwareRevision": {"type": "string", "nullable": True},
                "ready": {"type": "boolean"},
            }}}), "401": _401},
        },
    )
    path("/fixtures/benches/{bench_id}",
        parameters=[{"name": "bench_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Benches"], "summary": "Get test bench details", "security": _auth_security,
            "responses": {"200": _ok("TestBench"), "401": _401, "404": _404},
        },
        patch={
            "tags": ["Benches"], "summary": "Update a test bench", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "mtibAddress": {"type": "string"},
                    "mtibRevision": {"type": "string"},
                    "fixtureDesignId": {"type": "string"},
                    "profileOverrides": {"type": "object"},
                    "capabilities": {"type": "array", "items": {"type": "string"}},
                    "dutDeviceId": {"type": "string"},
                    "dutSnr": {"type": "string"},
                    "dutImei": {"type": "string"},
                    "dutIccids": {"type": "array", "items": {"type": "string"}},
                    "status": {"type": "string", "enum": ["AVAILABLE", "OFFLINE", "MAINTENANCE"]},
                    "metadata": {"type": "object"},
                },
            }}}},
            "responses": {"200": _ok("TestBench"), "400": _400, "404": _404},
        },
        delete={
            "tags": ["Benches"], "summary": "Delete a test bench", "security": _auth_security,
            "responses": {"200": _deleted_resp, "400": _400, "404": _404},
        },
    )
    path("/fixtures/benches/{bench_id}/lock",
        parameters=[{"name": "bench_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Benches"], "summary": "Lock a test bench for exclusive use", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["lockedBy"],
                "properties": {"lockedBy": {"type": "string", "description": "Build run or job ID acquiring the lock"}},
            }}}},
            "responses": {"200": _ok("TestBench"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/fixtures/benches/{bench_id}/unlock",
        parameters=[{"name": "bench_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Benches"], "summary": "Release a test bench lock", "security": _auth_security,
            "responses": {"200": _ok("TestBench"), "400": _400, "404": _404},
        },
    )
    path("/fixtures/benches/{bench_id}/profile",
        parameters=[{"name": "bench_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Benches"], "summary": "Get merged fixture profile for a test bench", "security": _auth_security,
            "description": (
                "Returns the complete fixture profile for a test bench, merging:\n"
                "1. FixtureDesign.profileTemplate (base hardware config)\n"
                "2. TestBench.profileOverrides (bench-specific overrides)\n"
                "3. TestBench DUT info (device_id, snr, imei, iccids)\n\n"
                "This is the profile that validation tests should use."
            ),
            "responses": {"200": _ok("FixtureProfile"), "401": _401, "404": _404},
        },
    )

    # ── Builds ──────────────────────────────────────────────────
    spec.components.schema("BuildJob", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "product": {"type": "string"},
            "board": {"type": "string"},
            "target": {"type": "string"},
            "variant": {"type": "string"},
            "mtibRev": {"type": "string"},
            "branch": {"type": "string"},
            "commitSha": {"type": "string", "nullable": True},
            "status": {"type": "string", "enum": ["QUEUED", "BUILDING", "SUCCESS", "FAILED", "CANCELLED"]},
            "versionString": {"type": "string", "nullable": True},
            "buildNum": {"type": "integer"},
            "errorMessage": {"type": "string", "nullable": True},
            "startedAt": {"type": "string", "format": "date-time", "nullable": True},
            "finishedAt": {"type": "string", "format": "date-time", "nullable": True},
            "durationSeconds": {"type": "integer", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "artifacts": {"type": "array", "items": {"$ref": "#/components/schemas/BuildArtifact"}},
        },
    })
    spec.components.schema("BuildArtifact", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "storageKey": {"type": "string"},
            "sizeBytes": {"type": "integer"},
            "checksum": {"type": "string"},
            "downloadUrl": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("BuildRun", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "product": {"type": "string"},
            "branch": {"type": "string"},
            "commitSha": {"type": "string", "nullable": True},
            "variant": {"type": "string"},
            "status": {"type": "string", "enum": ["PENDING", "RUNNING", "SUCCESS", "FAILED"]},
            "stages": {"type": "array", "items": {"type": "object"}},
            "buildJob": {"$ref": "#/components/schemas/BuildJob"},
            "runId": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
        },
    })

    path("/builds/webhooks/bitbucket", post={
        "tags": ["Builds"], "summary": "Bitbucket webhook receiver (HMAC-validated)", "security": [],
        "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
        "responses": {"200": _ok({"type": "object", "properties": {"triggered": {"type": "boolean"}, "buildJobId": {"type": "string"}}}), "400": _400},
    })
    path("/builds/trigger", post={
        "tags": ["Builds"], "summary": "Manual build run trigger",
        "requestBody": {"required": True, "content": {"application/json": {"schema": {
            "type": "object", "required": ["productId", "repoSlug", "branch"],
            "properties": {
                "productId": {"type": "string"},
                "repoSlug": {"type": "string"},
                "branch": {"type": "string"},
                "variant": {"type": "string", "default": "debug"},
                "mtibRev": {"type": "string", "default": "1.2"},
                "commitSha": {"type": "string", "nullable": True},
            },
        }}}},
        "responses": {"201": _ok({"type": "object", "properties": {"buildJobId": {"type": "string"}, "runId": {"type": "string", "nullable": True}}}), "400": _400, "404": _404},
    })
    path("/builds", get={
        "tags": ["Builds"], "summary": "List builds",
        "parameters": [
            {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
            {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
            {"name": "product", "in": "query", "schema": {"type": "string"}},
            {"name": "branch", "in": "query", "schema": {"type": "string"}},
            {"name": "status", "in": "query", "schema": {"type": "string"}},
        ],
        "responses": {"200": _paginated({"$ref": "#/components/schemas/BuildJob"})},
    })
    path("/builds/{build_id}", get={
        "tags": ["Builds"], "summary": "Build detail",
        "parameters": [{"name": "build_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": _ok({"$ref": "#/components/schemas/BuildJob"}), "404": _404},
    })
    path("/builds/{build_id}/artifacts", get={
        "tags": ["Builds"], "summary": "Build artifacts with download URLs",
        "parameters": [{"name": "build_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": _ok({"type": "array", "items": {"$ref": "#/components/schemas/BuildArtifact"}}), "404": _404},
    })
    path("/builds/{build_id}/log", get={
        "tags": ["Builds"], "summary": "Build log content",
        "parameters": [{"name": "build_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": _ok({"type": "object", "properties": {"log": {"type": "string"}}}), "404": _404},
    })
    path("/builds/runs", get={
        "tags": ["Builds"], "summary": "List build runs (build -> validate chains)",
        "parameters": [
            {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
            {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
            {"name": "product", "in": "query", "schema": {"type": "string"}},
            {"name": "branch", "in": "query", "schema": {"type": "string"}},
        ],
        "responses": {"200": _paginated({"$ref": "#/components/schemas/BuildRun"})},
    })
    path("/builds/runs/{run_id}", get={
        "tags": ["Builds"], "summary": "Build run detail with stages",
        "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": _ok({"$ref": "#/components/schemas/BuildRun"}), "404": _404},
    })

    # ── Health ──────────────────────────────────────────────────
    path("/healthcheck", get={
        "tags": ["Health"], "summary": "Health check", "security": [],
        "responses": {"200": {"description": "Service is healthy"}},
    })

    return spec


def get_spec() -> APISpec:
    """Get or build the cached OpenAPI spec."""
    global _spec
    if _spec is None:
        _spec = _build_spec()
    return _spec


def openapi_spec():
    """Serve the OpenAPI spec as JSON."""
    return jsonify(get_spec().to_dict())


SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Concord API Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <style>
    body { margin: 0; background: #fafafa; }
    .swagger-ui .topbar { display: none; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({
      url: "/v2/openapi.json",
      dom_id: "#swagger-ui",
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: "BaseLayout",
      deepLinking: true,
    });
  </script>
</body>
</html>
"""


def swagger_ui():
    """Serve the Swagger UI page."""
    return SWAGGER_HTML, 200, {"Content-Type": "text/html"}
