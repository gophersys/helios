# Token API

```js
/Authentication/Tokens
```

- [Token API](#token-api)
- [Overview](#overview)
- [API Documentation](#api-documentation)
  - [Get Token](#get-token)
    - [Get Token Request](#get-token-request)
    - [Get Token Response](#get-token-response)
  - [Refresh Token](#refresh-token)
    - [Refresh Token Request](#refresh-token-request)
    - [Refresh Token Response](#refresh-token-response)

<!-- SEPARATOR -->

# Overview

This API handles generating and, eventually, revoking access tokens.

# API Documentation

## Get Token

### Get Token Request

```js
POST /Authentication/Tokens/Request
```

**Headers**
| Header        | Value             |
| ------------- | ----------------- |
| X-API-KEY     | Valid API Key     |
| Authorization | Basic auth Base64 |

X-API-KEY
* Must be a valid API key

Authorization
* Format should be `Basic {base64EncodedCredentials}`
* For user logins, `base64EncodedCredentials` should be formatted like `ConvertToBase64(Username + ":" + Password)`
* For service logins, `base64EncodedCredentials` should be formatted like `ConvertToBase64(ClientId + ":" + ClientSecret)`

**Body**
* Body must be a form and include the `grant_type` field. Use `password` for user logins and `client_credentials` for service logins.

### Get Token Response

```js
200 Ok
```

```json
{
    "accessToken": "base64_encoded_token",
    "refreshToken": <null or token>,
    "tokenType": "bearer",
    "issued": "Wed, 03 May 2023 21:09:33 GMT",
    "expires": "Thu, 04 May 2023 01:09:33 GMT",
    "expiresIn": 14399
}
```

<hr />

## Refresh Token

### Refresh Token Request

```js
POST /Authentication/Tokens/Refresh
```

**Headers**
| Header        | Value             |
| ------------- | ----------------- |
| X-API-KEY     | Valid API Key     |

**Body**
```json
{
    "refreshToken": "token"
}
```

### Refresh Token Response

```js
200 Ok
```

```json
{
    "accessToken": "base64_encoded_token",
    "refreshToken": <null or token>,
    "tokenType": "bearer",
    "issued": "Wed, 03 May 2023 21:09:33 GMT",
    "expires": "Thu, 04 May 2023 01:09:33 GMT",
    "expiresIn": 14399
}
```