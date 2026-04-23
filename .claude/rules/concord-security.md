---
paths:
  - "apps/backend/http-api/**/*.py"
  - "apps/frontend/app/**/*.{ts,svelte}"
---

# Security Rules

## Authentication & Authorization

- Every endpoint MUST use `@require_permissions()` decorator — never `@require_auth` with manual checks
- Documented exceptions to `@require_permissions` (use `@require_auth` or no decorator):
  - `login`, `dev_login`, `dev_users` — pre-authentication flows
  - `healthcheck`, `/health`, `/ready` — K8s probes
  - `webhook_bitbucket` — validated via HMAC signature
  - `heartbeat` (ICLE) — device auto-discovery
  - `report_*`, `report_log_chunk` — K8s jobs use API keys, not permission sets
  - `dashboard_overview` — self-filters sections by caller's permission set
- GET endpoints use `_VIEW` permissions; POST/PUT/DELETE use `_MANAGE`
- API keys are hashed with SHA-256 before storage — never store raw keys
- JWT secret must be validated at startup — reject default value in production
- Permission cache must be thread-safe (use `threading.Lock`)

## Error Handling

- Never return `str(e)` to clients — log details server-side, return generic messages
- Never include user-provided input in error messages (e.g., `not_found(f"File not found: {key}")` leaks internal paths)
- Use helpers from `src/lib/errors`: `bad_request()`, `not_found()`, `conflict()`, `internal_error()`

## Input Validation

- All `from_json()` methods must strip/trim strings, range-check numbers, and validate enums
- Status fields must be validated against allowed enum values — never accept arbitrary strings
- Status transitions must be validated (e.g., TestRun: `PENDING→ACTIVE→COMPLETED|FAILED|CANCELLED`)
- URL protocols: only allow `http://` and `https://` for user-provided URLs
- Cross-entity ownership: validate that referenced entities (boardRevisionId, modemFirmwareId) belong to the correct parent product/revision

## File Uploads & Downloads

- Enforce `MAX_CONTENT_LENGTH` on all upload endpoints
- Validate file extensions against allowlists; block dangerous extensions (`.exe`, `.sh`, `.py`, `.bat`, `.cmd`, `.ps1`, `.msi`, `.dll`, `.so`)
- Presigned download URLs MUST set `Content-Disposition: attachment` — never `inline` (prevents XSS via content sniffing)
- Sanitize filenames in `Content-Disposition` headers: `re.sub(r'[^a-zA-Z0-9._-]', '_', filename)`
- Use `secure_filename()` from Werkzeug for user-uploaded filenames

## Zip Extraction

- Validate zip file paths before extraction to prevent path traversal
- Reject entries starting with `/` or containing `..`
- Block dangerous file extensions inside zips
- Normalize backslashes to forward slashes (Windows zip compatibility)
- Use `os.path.realpath()` comparison when extracting to verify paths stay within target directory

## Security Headers

- All responses must include security headers via `@server.after_request`:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (non-development only)
- CORS origins must come from environment config — never use `*`

## Storage & Paths

- Storage key downloads must validate against prefix allowlist (e.g., `firmware/`, `asset-sets/`, `test-packages/`)
- Use `X-Forwarded-For` header for client IP in audit logs (proxy-aware)

## Delete Operations

- Every delete endpoint MUST check for referencing child records before deletion
- Return `409 Conflict` with a clear message listing what blocks the delete
- Never silently cascade-delete audit records (TestRun, ManufacturingSession)
- Prisma schema must have explicit `onDelete` on every `@relation` — no implicit defaults

## Audit Logging

- Every mutation endpoint (POST, PUT, DELETE) MUST call `log_audit(action, entity_type, entity_id, details)`
- Core models should have `createdById` for record-level traceability
- `log_audit` captures the user identity from the request context

## Frontend

- Never access `localStorage` directly for auth tokens — use `api` / `apiUpload()` / `apiUploadRaw()` from `$lib/api`
- `localStorage` is acceptable for UI preferences (theme, sidebar state) but never for credentials
- Never use `{@html ...}` with untrusted content — always call `escapeHtml()` before inserting HTML tags
- For ANSI-to-HTML conversion, use the canonical `ansiToHtml` from `$lib/utils/formatting.ts` which escapes first
- All API errors must be caught and displayed to users — no empty `catch {}` blocks
- Form submissions must have `submitting` state to prevent double-submit
- Delete operations should handle `409 Conflict` responses with user-friendly messages
