"""Concord API client for corectl.

All corectl commands talk to the Concord HTTP API exclusively.
No direct database access, no CoreCloud access, no MTIB access.
"""

from typing import Any, Dict, Optional

import requests


class ConcordAPI:
    """Thin client for the Concord HTTP API.

    Args:
        base_url: API base URL (e.g., http://localhost:9001).
        token: API key or auth token.
    """

    def __init__(self, base_url: str, token: str, tls_verify: bool = True):
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.verify = tls_verify
        self._session.headers.update({
            "Authorization": f"ApiKey {token}",
            "Content-Type": "application/json",
        })

    def get(self, path: str, **kwargs) -> requests.Response:
        """GET request to Concord API."""
        return self._session.get(f"{self._base_url}{path}", **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        """POST request to Concord API."""
        return self._session.post(f"{self._base_url}{path}", **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        """PUT request to Concord API."""
        return self._session.put(f"{self._base_url}{path}", **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        """DELETE request to Concord API."""
        return self._session.delete(f"{self._base_url}{path}", **kwargs)

    def health_check(self) -> bool:
        """Check if the API is reachable."""
        try:
            resp = self.get("/v2/docs")
            return resp.status_code == 200
        except requests.RequestException:
            return False
