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
                "Concord platform API for managing hardware, codebases, releases, and device testing.\n\n"
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
            "category": {"type": "string", "enum": ["SOM", "CARRIER_BOARD", "ACCESSORY"]},
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
                "hardwareRevisionId": {"type": "string"},
                "quantity": {"type": "integer"},
                "hardwareRevision": {"type": "object", "properties": {
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
        "required": ["hardwareRevisionId", "quantity"],
        "properties": {
            "hardwareRevisionId": {"type": "string"},
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
    _auth_security = [{"BearerAuth": []}, {"ApiKeyAuth": []}]

    # ── Tags ────────────────────────────────────────────────────
    for tag in [
        "Auth", "Users", "Permission Sets", "API Keys", "Permissions",
        "Hardware Components", "Hardware Assemblies", "Hardware Image",
        "Codebases", "Releases", "Artifacts", "MTIB", "Admin", "Validation", "Health",
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

    # ── Hardware Components ─────────────────────────────────────
    path("/hardware/components",
        get={
            "tags": ["Hardware Components"], "summary": "List all components", "security": _auth_security,
            "responses": {"200": _ok("Component", array=True)},
        },
        post={
            "tags": ["Hardware Components"], "summary": "Create a component", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name", "category", "manufacturer", "partNumber"],
                "properties": {
                    "name": {"type": "string"}, "category": {"type": "string", "enum": ["SOM", "CARRIER_BOARD", "ACCESSORY"]},
                    "manufacturer": {"type": "string"}, "partNumber": {"type": "string"}, "description": {"type": "string"},
                },
            }}}},
            "responses": {"201": _ok("Component"), "400": _400, "409": _409},
        },
    )
    path("/hardware/components/{component_id}",
        parameters=[{"name": "component_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Hardware Components"], "summary": "Get a component with revisions", "security": _auth_security,
            "responses": {"200": _ok({"allOf": [
                {"$ref": "#/components/schemas/Component"},
                {"type": "object", "properties": {"revisions": {"type": "array", "items": {"$ref": "#/components/schemas/ComponentRevision"}}}},
            ]}), "404": _404},
        },
        put={
            "tags": ["Hardware Components"], "summary": "Update a component", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {
                    "name": {"type": "string"}, "category": {"type": "string", "enum": ["SOM", "CARRIER_BOARD", "ACCESSORY"]},
                    "manufacturer": {"type": "string"}, "partNumber": {"type": "string"}, "description": {"type": "string"},
                },
            }}}},
            "responses": {"200": _ok("Component"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Hardware Components"], "summary": "Delete a component", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )
    path("/hardware/components/{component_id}/image",
        parameters=[{"name": "component_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Hardware Components"], "summary": "Upload component image", "security": _auth_security,
            "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                "type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}},
            }}}},
            "responses": {"200": _ok("Component"), "400": _400, "404": _404},
        },
    )
    path("/hardware/components/{component_id}/revisions",
        parameters=[{"name": "component_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Hardware Components"], "summary": "Create a component revision", "security": _auth_security,
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
    path("/hardware/components/{component_id}/revisions/{revision_id}",
        parameters=[
            {"name": "component_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "revision_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        put={
            "tags": ["Hardware Components"], "summary": "Update a component revision", "security": _auth_security,
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
            "tags": ["Hardware Components"], "summary": "Delete a component revision", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404, "409": _409},
        },
    )

    # ── Hardware Assemblies ─────────────────────────────────────
    path("/hardware/assemblies",
        get={
            "tags": ["Hardware Assemblies"], "summary": "List all assemblies", "security": _auth_security,
            "responses": {"200": _ok("Assembly", array=True)},
        },
        post={
            "tags": ["Hardware Assemblies"], "summary": "Create an assembly", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "required": ["name"],
                "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
            }}}},
            "responses": {"201": _ok("Assembly"), "400": _400, "409": _409},
        },
    )
    path("/hardware/assemblies/{assembly_id}",
        parameters=[{"name": "assembly_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        get={
            "tags": ["Hardware Assemblies"], "summary": "Get an assembly with revisions and BOM", "security": _auth_security,
            "responses": {"200": _ok({"allOf": [
                {"$ref": "#/components/schemas/Assembly"},
                {"type": "object", "properties": {"revisions": {"type": "array", "items": {"$ref": "#/components/schemas/AssemblyRevision"}}}},
            ]}), "404": _404},
        },
        put={
            "tags": ["Hardware Assemblies"], "summary": "Update an assembly", "security": _auth_security,
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
            }}}},
            "responses": {"200": _ok("Assembly"), "400": _400, "404": _404, "409": _409},
        },
        delete={
            "tags": ["Hardware Assemblies"], "summary": "Delete an assembly", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404},
        },
    )
    path("/hardware/assemblies/{assembly_id}/image",
        parameters=[{"name": "assembly_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Hardware Assemblies"], "summary": "Upload assembly image", "security": _auth_security,
            "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                "type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}},
            }}}},
            "responses": {"200": _ok("Assembly"), "400": _400, "404": _404},
        },
    )
    path("/hardware/assemblies/{assembly_id}/revisions",
        parameters=[{"name": "assembly_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        post={
            "tags": ["Hardware Assemblies"], "summary": "Create an assembly revision", "security": _auth_security,
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
    path("/hardware/assemblies/{assembly_id}/revisions/{revision_id}",
        parameters=[
            {"name": "assembly_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "revision_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        put={
            "tags": ["Hardware Assemblies"], "summary": "Update an assembly revision", "security": _auth_security,
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
            "tags": ["Hardware Assemblies"], "summary": "Delete an assembly revision", "security": _auth_security,
            "responses": {"200": _deleted_resp, "404": _404},
        },
    )

    # ── Hardware Image ──────────────────────────────────────────
    path("/hardware/image/{key}",
        parameters=[{"name": "key", "in": "path", "required": True, "schema": {"type": "string"}, "description": "Image key, e.g. components/<id>/hero.png"}],
        get={
            "tags": ["Hardware Image"], "summary": "Get hardware image (redirect to storage)", "security": _auth_security,
            "responses": {"302": {"description": "Redirect to presigned image URL"}, "400": _400, "404": _404},
        },
    )

    # ── Codebases ───────────────────────────────────────────────
    path("/codebases",
        get={
            "tags": ["Codebases"], "summary": "List all codebases", "security": _auth_security,
            "responses": {"200": _ok("Codebase", array=True)},
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
            "responses": {"200": _ok("Artifact", array=True), "404": _404},
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
