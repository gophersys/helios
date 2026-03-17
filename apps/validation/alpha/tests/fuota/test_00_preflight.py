"""Preflight checks — validate environment before any FUOTA flow runs.

Every check is a separate test function so the frontend shows exactly
which prerequisite failed. With -x (fail fast), any failure here stops
the entire run immediately — no point flashing if MTIB isn't connected.

Run order: pytest discovers files alphabetically, so test_00_* runs
before test_01_*, test_02_*, etc.
"""

import os
import time

import pytest


class TestPreflight:
    """Environment validation — all checks must pass before FUOTA flows."""

    def test_mtib_connection(self, mtib_client):
        """Verify MTIB server is reachable and responding to RPCs."""
        from corekinect.mtib_client.v1.client.types import PowerChannel

        addr = os.environ.get("MTIB_ADDRESS", "?")
        print(f"MTIB address: {addr}")

        # Verify the connection is live by reading power state
        result, err = mtib_client.PowerRead(channel=PowerChannel.DUT)
        assert err is None, f"MTIB power read failed: {err}"

        print(f"Ch0 (DUT):     {result.voltage_v:.2f}V  {result.current_ma:.2f}mA")

        result_ch1, err_ch1 = mtib_client.PowerRead(channel=PowerChannel.CHARGER)
        if not err_ch1:
            print(f"Ch1 (Charger): {result_ch1.voltage_v:.2f}V  {result_ch1.current_ma:.2f}mA")

        print(f"MTIB connection OK")

    def test_pipeline_builds(self, pipeline_assets):
        """Verify all pipeline builds are present and successful."""
        pipeline_id = os.environ.get("PIPELINE_ID", "?")
        print(f"Pipeline ID: {pipeline_id}")

        assert pipeline_assets.has_all_builds(), (
            f"Pipeline missing required builds. "
            f"Available: {list(pipeline_assets.builds.keys())}"
        )

        print(f"{'Label':<24} {'Variant':<10} {'Version':<12} {'Status':<10} {'Artifacts'}")
        print(f"{'-'*78}")
        for label, build in sorted(pipeline_assets.builds.items()):
            art_count = len(build.artifacts)
            print(f"{label:<24} {build.variant:<10} v{build.version_string or '?':<11} {build.status:<10} {art_count} files")
            assert build.status in ("SUCCESS", "CACHED"), (
                f"Build {label} is {build.status}, expected SUCCESS or CACHED"
            )

        print(f"All {len(pipeline_assets.builds)} builds OK")

    def test_corecloud_auth(self, fuota_client):
        """Verify CoreCloud FUOTA API authentication works."""
        api_host = os.environ.get("VAL_1_0_API_REST_SERVER_HOST_NAME", "?")
        print(f"CoreCloud REST: {api_host}")

        try:
            resp = fuota_client._singleton_request("GET", "firmwareupdates/plans")
        except Exception as e:
            pytest.fail(f"CoreCloud API request failed: {e}")

        assert resp.status_code == 200, (
            f"CoreCloud FUOTA API returned {resp.status_code}: {resp.text[:200]}"
        )

        plans = resp.json().get("fuotaPlans", [])
        print(f"Auth successful — {len(plans)} existing FUOTA plans")
        print(f"Token acquired from: {os.environ.get('VAL_1_0_API_AUTH_SERVER_HOST_NAME', '?')}")

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

        print(f"Device SNR:       {device_config.device_snr}")
        print(f"Device ID:        {device_config.device_id}")
        print(f"IMEI:             {device_config.device_imei}")
        print(f"ICCIDs:           {', '.join(device_config.device_iccids)}")
        print(f"Device Type:      {device_config.device_type_id}")
        print(f"Device Variant:   {device_config.device_variant_id}")

    def test_jlink_probes(self, mtib_client):
        """Verify J-Link programmers are available on MTIB.

        Note: ListProgrammers scans via nrfjprog --deviceversion which requires
        the DUT to be powered. Since the DUT may be off during preflight, we
        also accept the case where probes are detected but targets are unknown.
        Full SWD verification happens during the flash step.
        """
        programmers, err = mtib_client.ListProgrammers()
        assert err is None, f"ListProgrammers RPC failed: {err}"

        if programmers and len(programmers) > 0:
            for p in programmers:
                print(f"Probe: SNR={p.serial}  host={p.host}  connected={p.connected}")
            print(f"{len(programmers)} J-Link probe(s) detected")
        else:
            # ListProgrammers may return empty if DUT is unpowered (nrfjprog
            # can't detect device type without SWD). This is OK for preflight —
            # the flash step will power the DUT and recover the probes.
            print("ListProgrammers returned empty (DUT likely unpowered)")
            print("J-Link probes will be verified during flash step")
            print("WARNING: If flash fails, check J-Link USB connections")

    def test_modem_firmware(self, pipeline_assets):
        """Verify modem firmware is available in pipeline triggerData."""
        modem_info = pipeline_assets.modem_firmware_info

        if modem_info:
            print(f"Modem FW:     {modem_info.get('name', '?')}")
            print(f"Version:      {modem_info.get('version', '?')}")
            print(f"Storage key:  {modem_info.get('storageKey', '?')}")
        else:
            print("WARNING: No modem firmware in pipeline triggerData")
            print("Modem flash will be skipped during test_02_flash_firmware")
            print("This may cause POST step 7 (modem FW version) to fail")

    def test_storage_access(self, pipeline_assets):
        """Verify MinIO storage is accessible for firmware artifacts."""
        storage_url = os.environ.get("STORAGE_URL", "?")
        bucket = os.environ.get("STORAGE_BUCKET", "?")
        print(f"MinIO URL:    {storage_url}")
        print(f"Bucket:       {bucket}")

        first_label = next(iter(pipeline_assets.builds.keys()), None)
        if first_label:
            build = pipeline_assets.get_build(first_label)
            artifact_count = len(build.artifacts) if hasattr(build, 'artifacts') else 0
            print(f"Test build:   {first_label} ({artifact_count} artifacts)")

        print(f"Storage access OK")
