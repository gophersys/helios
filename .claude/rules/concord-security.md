---
paths:
  - "apps/backend/http-api/**/*.py"
  - "apps/frontend/concord-app/**/*.{ts,tsx}"
---

# Security Rules

## Backend

- Every endpoint MUST use `@require_permissions()` decorator — never `@require_auth` with manual checks
- Never return `str(e)` to clients — log details server-side, return generic messages
- Validate URL protocols: only allow `http://` and `https://` for user-provided URLs
- Validate zip file paths before extraction to prevent path traversal
- Use `X-Forwarded-For` header for client IP in audit logs (proxy-aware)
- File uploads: enforce `MAX_CONTENT_LENGTH`, validate file extensions against allowlists
- Presigned download URLs must set `Content-Disposition: attachment`
- Permission cache must be thread-safe (use `threading.Lock`)
- JWT secret must be validated at startup — reject default value in production

## Frontend

- Never access `localStorage` directly for auth tokens — use `api()` / `apiUpload()` / `apiUploadRaw()` from `src/app/api.ts`
- Validate URLs with `isSafeUrl()` from `src/app/utils/url.ts` before rendering as `<a href>`
- Never use `dangerouslySetInnerHTML`
- All API errors must be caught and displayed to users — no empty `catch {}` blocks
- Form submissions must have `submitting` state to prevent double-submit
