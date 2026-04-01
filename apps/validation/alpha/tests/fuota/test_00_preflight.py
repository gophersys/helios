"""Preflight checks — validate environment before any FUOTA flow runs.

Every check is a separate test function so the frontend shows exactly
which prerequisite failed. With -x (fail fast), any failure here stops
the entire run immediately.

Tests that don't need MTIB (device_config, corecloud_auth, pipeline_builds,
modem_firmware, storage_access) use standalone fixtures and run even if
MTIB is unreachable. Tests that need MTIB (mtib_connection, jlink_probes)
use the root conftest's ``ctx`` fixture.
"""

import os

import pytest


class TestPreflight:
    """Environment validation — all checks must pass before FUOTA flows."""

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

    def test_jlink_probes(self, ctx):
        """Verify J-Link programmers are available on MTIB.

        Uses ctx.mtib — if MTIB connection failed, this test fails
        (which is correct: no point continuing without MTIB).

        TODO: Read the DUT SNR from the J-Link probe or MFG shell and verify
        it matches DEVICE_SNR. This would catch fixture slot misconfiguration
        (wrong device in the slot definition) before wasting time on flash +
        personalize + FUOTA for the wrong device.
        """
        programmers, err = ctx.mtib.ListProgrammers()
        assert err is None, f"ListProgrammers RPC failed: {err}"

        if programmers and len(programmers) > 0:
            for p in programmers:
                print(f"Probe: SNR={p.serial}  host={p.host}  connected={p.connected}")
            print(f"{len(programmers)} J-Link probe(s) detected")
        else:
            print("ListProgrammers returned empty (DUT likely unpowered)")
            print("J-Link probes will be verified during flash step")
            print("WARNING: If flash fails, check J-Link USB connections")

    def test_modem_firmware(self, stage_assets):
        """Verify modem firmware is available in pipeline triggerData."""
        modem_zip = stage_assets.modem_zip()

        if modem_zip:
            print(f"Modem FW:     {modem_zip}")
        else:
            print("WARNING: No modem firmware in pipeline triggerData")
            print("Modem flash will be skipped during test_02_flash_firmware")
            print("This may cause POST step 7 (modem FW version) to fail")

    def test_mtib_connection(self, ctx):
        """Verify MTIB server is reachable. Sets both power rails OFF as baseline.

        Uses ctx.mtib — TestContext.connect() already verified connectivity,
        but we do a power read to confirm the link is active, then disable
        both power rails to ensure a clean starting state.
        """
        from corekinect.mtib_client.v1.client.types import PowerChannel

        addr = os.environ.get("MTIB_ADDRESS", "?")
        print(f"MTIB address: {addr}")

        # Disable both power rails first (clean baseline)
        ctx.mtib.PowerDisable(channel=PowerChannel.DUT)
        ctx.mtib.PowerDisable(channel=PowerChannel.CHARGER)
        print(f"Power rails: both OFF (clean baseline)")

        import time
        time.sleep(1)

        result, err = ctx.mtib.PowerRead(channel=PowerChannel.DUT)
        assert err is None, f"MTIB power read failed: {err}"
        print(f"Ch0 (DUT):     {result.voltage_v:.2f}V  {result.current_ma:.2f}mA")

        result_ch1, err_ch1 = ctx.mtib.PowerRead(channel=PowerChannel.CHARGER)
        if not err_ch1:
            print(f"Ch1 (Charger): {result_ch1.voltage_v:.2f}V  {result_ch1.current_ma:.2f}mA")

        uart_status = "running" if ctx.uart._running else "stopped"
        print(f"UART capture:  {uart_status}")
        print(f"MTIB connection OK")

    def test_pipeline_builds(self, stage_assets):
        """Verify all pipeline builds are present and successful."""
        pipeline_id = os.environ.get("PIPELINE_ID", "?")
        print(f"Pipeline ID: {pipeline_id}")

        missing = stage_assets.missing_labels()
        assert missing == [], (
            f"Pipeline missing required builds: {missing}. "
            f"Available: {stage_assets.labels}"
        )

        print(f"{'Label':<24} {'Version':<12}")
        print(f"{'-'*36}")
        for label in sorted(stage_assets.labels):
            build = stage_assets.by_label(label)
            version = build.version()
            print(f"{label:<24} v{version or '?':<11}")

        print(f"All {len(stage_assets.labels)} builds OK")

    def test_storage_access(self, stage_assets):
        """Verify MinIO storage is accessible for firmware artifacts."""
        storage_url = os.environ.get("STORAGE_URL", "?")
        bucket = os.environ.get("STORAGE_BUCKET_NAME", "?")
        print(f"MinIO URL:    {storage_url}")
        print(f"Bucket:       {bucket}")

        first_label = next(iter(stage_assets.labels), None)
        if first_label:
            build = stage_assets.by_label(first_label)
            print(f"Test build:   {first_label} (v{build.version()})")

        print(f"Storage access OK")
