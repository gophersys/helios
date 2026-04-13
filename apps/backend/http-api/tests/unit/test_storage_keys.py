"""Unit tests for storage path helpers in src/services/storage/client.py."""

from services.storage.client import (
    asset_set_zip_filename,
    modem_firmware_key,
    product_asset_key,
    sanitize_filename,
)


# ── sanitize_filename ────────────────────────────────────────────────────


class TestSanitizeFilename:
    def test_strips_special_chars(self):
        assert sanitize_filename("hello world!@#.hex") == "hello_world___.hex"

    def test_empty_string_returns_download(self):
        assert sanitize_filename("") == "download"

    def test_already_clean_unchanged(self):
        assert sanitize_filename("app_nrf52840.hex") == "app_nrf52840.hex"

    def test_preserves_dots_hyphens_underscores(self):
        assert sanitize_filename("v1.2.0-debug_build.hex") == "v1.2.0-debug_build.hex"

    def test_unicode_replaced(self):
        result = sanitize_filename("firmware\u00e9.bin")
        assert result == "firmware_.bin"

    def test_all_special_chars_returns_underscores(self):
        # All replaced chars, non-empty result
        result = sanitize_filename("!!!")
        assert result == "___"

    def test_spaces_become_underscores(self):
        assert sanitize_filename("my file name.zip") == "my_file_name.zip"


# ── product_asset_key ────────────────────────────────────────────────────


class TestProductAssetKey:
    def test_normal_path(self):
        result = product_asset_key(
            "alpha", "b0", "VALIDATION", 1, "1.2.0", "debug", "MFG_APP", "app.hex"
        )
        assert result == "products/alpha/b0/validation/smoke/1.2.0-debug/MFG_APP/app.hex"

    def test_validation_stage_2_driver(self):
        result = product_asset_key(
            "alpha", "b0", "VALIDATION", 2, "1.0.0", "release", "APP", "fw.hex"
        )
        assert "/driver/" in result

    def test_validation_stage_3_integration(self):
        result = product_asset_key(
            "alpha", "b0", "VALIDATION", 3, "1.0.0", "release", "APP", "fw.hex"
        )
        assert "/integration/" in result

    def test_validation_stage_4_regression(self):
        result = product_asset_key(
            "alpha", "b0", "VALIDATION", 4, "2.0.0", "debug", "LABEL", "f.hex"
        )
        assert "/regression/" in result

    def test_validation_stage_5_fuota(self):
        result = product_asset_key(
            "alpha", "b0", "VALIDATION", 5, "3.0.0", "debug", "OTA", "ota.bin"
        )
        assert "/fuota/" in result

    def test_manufacturing_stage_1(self):
        result = product_asset_key(
            "alpha", "b0", "MANUFACTURING", 1, "1.0.0", "mfg", "MFG_APP", "app.hex"
        )
        assert result == "products/alpha/b0/manufacturing/manufacturing/1.0.0-mfg/MFG_APP/app.hex"

    def test_explicit_stage_name_overrides_lookup(self):
        result = product_asset_key(
            "alpha", "b0", "VALIDATION", 1, "1.0.0", "debug", "APP", "fw.hex",
            stage_name="custom_stage",
        )
        assert "/custom_stage/" in result
        assert "/smoke/" not in result

    def test_null_slug_fallback(self):
        result = product_asset_key(
            None, "b0", "VALIDATION", 1, "1.0.0", "debug", "APP", "fw.hex"
        )
        assert result.startswith("products/unknown/")

    def test_null_revision_fallback(self):
        result = product_asset_key(
            "alpha", None, "VALIDATION", 1, "1.0.0", "debug", "APP", "fw.hex"
        )
        assert "/unscoped/" in result

    def test_null_stage_type_fallback(self):
        result = product_asset_key(
            "alpha", "b0", None, None, "1.0.0", "debug", "APP", "fw.hex"
        )
        assert "/general/" in result

    def test_stage_name_sanitized(self):
        result = product_asset_key(
            "alpha", "b0", "VALIDATION", 1, "1.0.0", "debug", "APP", "fw.hex",
            stage_name="My Stage!",
        )
        # sanitize_filename lowercases and replaces special chars
        assert "/my_stage_/" in result

    def test_all_nulls(self):
        """All optional params None should still produce a valid path."""
        result = product_asset_key(
            None, None, None, None, "1.0.0", "debug", "APP", "fw.hex"
        )
        assert result.startswith("products/unknown/unscoped/general/general/")


# ── modem_firmware_key ───────────────────────────────────────────────────


class TestModemFirmwareKey:
    def test_normal_path(self):
        result = modem_firmware_key("alpha", "b0", "2.0.2", "mfw.zip")
        assert result == "products/alpha/b0/modem/2.0.2/mfw.zip"

    def test_null_slug_fallback(self):
        result = modem_firmware_key(None, "b0", "2.0.2", "mfw.zip")
        assert result.startswith("products/unknown/")

    def test_null_revision_fallback(self):
        result = modem_firmware_key("alpha", None, "2.0.2", "mfw.zip")
        assert "/unscoped/" in result

    def test_filename_sanitized(self):
        result = modem_firmware_key("alpha", "b0", "1.0.0", "modem fw!.zip")
        assert result.endswith("modem_fw_.zip")


# ── asset_set_zip_filename ───────────────────────────────────────────────


class TestAssetSetZipFilename:
    def test_normal_filename(self):
        result = asset_set_zip_filename("alpha", "b0", "VALIDATION", 1, "1.2.0", "debug")
        assert result == "alpha-b0-validation-smoke-v1.2.0-debug.zip"

    def test_manufacturing_stage(self):
        result = asset_set_zip_filename("alpha", "b0", "MANUFACTURING", 1, "1.0.0", "mfg")
        assert result == "alpha-b0-manufacturing-manufacturing-v1.0.0-mfg.zip"

    def test_null_slug_fallback(self):
        result = asset_set_zip_filename(None, "b0", "VALIDATION", 1, "1.0.0", "debug")
        assert result.startswith("unknown-")

    def test_null_revision_fallback(self):
        result = asset_set_zip_filename("alpha", None, "VALIDATION", 1, "1.0.0", "debug")
        assert "-unscoped-" in result

    def test_null_stage_type_fallback(self):
        result = asset_set_zip_filename("alpha", "b0", None, None, "1.0.0", "debug")
        assert "-general-general-" in result

    def test_null_variant_fallback(self):
        result = asset_set_zip_filename("alpha", "b0", "VALIDATION", 1, "1.0.0", None)
        assert result.endswith("-default.zip")

    def test_null_version_fallback(self):
        result = asset_set_zip_filename("alpha", "b0", "VALIDATION", 1, None, "debug")
        assert "-v0.0.0-" in result

    def test_explicit_stage_name_overrides(self):
        result = asset_set_zip_filename(
            "alpha", "b0", "VALIDATION", 1, "2.0.0", "release",
            stage_name="custom",
        )
        assert "-custom-" in result
        assert "-smoke-" not in result
