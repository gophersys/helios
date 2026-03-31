"""Common assertions for validation tests.

Re-exports from the corekinect.test framework. Existing imports
from ``tests.common.assertions`` continue to work unchanged.

Usage:
    from tests.common.assertions import assert_powered, assert_current_in_range

    assert_powered(ctx.fixture, min_current_ma=5.0)
    assert_current_in_range(current_ma, min_ma=0.05, max_ma=0.1, name="sleep")
"""

# Re-export everything from the framework module
from corekinect.test.assertions import (  # noqa: F401
    assert_powered,
    assert_current_in_range,
    assert_cloud_message,
    assert_flash_success,
    assert_fuota_progress,
)
