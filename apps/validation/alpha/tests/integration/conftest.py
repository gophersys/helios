"""Integration-specific pytest fixtures.

Provides:
- Harness command interface
- State machine observers
- IPC message capture
"""

import pytest

from corekinect.utils import Logger

log = Logger(log_name="integration")


@pytest.fixture(scope="module")
def harness(ctx):
    """Harness command interface.

    Provides methods to query and control firmware internals
    via the concord_harness shell commands.

    Returns None if harness is not available (production firmware).
    """
    # TODO: Implement HarnessClient
    # - Connect to APP UART
    # - Send harness commands
    # - Parse responses
    pytest.skip("Harness client not implemented")
