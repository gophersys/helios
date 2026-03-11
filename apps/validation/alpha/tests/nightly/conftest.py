"""Nightly-specific pytest fixtures and configuration.

Provides:
- NightlyConfig: All configuration for Nightly tests
- Extended timeout defaults
- Cloud message helpers
"""

import pytest

from corekinect.utils import Logger

log = Logger(log_name="nightly")


# Nightly tests don't need the pipeline_assets fixture
# They use pre-flashed firmware from Gate or manual setup
