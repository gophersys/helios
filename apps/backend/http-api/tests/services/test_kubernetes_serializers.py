"""Tests for services/kubernetes/serializers.py — K8s object serialization."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from src.services.kubernetes.serializers import (
    _isoformat,
    _age,
    serialize_namespace,
    serialize_node,
    serialize_event,
    serialize_pod,
    serialize_pod_detail,
    serialize_deployment,
    serialize_service,
    serialize_job,
    serialize_configmap,
    serialize_secret,
    serialize_role,
    serialize_role_binding,
    serialize_service_account,
)

_NOW = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc)


def _meta(name="test", namespace="staging", labels=None, annotations=None, creation_timestamp=_NOW):
    m = MagicMock()
    m.name = name
    m.namespace = namespace
    m.labels = labels or {}
    m.annotations = annotations or {}
    m.creation_timestamp = creation_timestamp
    return m


class TestIsoformat:
    def test_none(self):
        assert _isoformat(None) is None

    def test_aware(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _isoformat(dt) == "2026-01-01T00:00:00+00:00"

    def test_naive_gets_utc(self):
        dt = datetime(2026, 1, 1)
        result = _isoformat(dt)
        assert "+00:00" in result


class TestAge:
    def test_none(self):
        assert _age(None) == "Unknown"

    def test_days(self):
        dt = datetime.now(timezone.utc) - timedelta(days=3, hours=2)
        result = _age(dt)
        assert result.startswith("3d")

    def test_hours(self):
        dt = datetime.now(timezone.utc) - timedelta(hours=2, minutes=30)
        result = _age(dt)
        assert result.startswith("2h")

    def test_minutes(self):
        dt = datetime.now(timezone.utc) - timedelta(minutes=15)
        result = _age(dt)
        assert "m" in result

    def test_naive_datetime(self):
        dt = datetime.now() - timedelta(hours=1)
        result = _age(dt)
        assert "h" in result or "m" in result


class TestSerializeNamespace:
    def test_basic(self):
        ns = MagicMock()
        ns.metadata = _meta("staging")
        ns.status.phase = "Active"
        result = serialize_namespace(ns)
        assert result["name"] == "staging"
        assert result["status"] == "Active"

    def test_no_status(self):
        ns = MagicMock()
        ns.metadata = _meta("staging")
        ns.status = None
        result = serialize_namespace(ns)
        assert result["status"] == "Unknown"


class TestSerializeNode:
    def test_full_node(self):
        node = MagicMock()
        node.metadata = _meta("node-1", labels={"node-role.kubernetes.io/control-plane": ""})
        cond = MagicMock(type="Ready", status="True", reason=None, message=None, last_transition_time=_NOW)
        node.status.conditions = [cond]
        node.status.node_info.os_image = "Ubuntu"
        node.status.node_info.kubelet_version = "v1.28.0"
        node.status.node_info.container_runtime_version = "containerd://1.7"
        node.status.node_info.architecture = "amd64"
        node.status.capacity = {"cpu": "4", "memory": "8Gi", "pods": "110"}
        node.status.allocatable = {"cpu": "3800m", "memory": "7Gi", "pods": "110"}
        addr = MagicMock(type="InternalIP", address="10.4.45.1")
        node.status.addresses = [addr]
        node.spec.taints = [MagicMock(key="node-role", value="control-plane", effect="NoSchedule")]
        node.spec.unschedulable = False
        result = serialize_node(node)
        assert result["name"] == "node-1"
        assert result["status"] == "Ready"
        assert "control-plane" in result["roles"]
        assert result["internalIp"] == "10.4.45.1"

    def test_node_no_roles(self):
        node = MagicMock()
        node.metadata = _meta("worker-1", labels={})
        node.status.conditions = []
        node.status.node_info = None
        node.status.capacity = None
        node.status.allocatable = None
        node.status.addresses = []
        node.spec.taints = None
        node.spec.unschedulable = False
        result = serialize_node(node)
        assert result["roles"] == ["worker"]
        assert result["internalIp"] == ""


class TestSerializeEvent:
    def test_basic(self):
        event = MagicMock()
        event.type = "Warning"
        event.reason = "BackOff"
        event.message = "Container crashed"
        event.involved_object.kind = "Pod"
        event.involved_object.name = "pod-1"
        event.involved_object.namespace = "staging"
        event.count = 5
        event.first_timestamp = _NOW
        event.last_timestamp = _NOW
        event.source.component = "kubelet"
        result = serialize_event(event)
        assert result["type"] == "Warning"
        assert result["object"] == "pod/pod-1"
        assert result["count"] == 5


class TestSerializePod:
    def test_running_pod(self):
        pod = MagicMock()
        pod.metadata = _meta("pod-1")
        cs = MagicMock()
        cs.name = "main"
        cs.image = "concord:latest"
        cs.ready = True
        cs.restart_count = 0
        cs.state.running = True
        cs.state.terminated = None
        pod.status.container_statuses = [cs]
        pod.status.phase = "Running"
        pod.status.pod_ip = "10.0.0.1"
        pod.spec.node_name = "node-1"
        pod.spec.containers = []
        result = serialize_pod(pod)
        assert result["name"] == "pod-1"
        assert result["ready"] == "1/1"
        assert result["containers"][0]["state"] == "running"

    def test_pod_no_status(self):
        pod = MagicMock()
        pod.metadata = _meta("pod-1")
        pod.status = None
        pod.spec.node_name = "node-1"
        c = MagicMock()
        c.name = "main"
        c.image = "concord:latest"
        pod.spec.containers = [c]
        result = serialize_pod(pod)
        assert result["status"] == "Unknown"
        assert len(result["containers"]) == 1


class TestSerializePodDetail:
    def test_with_volumes_and_conditions(self):
        pod = MagicMock()
        pod.metadata = _meta("pod-1", labels={"app": "test"}, annotations={"note": "yes"})
        cs = MagicMock()
        cs.name = "main"; cs.image = "img"; cs.ready = True; cs.restart_count = 0
        cs.state.running = True; cs.state.terminated = None
        pod.status.container_statuses = [cs]
        pod.status.phase = "Running"; pod.status.pod_ip = "10.0.0.1"
        pod.status.qos_class = "BestEffort"
        cond = MagicMock(type="Ready", status="True", reason=None, message=None, last_transition_time=_NOW)
        pod.status.conditions = [cond]

        vol = MagicMock()
        vol.name = "config"
        vol.config_map = MagicMock()
        vol.secret = None; vol.persistent_volume_claim = None
        vol.empty_dir = None; vol.host_path = None; vol.projected = None; vol.downward_api = None
        pod.spec.volumes = [vol]
        pod.spec.containers = []; pod.spec.node_name = "n1"
        pod.spec.service_account_name = "default"
        tol = MagicMock(key="node.kubernetes.io/not-ready", operator="Exists", value=None, effect="NoExecute")
        pod.spec.tolerations = [tol]

        result = serialize_pod_detail(pod)
        assert len(result["volumes"]) == 1
        assert result["volumes"][0]["type"] == "configMap"
        assert len(result["tolerations"]) == 1
        assert result["qosClass"] == "BestEffort"


class TestSerializeDeployment:
    def test_basic(self):
        dep = MagicMock()
        dep.metadata = _meta("http-api")
        dep.spec.replicas = 2
        dep.spec.strategy.type = "RollingUpdate"
        c = MagicMock(); c.name = "api"; c.image = "concord:v1"
        dep.spec.template.spec.containers = [c]
        dep.spec.selector.match_labels = {"app": "concord"}
        dep.status.ready_replicas = 2
        dep.status.available_replicas = 2
        dep.status.updated_replicas = 2
        dep.status.conditions = []
        result = serialize_deployment(dep)
        assert result["name"] == "http-api"
        assert result["replicas"]["desired"] == 2
        assert result["strategy"] == "RollingUpdate"


class TestSerializeService:
    def test_basic(self):
        svc = MagicMock()
        svc.metadata = _meta("api-svc")
        p = MagicMock(); p.name = "http"; p.port = 9001; p.target_port = 9001
        p.protocol = "TCP"; p.node_port = None
        svc.spec.ports = [p]
        svc.spec.type = "ClusterIP"
        svc.spec.cluster_ip = "10.43.0.1"
        svc.spec.external_i_ps = None
        svc.spec.load_balancer_ip = None
        svc.spec.selector = {"app": "concord"}
        result = serialize_service(svc)
        assert result["type"] == "ClusterIP"
        assert len(result["ports"]) == 1


class TestSerializeJob:
    def test_complete_job(self):
        job = MagicMock()
        job.metadata = _meta("build-123")
        job.spec.completions = 1
        job.spec.parallelism = 1
        job.spec.backoff_limit = 6
        job.status.active = 0
        job.status.succeeded = 1
        job.status.failed = 0
        job.status.start_time = _NOW - timedelta(minutes=5)
        job.status.completion_time = _NOW
        job.status.conditions = []
        result = serialize_job(job)
        assert result["status"] == "Complete"
        assert "5m" in result["duration"]

    def test_failed_job(self):
        job = MagicMock()
        job.metadata = _meta("build-fail")
        job.spec.completions = 1; job.spec.parallelism = 1; job.spec.backoff_limit = 3
        job.status.active = 0; job.status.succeeded = 0; job.status.failed = 1
        job.status.start_time = _NOW
        job.status.completion_time = None
        job.status.conditions = []
        result = serialize_job(job)
        assert result["status"] == "Failed"


class TestSerializeConfigmap:
    def test_without_data(self):
        cm = MagicMock()
        cm.metadata = _meta("app-config")
        cm.data = {"key1": "val1", "key2": "val2"}
        result = serialize_configmap(cm)
        assert result["dataCount"] == 2
        assert "data" not in result

    def test_with_data(self):
        cm = MagicMock()
        cm.metadata = _meta("app-config")
        cm.data = {"key1": "val1"}
        result = serialize_configmap(cm, include_data=True)
        assert result["data"]["key1"] == "val1"


class TestSerializeSecret:
    def test_without_data(self):
        secret = MagicMock()
        secret.metadata = _meta("db-secret")
        secret.data = {"password": "c2VjcmV0"}  # base64 "secret"
        secret.type = "Opaque"
        result = serialize_secret(secret)
        assert result["dataCount"] == 1
        assert "data" not in result

    def test_with_data_masked(self):
        import base64
        secret = MagicMock()
        secret.metadata = _meta("db-secret")
        secret.data = {"password": base64.b64encode(b"my-secret-password").decode()}
        secret.type = "Opaque"
        result = serialize_secret(secret, include_data=True)
        assert result["data"]["password"].endswith("****")
        assert result["data"]["password"].startswith("my-s")

    def test_short_value_fully_masked(self):
        import base64
        secret = MagicMock()
        secret.metadata = _meta("short")
        secret.data = {"key": base64.b64encode(b"abc").decode()}
        secret.type = "Opaque"
        result = serialize_secret(secret, include_data=True)
        assert result["data"]["key"] == "****"


class TestSerializeRole:
    def test_basic(self):
        role = MagicMock()
        role.metadata = _meta("admin-role")
        rule = MagicMock()
        rule.api_groups = [""]
        rule.resources = ["pods"]
        rule.verbs = ["get", "list"]
        rule.resource_names = None
        role.rules = [rule]
        result = serialize_role(role)
        assert result["name"] == "admin-role"
        assert len(result["rules"]) == 1


class TestSerializeRoleBinding:
    def test_basic(self):
        binding = MagicMock()
        binding.metadata = _meta("admin-binding")
        binding.role_ref.kind = "ClusterRole"
        binding.role_ref.name = "admin"
        subject = MagicMock()
        subject.kind = "User"
        subject.name = "dev@example.com"
        subject.namespace = None
        binding.subjects = [subject]
        result = serialize_role_binding(binding)
        assert result["roleRef"]["name"] == "admin"
        assert len(result["subjects"]) == 1


class TestSerializeServiceAccount:
    def test_basic(self):
        sa = MagicMock()
        sa.metadata = _meta("default")
        secret = MagicMock()
        secret.name = "default-token-abc"
        sa.secrets = [secret]
        result = serialize_service_account(sa)
        assert result["name"] == "default"
        assert "default-token-abc" in result["secrets"]

    def test_no_secrets(self):
        sa = MagicMock()
        sa.metadata = _meta("no-secret-sa")
        sa.secrets = None
        result = serialize_service_account(sa)
        assert result["secrets"] == []
