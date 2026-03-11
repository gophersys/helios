"""Tests for CI overlay endpoints — verifies error responses use proper ErrorDetail format."""

import json
from pathlib import Path
from unittest.mock import patch

from tests.conftest import make_obj


_OVERLAYS_MODULE = "api.v2.ci.overlays"


class TestGetOverlays:
    """Tests for GET /v2/builds/overlays/<product>."""

    def test_get_overlays_not_found_returns_proper_error(self, authed_client, mock_db):
        """Verify 404 for unknown product returns {errors: [{message: ...}]} not raw string."""
        response = authed_client.get("/v2/builds/overlays/nonexistent_product")
        assert response.status_code == 404
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]

    def test_get_overlays_internal_error_returns_proper_error(self, authed_client, mock_db):
        """Verify 500 on exception returns proper error envelope, not raw string or traceback."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create overlays dir but make the tarball creation fail
            overlay_dir = Path(tmpdir) / "alpha" / "overlays"
            overlay_dir.mkdir(parents=True)
            (overlay_dir / "test.overlay").write_text("overlay content")

            with patch(f"{_OVERLAYS_MODULE}.PRODUCTS_DIR", Path(tmpdir)):
                with patch(f"{_OVERLAYS_MODULE}.tarfile.open", side_effect=OSError("disk full")):
                    response = authed_client.get("/v2/builds/overlays/alpha")

        assert response.status_code == 500
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]
        # Must NOT leak exception details
        assert "disk full" not in body["errors"][0]["message"]

    def test_get_overlays_success(self, authed_client, mock_db):
        """Verify successful overlay tarball download."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            overlay_dir = Path(tmpdir) / "alpha" / "overlays"
            overlay_dir.mkdir(parents=True)
            (overlay_dir / "test.overlay").write_text("overlay content")

            with patch(f"{_OVERLAYS_MODULE}.PRODUCTS_DIR", Path(tmpdir)):
                response = authed_client.get("/v2/builds/overlays/alpha")

        assert response.status_code == 200
        assert response.content_type == "application/gzip"


class TestListOverlays:
    """Tests for GET /v2/builds/overlays/<product>/list."""

    def test_list_overlays_not_found_returns_proper_error(self, authed_client, mock_db):
        """Verify 404 for unknown product returns proper error envelope."""
        response = authed_client.get("/v2/builds/overlays/nonexistent_product/list")
        assert response.status_code == 404
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]

    def test_list_overlays_internal_error_returns_proper_error(self, authed_client, mock_db):
        """Verify 500 returns proper error envelope with no exception leakage."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            overlay_dir = Path(tmpdir) / "alpha" / "overlays"
            overlay_dir.mkdir(parents=True)

            # Make glob raise an exception
            with patch(f"{_OVERLAYS_MODULE}.PRODUCTS_DIR", Path(tmpdir)):
                with patch.object(Path, "glob", side_effect=PermissionError("access denied")):
                    response = authed_client.get("/v2/builds/overlays/alpha/list")

        assert response.status_code == 500
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]
        # Must NOT leak exception details
        assert "access denied" not in body["errors"][0]["message"]

    def test_list_overlays_success(self, authed_client, mock_db):
        """Verify successful overlay listing."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            overlay_dir = Path(tmpdir) / "alpha" / "overlays"
            overlay_dir.mkdir(parents=True)
            (overlay_dir / "board_a.overlay").write_text("overlay a")
            (overlay_dir / "board_b.overlay").write_text("overlay b")

            with patch(f"{_OVERLAYS_MODULE}.PRODUCTS_DIR", Path(tmpdir)):
                response = authed_client.get("/v2/builds/overlays/alpha/list")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["product"] == "alpha"
        assert len(body["data"]["overlays"]) == 2
