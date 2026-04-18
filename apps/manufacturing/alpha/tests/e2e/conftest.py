"""pytest configuration for Alpha manufacturing E2E tests.

These tests drive the Concord HTTP API directly and assert against
real hardware behind a manufacturing fixture. They are NOT part of the
package's regular test suite (which runs inside the test runner on the
DUTs themselves). They are invoked explicitly by a human or a CI job
to verify end-to-end correctness of the parallel runner.

Required environment:
    CONCORD_API_URL        Base URL of the target environment's HTTP API
    CONCORD_API_KEY        Admin API key (ck_ci_admin_* from the seed)
    CONCORD_E2E_PRODUCT_ID Product ID for Alpha in the target env
    CONCORD_E2E_FIXTURE_ID Fixture ID for the manufacturing fixture
    CONCORD_E2E_ASSET_SET_ID AssetSet ID for the B0 firmware to use
    CONCORD_E2E_STANDALONE_SNR  SNR for single-slot baseline run
    CONCORD_E2E_PANEL_SNRS      Comma-separated SNRs for the panel run
                                (order matches slot index 0..N-1)

Tests skip automatically if any of these are missing so the suite
doesn't break CI when run in a non-E2E environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

import pytest


@dataclass(frozen=True)
class E2EConfig:
    """Frozen bundle of all the IDs/URLs needed to talk to a target env."""

    api_url: str
    api_key: str
    product_id: str
    fixture_id: str
    asset_set_id: str
    standalone_snr: str
    panel_snrs: List[str]

    @property
    def num_panel_slots(self) -> int:
        return len(self.panel_snrs)


def _env_or_skip(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} not set — skipping E2E test")
    return value


@pytest.fixture(scope="session")
def e2e_config() -> E2EConfig:
    api_url = _env_or_skip("CONCORD_API_URL")
    api_key = _env_or_skip("CONCORD_API_KEY")
    product_id = _env_or_skip("CONCORD_E2E_PRODUCT_ID")
    fixture_id = _env_or_skip("CONCORD_E2E_FIXTURE_ID")
    asset_set_id = _env_or_skip("CONCORD_E2E_ASSET_SET_ID")
    standalone_snr = _env_or_skip("CONCORD_E2E_STANDALONE_SNR")
    panel_snrs_raw = _env_or_skip("CONCORD_E2E_PANEL_SNRS")
    panel_snrs = [s.strip() for s in panel_snrs_raw.split(",") if s.strip()]
    if len(panel_snrs) < 2:
        pytest.skip(
            f"CONCORD_E2E_PANEL_SNRS must list ≥2 SNRs for a panel run, got {panel_snrs_raw!r}"
        )
    return E2EConfig(
        api_url=api_url.rstrip("/"),
        api_key=api_key,
        product_id=product_id,
        fixture_id=fixture_id,
        asset_set_id=asset_set_id,
        standalone_snr=standalone_snr,
        panel_snrs=panel_snrs,
    )
