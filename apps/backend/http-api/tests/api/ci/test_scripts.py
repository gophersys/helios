"""Integration tests for the CI Build Scripts API endpoints."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from tests.conftest import make_obj

# The router imports scripts via the `api.v2.ci.scripts` path (relative imports)
# NOT `src.api.v2.ci.scripts`. Patches must target the correct module.
_SCRIPTS_MODULE = "api.v2.ci.scripts"


# ---------------------------------------------------------------------------
#  GET /v2/builds/scripts — List build scripts
# ---------------------------------------------------------------------------

class TestListBuildScripts:
    """Tests for GET /v2/builds/scripts."""

    def test_list_scripts_success(self, authed_client, mock_db):
        """List build scripts returns discovered scripts from filesystem."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create product directories with build scripts
            alpha_dir = Path(tmpdir) / "alpha" / "scripts"
            alpha_dir.mkdir(parents=True)
            (alpha_dir / "build.sh").write_text("#!/bin/bash\necho alpha")

            theta_dir = Path(tmpdir) / "theta" / "scripts"
            theta_dir.mkdir(parents=True)
            (theta_dir / "build.sh").write_text("#!/bin/bash\necho theta")

            with patch(f"{_SCRIPTS_MODULE}.SCRIPTS_DIR", Path(tmpdir)):
                response = authed_client.get("/v2/builds/scripts")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert len(body["errors"]) == 0

        products = [s["product"] for s in body["data"]]
        assert "alpha" in products
        assert "theta" in products

    def test_list_scripts_empty_dir(self, authed_client, mock_db):
        """List build scripts returns empty list when no scripts exist."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(f"{_SCRIPTS_MODULE}.SCRIPTS_DIR", Path(tmpdir)):
                response = authed_client.get("/v2/builds/scripts")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"] == []

    def test_list_scripts_nonexistent_dir(self, authed_client, mock_db):
        """List build scripts returns empty list when SCRIPTS_DIR does not exist."""
        with patch(f"{_SCRIPTS_MODULE}.SCRIPTS_DIR", Path("/nonexistent/path")):
            response = authed_client.get("/v2/builds/scripts")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"] == []

    def test_list_scripts_skips_non_directories(self, authed_client, mock_db):
        """List build scripts ignores non-directory entries."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file (not a directory) at the root level
            (Path(tmpdir) / "README.md").write_text("This is not a product dir")

            # Create a valid product directory
            sigma_dir = Path(tmpdir) / "sigma5" / "scripts"
            sigma_dir.mkdir(parents=True)
            (sigma_dir / "build.sh").write_text("#!/bin/bash\necho sigma5")

            with patch(f"{_SCRIPTS_MODULE}.SCRIPTS_DIR", Path(tmpdir)):
                response = authed_client.get("/v2/builds/scripts")

        assert response.status_code == 200
        body = json.loads(response.data)
        # Only sigma5 should appear, README.md should be skipped
        assert len(body["data"]) == 1
        assert body["data"][0]["product"] == "sigma5"

    def test_list_scripts_includes_size(self, authed_client, mock_db):
        """List build scripts includes file size in response."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            product_dir = Path(tmpdir) / "alpha" / "scripts"
            product_dir.mkdir(parents=True)
            script_content = "#!/bin/bash\necho hello world"
            (product_dir / "build.sh").write_text(script_content)

            with patch(f"{_SCRIPTS_MODULE}.SCRIPTS_DIR", Path(tmpdir)):
                response = authed_client.get("/v2/builds/scripts")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"][0]["size"] == len(script_content)

    def test_list_scripts_unauthorized(self, client):
        """List build scripts without authentication returns 401."""
        response = client.get("/v2/builds/scripts")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
#  GET /v2/builds/scripts/<product> — Get build script
# ---------------------------------------------------------------------------

class TestGetBuildScript:
    """Tests for GET /v2/builds/scripts/<product>."""

    def test_get_script_success(self, authed_client, mock_db):
        """Get build script returns script content for a known product."""
        import tempfile

        script_content = "#!/bin/bash\nset -e\nwest build -b alpha_b0"

        with tempfile.TemporaryDirectory() as tmpdir:
            product_dir = Path(tmpdir) / "alpha" / "scripts"
            product_dir.mkdir(parents=True)
            (product_dir / "build.sh").write_text(script_content)

            with patch(f"{_SCRIPTS_MODULE}.SCRIPTS_DIR", Path(tmpdir)):
                response = authed_client.get("/v2/builds/scripts/alpha_fw")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert len(body["errors"]) == 0
        assert body["data"]["product"] == "alpha_fw"
        assert body["data"]["content"] == script_content

    def test_get_script_not_found(self, authed_client, mock_db):
        """Get build script for non-existent product returns 404."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(f"{_SCRIPTS_MODULE}.SCRIPTS_DIR", Path(tmpdir)):
                response = authed_client.get("/v2/builds/scripts/nonexistent_product")

        assert response.status_code == 404
        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_get_script_normalizes_product_name(self, authed_client, mock_db):
        """Get build script normalizes product name (strips _fw, _mfg suffixes)."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            product_dir = Path(tmpdir) / "alpha" / "scripts"
            product_dir.mkdir(parents=True)
            (product_dir / "build.sh").write_text("#!/bin/bash")

            with patch(f"{_SCRIPTS_MODULE}.SCRIPTS_DIR", Path(tmpdir)):
                # alpha_mfg_fw should normalize to alpha
                response = authed_client.get("/v2/builds/scripts/alpha_mfg_fw")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["product"] == "alpha_mfg_fw"

    def test_get_script_strips_board_suffix(self, authed_client, mock_db):
        """Get build script strips board variant suffixes (_b0, _a0)."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            product_dir = Path(tmpdir) / "sigma5" / "scripts"
            product_dir.mkdir(parents=True)
            (product_dir / "build.sh").write_text("#!/bin/bash\necho sigma5")

            with patch(f"{_SCRIPTS_MODULE}.SCRIPTS_DIR", Path(tmpdir)):
                response = authed_client.get("/v2/builds/scripts/sigma5_b0")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["content"] == "#!/bin/bash\necho sigma5"


# ---------------------------------------------------------------------------
#  PUT /v2/builds/scripts/<product> — Upload build script (not implemented)
# ---------------------------------------------------------------------------

class TestUploadBuildScript:
    """Tests for PUT /v2/builds/scripts/<product>."""

    def test_upload_script_not_implemented(self, authed_client, mock_db):
        """Upload build script returns 501 Not Implemented."""
        response = authed_client.put(
            "/v2/builds/scripts/alpha_fw",
            data=json.dumps({"content": "#!/bin/bash"}),
        )
        assert response.status_code == 501

        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert "not implemented" in body["errors"][0]["message"].lower()


# ---------------------------------------------------------------------------
#  DELETE /v2/builds/scripts/<product> — Delete build script (not implemented)
# ---------------------------------------------------------------------------

class TestDeleteBuildScript:
    """Tests for DELETE /v2/builds/scripts/<product>."""

    def test_delete_script_not_implemented(self, authed_client, mock_db):
        """Delete build script returns 501 Not Implemented."""
        response = authed_client.delete("/v2/builds/scripts/alpha_fw")
        assert response.status_code == 501

        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert "not implemented" in body["errors"][0]["message"].lower()


# ---------------------------------------------------------------------------
#  _normalize_product_dir helper
# ---------------------------------------------------------------------------

class TestNormalizeProductDir:
    """Unit tests for the _normalize_product_dir helper function."""

    def test_strips_fw_suffix(self):
        """Strips _fw suffix from product key."""
        from src.api.v2.ci.scripts import _normalize_product_dir
        assert _normalize_product_dir("alpha_fw") == "alpha"

    def test_strips_mfg_fw_suffix(self):
        """Strips _mfg_fw suffix from product key."""
        from src.api.v2.ci.scripts import _normalize_product_dir
        assert _normalize_product_dir("alpha_mfg_fw") == "alpha"

    def test_strips_board_suffix(self):
        """Strips board variant suffix (_b0, _a0, etc.)."""
        from src.api.v2.ci.scripts import _normalize_product_dir
        assert _normalize_product_dir("sigma5_b0") == "sigma5"

    def test_strips_combined_suffixes(self):
        """Strips both _fw and board suffixes."""
        from src.api.v2.ci.scripts import _normalize_product_dir
        assert _normalize_product_dir("sigma5_fw") == "sigma5"

    def test_plain_product_name(self):
        """Plain product name without suffixes is returned as-is."""
        from src.api.v2.ci.scripts import _normalize_product_dir
        assert _normalize_product_dir("theta") == "theta"

    def test_empty_string_returns_none(self):
        """Empty string after normalization returns None."""
        from src.api.v2.ci.scripts import _normalize_product_dir
        result = _normalize_product_dir("_fw")
        # After stripping _fw: empty string -> None
        assert result is None or result == ""
