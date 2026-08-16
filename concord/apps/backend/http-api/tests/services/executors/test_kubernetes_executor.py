"""Tests for KubernetesExecutor."""

from unittest.mock import MagicMock, patch, PropertyMock
from types import SimpleNamespace

import pytest

from services.executors.kubernetes_executor import KubernetesExecutor
from services.executors.base import VolumeMount


@pytest.fixture
def executor():
    return KubernetesExecutor(ttl_after_finished=600)


class TestKubernetesExecutorSubmit:
    def test_submit_success(self, executor):
        mock_batch = MagicMock()
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            result = executor.submit(
                image="containers.ad.corekinect.com/concord-test-runner:staging",
                job_id="entry-abc123",
                env={"CONCORD_API_URL": "http://api:9001", "STAGE": "smoke"},
                command=["/app/entrypoint.sh"],
                namespace="validation",
                labels={"app": "validation-alpha"},
                node_selector={"concord.corekinect.com/workload-worker": "true"},
            )
            assert result.success is True
            assert result.job_name is not None

            # Verify K8s Job was created
            mock_batch.create_namespaced_job.assert_called_once()
            call_kwargs = mock_batch.create_namespaced_job.call_args
            assert call_kwargs.kwargs["namespace"] == "validation"

            body = call_kwargs.kwargs["body"]
            assert body["apiVersion"] == "batch/v1"
            assert body["kind"] == "Job"
            assert body["spec"]["backoffLimit"] == 0
            assert body["spec"]["template"]["spec"]["restartPolicy"] == "Never"

    def test_submit_includes_env_vars(self, executor):
        mock_batch = MagicMock()
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            executor.submit(
                image="img:latest",
                job_id="job-002",
                env={"KEY_A": "val_a", "KEY_B": "val_b"},
                command=["bash", "-c", "echo hi"],
                namespace="default",
            )
            body = mock_batch.create_namespaced_job.call_args.kwargs["body"]
            container = body["spec"]["template"]["spec"]["containers"][0]
            env_names = {e["name"] for e in container["env"]}
            assert "KEY_A" in env_names
            assert "KEY_B" in env_names

    def test_submit_includes_node_selector(self, executor):
        mock_batch = MagicMock()
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            executor.submit(
                image="img:latest",
                job_id="job-003",
                env={},
                command=["true"],
                namespace="build",
                node_selector={"concord.corekinect.com/workload-build": "true"},
            )
            body = mock_batch.create_namespaced_job.call_args.kwargs["body"]
            spec = body["spec"]["template"]["spec"]
            assert spec["nodeSelector"]["concord.corekinect.com/workload-build"] == "true"

    def test_submit_includes_volumes(self, executor):
        mock_batch = MagicMock()
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            executor.submit(
                image="img:latest",
                job_id="job-004",
                env={},
                command=["true"],
                volumes=[VolumeMount(name="logs", host_path="/var/log/tests", mount_path="/var/log/runner")],
            )
            body = mock_batch.create_namespaced_job.call_args.kwargs["body"]
            spec = body["spec"]["template"]["spec"]
            assert len(spec["volumes"]) == 1
            assert spec["volumes"][0]["name"] == "logs"
            assert spec["volumes"][0]["hostPath"]["path"] == "/var/log/tests"

    def test_submit_includes_resource_limits(self, executor):
        mock_batch = MagicMock()
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            executor.submit(
                image="img:latest",
                job_id="job-005",
                env={},
                command=["true"],
                resource_requests={"cpu": "250m", "memory": "200Mi"},
                resource_limits={"cpu": "2000m", "memory": "2000Mi"},
            )
            body = mock_batch.create_namespaced_job.call_args.kwargs["body"]
            container = body["spec"]["template"]["spec"]["containers"][0]
            assert container["resources"]["requests"]["cpu"] == "250m"
            assert container["resources"]["limits"]["memory"] == "2000Mi"

    def test_submit_sets_active_deadline(self, executor):
        mock_batch = MagicMock()
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            executor.submit(
                image="img:latest",
                job_id="job-006",
                env={},
                command=["true"],
                timeout_seconds=1800,
            )
            body = mock_batch.create_namespaced_job.call_args.kwargs["body"]
            assert body["spec"]["activeDeadlineSeconds"] == 1800

    def test_submit_k8s_not_available(self, executor):
        with patch("services.executors.kubernetes_executor._get_batch_v1", side_effect=RuntimeError("not init")):
            result = executor.submit(
                image="img:latest",
                job_id="job-007",
                env={},
                command=["true"],
            )
            assert result.success is False
            assert result.error is not None

    def test_submit_k8s_api_error(self, executor):
        mock_batch = MagicMock()
        mock_batch.create_namespaced_job.side_effect = Exception("API server unreachable")
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            result = executor.submit(
                image="img:latest",
                job_id="job-008",
                env={},
                command=["true"],
            )
            assert result.success is False
            assert "API server unreachable" in result.error


class TestKubernetesExecutorCancel:
    def test_cancel_success(self, executor):
        mock_batch = MagicMock()
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            assert executor.cancel("concord-job-abc", namespace="validation") is True
            mock_batch.delete_namespaced_job.assert_called_once()

    def test_cancel_failure(self, executor):
        mock_batch = MagicMock()
        mock_batch.delete_namespaced_job.side_effect = Exception("not found")
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            assert executor.cancel("nonexistent") is False


class TestKubernetesExecutorIsAlive:
    def test_is_alive_active(self, executor):
        mock_batch = MagicMock()
        mock_job = MagicMock()
        mock_job.status.active = 1
        mock_job.status.succeeded = None
        mock_job.status.failed = None
        mock_batch.read_namespaced_job_status.return_value = mock_job
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            assert executor.is_alive("job-abc", namespace="validation") is True

    def test_is_alive_succeeded(self, executor):
        mock_batch = MagicMock()
        mock_job = MagicMock()
        mock_job.status.active = None
        mock_job.status.succeeded = 1
        mock_job.status.failed = None
        mock_batch.read_namespaced_job_status.return_value = mock_job
        with patch("services.executors.kubernetes_executor._get_batch_v1", return_value=mock_batch):
            assert executor.is_alive("job-abc") is False

    def test_is_alive_error(self, executor):
        with patch("services.executors.kubernetes_executor._get_batch_v1", side_effect=Exception("fail")):
            assert executor.is_alive("job-abc") is None


class TestJobNaming:
    def test_name_from_labels(self):
        name = KubernetesExecutor._make_job_name("cuid-abc123", labels={"app": "validation-alpha"})
        assert name.startswith("validation-alpha-")
        assert len(name) <= 63

    def test_name_rfc_1123_compliant(self):
        name = KubernetesExecutor._make_job_name("CUID_ABC!@#123", labels={"app": "My Build"})
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name)
        assert not name.startswith("-")
