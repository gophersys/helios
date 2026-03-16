"""Preflight checks — validate environment before any FUOTA flow runs.

Every check is a separate test function so the frontend shows exactly
which prerequisite failed. With -x (fail fast), any failure here stops
the entire run immediately — no point flashing if MTIB isn't connected.

Run order: pytest discovers files alphabetically, so test_00_* runs
before test_01_*, test_02_*, etc.
"""

import pytest


class TestPreflight:
    """Environment validation — all checks must pass before FUOTA flows."""

    def test_mtib_connection(self, mtib_client):
        """Verify MTIB server is reachable and responding to RPCs."""
        from corekinect.mtib_client.v1.client.types import PowerChannel

        # Verify the connection is live by reading power state
        # DutPowerRead returns (result, err) — we just need it to not error
        result, err = mtib_client.DutPowerRead(channel=PowerChannel.DUT)
        assert err is None, f"MTIB power read failed: {err}"

        print(f"  MTIB connected (ch0 voltage: {result.voltage_v:.2f}V)")

    def test_pipeline_builds(self, pipeline_assets):
        """Verify all pipeline builds are present and successful."""
        summary = pipeline_assets.summary()
        print(f"\n{summary}")

        assert pipeline_assets.has_all_builds(), (
            f"Pipeline missing required builds. "
            f"Available: {list(pipeline_assets.builds.keys())}"
        )

        # Verify each build has a version and SUCCESS status
        for label, build in pipeline_assets.builds.items():
            assert build.status == "SUCCESS", (
                f"Build {label} is not SUCCESS (status={build.status})"
            )
            print(f"  {label}: v{build.version_string} [{build.status}]")

    def test_corecloud_auth(self, fuota_client):
        """Verify CoreCloud FUOTA API authentication works."""
        # Hit a read-only endpoint to verify auth
        try:
            resp = fuota_client._singleton_request("GET", "firmwareupdates/plans")
        except Exception as e:
            pytest.fail(f"CoreCloud API request failed: {e}")

        assert resp.status_code == 200, (
            f"CoreCloud FUOTA API returned {resp.status_code}: {resp.text[:200]}"
        )

        plans = resp.json().get("fuotaPlans", [])
        print(f"  CoreCloud auth OK ({len(plans)} existing plans)")

    def test_device_config(self, device_config):
        """Verify device identity is configured (SNR, device_id, IMEI, ICCIDs)."""
        errors = []

        if not device_config.device_snr:
            errors.append("DEVICE_SNR is required")
        if not device_config.device_id:
            errors.append("DEVICE_ID is required")
        if not device_config.device_imei:
            errors.append("DEVICE_IMEI is required (skip modem read)")
        if not device_config.device_iccids:
            errors.append("DEVICE_ICCIDS is required (skip modem read)")

        assert not errors, (
            "Device config incomplete:\n  " + "\n  ".join(errors)
        )

        print(f"  SNR:     {device_config.device_snr}")
        print(f"  ID:      {device_config.device_id}")
        print(f"  IMEI:    {device_config.device_imei}")
        print(f"  ICCIDs:  {len(device_config.device_iccids)} configured")

    def test_jlink_probes(self, mtib_client):
        """Verify J-Link programmers are available on MTIB."""
        programmers, err = mtib_client.ListProgrammers()
        assert err is None, f"ListProgrammers failed: {err}"
        assert programmers and len(programmers) > 0, (
            "No J-Link programmers found on MTIB — cannot flash firmware"
        )

        for p in programmers:
            print(f"  Probe: SNR={p.serial_number}")

        print(f"  {len(programmers)} J-Link probe(s) available")
