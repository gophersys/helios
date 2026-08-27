"""Tests for the registry digest-pinning step in
``services/kubernetes/mtib_deployments.create_mtib_deployment``.

Before submitting a Deployment we HEAD the container registry to:

* Resolve the human-friendly tag (``...:latest``, ``...:v0.10.6``) to
  an immutable digest ``...@sha256:...``. The Deployment then pins
  that digest so a tag overwrite mid-rollout can't quietly change the
  running code.
* Fail fast when the tag resolves to ``404``. Without this, the cluster
  spins the pod up, the pull fails, and the operator stares at
  ``ImagePullBackOff`` for minutes before realising the image was
  never published.

These tests exercise both paths against a stubbed registry HEAD.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import src.services.kubernetes.mtib_deployments as mtib_mod


_TEMPLATE = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: "{{DEPLOYMENT_NAME}}"
  labels:
    app: "{{DEPLOYMENT_NAME}}"
    corekinect.com/fixture-id: "{{FIXTURE_ID}}"
    corekinect.com/deployment-id: "{{DEPLOYMENT_ID}}"
    corekinect.com/claim-id: "{{CLAIM_ID}}"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: "{{DEPLOYMENT_NAME}}"
  template:
    metadata:
      labels:
        app: "{{DEPLOYMENT_NAME}}"
    spec:
      containers:
      - name: mtib-server
        image: "{{IMAGE}}"
        ports:
        - containerPort: 50053
          hostPort: 50053
        resources:
          requests:
            cpu: "{{CPU_REQUEST}}"
            memory: "{{MEMORY_REQUEST}}"
          limits:
            cpu: "{{CPU_LIMIT}}"
            memory: "{{MEMORY_LIMIT}}"
"""


@pytest.fixture(autouse=True)
def _patched_template(monkeypatch):
    import builtins
    real_open = builtins.open

    def _fake_open(path, *args, **kwargs):
        if isinstance(path, str) and "mtib_server_deployment.yaml" in path:
            from io import StringIO
            return StringIO(_TEMPLATE)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _fake_open)


@pytest.fixture
def _patched_apis(monkeypatch):
    captured: dict = {"deployments": [], "services": []}
    apps_v1 = MagicMock()

    def _create_dep(namespace, body):
        captured["deployments"].append({"namespace": namespace, "body": body})
        return MagicMock()

    apps_v1.create_namespaced_deployment.side_effect = _create_dep

    core_v1 = MagicMock()
    monkeypatch.setattr(mtib_mod, "get_apps_v1_api", lambda: apps_v1)
    monkeypatch.setattr(mtib_mod, "get_core_v1_api", lambda: core_v1)
    return captured


def test_image_digest_resolved_and_pinned(monkeypatch, _patched_apis):
    """Tag → digest resolution lands in the Deployment manifest."""
    head_resp = MagicMock()
    head_resp.status_code = 200
    head_resp.headers = {"Docker-Content-Digest": "sha256:deadbeef" + "0" * 56}

    monkeypatch.setattr(
        mtib_mod, "_head_image_manifest",
        lambda image: head_resp,
    )

    mtib_mod.create_mtib_deployment(
        node_hostname="verdin-001",
        fixture_id="fix-1",
        deployment_id="fix-1-s0",
        slot_index=0,
        config={"image": "registry.example.com/concord-mtib-server:v0.10.6"},
        claim_id="",
    )

    body = _patched_apis["deployments"][-1]["body"]
    image_in_manifest = body["spec"]["template"]["spec"]["containers"][0]["image"]
    # Tag stripped, digest appended.
    assert "@sha256:" in image_in_manifest, image_in_manifest
    assert image_in_manifest.startswith("registry.example.com/concord-mtib-server@")


def test_404_raises_mtib_image_unavailable(monkeypatch, _patched_apis):
    """A 404 from the registry HEAD must raise MtibImageUnavailable.

    No Deployment should be submitted to the cluster — the caller is
    expected to surface this to the user before any K8s state changes.
    """
    head_resp = MagicMock()
    head_resp.status_code = 404
    head_resp.headers = {}

    monkeypatch.setattr(
        mtib_mod, "_head_image_manifest",
        lambda image: head_resp,
    )

    with pytest.raises(mtib_mod.MtibImageUnavailable) as exc_info:
        mtib_mod.create_mtib_deployment(
            node_hostname="verdin-001",
            fixture_id="fix-1",
            deployment_id="fix-1-s0",
            slot_index=0,
            config={"image": "registry.example.com/concord-mtib-server:does-not-exist"},
            claim_id="",
        )
    # Error message includes the image string so the operator can act.
    assert "does-not-exist" in str(exc_info.value)
    # And the cluster was never touched.
    assert _patched_apis["deployments"] == []
