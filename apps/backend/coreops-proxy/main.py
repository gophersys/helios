"""CoreOps Proxy — Minimal proxy for device ID assignment.

Runs on concordproxy node which has network access to CoreOps server.
Only proxies the SNR → Device ID mapping endpoint.

Endpoints:
    GET /health — Health check
    POST /v1/devices/ids/assign — Proxy to CoreOps device ID assignment

Environment:
    COREOPS_SERVER_URL: CoreOps server (default: https://coreops.office.corekinect.cloud:2013)
    COREOPS_AUTH_SERVER_URL: Auth server (default: https://auth.office.corekinect.cloud:2013)
    COREOPS_API_KEY: API key for CoreOps
    COREOPS_AUTH_USER: Auth username
    COREOPS_AUTH_PASS: Auth password
    PORT: Listen port (default: 8080)
"""

import base64
import logging
import os
import time
from typing import Optional

import requests
from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("coreops-proxy")

app = Flask(__name__)

# Config from environment
COREOPS_SERVER_URL = os.environ.get("COREOPS_SERVER_URL", "https://coreops.office.corekinect.cloud:2013")
COREOPS_AUTH_SERVER_URL = os.environ.get("COREOPS_AUTH_SERVER_URL", "https://auth.office.corekinect.cloud:2013")
COREOPS_API_KEY = os.environ.get("COREOPS_API_KEY", "")
COREOPS_AUTH_USER = os.environ.get("COREOPS_AUTH_USER", "")
COREOPS_AUTH_PASS = os.environ.get("COREOPS_AUTH_PASS", "")
VERIFY_SSL = os.environ.get("COREOPS_VERIFY_SSL", "false").lower() not in ("0", "false", "no")

# Token cache
_token: Optional[str] = None
_token_expiry: float = 0.0
_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def basic_auth_header() -> str:
    raw = f"{COREOPS_AUTH_USER}:{COREOPS_AUTH_PASS}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def ensure_token() -> str:
    global _token, _token_expiry

    now = time.time()
    if _token and now < _token_expiry - 30:
        return _token

    url = f"{COREOPS_AUTH_SERVER_URL.rstrip('/')}/authentication/tokens/request"
    headers = {
        "Authorization": basic_auth_header(),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    sess = get_session()
    resp = sess.post(url, data={"grant_type": "password"}, headers=headers, timeout=10, verify=VERIFY_SSL)
    resp.raise_for_status()
    data = resp.json()

    token = data.get("accessToken") or data.get("access_token") or data.get("token")
    if not token:
        raise RuntimeError(f"No token in auth response: {list(data.keys())}")

    expires_in = data.get("expires_in") or data.get("expiresIn") or 600
    _token_expiry = now + float(expires_in)
    _token = token
    log.info("Auth token acquired, expires in %ds", expires_in)
    return token


def auth_headers() -> dict:
    token = ensure_token()
    return {
        "Authorization": f"Bearer {token}",
        "X-API-KEY": COREOPS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def api_key_only_headers() -> dict:
    """Headers with just API key, no bearer token (some endpoints may work this way)."""
    return {
        "X-API-KEY": COREOPS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "coreops-proxy"})


@app.route("/v1/devices/ids/assign", methods=["POST"])
def assign_device_id():
    """Proxy device ID assignment to CoreOps.

    Request body: {"snr": "0964"}
    Response: {"deviceId": "70B3D584C01E1FCC", "snr": "0964"}
    """
    data = request.get_json() or {}
    snr = data.get("snr") or request.args.get("snr") or request.args.get("boardSerialNumber")

    if not snr:
        return jsonify({"error": "snr is required"}), 400

    try:
        url = f"{COREOPS_SERVER_URL.rstrip('/')}/devices/ids/assign"
        sess = get_session()
        headers = auth_headers()

        resp = sess.post(url, params={"boardSerialNumber": snr}, headers=headers, timeout=10, verify=VERIFY_SSL)

        # Retry once on 401 with fresh token
        if resp.status_code == 401:
            global _token
            _token = None
            headers = auth_headers()
            resp = sess.post(url, params={"boardSerialNumber": snr}, headers=headers, timeout=10, verify=VERIFY_SSL)

        # Try API-key-only if bearer auth failed
        if resp.status_code == 401:
            log.info("Bearer auth failed, trying API-key-only auth")
            headers = api_key_only_headers()
            resp = sess.post(url, params={"boardSerialNumber": snr}, headers=headers, timeout=10, verify=VERIFY_SSL)

        if not resp.ok:
            log.error("CoreOps error: %d %s", resp.status_code, resp.text[:200])
            return jsonify({"error": f"CoreOps error: {resp.status_code}", "detail": resp.text[:500]}), resp.status_code

        result = resp.json()
        device_id = result.get("deviceId")

        if not device_id:
            return jsonify({"error": "No deviceId in CoreOps response", "raw": result}), 500

        log.info("Assigned device ID %s to SNR %s", device_id, snr)
        return jsonify({"deviceId": device_id, "snr": snr})

    except requests.Timeout:
        log.error("CoreOps timeout for SNR %s", snr)
        return jsonify({"error": "CoreOps timeout"}), 504
    except requests.ConnectionError as e:
        log.error("CoreOps connection error: %s", e)
        return jsonify({"error": f"CoreOps connection error: {e}"}), 502
    except Exception as e:
        log.exception("Unexpected error")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    # Validate config
    missing = []
    if not COREOPS_API_KEY:
        missing.append("COREOPS_API_KEY")
    if not COREOPS_AUTH_USER:
        missing.append("COREOPS_AUTH_USER")
    if not COREOPS_AUTH_PASS:
        missing.append("COREOPS_AUTH_PASS")

    if missing:
        log.error("Missing required env vars: %s", ", ".join(missing))
        exit(1)

    log.info("Starting CoreOps proxy on port %d", port)
    log.info("CoreOps server: %s", COREOPS_SERVER_URL)
    log.info("Auth server: %s", COREOPS_AUTH_SERVER_URL)

    app.run(host="0.0.0.0", port=port)
