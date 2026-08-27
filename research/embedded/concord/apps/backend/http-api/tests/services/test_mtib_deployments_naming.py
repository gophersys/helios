"""Tests for the claim-mode naming + hostPort isolation in
``services/kubernetes/mtib_deployments.create_mtib_deployment``.

Two MTIB deployments cannot share a node and the ``hostPort: 50053``
binding. The previous naming scheme — ``mtib-{hostname}-s{slot}`` —
let a claim-mode deployment collide with the existing fixture-bound
deployment on the same node, and the 409 path then silently returned
"existing". The bug here is two-fold:

1. The names must differ so the 409 dedupe path does the right thing.
2. The claim-mode deployment must not request ``hostPort: 50053`` at
   all — that port is owned by the fixture-bound deployment. Claim
   pods are reachable inside the cluster via a Service instead.

The tests here verify both halves stay fixed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import yaml

import src.services.kubernetes.mtib_deployments as mtib_mod


# Minimal template content sufficient for the test — the real template
# lives at apps/backend/http-api/assets/templates/mtib_server_deployment.yaml
# and the function substitutes ``{{...}}`` placeholders into it. We
# patch open() so we don't depend on the real template path during
# unit tests.
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
        corekinect.com/claim-id: "{{CLAIM_ID}}"
    spec:
      nodeSelector:
        kubernetes.io/hostname: "{{NODE_HOSTNAME}}"
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


@pytest.fixture
def _patched_apis(monkeypatch):
    """Stub the K8s apps_v1 + core_v1 clients so no real cluster is touched."""
    captured: dict = {"deployments": [], "services": []}
    apps_v1 = MagicMock()

    def _create_dep(namespace, body):
        captured["deployments"].append({"namespace": namespace, "body": body})
        return MagicMock()

    apps_v1.create_namespaced_deployment.side_effect = _create_dep

    core_v1 = MagicMock()

    def _create_svc(namespace, body):
        captured["services"].append({"namespace": namespace, "body": body})
        return MagicMock()

    core_v1.create_namespaced_service.side_effect = _create_svc

    monkeypatch.setattr(mtib_mod, "get_apps_v1_api", lambda: apps_v1)
    monkeypatch.setattr(mtib_mod, "get_core_v1_api", lambda: core_v1)
    return captured


@pytest.fixture(autouse=True)
def _patched_template(monkeypatch):
    """Replace the on-disk template read with our minimal in-memory copy."""
    import builtins
    real_open = builtins.open

    def _fake_open(path, *args, **kwargs):
        if isinstance(path, str) and "mtib_server_deployment.yaml" in path:
            from io import StringIO
            return StringIO(_TEMPLATE)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _fake_open)


def test_fixture_bound_deployment_keeps_legacy_name(_patched_apis):
    """No claim_id → keep the historic ``mtib-{hostname}-s{slot}`` name."""
    name = mtib_mod.create_mtib_deployment(
        node_hostname="verdin-001",
        fixture_id="fix-1",
        deployment_id="fix-1-s0",
        slot_index=0,
        config={},
        claim_id="",
    )
    assert name == "mtib-verdin-001-s0"
    body = _patched_apis["deployments"][-1]["body"]
    # Fixture-bound stays on hostPort 50053 so the existing manufacturing
    # / validation rigs are untouched.
    ports = body["spec"]["template"]["spec"]["containers"][0]["ports"]
    assert ports[0].get("hostPort") == 50053


def test_claim_mode_deployment_uses_claim_namespaced_name(_patched_apis):
    """A claim_id → name embeds ``claim-<id_prefix>-<hostname>-s<slot>``.

    This is the core of the fix — without the ``claim-`` prefix the
    claim's pod fights the fixture-bound pod for the same Deployment
    name on the same node, and ``create_namespaced_deployment`` 409s.
    """
    name = mtib_mod.create_mtib_deployment(
        node_hostname="verdin-001",
        fixture_id="claim-standalone",
        deployment_id="claim-abc12345",
        slot_index=0,
        config={},
        claim_id="abc12345-9999-0000-aaaa-bbbbcccc",
    )
    # Name must be distinct from the fixture-bound one.
    assert name != "mtib-verdin-001-s0"
    assert name.startswith("mtib-claim-")
    assert "verdin-001" in name
    assert name.endswith("-s0")
    # And RFC 1123 still fits in 63 chars.
    assert len(name) <= 63


def test_claim_mode_drops_host_port_50053(_patched_apis):
    """A claim-mode deployment must not bind hostPort 50053.

    That port is owned by the fixture-bound deployment on the same
    node. Sharing it would put both pods into CrashLoopBackOff
    (only one can bind). Claim-mode reaches its pod via a ClusterIP
    Service instead — verified below.
    """
    mtib_mod.create_mtib_deployment(
        node_hostname="verdin-001",
        fixture_id="claim-standalone",
        deployment_id="claim-abc12345",
        slot_index=0,
        config={},
        claim_id="abc12345-9999-0000-aaaa-bbbbcccc",
    )
    body = _patched_apis["deployments"][-1]["body"]
    ports = body["spec"]["template"]["spec"]["containers"][0]["ports"]
    # containerPort 50053 is still present.
    assert any(p.get("containerPort") == 50053 for p in ports)
    # hostPort 50053 is NOT.
    assert all(p.get("hostPort") != 50053 for p in ports)


def test_claim_mode_creates_a_companion_service(_patched_apis):
    """When hostPort is dropped, the claim-mode flow creates a
    ClusterIP Service so the runner pods can still reach the MTIB.
    """
    mtib_mod.create_mtib_deployment(
        node_hostname="verdin-001",
        fixture_id="claim-standalone",
        deployment_id="claim-abc12345",
        slot_index=0,
        config={},
        claim_id="abc12345-9999-0000-aaaa-bbbbcccc",
    )
    assert _patched_apis["services"], "expected a companion Service to be created"
    svc_body = _patched_apis["services"][-1]["body"]
    # Service must target the deployment's pod selector and port 50053.
    if isinstance(svc_body, dict):
        spec = svc_body.get("spec") or {}
        ports = spec.get("ports") or []
        assert any((p.get("targetPort") == 50053 or p.get("port") == 50053) for p in ports)
