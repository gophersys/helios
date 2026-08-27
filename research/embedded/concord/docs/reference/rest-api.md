---
min_role: DEVELOPER
---
# REST API

All endpoints live under `/v2/`. The interactive docs are at `/v2/docs` on any running Concord instance.

## Authentication

Every request needs a valid JWT token or API key in the `Authorization` header:

```
Authorization: Bearer <your-token>
```

Generate API keys from **Settings > API Keys** in the Concord UI.

## Endpoints

### Products

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v2/products` | List all products |
| `GET` | `/v2/products/:id` | Get product details |
| `POST` | `/v2/products` | Create a product |
| `PUT` | `/v2/products/:id` | Update a product |
| `DELETE` | `/v2/products/:id` | Delete a product |

### Builds

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v2/builds` | List builds |
| `GET` | `/v2/builds/:id` | Get build details |
| `POST` | `/v2/builds` | Trigger a build |

### Validation

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v2/validation/runs` | List validation runs |
| `GET` | `/v2/validation/runs/:id` | Get run details with test results |
| `POST` | `/v2/validation/runs` | Start a validation run |

### Manufacturing

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v2/manufacturing/sessions` | List manufacturing sessions |
| `POST` | `/v2/manufacturing/sessions` | Create a session |

## Response Envelope

All responses use a standard wrapper:

```json
{
  "data": { ... },
  "errors": []
}
```

`errors` is empty on success. On failure, `data` may be null and `errors` contains one or more error strings.
