from apispec import APISpec
from flask import jsonify

# ── Spec singleton ────────────────────────────────────────────
_spec: APISpec | None = None


def _build_spec() -> APISpec:
    spec = APISpec(
        title="Concord API",
        version="2.0.0",
        openapi_version="3.0.3",
        info={
            "description": (
                "Concord platform API for managing inventory, codebases, releases, and device testing.\n\n"
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
    spec.components.schema("Component", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string", "nullable": True},
            "category": {"type": "string", "enum": ["HARDWARE", "MECHANICAL", "CABLE", "ACCESSORY", "OTHER"]},
            "manufacturer": {"type": "string"},
            "partNumber": {"type": "string"},
            "imageKey": {"type": "string", "nullable": True},
            "imageUrl": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
            "revisionCount": {"type": "integer"},
        },
    })
    spec.components.schema("ComponentRevision", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "componentId": {"type": "string"},
            "version": {"type": "string"},
            "status": {"type": "string", "enum": ["ACTIVE", "DEPRECATED", "EOL"]},
            "releaseNotes": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("Assembly", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string", "nullable": True},
            "imageKey": {"type": "string", "nullable": True},
            "imageUrl": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
            "revisionCount": {"type": "integer"},
        },
    })
    spec.components.schema("AssemblyRevision", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "assemblyId": {"type": "string"},
            "version": {"type": "string"},
            "status": {"type": "string", "enum": ["ACTIVE", "DEPRECATED", "EOL"]},
            "releaseNotes": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
            "bom": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string"},
                "inventoryRevisionId": {"type": "string"},
                "quantity": {"type": "integer"},
                "inventoryRevision": {"type": "object", "properties": {
                    "id": {"type": "string"}, "version": {"type": "string"},
                    "component": {"type": "object", "properties": {
                        "id": {"type": "string"}, "name": {"type": "string"}, "category": {"type": "string"},
                    }},
                }},
            }}},
        },
    })
    spec.components.schema("BomItem", {
        "type": "object",
        "required": ["inventoryRevisionId", "quantity"],
        "properties": {
            "inventoryRevisionId": {"type": "string"},
            "quantity": {"type": "integer", "minimum": 1},
        },
    })
    spec.components.schema("Codebase", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string", "nullable": True},
            "repoUrl": {"type": "string", "nullable": True},
            "defaultBranch": {"type": "string"},
            "imageKey": {"type": "string", "nullable": True},
            "imageUrl": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
            "releaseCount": {"type": "integer"},
            "latestRelease": {"nullable": True, "allOf": [{"$ref": "#/components/schemas/Release"}]},
        },
    })
    spec.components.schema("Release", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "codebaseId": {"type": "string"},
            "version": {"type": "string"},
            "status": {"type": "string", "enum": ["DRAFT", "RELEASED", "DEPRECATED"]},
            "releaseNotes": {"type": "string", "nullable": True},
            "tagName": {"type": "string", "nullable": True},
            "releasedAt": {"type": "string", "format": "date-time", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
            "artifactCount": {"type": "integer"},
            "artifacts": {"type": "array", "items": {"$ref": "#/components/schemas/Artifact"}},
        },
    })
    spec.components.schema("Artifact", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "releaseId": {"type": "string"},
            "name": {"type": "string"},
            "filename": {"type": "string", "nullable": True},
            "type": {"type": "string", "enum": ["EXTERNAL", "UPLOAD"]},
            "storageKey": {"type": "string", "nullable": True},
            "externalUrl": {"type": "string", "nullable": True},
            "sizeBytes": {"type": "integer", "nullable": True},
            "checksum": {"type": "string", "nullable": True},
            "contentType": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("Chipset", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "manufacturer": {"type": "string", "nullable": True},
            "isModem": {"type": "boolean"},
            "description": {"type": "string", "nullable": True},
            "active": {"type": "boolean"},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("Product", {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string", "nullable": True},
            "active": {"type": "boolean"},
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
            "chipsets": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string"}, "name": {"type": "string"}, "isModem": {"type": "boolean"},
            }}},
            "selectedBuilds": {"type": "object"},
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
            "chipsetId": {"type": "string"},
            "chipset": {"type": "object", "nullable": True, "properties": {
                "id": {"type": "string"}, "name": {"type": "string"}, "isModem": {"type": "boolean"},
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
    spec.components.schema("MtibSummary", {
        "type": "object",
        "properties": {
            "hostname": {"type": "string"},
            "name": {"type": "string"},
            "type": {"type": "string"},
            "features": {"type": "array", "items": {"type": "string"}},
            "appIdCount": {"type": "integer"},
            "createdAt": {"type": "string", "format": "date-time"},
            "updatedAt": {"type": "string", "format": "date-time"},
        },
    })
    spec.components.schema("MtibDetail", {
        "type": "object",
        "properties": {
            "hostname": {"type": "string"},
            "name": {"type": "string"},
            "type": {"type": "string"},
            "features": {"type": "array", "items": {"type": "string"}},
            "appIds": {"type": "array", "items": {"type": "object", "properties": {
                "jlink": {"type": "integer"}, "appId": {"type": "integer"},
                "appName": {"type": "string"}, "chipset": {"type": "string"},
                "target": {"type": "string"}, "notes": {"type": "string", "nullable": True},
            }}},
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
        return {"description": desc, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}

    _deleted_resp = {"description": "Resource deleted", "content": {"application/json": {"schema": {
        "type": "object", "properties": {
            "data": {"nullable": True, "example": None},
            "errors": {"type": "array", "items": {"$ref": "#/components/schemas/ErrorDetail"}, "example": []},
        },
    }}}}

    def _ok(ref_or_schema, *, array=False):
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
    _auth_security = [{"BearerAuth": []}, {"ApiKeyAuth": []}]

    # ── Pagination helpers ──────────────────────────────────────
    _pagination_params = [
        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50, "maximum": 100}},
    ]

    def _paginated(ref):
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
        "Auth", "Users", "Permission Sets", "API Keys", "Permissions",
        "Inventory Components", "Inventory Assemblies", "Inventory Image",
        "Catalog", "Chipsets", "Boards", "Board Revisions", "Firmware Builds",
        "Codebases", "Releases", "Artifacts", "System", "MTIB", "Admin",
        "Nodes", "Fixtures", "Fixture Slots", "Deployments",
        "Validation", "Health",
    ]:
        spec.tag({"name": tag})

    # ── Helper to add paths ─────────────────────────────────────
    def path(url, **kwargs):
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
    path("/auth/users",
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
    path("/auth/users/{user_id}",
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

    # ── Permission Sets ─────────────────────────────────────────
    path("/auth/permission-sets",
        get={
            "tags": ["Permission Sets"], "summary": "List all permission sets", "security": _auth_security,
            "responses": {"200": _ok("PermissionSet", array=True), "401": _401, "403": _403},
        },
        post={
            "tags": ["Permission Sets"], "summary": "Create a permission set", "security": _auth_security,
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
    path("/auth/permission-sets/{set_id}",
        parameters=[{"name": "set_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        put={
            "tags": ["Permission Sets"], "summary": "Update a permission set", "security": _auth_security,
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
            "tags": ["Permission Sets"], "summary": "Delete a permission set", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )

    # ── API Keys ────────────────────────────────────────────────
    path("/auth/api-keys",
        get={
            "tags": ["API Keys"], "summary": "List API keys",
            "description": "Users see their own keys. Admins with ApiKeys.View see all.",
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
    path("/auth/api-keys/{key_id}",
        parameters=[{"name": "key_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        delete={
            "tags": ["API Keys"], "summary": "Delete an API key", "security": _auth_security,
            "responses": {"200": _deleted_resp, "403": _403, "404": _404},
        },
    )

    # ── Permissions ─────────────────────────────────────────────
    path("/auth/permissions", get={
        "tags": ["Permissions"], "summary": "List all available permissions", "security": _auth_security,
        "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
            "key": {"type": "string"}, "name": {"type": "string"},
        }}}), "401": _401, "403": _403},
    })

    # ── Inventory Components ─────────────────────────────────────
    path("/inventory/components",
        get={
            "tags": ["Inventory Components"], "summary": "List all components", "security": _auth_security,
            "parameters": _pagination_params,
            "responses": {"200": _paginated("Component")},
        },
        post={
            "tags": ["Inventory Components"], "summary": "Create a component", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name", "category", "manufacturer", "partNumber"],
                "properties": {
                    "name": {"type": "string"}, "category": {"type": "string", "enum": ["HARDWARE", "MECHANICAL", "CABLE", "ACCESSORY", "OTHER"]},
                    "manufacturer": {"type": "string"}, "partNumber": {"type": "string"}, "description": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("Component"), "400": _400, "409": _409},
        },
    )
    path("/inventory/components/{component_id}",
        parameters=[{"name": "component_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Inventory Components"], "summary": "Get a component with revisions", "security": _auth_security,
            "responses": {"200": _ok({"allOf": [
                {"$ref": "#/components/schemas/Component"},
                {"type": "object", "properties": {"revisions": {"type": "array", "items": {"$ref": "#/components/schemas/ComponentRevision"}}}},
            ]}), "404": _404},
        },
        put={
            "tags": ["Inventory Components"], "summary": "Update a component", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"}, "category": {"type": "string", "enum": ["HARDWARE", "MECHANICAL", "CABLE", "ACCESSORY", "OTHER"]},
                    "manufacturer": {"type": "string"}, "partNumber": {"type": "string"}, "description": {"type": "string"},
                },
            }}}},
            "responses": {"200": _ok("Component"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Inventory Components"], "summary": "Delete a component", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )
    path("/inventory/components/{component_id}/image",
        parameters=[{"name": "component_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Inventory Components"], "summary": "Upload component image", "security": _auth_security,
            "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                "type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}},
            }}}},
            "responses": {"200": _ok("Component"), "400": _400, "404": _404},
        },
    )
    path("/inventory/components/{component_id}/revisions",
        parameters=[{"name": "component_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Inventory Components"], "summary": "Create a component revision", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["version"],
                "properties": {
                    "version": {"type": "string"},
                    "status": {"type": "string", "enum": ["ACTIVE", "DEPRECATED", "EOL"], "default": "ACTIVE"},
                    "releaseNotes": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("ComponentRevision"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/inventory/components/{component_id}/revisions/{revision_id}",
        parameters=[
            {"name": "component_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "revision_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        put={
            "tags": ["Inventory Components"], "summary": "Update a component revision", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "version": {"type": "string"},
                    "status": {"type": "string", "enum": ["ACTIVE", "DEPRECATED", "EOL"]},
                    "releaseNotes": {"type": "string"},
                },
            }}}},
            "responses": {"200": _ok("ComponentRevision"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Inventory Components"], "summary": "Delete a component revision", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )

    # ── Inventory Assemblies ─────────────────────────────────────
    path("/inventory/assemblies",
        get={
            "tags": ["Inventory Assemblies"], "summary": "List all assemblies", "security": _auth_security,
            "parameters": _pagination_params,
            "responses": {"200": _paginated("Assembly")},
        },
        post={
            "tags": ["Inventory Assemblies"], "summary": "Create an assembly", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name"],
                "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
            }}}},
            "responses": {"201": _ok("Assembly"), "400": _400, "409": _409},
        },
    )
    path("/inventory/assemblies/{assembly_id}",
        parameters=[{"name": "assembly_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Inventory Assemblies"], "summary": "Get an assembly with revisions and BOM", "security": _auth_security,
            "responses": {"200": _ok({"allOf": [
                {"$ref": "#/components/schemas/Assembly"},
                {"type": "object", "properties": {"revisions": {"type": "array", "items": {"$ref": "#/components/schemas/AssemblyRevision"}}}},
            ]}), "404": _404},
        },
        put={
            "tags": ["Inventory Assemblies"], "summary": "Update an assembly", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
            }}}},
            "responses": {"200": _ok("Assembly"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Inventory Assemblies"], "summary": "Delete an assembly", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404},
        },
    )
    path("/inventory/assemblies/{assembly_id}/image",
        parameters=[{"name": "assembly_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Inventory Assemblies"], "summary": "Upload assembly image", "security": _auth_security,
            "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                "type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}},
            }}}},
            "responses": {"200": _ok("Assembly"), "400": _400, "404": _404},
        },
    )
    path("/inventory/assemblies/{assembly_id}/revisions",
        parameters=[{"name": "assembly_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Inventory Assemblies"], "summary": "Create an assembly revision", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["version"],
                "properties": {
                    "version": {"type": "string"},
                    "status": {"type": "string", "enum": ["ACTIVE", "DEPRECATED", "EOL"], "default": "ACTIVE"},
                    "releaseNotes": {"type": "string"},
                    "bom": {"type": "array", "items": {"$ref": "#/components/schemas/BomItem"}},
                },
            }}}},
            "responses": {"201": _ok("AssemblyRevision"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/inventory/assemblies/{assembly_id}/revisions/{revision_id}",
        parameters=[
            {"name": "assembly_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "revision_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        put={
            "tags": ["Inventory Assemblies"], "summary": "Update an assembly revision", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "version": {"type": "string"},
                    "status": {"type": "string", "enum": ["ACTIVE", "DEPRECATED", "EOL"]},
                    "releaseNotes": {"type": "string"},
                    "bom": {"type": "array", "items": {"$ref": "#/components/schemas/BomItem"}},
                },
            }}}},
            "responses": {"200": _ok("AssemblyRevision"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Inventory Assemblies"], "summary": "Delete an assembly revision", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404},
        },
    )

    # ── Inventory Image ──────────────────────────────────────────
    path("/inventory/image/{key}",
        parameters=[{"name": "key", "in": "path", "required": True, "schema": {"type": "string"}, "description": "Image key, e.g. components/<id>/hero.png"}],
        get={
            "tags": ["Inventory Image"], "summary": "Get inventory image (redirect to storage)", "security": _auth_security,
            "responses": {"302": {"description": "Redirect to presigned image URL"}, "400": _400, "404": _404},
        },
    )

    # ── Codebases ───────────────────────────────────────────────
    path("/codebases",
        get={
            "tags": ["Codebases"], "summary": "List all codebases", "security": _auth_security,
            "parameters": _pagination_params,
            "responses": {"200": _paginated("Codebase")},
        },
        post={
            "tags": ["Codebases"], "summary": "Create a codebase", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name"],
                "properties": {
                    "name": {"type": "string"}, "description": {"type": "string"},
                    "repoUrl": {"type": "string"}, "defaultBranch": {"type": "string", "default": "main"},
                },
            }}}},
            "responses": {"201": _ok("Codebase"), "400": _400, "409": _409},
        },
    )
    path("/codebases/{codebase_id}",
        parameters=[{"name": "codebase_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Codebases"], "summary": "Get a codebase with releases", "security": _auth_security,
            "responses": {"200": _ok({"allOf": [
                {"$ref": "#/components/schemas/Codebase"},
                {"type": "object", "properties": {"releases": {"type": "array", "items": {"$ref": "#/components/schemas/Release"}}}},
            ]}), "404": _404},
        },
        put={
            "tags": ["Codebases"], "summary": "Update a codebase", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"}, "description": {"type": "string"},
                    "repoUrl": {"type": "string"}, "defaultBranch": {"type": "string"},
                },
            }}}},
            "responses": {"200": _ok("Codebase"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Codebases"], "summary": "Delete a codebase", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404},
        },
    )
    path("/codebases/{codebase_id}/image",
        parameters=[{"name": "codebase_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Codebases"], "summary": "Upload codebase image", "security": _auth_security,
            "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                "type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}},
            }}}},
            "responses": {"200": _ok("Codebase"), "400": _400, "404": _404},
        },
    )

    # ── Releases ────────────────────────────────────────────────
    path("/codebases/{codebase_id}/releases",
        parameters=[{"name": "codebase_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Releases"], "summary": "Create a release", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["version"],
                "properties": {
                    "version": {"type": "string"},
                    "status": {"type": "string", "enum": ["DRAFT", "RELEASED", "DEPRECATED"], "default": "DRAFT"},
                    "releaseNotes": {"type": "string"}, "tagName": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("Release"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/codebases/{codebase_id}/releases/{release_id}",
        parameters=[
            {"name": "codebase_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "release_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        put={
            "tags": ["Releases"], "summary": "Update a release", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "version": {"type": "string"},
                    "status": {"type": "string", "enum": ["DRAFT", "RELEASED", "DEPRECATED"]},
                    "releaseNotes": {"type": "string"}, "tagName": {"type": "string"},
                },
            }}}},
            "responses": {"200": _ok("Release"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Releases"], "summary": "Delete a release", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404},
        },
    )

    # ── Artifacts ───────────────────────────────────────────────
    path("/codebases/{codebase_id}/releases/{release_id}/artifacts",
        parameters=[
            {"name": "codebase_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "release_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        get={
            "tags": ["Artifacts"], "summary": "List artifacts for a release", "security": _auth_security,
            "parameters": _pagination_params,
            "responses": {"200": _paginated("Artifact"), "404": _404},
        },
        post={
            "tags": ["Artifacts"], "summary": "Create an artifact (external URL)", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name", "externalUrl"],
                "properties": {"name": {"type": "string"}, "externalUrl": {"type": "string", "format": "uri"}},
            }}}},
            "responses": {"201": _ok("Artifact"), "400": _400, "404": _404},
        },
    )
    path("/codebases/{codebase_id}/releases/{release_id}/artifacts/upload",
        parameters=[
            {"name": "codebase_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "release_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        post={
            "tags": ["Artifacts"], "summary": "Upload an artifact file", "security": _auth_security,
            "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                "type": "object", "required": ["file"],
                "properties": {"file": {"type": "string", "format": "binary"}, "name": {"type": "string"}},
            }}}},
            "responses": {"201": _ok("Artifact"), "400": _400, "404": _404},
        },
    )
    path("/codebases/{codebase_id}/releases/{release_id}/artifacts/{artifact_id}",
        parameters=[
            {"name": "codebase_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "release_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "artifact_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        delete={
            "tags": ["Artifacts"], "summary": "Delete an artifact", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404},
        },
    )
    path("/codebases/artifacts/{artifact_id}/download",
        parameters=[{"name": "artifact_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Artifacts"], "summary": "Get artifact download URL", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {"url": {"type": "string", "format": "uri"}}}), "404": _404},
        },
    )

    # ── Catalog ───────────────────────────────────────────────────

    # Chipsets CRUD
    path("/catalog/chipsets",
        get={
            "tags": ["Chipsets"], "summary": "List all chipsets", "security": _auth_security,
            "parameters": _pagination_params,
            "responses": {"200": _paginated("Chipset")},
        },
        post={
            "tags": ["Chipsets"], "summary": "Create a chipset", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name"],
                "properties": {
                    "name": {"type": "string"}, "manufacturer": {"type": "string"},
                    "isModem": {"type": "boolean", "default": False},
                    "description": {"type": "string"}, "active": {"type": "boolean", "default": True},
                },
            }}}},
            "responses": {"201": _ok("Chipset"), "400": _400, "409": _409},
        },
    )
    path("/catalog/chipsets/{chipset_id}",
        parameters=[{"name": "chipset_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Chipsets"], "summary": "Get a chipset", "security": _auth_security,
            "responses": {"200": _ok("Chipset"), "404": _404},
        },
        put={
            "tags": ["Chipsets"], "summary": "Update a chipset", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"}, "manufacturer": {"type": "string"},
                    "isModem": {"type": "boolean"}, "description": {"type": "string"},
                    "active": {"type": "boolean"},
                },
            }}}},
            "responses": {"200": _ok("Chipset"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Chipsets"], "summary": "Delete a chipset", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )

    # Products
    path("/catalog",
        get={
            "tags": ["Catalog"], "summary": "List all products", "security": _auth_security,
            "parameters": _pagination_params,
            "responses": {"200": _paginated("Product")},
        },
        post={
            "tags": ["Catalog"], "summary": "Create a product", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name"],
                "properties": {
                    "name": {"type": "string"}, "description": {"type": "string"},
                    "active": {"type": "boolean", "default": True},
                },
            }}}},
            "responses": {"201": _ok("Product"), "400": _400, "409": _409},
        },
    )
    path("/catalog/{product_id}",
        parameters=[{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Catalog"], "summary": "Get a product with children", "security": _auth_security,
            "responses": {"200": _ok({"allOf": [
                {"$ref": "#/components/schemas/Product"},
                {"type": "object", "properties": {
                    "boards": {"type": "array", "items": {"$ref": "#/components/schemas/Board"}},
                    "firmwareBuilds": {"type": "array", "items": {"$ref": "#/components/schemas/FirmwareBuild"}},
                }},
            ]}), "404": _404},
        },
        put={
            "tags": ["Catalog"], "summary": "Update a product", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"}, "description": {"type": "string"},
                    "active": {"type": "boolean"},
                },
            }}}},
            "responses": {"200": _ok("Product"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Catalog"], "summary": "Delete a product", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )

    # ── Boards ───────────────────────────────────────────────────
    path("/catalog/{product_id}/boards",
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
    path("/catalog/{product_id}/boards/{board_id}",
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
    path("/catalog/{product_id}/boards/{board_id}/revisions",
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
                    "chipsetIds": {"type": "array", "items": {"type": "string"}},
                    "status": {"type": "string", "enum": ["ACTIVE", "DEPRECATED", "EOL"], "default": "ACTIVE"},
                    "notes": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("BoardRevision"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/catalog/{product_id}/boards/{board_id}/revisions/{revision_id}",
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
                    "chipsetIds": {"type": "array", "items": {"type": "string"}},
                    "selectedBuilds": {"type": "object"},
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
    path("/catalog/{product_id}/firmware-builds",
        parameters=[{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Firmware Builds"], "summary": "List firmware builds for a product", "security": _auth_security,
            "parameters": [
                {"name": "chipsetId", "in": "query", "schema": {"type": "string"}},
                {"name": "status", "in": "query", "schema": {"type": "string", "enum": ["DRAFT", "RELEASED", "DEPRECATED"]}},
                {"name": "isManufacturing", "in": "query", "schema": {"type": "boolean"}},
            ] + _pagination_params,
            "responses": {"200": _ok("FirmwareBuild", array=True), "404": _404},
        },
    )
    path("/catalog/{product_id}/firmware-builds/upload",
        parameters=[{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Firmware Builds"], "summary": "Upload a firmware build", "security": _auth_security,
            "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                "type": "object", "required": ["file", "chipsetId", "version"],
                "properties": {
                    "file": {"type": "string", "format": "binary"},
                    "modemFile": {"type": "string", "format": "binary"},
                    "chipsetId": {"type": "string"}, "version": {"type": "string"},
                    "isManufacturing": {"type": "boolean"},
                    "status": {"type": "string", "enum": ["DRAFT", "RELEASED", "DEPRECATED"]},
                    "notes": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("FirmwareBuild"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/catalog/{product_id}/firmware-builds/{build_id}",
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
    path("/catalog/firmware-builds/{build_id}/download",
        parameters=[{"name": "build_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Firmware Builds"], "summary": "Get firmware build download URL", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {
                "url": {"type": "string", "format": "uri"},
                "filename": {"type": "string"},
            }}), "404": _404},
        },
    )

    # ── System ─────────────────────────────────────────────────
    _ns_param = {"name": "namespace", "in": "query", "schema": {"type": "string"}, "description": "Filter by namespace"}
    _k8s_limit_param = {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 500, "maximum": 1000}}
    _ns_path_param = {"name": "namespace", "in": "path", "required": True, "schema": {"type": "string"}}
    _name_path_param = {"name": "name", "in": "path", "required": True, "schema": {"type": "string"}}

    path("/system/cluster", get={
        "tags": ["System"], "summary": "Get cluster overview", "security": _auth_security,
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
    path("/system/namespaces", get={
        "tags": ["System"], "summary": "List namespaces", "security": _auth_security,
        "responses": {"200": _ok({"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "status": {"type": "string"},
            "createdAt": {"type": "string", "format": "date-time"},
            "age": {"type": "string"},
        }}}), "401": _401, "403": _403},
    })
    path("/system/nodes",
        get={
            "tags": ["System"], "summary": "List nodes", "security": _auth_security,
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
    path("/system/nodes/{node_name}",
        parameters=[{"name": "node_name", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["System"], "summary": "Get node details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Node detail object"}), "404": _404},
        },
    )
    path("/system/events", get={
        "tags": ["System"], "summary": "List cluster events", "security": _auth_security,
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
    path("/system/pods",
        get={
            "tags": ["System"], "summary": "List pods", "security": _auth_security,
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
    path("/system/pods/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["System"], "summary": "Get pod details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Pod detail object"}), "404": _404},
        },
        delete={
            "tags": ["System"], "summary": "Delete a pod", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {"deleted": {"type": "boolean"}}}), "404": _404},
        },
    )
    path("/system/deployments",
        get={
            "tags": ["System"], "summary": "List deployments", "security": _auth_security,
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
    path("/system/deployments/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["System"], "summary": "Get deployment details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Deployment detail object"}), "404": _404},
        },
    )
    path("/system/deployments/{namespace}/{name}/scale",
        parameters=[_ns_path_param, _name_path_param],
        post={
            "tags": ["System"], "summary": "Scale a deployment", "security": _auth_security,
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
    path("/system/deployments/{namespace}/{name}/restart",
        parameters=[_ns_path_param, _name_path_param],
        post={
            "tags": ["System"], "summary": "Restart a deployment", "security": _auth_security,
            "responses": {
                "200": _ok({"type": "object", "properties": {"restarted": {"type": "boolean"}}}),
                "404": _404,
            },
        },
    )
    path("/system/services",
        get={
            "tags": ["System"], "summary": "List services", "security": _auth_security,
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
    path("/system/services/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["System"], "summary": "Get service details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Service detail object"}), "404": _404},
        },
    )
    path("/system/jobs",
        get={
            "tags": ["System"], "summary": "List jobs", "security": _auth_security,
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
    path("/system/jobs/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["System"], "summary": "Get job details", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Job detail object"}), "404": _404},
        },
        delete={
            "tags": ["System"], "summary": "Delete a job", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {"deleted": {"type": "boolean"}}}), "404": _404},
        },
    )
    path("/system/configmaps",
        get={
            "tags": ["System"], "summary": "List ConfigMaps", "security": _auth_security,
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
    path("/system/configmaps/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["System"], "summary": "Get ConfigMap details", "security": _auth_security,
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
    path("/system/secrets",
        get={
            "tags": ["System"], "summary": "List Secrets", "security": _auth_security,
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
    path("/system/secrets/{namespace}/{name}",
        parameters=[_ns_path_param, _name_path_param],
        get={
            "tags": ["System"], "summary": "Get Secret details (values masked)", "security": _auth_security,
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
    path("/system/resources/{kind}/{namespace}/{name}",
        parameters=[
            {"name": "kind", "in": "path", "required": True, "schema": {"type": "string"}, "description": "Resource kind (e.g. pod, deployment, service, job, configmap, secret)"},
            _ns_path_param, _name_path_param,
        ],
        get={
            "tags": ["System"], "summary": "Get resource YAML", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "description": "Raw resource YAML as object"}), "400": _400, "404": _404},
        },
        put={
            "tags": ["System"], "summary": "Apply resource YAML", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["yaml"],
                "properties": {"yaml": {"type": "string", "description": "YAML string (max 100KB)"}},
            }}}},
            "responses": {"200": _ok({"type": "object", "description": "Updated resource object"}), "400": _400, "404": _404},
        },
        delete={
            "tags": ["System"], "summary": "Delete a resource", "security": _auth_security,
            "responses": {"200": _ok({"type": "object", "properties": {"deleted": {"type": "boolean"}}}), "400": _400, "404": _404},
        },
    )
    path("/system/rbac/roles", get={
        "tags": ["System"], "summary": "List Roles", "security": _auth_security,
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
    path("/system/rbac/clusterroles", get={
        "tags": ["System"], "summary": "List ClusterRoles", "security": _auth_security,
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
    path("/system/rbac/bindings", get={
        "tags": ["System"], "summary": "List RoleBindings", "security": _auth_security,
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
    path("/system/rbac/clusterrolebindings", get={
        "tags": ["System"], "summary": "List ClusterRoleBindings", "security": _auth_security,
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
    path("/system/rbac/serviceaccounts", get={
        "tags": ["System"], "summary": "List ServiceAccounts", "security": _auth_security,
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

    # ── MTIB ────────────────────────────────────────────────────
    path("/mtib/list", get={
        "tags": ["MTIB"], "summary": "List all MTIBs", "security": _auth_security,
        "responses": {"200": _ok("MtibSummary", array=True)},
    })
    path("/mtib/get", get={
        "tags": ["MTIB"], "summary": "Get MTIB details", "security": _auth_security,
        "parameters": [{"name": "hostname", "in": "query", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": _ok("MtibDetail"), "400": _400, "404": _404},
    })
    path("/mtib/register", post={
        "tags": ["MTIB"], "summary": "Register an MTIB", "security": _auth_security,
        "requestBody": {"required": True, "content": {"application/json": {"schema": {
            "type": "object", "required": ["name", "hostname", "mtibType", "features", "appIds"],
            "properties": {
                "name": {"type": "string", "description": 'Must start with "verdin-"'},
                "hostname": {"type": "string"},
                "mtibType": {"type": "string", "enum": ["validation", "manufacturing"]},
                "features": {"type": "array", "items": {"type": "string", "enum": ["joulescope", "motion"]}},
                "appIds": {"type": "array", "items": {"type": "object", "required": ["jlink", "appId"], "properties": {
                    "jlink": {"type": "integer"}, "appId": {"type": "integer"},
                }}},
            },
        }}}},
        "responses": {"201": _ok({"type": "object", "properties": {
            "id": {"type": "string"}, "name": {"type": "string"}, "hostname": {"type": "string"},
            "mtibType": {"type": "string"}, "features": {"type": "array", "items": {"type": "string"}},
            "status": {"type": "string"}, "message": {"type": "string"},
        }}), "400": _400, "409": _409},
    })
    path("/mtib/unregister", post={
        "tags": ["MTIB"], "summary": "Unregister an MTIB", "security": _auth_security,
        "requestBody": {"required": True, "content": {"application/json": {"schema": {
            "type": "object", "required": ["hostname"],
            "properties": {"hostname": {"type": "string"}},
        }}}},
        "responses": {"200": _ok({"type": "object", "properties": {
            "hostname": {"type": "string"}, "status": {"type": "string"}, "message": {"type": "string"},
        }}), "400": _400, "404": _404},
    })

    # ── Admin ───────────────────────────────────────────────────
    path("/admin/history", get={
        "tags": ["Admin"], "summary": "List audit log entries", "security": _auth_security,
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
    path("/admin/history/{entry_id}",
        parameters=[{"name": "entry_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Admin"], "summary": "Get a single audit log entry", "security": _auth_security,
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

    # ── Deployments (managed) ──────────────────────────────────
    path("/deployments",
        get={
            "tags": ["Deployments"], "summary": "List managed deployments", "security": _auth_security,
            "parameters": _pagination_params + [
                {"name": "fixtureId", "in": "query", "schema": {"type": "string"}, "description": "Filter by fixture ID"},
            ],
            "responses": {"200": _paginated("ConcordDeployment"), "401": _401, "403": _403},
        },
        post={
            "tags": ["Deployments"], "summary": "Create a deployment", "security": _auth_security,
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
    path("/deployments/{deployment_id}",
        parameters=[{"name": "deployment_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Deployments"], "summary": "Get a deployment", "security": _auth_security,
            "responses": {"200": _ok("ConcordDeployment"), "404": _404},
        },
        delete={
            "tags": ["Deployments"], "summary": "Delete a deployment", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )
    path("/deployments/{deployment_id}/deploy",
        parameters=[{"name": "deployment_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Deployments"], "summary": "Deploy a fixture to K8s", "security": _auth_security,
            "responses": {"200": _ok("ConcordDeployment"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/deployments/{deployment_id}/stop",
        parameters=[{"name": "deployment_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Deployments"], "summary": "Stop a running deployment", "security": _auth_security,
            "responses": {"200": _ok("ConcordDeployment"), "404": _404, "409": _409},
        },
    )
    path("/deployments/{deployment_id}/restart",
        parameters=[{"name": "deployment_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Deployments"], "summary": "Restart a running deployment", "security": _auth_security,
            "responses": {"200": _ok("ConcordDeployment"), "404": _404, "409": _409},
        },
    )
    path("/deployments/{deployment_id}/status",
        parameters=[{"name": "deployment_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Deployments"], "summary": "Get deployment status with K8s pod info", "security": _auth_security,
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
    path("/validation/runs",
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
    path("/validation/runs/{run_id}",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Validation"], "summary": "Get a validation run", "security": _auth_security,
            "responses": {"200": _ok("ValidationRun"), "401": _401, "404": _404},
        },
    )
    path("/validation/runs/{run_id}/cancel",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Validation"], "summary": "Cancel a validation run", "security": _auth_security,
            "responses": {"200": _ok("ValidationRun"), "400": _400, "404": _404, "409": _409},
        },
    )
    path("/validation/runs/{run_id}/trigger",
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
    path("/validation/runs/{run_id}/executions",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Validation"], "summary": "List executions for a run", "security": _auth_security,
            "parameters": _pagination_params,
            "responses": {"200": _paginated("ValidationExecution"), "401": _401, "404": _404},
        },
    )
    path("/validation/runs/{run_id}/executions/{execution_id}/results",
        parameters=[
            {"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "execution_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        get={
            "tags": ["Validation"], "summary": "List results for an execution", "security": _auth_security,
            "responses": {"200": _ok("ValidationResult", array=True), "401": _401, "404": _404},
        },
    )
    path("/validation/runs/{run_id}/artifacts",
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
    path("/validation/runs/{run_id}/artifacts/{name}",
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
    path("/validation/runs/{run_id}/report/start",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Validation"], "summary": "Report run started (pytest reporter)", "security": [{"ApiKeyAuth": []}],
            "responses": {"200": _ok({"type": "object", "properties": {"status": {"type": "string"}}}), "404": _404},
        },
    )
    path("/validation/runs/{run_id}/report/test-start",
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
    path("/validation/runs/{run_id}/report/test-result",
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
    path("/validation/runs/{run_id}/report/finish",
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
    path("/validation/runs/{run_id}/report/log-chunk",
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
    path("/validation/runs/{run_id}/logs/{file_path}",
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
    path("/validation/runs/{run_id}/download",
        parameters=[{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Validation"], "summary": "Download run as ZIP",
            "description": "Generate ZIP archive on-demand (if not cached) and return presigned URL for download.",
            "responses": {"200": _ok({"type": "object", "properties": {"url": {"type": "string", "format": "uri"}}}), "404": _404},
        },
    )
    path("/validation/runs/{run_id}/manifest",
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

    # ── CI / Builds ────────────────────────────────────────────
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
            "artifacts": {"type": "array", "items": {"$ref": "#/components/schemas/BuildJobArtifact"}},
        },
    })
    spec.components.schema("BuildJobArtifact", {
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
    spec.components.schema("Pipeline", {
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

    path("/ci/webhooks/bitbucket", post={
        "tags": ["CI"], "summary": "Bitbucket webhook receiver (HMAC-validated)", "security": [],
        "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
        "responses": {"200": _ok({"type": "object", "properties": {"triggered": {"type": "boolean"}, "buildJobId": {"type": "string"}}}), "400": _400},
    })
    path("/ci/trigger", post={
        "tags": ["CI"], "summary": "Manual pipeline trigger",
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
    path("/ci/builds", get={
        "tags": ["CI"], "summary": "List builds",
        "parameters": [
            {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
            {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
            {"name": "product", "in": "query", "schema": {"type": "string"}},
            {"name": "branch", "in": "query", "schema": {"type": "string"}},
            {"name": "status", "in": "query", "schema": {"type": "string"}},
        ],
        "responses": {"200": _paginated({"$ref": "#/components/schemas/BuildJob"})},
    })
    path("/ci/builds/{build_id}", get={
        "tags": ["CI"], "summary": "Build detail",
        "parameters": [{"name": "build_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": _ok({"$ref": "#/components/schemas/BuildJob"}), "404": _404},
    })
    path("/ci/builds/{build_id}/artifacts", get={
        "tags": ["CI"], "summary": "Build artifacts with download URLs",
        "parameters": [{"name": "build_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": _ok({"type": "array", "items": {"$ref": "#/components/schemas/BuildJobArtifact"}}), "404": _404},
    })
    path("/ci/builds/{build_id}/log", get={
        "tags": ["CI"], "summary": "Build log content",
        "parameters": [{"name": "build_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": _ok({"type": "object", "properties": {"log": {"type": "string"}}}), "404": _404},
    })
    path("/ci/pipelines", get={
        "tags": ["CI"], "summary": "List pipelines (build → flash → validate chains)",
        "parameters": [
            {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
            {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
            {"name": "product", "in": "query", "schema": {"type": "string"}},
            {"name": "branch", "in": "query", "schema": {"type": "string"}},
        ],
        "responses": {"200": _paginated({"$ref": "#/components/schemas/Pipeline"})},
    })
    path("/ci/pipelines/{pipeline_id}", get={
        "tags": ["CI"], "summary": "Pipeline detail with stages",
        "parameters": [{"name": "pipeline_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": _ok({"$ref": "#/components/schemas/Pipeline"}), "404": _404},
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
