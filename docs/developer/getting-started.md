# Getting Started

## Login

Go to [concord.local](https://concord.local) and sign in with your CoreCloud (Google) credentials. Your account needs to be provisioned by an admin first — if you see a 403, ask Mateo or Enos to add you.

## Finding Your Products

After login, you'll land on the **Products** page. You'll only see products you have access to. Click a product to see its builds, validation runs, and settings.

If a product is missing, your access level might not include it. Ask a Maintainer to grant you `develop` access on the product.

## Dashboard Overview

The sidebar has four main sections:

| Section | What's There |
|---------|-------------|
| **Products** | Your products, board revisions, firmware config |
| **Builds** | Build history, artifacts, build status |
| **Validation** | Validation runs, test results, stage progress |
| **Manufacturing** | Manufacturing runs, POST results (if you have operator access) |

## Key URLs

| Service | URL | Notes |
|---------|-----|-------|
| App | `https://concord.local` | Production frontend |
| App (staging) | `https://staging.concord.local` | Staging frontend |
| API | `https://concord.local/v2/docs` | REST API docs (Swagger) |
| API (staging) | `https://staging.concord.local/v2/docs` | Staging API docs |
| Docs | `https://docs.concord.local` | This documentation site |
| PyPI | `https://pypi.concord.local` | Internal Python packages |

## Next Steps

- [View your builds](builds.md) — see what firmware is available
- [Run validation](validation.md) — trigger a test run against hardware
- [Write tests](writing-tests.md) — create test packages for your product
