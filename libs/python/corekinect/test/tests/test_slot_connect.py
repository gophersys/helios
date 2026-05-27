"""Tests for :class:`corekinect.test.slot.SlotContext` lifecycle.

These tests focus on the connect/ensure_connected/disconnect contract of
SlotContext — the retry loop, pod-state surfacing on failure, lenient
HealthCheck behaviour, and health-check-based reconnection. The
``MtibV1Client`` is fully mocked here so every branch of the retry
state machine can be driven deterministically; the live-gRPC contract
is exercised in ``test_slot_integration.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import grpc
import pytest

import corekinect.test.slot as slot_mod
from corekinect.test.slot import SlotContext


# ────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """Slot connect uses time.sleep between retries. Tests don't care."""
    monkeypatch.setattr(slot_mod, "CONNECT_RETRY_DELAY_S", 0.0)
    monkeypatch.setattr(slot_mod.time, "sleep", lambda _s: None)


def _rpc_error(code: grpc.StatusCode, details: str = "") -> grpc.RpcError:
    """Build a minimal :class:`grpc.RpcError` carrying the given code."""
    err = grpc.RpcError()
    err.code = MagicMock(return_value=code)
    err.details = MagicMock(return_value=details)
    return err


def _make_slot(**overrides) -> SlotContext:
    defaults = dict(
        slot_id="slot-0",
        slot_index=0,
        mtib_address="10.0.0.1",
        mtib_port=50053,
    )
    defaults.update(overrides)
    return SlotContext(**defaults)


def _success_mtib() -> MagicMock:
    """An MtibV1Client mock whose connect+HealthCheck always succeed."""
    mock = MagicMock()
    mock.connect.return_value = None
    mock.HealthCheck.return_value = (True, [], None)
    mock.disconnect.return_value = None
    return mock


# ────────────────────────────────────────────────────────────────────────
# SlotContext.connect — happy path
# ────────────────────────────────────────────────────────────────────────


class TestSlotContextConnectHappyPath:
    """First-attempt success — no retries, no testbed unless provided."""

    @patch("corekinect.test.slot.MtibV1Client")
    def test_connect_first_attempt_no_testbed_factory(self, mock_client_cls):
        mock_mtib = _success_mtib()
        mock_client_cls.return_value = mock_mtib

        slot = _make_slot()
        slot.connect()

        assert slot.mtib is mock_mtib
        assert slot.testbed is None
        # The retry loop should not have engaged at all — exactly one
        # MtibV1Client instantiation and one HealthCheck.
        assert mock_client_cls.call_count == 1
        assert mock_mtib.connect.call_count == 1
        assert mock_mtib.HealthCheck.call_count == 1

    @patch("corekinect.test.slot.MtibV1Client")
    def test_connect_invokes_testbed_factory_when_provided(self, mock_client_cls):
        mock_mtib = _success_mtib()
        mock_client_cls.return_value = mock_mtib
        fake_testbed = object()
        factory = MagicMock(return_value=fake_testbed)

        slot = _make_slot()
        slot.connect(testbed_factory=factory)

        # Factory receives the connected MTIB and the slot stores the result.
        factory.assert_called_once_with(mock_mtib)
        assert slot.testbed is fake_testbed


# ────────────────────────────────────────────────────────────────────────
# SlotContext.connect — retry semantics
# ────────────────────────────────────────────────────────────────────────


class TestSlotContextConnectRetries:
    """Retry loop wiring — sleeps, stale-client cleanup, attempt counter."""

    @patch("corekinect.test.slot.MtibV1Client")
    def test_retries_then_succeeds(self, mock_client_cls, monkeypatch):
        """Two failures followed by success: assert exactly 2 sleeps, 2
        stale-client disconnects, and the slot ends up connected.
        """
        # Track sleep calls.
        sleeps: list = []
        monkeypatch.setattr(slot_mod.time, "sleep", lambda s: sleeps.append(s))

        attempts = []

        def make_client(_cfg):
            attempts.append(len(attempts) + 1)
            mock = MagicMock()
            if len(attempts) <= 2:
                mock.connect.return_value = "boom"
            else:
                mock.connect.return_value = None
                mock.HealthCheck.return_value = (True, [], None)
            return mock

        mock_client_cls.side_effect = make_client

        slot = _make_slot()
        slot.connect()

        assert len(sleeps) == 2  # Sleep after attempt 1 and 2; success on 3
        assert mock_client_cls.call_count == 3
        # The stale clients (attempts 1 and 2) each had disconnect called.
        # The 3rd (successful) client is the one stored on the slot.
        assert slot.mtib is not None

    @patch("corekinect.test.slot.MtibV1Client")
    def test_all_attempts_fail_raises_with_format(self, mock_client_cls):
        mock_mtib = MagicMock()
        mock_mtib.connect.return_value = "connection refused"
        mock_client_cls.return_value = mock_mtib

        slot = _make_slot(slot_id="slot-3", mtib_address="10.4.45.33", mtib_port=50053)

        with pytest.raises(ConnectionError) as exc_info:
            slot.connect()

        msg = str(exc_info.value)
        # Final error must include slot id, host:port, attempt count, and the
        # last-attempt error string.
        assert "slot-3" in msg
        assert "10.4.45.33:50053" in msg
        assert f"failed after {slot_mod.CONNECT_MAX_ATTEMPTS} attempts" in msg
        assert "connection refused" in msg
        # Without a pod_state_lookup, no suffix.
        assert "[pod state:" not in msg
        assert mock_mtib.connect.call_count == slot_mod.CONNECT_MAX_ATTEMPTS

    @patch("corekinect.test.slot.MtibV1Client")
    def test_connect_returning_err_string_triggers_retry(self, mock_client_cls):
        """MtibV1Client.connect() returns a non-None error → ConnectionError
        inside the loop → retry path engaged.
        """
        attempts = []

        def make_client(_cfg):
            mock = MagicMock()
            if not attempts:
                attempts.append(1)
                mock.connect.return_value = "some sdk error"
            else:
                attempts.append(2)
                mock.connect.return_value = None
                mock.HealthCheck.return_value = (True, [], None)
            return mock

        mock_client_cls.side_effect = make_client

        slot = _make_slot()
        slot.connect()
        assert len(attempts) == 2
        assert slot.mtib is not None

    @patch("corekinect.test.slot.MtibV1Client")
    def test_healthcheck_non_unimplemented_err_triggers_retry(self, mock_client_cls):
        """HealthCheck returning an error other than UNIMPLEMENTED must
        still raise ConnectionError and engage the retry loop.
        """
        first = MagicMock()
        first.connect.return_value = None
        first.HealthCheck.return_value = (None, None, "gRPC error: server died")
        second = _success_mtib()
        mock_client_cls.side_effect = [first, second]

        slot = _make_slot()
        slot.connect()
        # Both clients constructed; both connect calls invoked.
        assert mock_client_cls.call_count == 2
        # The stale first client was disconnected before the retry.
        assert first.disconnect.call_count == 1

    @patch("corekinect.test.slot.MtibV1Client")
    def test_healthcheck_ready_false_triggers_retry_and_then_fails(self, mock_client_cls):
        """HealthCheck returning ready=False with no err → ConnectionError
        with the errors list, retried up to the cap.
        """
        mock_mtib = MagicMock()
        mock_mtib.connect.return_value = None
        mock_mtib.HealthCheck.return_value = (False, ["uart down"], None)
        mock_client_cls.return_value = mock_mtib

        slot = _make_slot()
        with pytest.raises(ConnectionError) as exc_info:
            slot.connect()
        assert "MTIB not ready" in str(exc_info.value)
        assert "uart down" in str(exc_info.value)

    @patch("corekinect.test.slot.MtibV1Client")
    def test_stale_client_disconnect_swallows_exception(self, mock_client_cls):
        """If the stale client's disconnect() raises during cleanup, the
        retry loop must still advance — the operator's terminal error
        comes from the *next* attempt, not the cleanup failure.
        """
        bad = MagicMock()
        bad.connect.return_value = "boom"
        bad.disconnect.side_effect = RuntimeError("disconnect blew up")
        good = _success_mtib()
        mock_client_cls.side_effect = [bad, good]

        slot = _make_slot()
        # Should not raise — exception is swallowed.
        slot.connect()
        assert slot.mtib is good
        # The bad client's disconnect was attempted before the second client
        # was constructed.
        assert bad.disconnect.call_count == 1

    @patch("corekinect.test.slot.MtibV1Client")
    def test_stale_mtib_field_reset_between_attempts(self, mock_client_cls):
        """Between attempts the mtib field must be cleared so a failure
        on the next attempt doesn't double-disconnect the previous
        client.
        """
        bad = MagicMock()
        bad.connect.return_value = "boom"
        good = _success_mtib()
        mock_client_cls.side_effect = [bad, good]

        slot = _make_slot()
        slot.connect()
        # The successful client is the one stored, not the failed one.
        assert slot.mtib is good
        # bad.disconnect called exactly once during the retry cleanup.
        assert bad.disconnect.call_count == 1


# ────────────────────────────────────────────────────────────────────────
# Env overrides — CONNECT_MAX_ATTEMPTS / CONNECT_RETRY_DELAY_S
# ────────────────────────────────────────────────────────────────────────


class TestSlotContextRetryEnvOverrides:
    """Module-level constants reflect env vars at import time, but the
    tests reload the module to verify the override path is wired."""

    def test_max_attempts_env_override_one(self, monkeypatch):
        """Set the max attempts to 1 → exactly one connect call, no sleep."""
        monkeypatch.setenv("MTIB_CONNECT_MAX_ATTEMPTS", "1")
        monkeypatch.setenv("MTIB_CONNECT_RETRY_DELAY_S", "0")
        import importlib

        reloaded = importlib.reload(slot_mod)
        try:
            assert reloaded.CONNECT_MAX_ATTEMPTS == 1
            assert reloaded.CONNECT_RETRY_DELAY_S == 0.0

            sleeps = []
            monkeypatch.setattr(reloaded.time, "sleep", lambda s: sleeps.append(s))

            with patch.object(reloaded, "MtibV1Client") as mock_cls:
                mock_mtib = MagicMock()
                mock_mtib.connect.return_value = "boom"
                mock_cls.return_value = mock_mtib

                slot = reloaded.SlotContext(
                    slot_id="slot-0", slot_index=0, mtib_address="10.0.0.1",
                )
                with pytest.raises(ConnectionError):
                    slot.connect()

                assert mock_mtib.connect.call_count == 1
                # No retries means no sleeps.
                assert sleeps == []
        finally:
            monkeypatch.delenv("MTIB_CONNECT_MAX_ATTEMPTS", raising=False)
            monkeypatch.delenv("MTIB_CONNECT_RETRY_DELAY_S", raising=False)
            importlib.reload(slot_mod)

    def test_max_attempts_env_override_ten(self, monkeypatch):
        monkeypatch.setenv("MTIB_CONNECT_MAX_ATTEMPTS", "10")
        monkeypatch.setenv("MTIB_CONNECT_RETRY_DELAY_S", "0")
        import importlib

        reloaded = importlib.reload(slot_mod)
        try:
            assert reloaded.CONNECT_MAX_ATTEMPTS == 10
            monkeypatch.setattr(reloaded.time, "sleep", lambda _s: None)

            with patch.object(reloaded, "MtibV1Client") as mock_cls:
                mock_mtib = MagicMock()
                mock_mtib.connect.return_value = "boom"
                mock_cls.return_value = mock_mtib

                slot = reloaded.SlotContext(
                    slot_id="slot-0", slot_index=0, mtib_address="10.0.0.1",
                )
                with pytest.raises(ConnectionError):
                    slot.connect()
                assert mock_mtib.connect.call_count == 10
        finally:
            monkeypatch.delenv("MTIB_CONNECT_MAX_ATTEMPTS", raising=False)
            monkeypatch.delenv("MTIB_CONNECT_RETRY_DELAY_S", raising=False)
            importlib.reload(slot_mod)

    def test_retry_delay_env_override(self, monkeypatch):
        """The retry-delay env var is consumed at import time."""
        monkeypatch.setenv("MTIB_CONNECT_RETRY_DELAY_S", "0.25")
        import importlib

        reloaded = importlib.reload(slot_mod)
        try:
            assert reloaded.CONNECT_RETRY_DELAY_S == 0.25
        finally:
            monkeypatch.delenv("MTIB_CONNECT_RETRY_DELAY_S", raising=False)
            importlib.reload(slot_mod)


# ────────────────────────────────────────────────────────────────────────
# pod_state_lookup — error message surfacing
# ────────────────────────────────────────────────────────────────────────


class TestSlotContextPodStateSurfacing:
    """When the MTIB never answers, the final error optionally mentions pod state."""

    @patch("corekinect.test.slot.MtibV1Client")
    def test_failure_message_includes_pod_state_when_lookup_returns_one(self, mock_client_cls):
        """If a ``pod_state_lookup`` callable is wired on the slot, its
        return value (e.g. ``ImagePullBackOff``) must appear in the final
        ConnectionError so the operator sees *why* gRPC was unreachable
        instead of just "connection failed".
        """
        mock_mtib = MagicMock()
        mock_mtib.connect.return_value = "connection refused"
        mock_client_cls.return_value = mock_mtib

        slot = _make_slot()
        slot.pod_state_lookup = MagicMock(return_value="ImagePullBackOff")

        with pytest.raises(ConnectionError) as exc_info:
            slot.connect()
        assert "ImagePullBackOff" in str(exc_info.value)
        assert "[pod state: ImagePullBackOff]" in str(exc_info.value)

    @patch("corekinect.test.slot.MtibV1Client")
    def test_no_pod_state_lookup_falls_back_to_plain_error(self, mock_client_cls):
        """Without a lookup configured, the historic generic error message
        is preserved. We don't want to silently start requiring k8s
        access from every test runner.
        """
        mock_mtib = MagicMock()
        mock_mtib.connect.return_value = "connection refused"
        mock_client_cls.return_value = mock_mtib

        slot = _make_slot()
        with pytest.raises(ConnectionError) as exc_info:
            slot.connect()
        assert "ImagePullBackOff" not in str(exc_info.value)
        assert "10.0.0.1" in str(exc_info.value)
        assert "[pod state:" not in str(exc_info.value)

    @patch("corekinect.test.slot.MtibV1Client")
    def test_pod_state_lookup_not_called_when_first_attempt_succeeds(
        self, mock_client_cls,
    ):
        """If attempt 1 succeeds, the lookup is never invoked — the K8s
        round trip is a recovery-mode tool, not a steady-state one.
        """
        mock_mtib = _success_mtib()
        mock_client_cls.return_value = mock_mtib

        lookup = MagicMock(return_value="Pending")
        slot = _make_slot()
        slot.pod_state_lookup = lookup

        slot.connect()
        # Attempt 1 succeeded → the failure-handler never ran → lookup not called.
        assert lookup.call_count == 0

    @patch("corekinect.test.slot.MtibV1Client")
    def test_pod_state_lookup_not_called_when_only_first_attempt_fails(
        self, mock_client_cls,
    ):
        """The lookup runs inside the failure handler at ``attempt >= 2``.
        If the first attempt fails (attempt=1) and the second succeeds,
        the lookup is never consulted — single transient failure is
        below the threshold for a K8s API round trip.
        """
        first = MagicMock()
        first.connect.return_value = "boom"
        good = _success_mtib()
        mock_client_cls.side_effect = [first, good]

        lookup = MagicMock(return_value="Pending")
        slot = _make_slot()
        slot.pod_state_lookup = lookup

        slot.connect()
        # Attempt 1 failed (attempt < 2 → no lookup), attempt 2 succeeded
        # (no exception → no lookup). Lookup never fires.
        assert lookup.call_count == 0

    @patch("corekinect.test.slot.MtibV1Client")
    def test_pod_state_lookup_called_when_second_attempt_also_fails(
        self, mock_client_cls,
    ):
        """First and second attempt both fail, third succeeds → the
        lookup fires inside the attempt-2 failure handler.
        """
        bad = MagicMock()
        bad.connect.return_value = "boom"
        good = _success_mtib()
        # Two failures, then success.
        mock_client_cls.side_effect = [bad, bad, good]

        lookup = MagicMock(return_value="Pending")
        slot = _make_slot()
        slot.pod_state_lookup = lookup

        slot.connect()
        # Attempt 2 failed, so the lookup ran exactly once.
        assert lookup.call_count == 1

    @patch("corekinect.test.slot.MtibV1Client")
    def test_pod_state_lookup_called_once_even_when_all_attempts_fail(
        self, mock_client_cls,
    ):
        """The lookup result is memoised in a local var — even with 5
        failures, the K8s lookup runs at most once.
        """
        mock_mtib = MagicMock()
        mock_mtib.connect.return_value = "boom"
        mock_client_cls.return_value = mock_mtib

        lookup = MagicMock(return_value="CrashLoopBackOff")
        slot = _make_slot()
        slot.pod_state_lookup = lookup

        with pytest.raises(ConnectionError) as exc_info:
            slot.connect()
        assert lookup.call_count == 1
        assert "CrashLoopBackOff" in str(exc_info.value)

    @patch("corekinect.test.slot.MtibV1Client")
    def test_pod_state_lookup_exception_is_swallowed(self, mock_client_cls):
        """The pod lookup is best-effort. If it raises (e.g., the K8s
        client can't reach the API server) the connect must still fail
        with the original gRPC error, sans pod-state suffix.
        """
        mock_mtib = MagicMock()
        mock_mtib.connect.return_value = "boom"
        mock_client_cls.return_value = mock_mtib

        lookup = MagicMock(side_effect=RuntimeError("kube down"))
        slot = _make_slot()
        slot.pod_state_lookup = lookup

        with pytest.raises(ConnectionError) as exc_info:
            slot.connect()
        assert "[pod state:" not in str(exc_info.value)
        assert "boom" in str(exc_info.value)

    @patch("corekinect.test.slot.MtibV1Client")
    def test_pod_state_lookup_returning_none_omits_suffix(self, mock_client_cls):
        """The lookup may legitimately return None (e.g., pod is
        actually Running, just slow to answer). No suffix in that case.
        """
        mock_mtib = MagicMock()
        mock_mtib.connect.return_value = "boom"
        mock_client_cls.return_value = mock_mtib

        slot = _make_slot()
        slot.pod_state_lookup = MagicMock(return_value=None)

        with pytest.raises(ConnectionError) as exc_info:
            slot.connect()
        assert "[pod state:" not in str(exc_info.value)


# ────────────────────────────────────────────────────────────────────────
# SlotContext.connect — lenient HealthCheck
# ────────────────────────────────────────────────────────────────────────


class TestSlotContextConnectLenient:
    """Lenient HealthCheck behaviour mirrored from MtibV1Client."""

    @patch("corekinect.test.slot.MtibV1Client")
    def test_connect_proceeds_on_unimplemented_healthcheck(self, mock_client_cls):
        """When the underlying MtibV1Client.connect() returns success but
        the explicit HealthCheck()-style check inside SlotContext.connect
        receives UNIMPLEMENTED, the slot should still be considered
        connected. The slot logs the degradation but does not raise.
        """
        mock_mtib = MagicMock()
        mock_mtib.connect.return_value = None
        mock_mtib.HealthCheck.return_value = (
            None,
            None,
            "gRPC error for HealthCheck at 10.0.0.1. Error: UNIMPLEMENTED",
        )
        mock_client_cls.return_value = mock_mtib

        slot = _make_slot()
        slot.connect()
        assert slot.mtib is mock_mtib


# ────────────────────────────────────────────────────────────────────────
# SlotContext.ensure_connected
# ────────────────────────────────────────────────────────────────────────


class TestSlotContextEnsureConnected:
    """Health-check-driven self-healing reconnect."""

    @patch("corekinect.test.slot.MtibV1Client")
    def test_ensure_connected_no_mtib_calls_connect_and_returns_true(
        self, mock_client_cls,
    ):
        mock_mtib = _success_mtib()
        mock_client_cls.return_value = mock_mtib

        slot = _make_slot()
        assert slot.mtib is None

        assert slot.ensure_connected() is True
        assert slot.mtib is mock_mtib

    @patch("corekinect.test.slot.MtibV1Client")
    def test_ensure_connected_no_mtib_failure_returns_false(self, mock_client_cls):
        """When the slot has no MTIB and connect fails, the method
        catches the ConnectionError and returns False — callers use the
        boolean to decide whether to skip the slot's tests.
        """
        mock_mtib = MagicMock()
        mock_mtib.connect.return_value = "boom"
        mock_client_cls.return_value = mock_mtib

        slot = _make_slot()
        assert slot.ensure_connected() is False

    def test_ensure_connected_healthy_mtib_returns_true_no_reconnect(self):
        """Existing MTIB with a clean HealthCheck → no reconnect."""
        slot = _make_slot()
        existing = MagicMock()
        existing.HealthCheck.return_value = (True, [], None)
        slot.mtib = existing

        with patch("corekinect.test.slot.MtibV1Client") as mock_cls:
            assert slot.ensure_connected() is True
            # No new client was created — the existing one stays.
            mock_cls.assert_not_called()
        assert slot.mtib is existing

    @patch("corekinect.test.slot.MtibV1Client")
    def test_ensure_connected_healthcheck_err_triggers_reconnect(self, mock_client_cls):
        stale = MagicMock()
        stale.HealthCheck.return_value = (None, None, "gRPC error: server died")
        stale.disconnect.return_value = None

        fresh = _success_mtib()
        mock_client_cls.return_value = fresh

        slot = _make_slot()
        slot.mtib = stale

        assert slot.ensure_connected() is True
        # Stale was disconnected, new client built.
        assert stale.disconnect.call_count == 1
        assert slot.mtib is fresh

    @patch("corekinect.test.slot.MtibV1Client")
    def test_ensure_connected_not_ready_triggers_reconnect(self, mock_client_cls):
        stale = MagicMock()
        stale.HealthCheck.return_value = (False, ["bad"], None)
        stale.disconnect.return_value = None

        fresh = _success_mtib()
        mock_client_cls.return_value = fresh

        slot = _make_slot()
        slot.mtib = stale

        assert slot.ensure_connected() is True
        assert slot.mtib is fresh

    @patch("corekinect.test.slot.MtibV1Client")
    def test_ensure_connected_healthcheck_raises_triggers_reconnect(
        self, mock_client_cls,
    ):
        stale = MagicMock()
        stale.HealthCheck.side_effect = RuntimeError("network burp")
        stale.disconnect.return_value = None

        fresh = _success_mtib()
        mock_client_cls.return_value = fresh

        slot = _make_slot()
        slot.mtib = stale

        assert slot.ensure_connected() is True
        assert slot.mtib is fresh

    @patch("corekinect.test.slot.MtibV1Client")
    def test_ensure_connected_disconnect_failure_during_reconnect_is_swallowed(
        self, mock_client_cls,
    ):
        """If the stale client's disconnect() raises during the reconnect
        path, the reconnect must still proceed.
        """
        stale = MagicMock()
        stale.HealthCheck.return_value = (False, ["bad"], None)
        stale.disconnect.side_effect = RuntimeError("disconnect blew up")

        fresh = _success_mtib()
        mock_client_cls.return_value = fresh

        slot = _make_slot()
        slot.mtib = stale

        # Should still return True — the disconnect raise is swallowed.
        assert slot.ensure_connected() is True
        assert slot.mtib is fresh

    @patch("corekinect.test.slot.MtibV1Client")
    def test_ensure_connected_forwards_testbed_factory(self, mock_client_cls):
        mock_mtib = _success_mtib()
        mock_client_cls.return_value = mock_mtib
        sentinel = object()
        factory = MagicMock(return_value=sentinel)

        slot = _make_slot()
        assert slot.ensure_connected(testbed_factory=factory) is True
        factory.assert_called_once_with(mock_mtib)
        assert slot.testbed is sentinel


# ────────────────────────────────────────────────────────────────────────
# SlotContext.disconnect
# ────────────────────────────────────────────────────────────────────────


class TestSlotContextDisconnect:
    def test_disconnect_no_mtib_is_noop(self):
        slot = _make_slot()
        # Must not raise.
        slot.disconnect()
        assert slot.mtib is None

    def test_disconnect_clean(self):
        slot = _make_slot()
        slot.mtib = MagicMock()
        slot.mtib.disconnect.return_value = None
        slot.disconnect()
        slot.mtib.disconnect.assert_called_once()

    def test_disconnect_logs_warning_on_error(self):
        """If the underlying client reports an error, disconnect logs
        but does not raise — the slot remains in a defined post-state.
        """
        slot = _make_slot()
        slot.mtib = MagicMock()
        slot.mtib.disconnect.return_value = "something went wrong"
        # Must not raise.
        slot.disconnect()
        slot.mtib.disconnect.assert_called_once()
