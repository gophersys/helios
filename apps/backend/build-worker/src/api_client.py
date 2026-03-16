"""HTTP client for the Concord API."""

import logging
from pathlib import Path
from typing import Dict, Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("build-worker")


class ConcordApiClient:
    """HTTP client for Concord API requests."""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"ApiKey {self.api_key}",
            "Content-Type": "application/json",
        }

    def api_get(self, path: str) -> Optional[dict]:
        """GET request to API."""
        try:
            resp = requests.get(
                f"{self.api_url}{path}",
                headers=self._headers(),
                timeout=30,
                verify=False,
            )
            if resp.status_code >= 400:
                log.error("API GET %s: %d %s", path, resp.status_code, resp.text[:200])
                return None
            return resp.json()
        except Exception as e:
            log.error("API GET %s failed: %s", path, e)
            return None

    def api_post(self, path: str, data: dict) -> Optional[dict]:
        """POST request to API."""
        try:
            resp = requests.post(
                f"{self.api_url}{path}",
                json=data,
                headers=self._headers(),
                timeout=30,
                verify=False,
            )
            if resp.status_code >= 400:
                log.error("API POST %s: %d %s", path, resp.status_code, resp.text[:200])
                return None
            return resp.json()
        except Exception as e:
            log.error("API POST %s failed: %s", path, e)
            return None

    def api_patch(self, path: str, data: dict) -> Optional[dict]:
        """PATCH request to API."""
        try:
            resp = requests.patch(
                f"{self.api_url}{path}",
                json=data,
                headers=self._headers(),
                timeout=30,
                verify=False,
            )
            if resp.status_code >= 400:
                log.error("API PATCH %s: %d %s", path, resp.status_code, resp.text[:200])
                return None
            return resp.json()
        except Exception as e:
            log.error("API PATCH %s failed: %s", path, e)
            return None

    def upload_file(self, path: str, file_path: Path, name: str) -> bool:
        """Upload a file as multipart form data."""
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    f"{self.api_url}{path}",
                    files={"file": (name, f)},
                    headers={"Authorization": f"ApiKey {self.api_key}"},
                    timeout=120,
                    verify=False,
                )
            if resp.status_code >= 400:
                log.error("Upload %s: %d %s", name, resp.status_code, resp.text[:200])
                return False
            return True
        except Exception as e:
            log.error("Upload %s failed: %s", name, e)
            return False

    def stream_log_chunk(self, job_id: str, chunk: str) -> None:
        """Stream a log chunk to the API for WebSocket broadcast."""
        try:
            # Fire and forget - don't block build on API calls
            requests.post(
                f"{self.api_url}/v2/builds/{job_id}/log",
                json={"chunk": chunk},
                headers=self._headers(),
                timeout=5,
                verify=False,
            )
        except Exception:
            pass  # Don't fail build if streaming fails
