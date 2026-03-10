# Build Service Architecture

> Headless firmware build orchestrator. Triggered by Bitbucket webhooks,
> stores artifacts in MinIO, queryable by HTTP API. All functionality
> exposed as a **library** wrapped by gRPC and HTTP interfaces.

---

## 1. Design Principles

1. **Library-first** — All business logic lives in `BuildEngine` (a plain
   Python class). gRPC and HTTP servers are thin wrappers that call the
   same library methods. No logic in the transport layer.
2. **Follow MTIB pattern** — Same project layout as `apps/edge/mtib-server`:
   `src/services/` for hardware/domain, `src/providers/` for transport.
3. **Artifact immutability** — Once a build is stored in MinIO, it is never
   overwritten. Each build has a unique key: `{product}/{variant}/{version}/{build_num}`.
4. **Webhook-driven** — Bitbucket POST webhooks trigger builds. The service
   validates HMAC signatures before processing.
5. **Idempotent** — Re-triggering a build for the same commit + config
   returns the existing artifact rather than rebuilding.

---

## 2. Repository Layout

```
libs/protocols/build/
    build.proto              # gRPC service + message definitions
    build_pb2.py             # Generated Python stubs
    build_pb2_grpc.py        # Generated gRPC stubs
    build_pb2.pyi            # Type stubs

apps/backend/build/
    setup.py
    src/
        main.py              # Entrypoint: starts gRPC + HTTP servers
        engine/
            __init__.py
            build_engine.py  # Core library — ALL business logic here
            types.py         # BuildRequest, BuildResult, ArtifactRef dataclasses
            firmware.py      # west build invocation, hex→cfw conversion
            storage.py       # MinIO upload/download/query
            webhooks.py      # Bitbucket webhook parsing + HMAC validation
        providers/
            grpc_server.py   # gRPC transport wrapper
            http_server.py   # HTTP/REST transport wrapper (Flask)
        config.py            # EnvConfig subclass
    tests/
    deploy/
        Dockerfile
        deployment.yaml
```

### Why This Layout

- `engine/` is the library. It has zero transport dependencies (no grpc,
  no flask imports). It operates on dataclasses and returns dataclasses.
- `providers/grpc_server.py` imports `engine/` and maps gRPC requests to
  engine method calls.
- `providers/http_server.py` imports `engine/` and maps HTTP requests to
  the same engine method calls.
- Either server can run standalone or both can run in the same process
  (default: both, on different ports).

---

## 3. Core Library: `BuildEngine`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class BuildRequest:
    """Input to a firmware build."""
    product: str              # "alpha", "sigma5"
    firmware_type: str        # "alpha_fw", "alpha_mfg_fw"
    variant: str              # "release", "debug"
    git_ref: str              # commit SHA or branch name
    build_num: int            # BUILD_NUM to inject
    is_manufacturing: bool    # IS_MANUFACTURING flag
    mtib_rev: str = "1.2"    # MTIB hardware revision
    triggered_by: str = ""   # PR number, webhook ID, or manual

@dataclass
class ArtifactRef:
    """Reference to a stored build artifact."""
    bucket: str
    key: str                  # e.g. "alpha/alpha_fw/debug/0.8.3/109.0.8.3-ED.cfw"
    version_string: str       # e.g. "109.0.8.3-ED"
    app_id: int
    major: int
    minor: int
    build: int
    track: str
    size_bytes: int
    sha256: str

@dataclass
class BuildResult:
    """Output of a firmware build."""
    request: BuildRequest
    commit_sha: str
    artifacts: list[ArtifactRef]  # 2 CFW files (app + comms) minimum
    hex_artifacts: list[ArtifactRef]  # Raw hex files for J-Link
    build_log_key: str        # MinIO key for build stdout/stderr
    duration_s: float
    success: bool
    error: Optional[str] = None


class BuildEngine:
    """Firmware build orchestrator. Transport-agnostic.

    This is the core library. gRPC and HTTP servers are thin wrappers.
    """

    def __init__(self, config: "BuildConfig"):
        self.config = config
        self._storage = StorageClient(config)

    # -- Build operations --

    def build(self, req: BuildRequest) -> BuildResult:
        """Build firmware. Returns artifacts stored in MinIO.

        Idempotent: if artifacts for this commit+config already exist,
        returns them without rebuilding.
        """

    def build_pair(self, req: BuildRequest) -> tuple[BuildResult, BuildResult]:
        """Build same firmware twice with consecutive build numbers.

        Used for "same code, different version" FUOTA validation.
        Returns (result_N, result_N+1).
        """

    # -- Query operations --

    def get_build(self, build_id: str) -> Optional[BuildResult]:
        """Get build result by ID."""

    def list_builds(
        self,
        product: Optional[str] = None,
        firmware_type: Optional[str] = None,
        git_ref: Optional[str] = None,
        limit: int = 50,
    ) -> list[BuildResult]:
        """List builds with optional filters."""

    def get_artifact(self, artifact_key: str) -> bytes:
        """Download artifact content from MinIO."""

    def get_artifact_url(self, artifact_key: str, expires_s: int = 3600) -> str:
        """Get presigned URL for artifact download."""

    # -- Webhook operations --

    def handle_webhook(self, headers: dict, body: bytes) -> Optional[BuildResult]:
        """Parse Bitbucket webhook, validate HMAC, trigger build if relevant.

        Returns None if webhook is not a build-triggering event.
        Returns BuildResult if build was triggered (may be async).
        """

    # -- Lifecycle --

    def get_status(self) -> dict:
        """Health check / status. Returns active builds, queue depth, etc."""
```

---

## 4. Protocol Definition (`build.proto`)

```protobuf
syntax = "proto3";

package concord.build;

option go_package = "concord/build";

// -- Messages --

message BuildRequest {
    string product = 1;           // "alpha", "sigma5"
    string firmware_type = 2;     // "alpha_fw", "alpha_mfg_fw"
    string variant = 3;           // "release", "debug"
    string git_ref = 4;           // commit SHA or branch
    int32  build_num = 5;
    bool   is_manufacturing = 6;
    string mtib_rev = 7;
    string triggered_by = 8;
}

message ArtifactRef {
    string bucket = 1;
    string key = 2;
    string version_string = 3;    // "109.0.8.3-ED"
    int32  app_id = 4;
    int32  major = 5;
    int32  minor = 6;
    int32  build = 7;
    string track = 8;
    int64  size_bytes = 9;
    string sha256 = 10;
}

message BuildResult {
    string build_id = 1;
    BuildRequest request = 2;
    string commit_sha = 3;
    repeated ArtifactRef artifacts = 4;
    repeated ArtifactRef hex_artifacts = 5;
    string build_log_key = 6;
    double duration_s = 7;
    bool success = 8;
    string error = 9;
}

message BuildPairRequest {
    BuildRequest base_request = 1;
}

message BuildPairResult {
    BuildResult first = 1;
    BuildResult second = 2;
}

message GetBuildRequest {
    string build_id = 1;
}

message ListBuildsRequest {
    string product = 1;
    string firmware_type = 2;
    string git_ref = 3;
    int32 limit = 4;
}

message ListBuildsResponse {
    repeated BuildResult builds = 1;
}

message GetArtifactRequest {
    string artifact_key = 1;
}

message GetArtifactResponse {
    bytes content = 1;
}

message GetArtifactUrlRequest {
    string artifact_key = 1;
    int32 expires_s = 2;
}

message GetArtifactUrlResponse {
    string url = 1;
}

message WebhookRequest {
    map<string, string> headers = 1;
    bytes body = 2;
}

message WebhookResponse {
    bool triggered = 1;
    BuildResult result = 2;  // only set if triggered
}

message StatusRequest {}

message StatusResponse {
    int32 active_builds = 1;
    int32 queue_depth = 2;
    repeated string active_build_ids = 3;
}

// -- Service --

service BuildService {
    // Build operations
    rpc Build(BuildRequest) returns (BuildResult);
    rpc BuildPair(BuildPairRequest) returns (BuildPairResult);

    // Query operations
    rpc GetBuild(GetBuildRequest) returns (BuildResult);
    rpc ListBuilds(ListBuildsRequest) returns (ListBuildsResponse);
    rpc GetArtifact(GetArtifactRequest) returns (GetArtifactResponse);
    rpc GetArtifactUrl(GetArtifactUrlRequest) returns (GetArtifactUrlResponse);

    // Webhook
    rpc HandleWebhook(WebhookRequest) returns (WebhookResponse);

    // Health
    rpc GetStatus(StatusRequest) returns (StatusResponse);
}
```

---

## 5. Transport: gRPC Server

```python
# apps/backend/build/src/providers/grpc_server.py

class BuildServicer(build_pb2_grpc.BuildServiceServicer):
    """gRPC wrapper around BuildEngine. No business logic here."""

    def __init__(self, engine: BuildEngine):
        self._engine = engine

    def Build(self, request, context):
        req = _proto_to_build_request(request)
        result = self._engine.build(req)
        return _build_result_to_proto(result)

    def BuildPair(self, request, context):
        req = _proto_to_build_request(request.base_request)
        first, second = self._engine.build_pair(req)
        return build_pb2.BuildPairResult(
            first=_build_result_to_proto(first),
            second=_build_result_to_proto(second),
        )

    # ... same pattern for all RPCs
```

---

## 6. Transport: HTTP Server

```python
# apps/backend/build/src/providers/http_server.py

from flask import Flask, request, jsonify

def create_http_app(engine: BuildEngine) -> Flask:
    """HTTP/REST wrapper around BuildEngine. No business logic here."""

    app = Flask(__name__)

    @app.route("/api/builds", methods=["POST"])
    def build():
        req = BuildRequest(**request.json)
        result = engine.build(req)
        return jsonify({"data": _result_to_dict(result), "errors": []})

    @app.route("/api/builds/pair", methods=["POST"])
    def build_pair():
        req = BuildRequest(**request.json["base_request"])
        first, second = engine.build_pair(req)
        return jsonify({"data": {"first": _result_to_dict(first), "second": _result_to_dict(second)}, "errors": []})

    @app.route("/api/builds/<build_id>", methods=["GET"])
    def get_build(build_id):
        result = engine.get_build(build_id)
        if not result:
            return jsonify({"data": None, "errors": ["Build not found"]}), 404
        return jsonify({"data": _result_to_dict(result), "errors": []})

    @app.route("/api/builds", methods=["GET"])
    def list_builds():
        results = engine.list_builds(
            product=request.args.get("product"),
            firmware_type=request.args.get("firmware_type"),
            git_ref=request.args.get("git_ref"),
            limit=int(request.args.get("limit", 50)),
        )
        return jsonify({"data": [_result_to_dict(r) for r in results], "errors": []})

    @app.route("/api/artifacts/<path:key>", methods=["GET"])
    def get_artifact(key):
        content = engine.get_artifact(key)
        return content, 200, {"Content-Type": "application/octet-stream"}

    @app.route("/api/artifacts/<path:key>/url", methods=["GET"])
    def get_artifact_url(key):
        url = engine.get_artifact_url(key)
        return jsonify({"data": {"url": url}, "errors": []})

    @app.route("/webhooks/bitbucket", methods=["POST"])
    def webhook():
        result = engine.handle_webhook(dict(request.headers), request.data)
        triggered = result is not None
        return jsonify({"data": {"triggered": triggered, "result": _result_to_dict(result) if result else None}, "errors": []})

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(engine.get_status())

    return app
```

---

## 7. Entrypoint

```python
# apps/backend/build/src/main.py

import threading
from concurrent import futures
import grpc

from engine.build_engine import BuildEngine
from providers.grpc_server import BuildServicer, serve_grpc
from providers.http_server import create_http_app
from config import BuildConfig

def main():
    config = BuildConfig.from_env()
    engine = BuildEngine(config)

    # Start gRPC server in thread
    grpc_thread = threading.Thread(
        target=serve_grpc, args=(engine, config.grpc_port), daemon=True
    )
    grpc_thread.start()

    # Start HTTP server in main thread
    app = create_http_app(engine)
    app.run(host="0.0.0.0", port=config.http_port)

if __name__ == "__main__":
    main()
```

Default ports: gRPC = 50054, HTTP = 8080.

---

## 8. MinIO Storage Schema

```
firmware-builds/                       # Bucket
    alpha/
        alpha_fw/
            debug/
                0.8.3/
                    109.0.8.3-ED.cfw
                    108.0.8.3-ED.cfw
                    alpha_fw.hex        # Full merged hex for J-Link
                    comm_coproc.hex
                    build.json          # BuildResult metadata
                    build.log           # stdout/stderr
            release/
                0.8.3/
                    109.0.8.3-P.cfw
                    108.0.8.3-P.cfw
                    ...
        alpha_mfg_fw/
            release/
                0.5.1/
                    109.0.5.1-PM.cfw
                    108.0.5.1-PM.cfw
                    ...
    sigma5/
        sigma5_fw/
            ...
```

**Key format:** `{product}/{firmware_type}/{variant}/{major}.{minor}.{build}/{filename}`

**Bucket:** `firmware-builds` (configurable via `MINIO_FIRMWARE_BUCKET` env var)

---

## 9. Bitbucket Webhook Integration

### Webhook Payload (PR opened/updated)

```json
{
    "eventKey": "pr:opened",
    "pullRequest": {
        "id": 42,
        "fromRef": {
            "id": "refs/heads/feature/new-sensor",
            "latestCommit": "abc123..."
        },
        "toRef": {
            "id": "refs/heads/main"
        }
    },
    "repository": {
        "slug": "alpha_fw",
        "project": { "key": "FIRM" }
    }
}
```

### Build Trigger Rules

| Event | `toRef` | Repo | Action |
|-------|---------|------|--------|
| `pr:opened` | `main` | `alpha_fw` | Build FUT_DEBUG_A/B + FUT_RELEASE_A/B |
| `pr:opened` | `main` | `alpha_mfg_fw` | Build MFG_BASE + MFG_BUMP |
| `pr:from_ref_updated` | `main` | any | Rebuild affected assets |
| `pr:merged` | `main` | any | Build MAIN_MERGED |

### HMAC Validation

Bitbucket signs webhooks with `X-Hub-Signature` header (HMAC-SHA256).
The service validates before processing:

```python
import hmac, hashlib

def validate_webhook(secret: str, signature: str, body: bytes) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## 10. Build Execution

### Docker Build Container

The build service runs `build.sh` inside a Docker container with the
Zephyr SDK and nRF Connect SDK pre-installed.

```python
def _execute_build(self, req: BuildRequest) -> BuildResult:
    """Run firmware build in isolated Docker container."""

    # 1. Clone/checkout firmware repo at git_ref
    # 2. Prepare build args
    build_args = [
        f"--product {req.product}",
        f"--variant {req.variant}",
        f"--mtib-rev {req.mtib_rev}",
        f"--build-num {req.build_num}",
    ]
    if not req.is_manufacturing:
        build_args.append("--is-mfg 0")

    # 3. Run build.sh in container
    # 4. Collect zephyr.signed.encrypted.bin from build output
    # 5. Generate CFW files via corekinect.firmware.cfw
    # 6. Upload all artifacts to MinIO
    # 7. Return BuildResult
```

### Build Queue

Builds are queued in-process (threading + queue). Single build at a time
(Zephyr builds are CPU-intensive). Future: scale with K8s Jobs.

---

## 11. HTTP API Consumed by Concord HTTP API

The Concord HTTP API (`apps/backend/http-api`) can query build results:

```
GET /api/builds?product=alpha&firmware_type=alpha_fw&git_ref=abc123
```

This enables the frontend to show build status, download artifacts, and
link firmware versions to validation results.

---

## 12. Configuration

```python
class BuildConfig(EnvConfig):
    ENV_PREFIX = "BUILD"

    grpc_port: int = 50054
    http_port: int = 8080

    minio_endpoint: str = "minio.concord.svc:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_firmware_bucket: str = "firmware-builds"

    bitbucket_webhook_secret: str = ""
    bitbucket_base_url: str = ""
    bitbucket_token: str = ""

    build_image: str = "concord/firmware-builder:latest"
    build_timeout_s: int = 600
    max_concurrent_builds: int = 1

    # Firmware repo paths (in build container)
    firmware_repos_base: str = "/repos"
```

---

## 13. Deployment

Kubernetes Deployment in `deploy/build/`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: build-service
spec:
  replicas: 1    # Single replica (build queue is in-process)
  template:
    spec:
      containers:
      - name: build-service
        image: concord/build-service:latest
        ports:
        - containerPort: 50054  # gRPC
          name: grpc
        - containerPort: 8080   # HTTP
          name: http
        volumeMounts:
        - name: docker-socket
          mountPath: /var/run/docker.sock  # For Docker-in-Docker builds
        env:
        - name: BUILD_MINIO_ENDPOINT
          value: "minio.concord.svc:9000"
        # ... other env vars from ConfigMap/Secret
      volumes:
      - name: docker-socket
        hostPath:
          path: /var/run/docker.sock
---
apiVersion: v1
kind: Service
metadata:
  name: build-service
spec:
  ports:
  - name: grpc
    port: 50054
  - name: http
    port: 8080
  selector:
    app: build-service
```

---

## 14. Integration with Stage 4 Validation

The Stage 4 PR Validation Flow (see `docs/validation/architecture/stage4-pr-validation-flow.md`)
consumes the build service to:

1. **Trigger builds** when a PR is opened (via webhook or direct gRPC call)
2. **Query artifacts** to download CFW files for FUOTA upload
3. **Build pairs** for "same code, different version" validation

```python
# In Stage4Orchestrator:
from concord.build.client import BuildClient

build = BuildClient(addr="build-service.concord.svc:50054")

# Build FUT debug pair (same code, consecutive build numbers)
fut_debug_a, fut_debug_b = build.build_pair(BuildRequest(
    product="alpha",
    firmware_type="alpha_fw",
    variant="debug",
    git_ref=pr_commit_sha,
    build_num=allocate_build_num(),
    is_manufacturing=False,
))

# Download CFW for FUOTA upload
cfw_bytes = build.get_artifact(fut_debug_a.artifacts[0].key)
```

---

## 15. Database Schema (Prisma)

The build service shares the Concord PostgreSQL database. New models:

```prisma
enum BuildJobStatus {
    QUEUED
    BUILDING
    SUCCESS
    FAILED
    CANCELLED
}

model BuildJob {
    id              String          @id @default(cuid())
    product         String          // "alpha", "sigma5"
    board           String          // "alpha_b0"
    target          String          // "app", "mfg", "all"
    variant         String          @default("release")
    mtibRev         String          @default("1.2")
    branch          String
    commitSha       String?
    status          BuildJobStatus  @default(QUEUED)
    versionMajor    Int?
    versionMinor    Int?
    buildNum        Int             @default(autoincrement())
    versionString   String?         // "109.0.8.42"
    errorMessage    String?
    webhookData     Json?
    startedAt       DateTime?
    finishedAt      DateTime?
    durationSeconds Int?
    createdAt       DateTime        @default(now())
    updatedAt       DateTime        @updatedAt
    artifacts       BuildJobArtifact[]
    @@index([product, branch])
    @@index([status])
    @@map("build_jobs")
}

model BuildJobArtifact {
    id          String   @id @default(cuid())
    buildJobId  String
    name        String   // "109.0.8.42-P.cfw"
    storageKey  String   // MinIO object key
    sizeBytes   BigInt
    checksum    String   // SHA-256
    createdAt   DateTime @default(now())
    buildJob    BuildJob @relation(fields: [buildJobId], references: [id], onDelete: Cascade)
    @@index([buildJobId])
    @@map("build_job_artifacts")
}
```

**Relationship to existing `FirmwareBuild` table:** `BuildJob` tracks the build
process. On successful merge-to-main builds, optionally promote to `FirmwareBuild`
for the catalog. PR builds produce artifacts but don't auto-promote.

---

## 16. Implementation Phases

### Phase 1: Core Build Pipeline (1-2 weeks)
1. Add `BuildJob`/`BuildJobArtifact` to `prisma/schema.prisma`
2. Create `libs/protocols/build/build.proto` + generate stubs
3. Implement `apps/backend/build/` with `BuildEngine` + gRPC + HTTP servers
4. Add `#ifndef BUILD_NUM` guards to `VersionDevice.h` (4 files)
5. Modify `build.sh` to accept `CONCORD_BUILD_NUM` env var
6. Test: manual build via `grpcurl` and `curl`

### Phase 2: HTTP API + Frontend (1 week)
7. Add REST endpoints at `/v2/builds/*` in HTTP API
8. Add `ADMIN_BUILDS_VIEW` and `ADMIN_BUILDS_MANAGE` permissions
9. Wire up gRPC client in HTTP API for build submission
10. Frontend build status page

### Phase 3: Webhook + Automation (1 week)
11. Bitbucket webhook handler + HMAC validation
12. Auto-catalog promotion on merge-to-main
13. Integration with Stage 4 validation orchestrator

### Phase 4: Deployment (1 week)
14. Dockerfile + Helm chart templates
15. Add to `deploy/ctl.sh`
16. Deploy to staging, test end-to-end

---

## 17. Open Questions

| Question | Status |
|----------|--------|
| Docker-in-Docker vs K8s Job for builds? | Start with DinD, migrate to Jobs |
| Build number allocation strategy? | Auto-increment per (product, major.minor) in DB |
| Zephyr SDK version pinning? | Pin in Dockerfile, tagged per NCS version |
| Bitbucket Server vs Cloud webhook format? | Verify with actual webhook payload |
| Private firmware repo cloning? | SSH key mount or Bitbucket app token |
| Build cache strategy? | Default pristine, add ccache later |
| NCS version per product? | Alpha=v3.2.1, Sigma5=v2.7.0 — map in config |
| Build retention policy? | 30 days for PR builds, indefinite for catalog |
