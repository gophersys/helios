"""Unit tests for FuotaClient — pure logic paths without network.

Tests _safe_json parsing, constructor state, upload file validation,
and data transformation helpers.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from corekinect.errors import CloudError
from corekinect.test.fuota_client import FuotaClient
from corekinect.utils import Logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL = object()


def _mock_response(json_data=_SENTINEL, text="", status_code=200, json_raises=None):
    """Create a mock requests.Response with configurable behavior."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if json_raises:
        resp.json.side_effect = json_raises
    elif json_data is not _SENTINEL:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("No JSON content")
    return resp


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestFuotaClientConstructor:
    """Tests for FuotaClient.__init__() state setup."""

    def test_default_api_env(self):
        """Default api_env is VAL_1_0."""
        client = FuotaClient()
        assert client._api_env == "VAL_1_0"

    def test_custom_api_env(self):
        """Custom api_env is stored."""
        client = FuotaClient(api_env="STAGING_1_0")
        assert client._api_env == "STAGING_1_0"

    def test_api_not_eagerly_initialized(self):
        """API client should not be created during construction."""
        client = FuotaClient()
        assert client._api is None
        assert client._base_url is None

    def test_logger_child_created(self):
        """When a parent logger is passed, creates a child logger."""
        parent = Logger(log_name="test_parent")
        client = FuotaClient(logger=parent)
        assert client._log is not None

    def test_default_logger_used(self):
        """When no logger is passed, module-level logger is used."""
        client = FuotaClient()
        assert client._log is not None


# ---------------------------------------------------------------------------
# _safe_json
# ---------------------------------------------------------------------------

class TestSafeJson:
    """Tests for _safe_json() response parsing."""

    def setup_method(self):
        """Setup method."""
        self.client = FuotaClient()

    def test_valid_json_dict(self):
        """Valid JSON object returns the dict."""
        resp = _mock_response(json_data={"planId": 42, "stages": []})
        result = self.client._safe_json(resp, "test context")
        assert result == {"planId": 42, "stages": []}

    def test_empty_dict(self):
        """Empty JSON object is valid."""
        resp = _mock_response(json_data={})
        result = self.client._safe_json(resp, "test context")
        assert result == {}

    def test_invalid_json_raises_cloud_error(self):
        """Non-JSON response body raises CloudError."""
        resp = _mock_response(json_raises=ValueError("Expecting value"))
        with pytest.raises(CloudError, match="invalid JSON response"):
            self.client._safe_json(resp, "upload check")

    def test_json_parse_error_includes_context(self):
        """Error message includes the context string."""
        resp = _mock_response(json_raises=ValueError("bad"))
        with pytest.raises(CloudError, match="upload check"):
            self.client._safe_json(resp, "upload check")

    def test_list_response_raises_cloud_error(self):
        """JSON array (not dict) raises CloudError."""
        resp = _mock_response(json_data=[1, 2, 3])
        with pytest.raises(CloudError, match="expected dict, got list"):
            self.client._safe_json(resp, "plan creation")

    def test_string_response_raises_cloud_error(self):
        """JSON string (not dict) raises CloudError."""
        resp = _mock_response(json_data="just a string")
        with pytest.raises(CloudError, match="expected dict, got str"):
            self.client._safe_json(resp, "plan creation")

    def test_integer_response_raises_cloud_error(self):
        """JSON integer (not dict) raises CloudError."""
        resp = _mock_response(json_data=42)
        with pytest.raises(CloudError, match="expected dict, got int"):
            self.client._safe_json(resp, "progress check")

    def test_none_response_raises_cloud_error(self):
        """JSON null (not dict) raises CloudError."""
        resp = _mock_response(json_data=None)
        with pytest.raises(CloudError, match="expected dict, got NoneType"):
            self.client._safe_json(resp, "status")

    def test_nested_dict_returned_intact(self):
        """Deeply nested dict is returned without modification."""
        data = {"devices": [{"id": "A", "status": {"active": True}}]}
        resp = _mock_response(json_data=data)
        result = self.client._safe_json(resp, "search")
        assert result == data


# ---------------------------------------------------------------------------
# upload_cfw — file validation
# ---------------------------------------------------------------------------

class TestUploadCfwValidation:
    """Tests for upload_cfw() file existence check."""

    def test_missing_file_raises(self):
        """FileNotFoundError raised for non-existent CFW path."""
        client = FuotaClient()
        with pytest.raises(FileNotFoundError, match="CFW file not found"):
            client.upload_cfw("/nonexistent/path/108.0.5.2-BM.cfw")

    def test_missing_file_includes_path(self):
        """Error message includes the missing file path."""
        client = FuotaClient()
        path = "/tmp/does_not_exist_test_12345.cfw"
        with pytest.raises(FileNotFoundError, match=path):
            client.upload_cfw(path)


# ---------------------------------------------------------------------------
# upload_cfw — response handling (mocked API)
# ---------------------------------------------------------------------------

class TestUploadCfwResponses:
    """Tests for upload_cfw() response handling with mocked singleton_request."""

    def test_successful_upload(self, tmp_path):
        """204 response means successful upload."""
        cfw_file = tmp_path / "108.0.5.2-BM.cfw"
        cfw_file.write_bytes(b"\x00" * 100)

        client = FuotaClient()
        resp = _mock_response(status_code=204, text="")
        with patch.object(client, "_singleton_request", return_value=resp):
            client.upload_cfw(str(cfw_file))  # should not raise

    def test_already_exists_skipped(self, tmp_path):
        """400 with 'already exists' is silently skipped."""
        cfw_file = tmp_path / "108.0.5.2-BM.cfw"
        cfw_file.write_bytes(b"\x00" * 50)

        client = FuotaClient()
        resp = _mock_response(status_code=400, text="Image already exists on server")
        with patch.object(client, "_singleton_request", return_value=resp):
            client.upload_cfw(str(cfw_file))  # should not raise

    def test_server_error_raises_cloud_error(self, tmp_path):
        """500 response raises CloudError."""
        cfw_file = tmp_path / "108.0.5.2-BM.cfw"
        cfw_file.write_bytes(b"\x00" * 50)

        client = FuotaClient()
        resp = _mock_response(status_code=500, text="Internal Server Error")
        with patch.object(client, "_singleton_request", return_value=resp):
            with pytest.raises(CloudError, match="CFW upload failed"):
                client.upload_cfw(str(cfw_file))

    def test_403_raises_cloud_error(self, tmp_path):
        """403 response raises CloudError."""
        cfw_file = tmp_path / "108.0.5.2-BM.cfw"
        cfw_file.write_bytes(b"\x00" * 50)

        client = FuotaClient()
        resp = _mock_response(status_code=403, text="Forbidden")
        with patch.object(client, "_singleton_request", return_value=resp):
            with pytest.raises(CloudError, match="CFW upload failed.*403"):
                client.upload_cfw(str(cfw_file))


# ---------------------------------------------------------------------------
# delete_cfw — response handling
# ---------------------------------------------------------------------------

class TestDeleteCfw:
    """Tests for delete_cfw() response handling."""

    def test_successful_delete(self):
        """204 response returns True."""
        client = FuotaClient()
        resp = _mock_response(status_code=204, text="")
        with patch.object(client, "_singleton_request", return_value=resp):
            assert client.delete_cfw("108.0.5.2-BM.cfw") is True

    def test_not_found_returns_false(self):
        """404 response returns False (already deleted)."""
        client = FuotaClient()
        resp = _mock_response(status_code=404, text="Not found")
        with patch.object(client, "_singleton_request", return_value=resp):
            assert client.delete_cfw("108.0.5.2-BM.cfw") is False

    def test_server_error_raises(self):
        """500 response raises CloudError."""
        client = FuotaClient()
        resp = _mock_response(status_code=500, text="Server Error")
        with patch.object(client, "_singleton_request", return_value=resp):
            with pytest.raises(CloudError, match="CFW delete failed"):
                client.delete_cfw("108.0.5.2-BM.cfw")


# ---------------------------------------------------------------------------
# create_plan — response handling
# ---------------------------------------------------------------------------

class TestCreatePlan:
    """Tests for create_plan() response validation."""

    def _make_stages(self):
        """ make stages."""
        return [
            {"targets": ["108.0.5.0-BM"], "description": "From", "isSkippable": False},
            {"targets": ["108.0.5.2-BM"], "description": "To", "isSkippable": False},
        ]

    def test_successful_plan_returns_id(self):
        """200 response with planId returns the integer ID."""
        client = FuotaClient()
        resp = _mock_response(json_data={"planId": 42}, status_code=200)
        with patch.object(client, "_singleton_request", return_value=resp):
            plan_id = client.create_plan(self._make_stages(), "test plan")
        assert plan_id == 42

    def test_missing_plan_id_raises(self):
        """200 response without planId raises CloudError."""
        client = FuotaClient()
        resp = _mock_response(json_data={"status": "ok"}, status_code=200)
        with patch.object(client, "_singleton_request", return_value=resp):
            with pytest.raises(CloudError, match="missing 'planId'"):
                client.create_plan(self._make_stages(), "test plan")

    def test_non_200_raises(self):
        """Non-200 response raises CloudError."""
        client = FuotaClient()
        resp = _mock_response(status_code=400, text="Bad request: invalid stages")
        with patch.object(client, "_singleton_request", return_value=resp):
            with pytest.raises(CloudError, match="Plan creation failed.*400"):
                client.create_plan(self._make_stages(), "test plan")


# ---------------------------------------------------------------------------
# get_progress — response handling
# ---------------------------------------------------------------------------

class TestGetProgress:
    """Tests for get_progress() response handling."""

    def test_returns_progress_dict(self):
        """200 response returns parsed progress dict."""
        client = FuotaClient()
        progress = {"deviceId": "ABC", "percentComplete": 50, "pagesApplied": 100}
        resp = _mock_response(json_data=progress, status_code=200)
        with patch.object(client, "_singleton_request", return_value=resp):
            result = client.get_progress("ABC")
        assert result["percentComplete"] == 50

    def test_404_returns_none(self):
        """404 means no active FUOTA transfer — returns None."""
        client = FuotaClient()
        resp = _mock_response(status_code=404, text="Not found")
        resp.raise_for_status = MagicMock()  # should not be called on 404 path
        with patch.object(client, "_singleton_request", return_value=resp):
            result = client.get_progress("ABC")
        assert result is None


# ---------------------------------------------------------------------------
# execute_fuota_transition — stage construction
# ---------------------------------------------------------------------------

class TestExecuteFuotaTransition:
    """Tests for execute_fuota_transition() stage building logic."""

    def test_builds_two_stage_plan(self):
        """Verify the stages list passed to create_plan has correct structure."""
        client = FuotaClient()
        captured_stages = []

        def mock_create_plan(stages, desc, device_type_id, device_variant_id):
            """Mock create plan."""
            captured_stages.extend(stages)
            return 99

        with patch.object(client, "ensure_device_registered"), \
             patch.object(client, "create_plan", side_effect=mock_create_plan), \
             patch.object(client, "assign_device", return_value={"numDevicesUpdated": 1}), \
             patch.object(client, "wait_for_stage_complete", return_value={"percentComplete": 100}):
            plan_id = client.execute_fuota_transition(
                device_id="70B3D584C01E1FCC",
                from_targets=["108.0.5.0-BM", "109.0.5.0-BM"],
                to_targets=["108.0.5.2-BM", "109.0.5.2-BM"],
                description="test transition",
            )

        assert plan_id == 99
        assert len(captured_stages) == 2
        assert captured_stages[0]["targets"] == ["108.0.5.0-BM", "109.0.5.0-BM"]
        assert captured_stages[1]["targets"] == ["108.0.5.2-BM", "109.0.5.2-BM"]
        assert captured_stages[0]["isSkippable"] is False
        assert captured_stages[1]["isSkippable"] is False

    def test_calls_cloud_client_when_provided(self):
        """When cloud_client is passed, mark_test_start and wait_for_fuota_boot are called."""
        client = FuotaClient()
        mock_cloud = MagicMock()

        with patch.object(client, "ensure_device_registered"), \
             patch.object(client, "create_plan", return_value=99), \
             patch.object(client, "assign_device", return_value={}), \
             patch.object(client, "wait_for_stage_complete", return_value={}), \
             patch.object(client, "wait_for_fuota_boot", return_value={}):
            client.execute_fuota_transition(
                device_id="70B3D584C01E1FCC",
                from_targets=["108.0.5.0-BM"],
                to_targets=["108.0.5.2-BM"],
                description="test",
                cloud_client=mock_cloud,
            )

        mock_cloud.mark_test_start.assert_called_once()

    def test_skips_cloud_client_when_none(self):
        """When cloud_client is None, no boot wait happens."""
        client = FuotaClient()

        with patch.object(client, "ensure_device_registered"), \
             patch.object(client, "create_plan", return_value=99), \
             patch.object(client, "assign_device", return_value={}), \
             patch.object(client, "wait_for_stage_complete", return_value={}), \
             patch.object(client, "wait_for_fuota_boot") as mock_boot:
            client.execute_fuota_transition(
                device_id="70B3D584C01E1FCC",
                from_targets=["108.0.5.0-BM"],
                to_targets=["108.0.5.2-BM"],
                description="test",
                cloud_client=None,
            )

        mock_boot.assert_not_called()


# ---------------------------------------------------------------------------
# wait_for_fuota_boot — delegation
# ---------------------------------------------------------------------------

class TestWaitForFuotaBoot:
    """Tests for wait_for_fuota_boot() delegation logic."""

    def test_delegates_to_cloud_client(self):
        """Calls mark_test_start and wait_for_boot(boot_reason=2) on cloud_client."""
        client = FuotaClient()
        mock_cloud = MagicMock()
        mock_cloud.wait_for_boot.return_value = {"bootReason": "Fuota", "recordId": 10}

        result = client.wait_for_fuota_boot(mock_cloud, timeout_s=300)

        mock_cloud.mark_test_start.assert_called_once()
        mock_cloud.wait_for_boot.assert_called_once_with(boot_reason=2, timeout_s=300)
        assert result["bootReason"] == "Fuota"
