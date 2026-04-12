"""Manufacturing app configuration.

Environment-driven. All values have sensible defaults for local development.
Production values come from K8s env vars or .env file in the container.
"""

import os

from dotenv import load_dotenv

load_dotenv()


# ── CoreOps Proxy ──────────────────────────────────────────────────────────
PROXY_SERVER_URL = os.environ.get("PROXY_SERVER_URL", "http://10.4.45.30:8001")

# ── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
