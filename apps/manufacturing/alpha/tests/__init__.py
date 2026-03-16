"""pytest-based manufacturing tests.

This module contains manufacturing tests migrated from the legacy
Test/TestStep framework to pytest. Tests use session-scoped fixtures
from conftest.py and stream results to Concord via the reporter plugin.

Directory structure:
    post/           - POST (Power-On Self Test) sequence
    electrical/     - Electrical characterization tests
    fw_flash/       - Firmware flash tests

Run with:
    cd apps/manufacturing/alpha
    PYTHONPATH=.:../../../libs/python:../../../libs pytest tests_pytest/ -v
"""
