# Validation API

```js
/Authorization
```

- [Validation API](#validation-api)
- [Overview](#overview)
- [API Documentation](#api-documentation)
  - [Validate API Key](#validate-api-key)
    - [Validate API Key Request](#validate-api-key-request)
    - [Validate API Key Response](#validate-api-key-response)
  - [Validate Permissions](#validate-permissions)
    - [Validate Permissions Request](#validate-permissions-request)
    - [Validate Permissions Response](#validate-permissions-response)

# Overview

This API provides a mechanism for validating API keys, access tokens, and permissions, and should be used by middleware services to determine if a client has sufficient privileges for a request.

# API Documentation

## Validate API Key

Validates an API key and returns its relevant information.

### Validate API Key Request

```js
POST /Authorization/ValidateApiKey
```

```json
{
    "apiKey": "apiKey"
}
```

### Validate API Key Response

```js
200 Ok
```

```json
{
    "isValid": true,
    "hasPrivilegedAccess" : true,
    "accountId": 1 // -1 if API key is invalid
}
```

<hr />

## Validate Permissions

Accepts an API key, authorization header, boolean indicating if privileged access is required, and a list of permission keys to check against. This endpoint will assess the API key and authorization header contents, and return a result indicating whether the client possesses the requested privilege and permissions.

### Validate Permissions Request

```js
POST /Authorization/ValidatePermissions
```

```json
{
    "apiKey": "apiKey",
    "authorizationHeader": "Bearer tokencontentshere",
    "requiresPrivilegedAccess": true,
    "permissionKeys": [
        "family.group.name"
    ]
}
```

### Validate Permissions Response

```js
200 Ok
```

```json
{
    "isAuthorized": true,
    "hasPrivilegedAccess" : true,
    /* below null if unauthorized */
    "loginId": 1,
    "accountId": 1,
    "loginType": "U", // "U" for User or "S" for Service
    "email": "email@domain.com" // for CoreSentry
}
```
