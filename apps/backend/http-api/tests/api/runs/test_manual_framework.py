"""Tests for create_kubernetes_job framework dispatch.

Locks the YAML-render + container.command override behavior at the
manual.py boundary:

    - framework=None       → entrypoint.sh (pytest path, back-compat)
    - framework="pytest"   → entrypoint.sh
    - framework="PYTEST"   → entrypoint.sh
    - framework="ztest"    → python -m corekinect.test.ztest_runner
    - framework="ZTEST"    → python -m corekinect.test.ztest_runner
    - framework="bogus"    → returns None (logged + rejected)

Also asserts the rendered env block carries ``TEST_FRAMEWORK`` so the
runner pod can verify the dispatch.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Path to the real validation_job.yaml template — copied into the
# conftest's ASSETS_FOLDER (/tmp/concord-test-assets) so the templating
# code can find it without changing global config.
_REAL_TEMPLATE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "assets" / "templates" / "validation_job.yaml"
)


@pytest.fixture
def assets_dir_with_template(tmp_path, monkeypatch):
    """Copy the real validation_job.yaml into a temp ASSETS_FOLDER.

    Pointing ``ASSETS_FOLDER`` at ``tmp_path`` means the test reads the
    same template the production code would read, so any drift between
    the template's placeholders and the Python substitution code shows
    up here as a render failure."""
    templates = tmp_path / "templates"
    templates.mkdir()
    shutil.copy(_REAL_TEMPLATE, templates / "validation_job.yaml")

    from config.env import env_config

    monkeypatch.setattr(env_config, "ASSETS_FOLDER", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_k8s_api():
    """Patch get_batch_v1_api + get_logger so the renderer runs end-to-end
    in tests without hitting the cluster or requiring app init."""
    captured = {}

    def _capture(namespace, body):
        captured["namespace"] = namespace
        captured["body"] = body
        return MagicMock()

    api = MagicMock()
    api.create_namespaced_job.side_effect = _capture

    with patch("src.api.v2.runs.manual.get_batch_v1_api", return_value=api), \
         patch("src.api.v2.runs.manual.get_logger", return_value=MagicMock()):
        yield captured


def _make_job_for_framework(framework):
    """Helper — minimal call into create_kubernetes_job."""
    from src.api.v2.runs.manual import create_kubernetes_job

    return create_kubernetes_job(
        product="alpha",
        job_id="entry-abc",
        firmware_path="",
        test_type="validation",
        firmware_version="1.0.0",
        run_id="run-1",
        api_key="key",
        api_url="http://api.local",
        mtib_address="10.0.0.1",
        fixture_id="fx-1",
        device_id="dev-1",
        device_snr="SN001",
        build_run_id="br-1",
        product_slug="alpha",
        test_package_version="1.0.0",
        stage="smoke",
        framework=framework,
    )


def _env_dict(captured_spec):
    """Pull the rendered container env block into a name→value dict."""
    container = captured_spec["body"]["spec"]["template"]["spec"]["containers"][0]
    return {e["name"]: e["value"] for e in container.get("env", []) if "value" in e}


def _container(captured_spec):
    return captured_spec["body"]["spec"]["template"]["spec"]["containers"][0]


class TestFrameworkEnvVar:
    def test_default_none_renders_pytest(self, assets_dir_with_template, fake_k8s_api):
        result = _make_job_for_framework(None)
        assert result is not None
        env = _env_dict(fake_k8s_api)
        assert env["TEST_FRAMEWORK"] == "PYTEST"

    def test_pytest_lowercase_renders_pytest(self, assets_dir_with_template, fake_k8s_api):
        _make_job_for_framework("pytest")
        env = _env_dict(fake_k8s_api)
        assert env["TEST_FRAMEWORK"] == "PYTEST"

    def test_pytest_uppercase_renders_pytest(self, assets_dir_with_template, fake_k8s_api):
        _make_job_for_framework("PYTEST")
        env = _env_dict(fake_k8s_api)
        assert env["TEST_FRAMEWORK"] == "PYTEST"

    def test_ztest_lowercase_renders_ztest(self, assets_dir_with_template, fake_k8s_api):
        _make_job_for_framework("ztest")
        env = _env_dict(fake_k8s_api)
        assert env["TEST_FRAMEWORK"] == "ZTEST"

    def test_ztest_uppercase_renders_ztest(self, assets_dir_with_template, fake_k8s_api):
        _make_job_for_framework("ZTEST")
        env = _env_dict(fake_k8s_api)
        assert env["TEST_FRAMEWORK"] == "ZTEST"

    def test_unknown_framework_returns_none(self, assets_dir_with_template, fake_k8s_api):
        result = _make_job_for_framework("rust-test")
        assert result is None
        # And no K8s call was made — we abort BEFORE the API call.
        assert "body" not in fake_k8s_api


class TestContainerCommandOverride:
    def test_pytest_does_not_override_command(self, assets_dir_with_template, fake_k8s_api):
        """PYTEST must leave container.command alone so the image's
        ENTRYPOINT (/app/entrypoint.sh) runs unchanged. This is the
        non-negotiable back-compat guarantee."""
        _make_job_for_framework(None)
        container = _container(fake_k8s_api)
        assert "command" not in container or container["command"] in (None, [])

    def test_pytest_explicit_does_not_override_command(self, assets_dir_with_template, fake_k8s_api):
        _make_job_for_framework("pytest")
        container = _container(fake_k8s_api)
        assert "command" not in container or container["command"] in (None, [])

    def test_ztest_overrides_command_to_module_invocation(self, assets_dir_with_template, fake_k8s_api):
        """ZTEST bypasses entrypoint.sh and invokes the ztest_runner module
        directly. The K8s spec needs ``command`` set so the override
        takes precedence over the image's ENTRYPOINT."""
        _make_job_for_framework("ztest")
        container = _container(fake_k8s_api)
        assert container["command"][0] == "python3"
        assert "corekinect.test.ztest_runner" in container["command"]
        # No leftover args from any earlier path.
        assert container["args"] == []

    def test_ztest_uppercase_overrides_command(self, assets_dir_with_template, fake_k8s_api):
        _make_job_for_framework("ZTEST")
        container = _container(fake_k8s_api)
        assert "ztest_runner" in container["command"][-1]


class TestBackwardCompatibility:
    """Pinned tests for the back-compat guarantee.

    These run on every CI cycle so any future change to dispatch that
    breaks the legacy path fails loudly."""

    def test_legacy_call_without_framework_kwarg_renders_pytest(
        self, assets_dir_with_template, fake_k8s_api
    ):
        """Existing callers that haven't been updated to pass framework=
        must still get the pytest path. The kwarg defaults to None."""
        from src.api.v2.runs.manual import create_kubernetes_job

        result = create_kubernetes_job(
            product="alpha",
            job_id="entry-abc",
            firmware_path="",
            test_type="validation",
            firmware_version="1.0.0",
            run_id="run-1",
            api_key="key",
            api_url="http://api.local",
            mtib_address="10.0.0.1",
            fixture_id="fx-1",
            device_id="dev-1",
            device_snr="SN001",
            build_run_id="br-1",
            product_slug="alpha",
            test_package_version="1.0.0",
            stage="smoke",
            # NB: framework= intentionally omitted (legacy call site).
        )
        assert result is not None
        env = _env_dict(fake_k8s_api)
        assert env["TEST_FRAMEWORK"] == "PYTEST"
        container = _container(fake_k8s_api)
        assert "command" not in container or container["command"] in (None, [])
