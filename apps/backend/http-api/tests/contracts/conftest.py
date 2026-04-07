"""
Contract test fixtures — re-exports from root conftest for convenience.

The root conftest.py provides all fixtures used here (mock_db, authed_client,
client, app). This file exists so IDEs and pytest discovery correctly scope
the contracts subdirectory without re-importing anything.
"""

# Re-export make_obj so contract tests can import it from one place.
from tests.conftest import make_obj  # noqa: F401
