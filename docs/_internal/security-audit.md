# Concord Platform Security Audit Report

**Date:** 2026-04-10 (updated with Wave 5 verification pass)
**Branch:** `feature/validation-demo`
**Scope:** Full platform — 5 waves, 19 agents, ~700 files analyzed

---

## Executive Summary

Concord has **solid application-layer fundamentals** — Prisma ORM prevents SQL injection, permission decorators protect most endpoints, JWT crypto is properly implemented, and API key generation uses cryptographically secure randomness. But there are **serious gaps** in infrastructure trust model, auth lifecycle, and hardware control plane that must be closed before delivery.

**Total unique findings: 11 Critical, 17 High, 24+ Medium, ~10 Low/Informational**

**Wave 5 verification (2026-04-10):** All 8 spot-checked claims confirmed still accurate against current code. 6 new findings from recently changed files added.

---

## Confirmed Secure (Validated Across All Waves)

These areas held up under repeated scrutiny:

| Area | Detail |
|------|--------|
| **JWT crypto** | HS256 hardcoded, algorithm confusion prevented, 32-char minimum enforced at startup |
| **API key generation** | `secrets.token_hex()`, 128-bit entropy, SHA256 hashed storage |
| **HMAC webhook** | `hmac.compare_digest()` — timing-safe |
| **SQL injection** | Prisma ORM throughout, zero raw SQL |
| **Command injection** | All subprocess uses list args, no `shell=True` |
| **SSTI** | No Jinja2 template rendering with user input |
| **SSRF** | Git URLs passed safely via list arguments |
| **Deserialization** | `yaml.safe_load()` only, no pickle/eval/exec |
| **ZIP path traversal** | Properly validated (reject `..` and `/` prefixes) |
| **Product access scoping** | `ProductAccess` table queries properly scoped to userId |
| **Input validation** | Request bodies validated via `from_json()`, upload size limit 100MB |
| **JWT secret enforcement** | Production rejects dev default, requires 32+ chars |

---

## CRITICAL Findings

### C1. Secrets Committed to Git
**Layer: Infrastructure**

| File | Secret |
|------|--------|
| `deploy/development/.env` | Base64-encoded SSH private key, Bitbucket API token |
| `infrastructure/clusters/office/secrets/.env` | Hardcoded CI admin API key |
| `prisma/.env` | Database credentials in plaintext |

**Impact:** Anyone with repo access can clone firmware repos, impersonate CI, and access the database.
**Fix:** Rotate all committed secrets immediately. Move to Vault/K8s secrets. Add `.env` to pre-commit hooks.

---

### C2. MTIB gRPC — Unencrypted, Unauthenticated
**Layer: Hardware**

`libs/python/corekinect/mtib_client/v1/client/core.py:268` — uses `grpc.insecure_channel()` with zero authentication. Anyone on the network can flash firmware, control GPIO, read UART, and power-cycle devices.

**Impact:** Complete device takeover. Malicious firmware injection.
**Fix:** Implement mTLS for all MTIB gRPC connections.

---

### C3. No Firmware Signature Verification
**Layer: Hardware**

`libs/python/corekinect/firmware/validator.py` — validates metadata consistency only, not cryptographic signatures. `FlashFwFile()` accepts any binary. The `sha256_digest` field exists in the proto but is never verified before flash.

**Impact:** MITM attacker can inject malicious firmware during flashing.
**Fix:** Implement firmware image signing at build time, verify signatures before every flash.

---

### C4. TLS Verification Disabled for CoreOps
**Layer: Hardware/Manufacturing**

`apps/manufacturing/alpha/tests/manufacturing/test_post.py:119,150,166` — all CoreOps API calls use `verify=False`. Device ID assignment, public key upload, and ICCID registration are all unprotected.

**Impact:** MITM during manufacturing can steal device credentials or reassign identities.
**Fix:** Enable TLS verification. Pin CoreOps CA certificate.

---

### C5. JWT Token in localStorage (XSS-Vulnerable)
**Layer: Frontend**

`apps/frontend/app/src/lib/api.ts:3,8,13` — auth token stored in `localStorage`, accessible to any JavaScript running on the page. Also leaked via query string in `docs.ts:52-55`.

**Impact:** Any XSS vulnerability exfiltrates all user sessions.
**Fix:** Move auth to HTTP-only, Secure, SameSite=Strict cookies. Remove token from URL query strings.

---

### C6. Open PyPI Server — Anyone Can Upload Packages
**Layer: Supply Chain**

`deploy/production/helm/concord/templates/infra-pypi.yaml` — pypiserver configured with `-P . -a .` which disables authentication. Any network actor can upload a malicious package that gets `pip install`ed by build-service.

**Impact:** Code injection into all firmware builds.
**Fix:** Enable `.htpasswd` authentication on PyPI server. Pin pypiserver version.

---

### C7. No Token Revocation / Logout Mechanism
**Layer: Auth**

Zero implementation of logout, token blacklist, or refresh rotation. A stolen JWT has 24 hours of unrestricted access with no way to invalidate it. No `jti` claim for session tracking.

**Fix:** Implement token blacklist (Redis-backed) or switch to short-lived tokens + refresh flow.

---

### C8. WebSocket Authorization Bypass — Subscribe to Any Run/Device
**Layer: Real-time**

`src/api/v2/runs/ws.py:85` — `subscribe_run()` validates JWT but never checks if the user owns that run. Any authenticated OPERATOR can subscribe to any run by ID and receive all test results, telemetry, and measurements. Same pattern in `validation_ws.py:83` and `observability_ws.py:151`.

**Fix:** Add product-level or run-level ownership check before `join_room()`.

---

### C9. Zero Rate Limiting on All Endpoints
**Layer: API**

No rate limiting detected anywhere. Login brute-force, API key enumeration, validation trigger spam, webhook flooding — all unconstrained.

**Fix:** Implement per-IP rate limiting (Redis + sliding window or token bucket).

---

### C10. No Failed Authentication Logging / No Alerting
**Layer: Monitoring**

Failed login attempts, API key failures, and permission denials are never logged to the audit trail. No Prometheus alerting, no PagerDuty, no anomaly detection. Brute-force attacks are invisible.

**Fix:** Add failed auth logging. Deploy Prometheus + Alertmanager. Alert on >5 failures/min from same IP.

---

### C11. TOCTOU Race in Fixture Locking
**Layer: Concurrency**

`src/api/v2/runs/trigger.py:257` — Fixture availability check and lock are not atomic. Two concurrent validation runs can grab the same fixture, risking device damage or corrupted test state.

**Fix:** Use database transactions with row-level locking or atomic upsert pattern.

---

## HIGH Findings

### H1. No CSRF Protection
**Layer: Frontend**

No CSRF tokens anywhere. Cookie set with `SameSite=Lax` (insufficient). All state-changing API calls (POST/PUT/DELETE) are vulnerable.

**Fix:** Implement CSRF tokens or switch to `SameSite=Strict` + double-submit cookie pattern.

---

### H2. No Content Security Policy
**Layer: Frontend/Backend**

No CSP headers configured in SvelteKit or Flask. Combined with `@html` usage in multiple components, XSS attacks have no mitigation layer.

**Fix:** Add CSP headers with strict `script-src` and `style-src` directives.

---

### H3. Privileged Container + Docker Socket Mount
**Layer: Infrastructure**

`deploy/production/helm/concord/templates/build-service-deployment.yaml` — build service runs `privileged: true` with `/var/run/docker.sock` mounted. Container escape = full host compromise.

**Fix:** Use rootless Docker-in-Docker or Kaniko for builds. Remove privileged mode.

---

### H4. HTTP API Service Account Has Cluster-Wide Privileges
**Layer: Kubernetes**

`infrastructure/clusters/office/rbac/clusterroles.yaml:89-126` — `concord-api-system-monitor` ClusterRole grants `pods/exec` (create), `pods` (delete), `secrets` (patch/delete), `deployments` (patch) cluster-wide. API compromise = near-cluster-admin.

**Fix:** Scope RBAC to specific namespaces. Remove `secrets` patch/delete.

---

### H5. SSH Host Key Checking Disabled
**Layer: Supply Chain**

`apps/backend/build-service/src/worker/git_ops.py:124` — `StrictHostKeyChecking=no` in 4+ locations. DNS poisoning or compromised Bitbucket redirects git clone to attacker's repo.

**Fix:** Use `StrictHostKeyChecking=accept-new` with managed `known_hosts`.

---

### H6. Unpinned Container Images
**Layer: Infrastructure**

Production Helm templates use `minio/minio:latest`, `pypiserver/pypiserver:latest`, `minio/mc:latest`. Silent malicious updates auto-deploy.

**Fix:** Pin all images to SHA256 digests.

---

### H7. Vulnerable Python Dependencies
**Layer: Backend**

`apps/backend/http-api/setup.py` — `requests==2.26.0` (CVE-2023-32681), `flask==3.0.2` (known issues in 3.0.x).

**Fix:** Upgrade to `requests>=2.31.0`, `flask>=3.1.0`.

---

### H8. Error Information Disclosure
**Layer: Backend**

`src/api/v2/builds/stage_config.py:194` — `str(e)` returned directly to client. Same pattern in `recipes.py:133`, `board_discovery.py:87`.

**Fix:** Return generic error messages. Log details server-side only.

---

### H9. XSS via @html with Log Data
**Layer: Frontend**

`apps/frontend/app/src/lib/components/products/stage-config-wizard.svelte:1331` — renders `{@html entry.html}` from build logs. Also `hooks.client.ts:15` — `innerHTML` with error stack traces.

**Fix:** Use DOMPurify before any `@html` rendering.

---

### H10. HTTP Response Header Injection
**Layer: Backend**

Unsanitized filenames in Content-Disposition headers in 4 endpoints: `storage_download.py:41`, `board_revisions.py:460`, `runs/artifacts.py:110`, `sessions/artifacts.py:101`.

**Fix:** Apply `_sanitize_filename()` (already exists in `builds.py:23-31`) to all Content-Disposition headers.

---

### H11. No Egress NetworkPolicy
**Layer: Kubernetes**

All three NetworkPolicy definitions define only `policyTypes: [Ingress]`. Compromised pods can make outbound connections to exfiltrate data or connect to C2.

**Fix:** Add egress rules limiting pods to required internal services only.

---

### H12. No Python Lockfiles
**Layer: Supply Chain**

http-api, build-service, git-poller have no Poetry/pip lock files. Open to dependency resolution/confusion attacks.

**Fix:** Generate and commit lockfiles for all Python services.

---

### H13. Audit Logs Mutable — No Tamper Protection
**Layer: Monitoring**

PostgreSQL `AuditLog` table has no immutability guarantees. Any DB admin or SQL injection can modify/delete audit entries.

**Fix:** External log aggregation with immutable storage.

---

### H14. No Bulk Session/Credential Revocation
**Layer: Incident Response**

No endpoint to revoke all sessions for a compromised user. No way to invalidate all API keys instantly. No emergency shutdown capability.

**Fix:** Implement bulk revocation endpoints for incident response.

---

### H15. Unbounded Validation Triggers
**Layer: Concurrency**

No limit on concurrent validation runs a user can trigger. Can lock all fixtures and exhaust cluster capacity.

**Fix:** Per-user quotas and request throttling.

---

### H16. Reporter Endpoints Accept Results for Any Run
**Layer: Real-time**

`runs/reporter.py:221-766` — Reporter validates run exists but doesn't verify the test runner is authorized to report on that specific run. Any client with a valid API key can falsify results.

**Fix:** Bind API keys to specific runs/jobs.

---

### H17. Device Keys Transmitted Over Plaintext UART
**Layer: Hardware**

`libs/python/corekinect/test/device_personalizer.py:73-180` — EC public key transmitted over unencrypted UART during personalization.

**Fix:** Encrypt UART channel during key exchange or use out-of-band provisioning.

---

### H18. Secret Model Lacks Serialization Protection
**Layer: Database**

`libs/python/database/models.py` — `Secret` model contains plaintext `value` field with no `model_dump(exclude=)` override or serialization filter. If any API endpoint or logging path serializes this model, signing keys, API tokens, and SSH keys leak.

**Fix:** Add explicit serialization exclusion for `Secret.value`. Override `__repr__` to redact.

---

### H19. Missing Unique Constraints on Panel Identifiers
**Layer: Database**

`libs/python/database/schema.prisma` — `panelIdentifier` on TestRun and `serialNumber` on RunTarget lack uniqueness constraints. Multiple runs could reference the same panel, breaking manufacturing traceability and enabling panel swap fraud.

**Fix:** Add `@@unique([panelIdentifier])` on TestRun and `@@unique([serialNumber, productId])` on RunTarget.

---

### H20. Unvalidated Base64 Log Chunks
**Layer: Backend**

`apps/backend/http-api/src/api/v2/runs/types.py:260,287` — `ReportLogChunkRequest` accepts data marked as "base64-encoded" but never validates it. Malformed payloads stored directly, causing corruption or DoS when downstream consumers decode.

**Fix:** Add `base64.b64decode(chunk_data, validate=True)` in `from_json()`.

---

### H21. Sensitive Device Metadata Stored Unencrypted
**Layer: Database**

`libs/python/database/schema.prisma` — `RunTarget.metadata` (Json?) stores IMEI, ICCID, hardware info, and calibration data in plaintext. Database compromise exposes device identity.

**Fix:** Field-level encryption for sensitive device metadata, or segregate into encrypted column.

---

### H22. Log Storage Keys Not Validated
**Layer: Backend**

`libs/python/database/schema.prisma` — `logStorageKey` strings stored without validation against expected MinIO key format. Could enable path traversal in presigned URL generation.

**Fix:** Whitelist allowed key prefixes (e.g., `logs/runs/{runId}/`) and validate before storing.

---

## MEDIUM Findings

| # | Finding | Location |
|---|---------|----------|
| M1 | Permission cache 60s TTL — revoked permissions active for up to 1 min | `decorators.py:20` |
| M2 | X-View-As-Role header accepted without permission set validation | `decorators.py:241` |
| M3 | No JWT secret rotation mechanism | `jwt.py` |
| M4 | TLS cipher suites not explicitly configured (Traefik defaults) | `ingress.yaml` |
| M5 | Device IDs/serial numbers in URL paths — logged by proxies | Router URLs |
| M6 | Auto-run database migrations with no review gate | `prisma/migrations/` |
| M7 | Kubeconfig certificates valid 365 days, no revocation | `generate.sh:365` |
| M8 | Ingress lacks rate limiting annotations | `ingress.yaml` |
| M9 | No database connection pool limits configured | Prisma config |
| M10 | Build log injection — rogue worker can fake CI output | `builds.py:830` |
| M11 | GDPR gaps — emails in plaintext audit logs, no DSAR export | Audit system |
| M12 | Fixture status not atomic — can deadlock if update fails mid-lock | `trigger.py` |
| M13 | Missing security headers (X-Frame-Options, HSTS, X-Content-Type-Options) | `main.py` |
| M14 | SameSite=Lax cookie exposed to all `.concord.local` subdomains | `api.ts:30` |
| M15 | gRPC version mismatch (1.62.0 vs 1.76.0) | `mtib_client` vs `deploy/runner` |
| M16 | Dev login endpoint callable if AUTH_ENABLED misconfigured | `dev_login.py:29` |
| M17 | No per-message re-auth on WebSocket — expired tokens stay active | All `*_ws.py` |
| M18 | Backup cronjob mounts writable hostPath | `backup-cronjob.yaml:189` |
| M19 | Hardcoded test credentials in conftest.py | `conftest.py:37-60` |
| M20 | 631 bare `except Exception` blocks across 173 files | Various |
| M21 | Temp files created with mkdtemp() without cleanup | `artifact_resolver.py:445` |
| M22 | No content-type validation on file upload | `assets.py:64` |
| M23 | Artifact downloads use Content-Disposition: inline for JSON/CSV | `artifacts.py:110` |
| M24 | No WebSocket rate limiting — event flooding possible | All `*_ws.py` |
| M25 | Enum/Literal values in Prisma types.py not validated at runtime | `database/types.py:54-75` |
| M26 | Empty filter objects `{}` accepted — could bypass query constraints | `database/types.py` (all filter TypedDicts) |
| M27 | MTIB TLS config now opaque after manufacturing refactor — delegated to FixtureContext library | `manufacturing/alpha/conftest.py` |
| M28 | Exception details logged in manufacturing conftest (network paths, API internals) | `conftest.py:76` |
| M29 | Panel/serial identifiers exposed in API responses without role-based filtering | `runs/types.py:75,139` |

---

## Priority Matrix

| Priority | Items | Effort |
|----------|-------|--------|
| **P0 — Block delivery** | C1 (rotate secrets), C2 (mTLS for MTIB), C3 (firmware signing), C4 (TLS verification), C5 (JWT to cookie), C6 (close PyPI auth), C11 (fixture locking) | 3-4 days |
| **P1 — Before production** | H1 (CSRF), H2 (CSP), H3 (unprivilege containers), H4 (scope RBAC), H5 (SSH host keys), H6 (pin images), H7 (upgrade deps), C8 (WebSocket auth), C9 (rate limiting), H18 (Secret serialization), H19 (panel uniqueness) | 3-4 days |
| **P2 — First sprint post-launch** | C7 (token revocation), C10 (auth logging + alerting), H8 (error messages), H9 (XSS sanitize), H10 (header injection), H11 (egress policies), H12 (lockfiles), H16 (reporter binding), H20 (base64 validation), H21 (metadata encryption), H22 (log key validation) | 2-3 days |
| **P3 — Ongoing hardening** | H13 (audit immutability), H14 (bulk revocation), H15 (resource quotas), M1-M29 | Ongoing |

---

## Recommended External Tooling

Claude-based analysis has blind spots. Complement with:

| Tool | Purpose |
|------|---------|
| `bandit` | Python SAST (catches patterns Claude may miss) |
| `semgrep` | Cross-language pattern matching |
| `npm audit` | JS transitive dependency CVEs |
| `pip-audit` | Python dependency CVEs |
| `trivy` | Container image vulnerability scanning |
| `trufflehog` / `gitleaks` | Full git history secrets scanning |
| OWASP ZAP | Dynamic API testing |
| `kube-bench` | CIS Kubernetes benchmark |

---

## Methodology

- **Wave 1 (6 agents):** Layer-by-layer audit — backend, frontend, infra, hardware, Python quality, methodology research
- **Wave 2 (3 agents):** Attack vector analysis — auth bypass chains, injection/file attacks, WebSocket/real-time
- **Wave 3 (3 agents):** Trust boundary analysis — data flow, supply chain, Kubernetes attack surface
- **Wave 4 (3 agents):** Edge case analysis — race conditions/timing, cryptography, logging/monitoring/incident response
- **Wave 5 (4 agents):** Verification pass — cross-checked 8 claims against current code (all confirmed), audited recently changed files (types.py, models.py, schema.prisma, conftest.py, fixtures-tab.svelte, build_run_service.py), found 6 new findings

## Wave 5 Verification Results

All 8 spot-checked claims from the original report were verified against current code:

| Claim | Status | Notes |
|-------|--------|-------|
| C2 — `insecure_channel()` at core.py:268 | CONFIRMED | Line number exact match |
| C5 — JWT in localStorage at api.ts:3,8,13 | CONFIRMED | Still using `localStorage` |
| C6 — PyPI `-P . -a .` disabling auth | CONFIRMED | Line 23 of infra-pypi.yaml |
| C8 — subscribe_run no ownership check | CONFIRMED | Handler at ws.py:126+ lacks check |
| C11 — TOCTOU fixture locking | CONFIRMED | Race between find_first and update |
| H4 — pods/exec cluster-wide RBAC | CONFIRMED | Lines 104-105 of clusterroles.yaml |
| H7 — requests==2.26.0 | CONFIRMED | Line 17 of setup.py |
| H10 — Unsanitized Content-Disposition | CONFIRMED | Line 41 of storage_download.py |

**Recently changed files audit:** `libs/python/database/types.py` (1586 lines) is Prisma-generated — safe from hand-authored vulnerabilities but TypedDict Literal values lack runtime validation. `fixtures-tab.svelte` changes are clean (no `@html`). Manufacturing `conftest.py` refactor improved security by removing custom log upload but made MTIB TLS config opaque.
