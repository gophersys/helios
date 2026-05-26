"""Integration tests: drive :class:`SlotContext.connect` against a real
gRPC server with a stub :class:`MtibV1Servicer`.

These tests are deliberately complementary to the mock-heavy
``test_slot_connect.py`` — they exercise the live ``MtibV1Client``
end-to-end so any regression in the gRPC plumbing (channel state,
serialization, status-code surfacing) surfaces here.

The server runs on ``localhost:<auto-port>`` and is torn down after
each test. Each test waits at most a few seconds; the autouse fixture
clamps the SlotContext retry delay so we don't spend real seconds on
the failure paths.
"""

from __future__ import annotations

import socket
import time
from concurrent import futures
from typing import Optional

import grpc
import pytest

from protocols.mtib import mtib_pb2, mtib_pb2_grpc

import corekinect.test.slot as slot_mod
from corekinect.test.slot import SlotContext


# ────────────────────────────────────────────────────────────────────────
# Test fixtures: ephemeral gRPC server + free-port allocator
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """Stub out the inter-attempt sleep so failure paths run fast."""
    monkeypatch.setattr(slot_mod, "CONNECT_RETRY_DELAY_S", 0.0)
    monkeypatch.setattr(slot_mod.time, "sleep", lambda _s: None)


def _free_port() -> int:
    """Reserve a free port. We close the socket immediately; there's a
    small race window before the gRPC server binds it, but this is
    standard practice for ephemeral test servers and the OS recycles
    ports lazily.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _BaseServicer(mtib_pb2_grpc.MtibV1Servicer):
    """Default servicer — every RPC returns UNIMPLEMENTED. Subclasses
    override just the methods they need.
    """

    def HealthCheck(self, request, context):  # noqa: D401
        # Default to UNIMPLEMENTED with the explicit token in details so
        # the slot's substring match recognises this path.
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("UNIMPLEMENTED: HealthCheck not implemented")
        return mtib_pb2.HealthCheckResponse()


class _HealthyServicer(_BaseServicer):
    def HealthCheck(self, request, context):
        return mtib_pb2.HealthCheckResponse(ready=True, errors=[])


class _UnimplementedServicer(_BaseServicer):
    """Inherits default: HealthCheck → UNIMPLEMENTED with the explicit
    details string. The string ``"UNIMPLEMENTED"`` appears in the
    server-set details so the substring-match in
    :meth:`SlotContext.connect` fires correctly.

    See :class:`_BareServicer` for the case where the server doesn't
    implement HealthCheck at all — gRPC then auto-generates
    ``"Method not implemented!"`` as details, which the slot's
    substring match does **not** recognize. That divergence is
    intentionally exercised by ``test_bare_unimplemented_servicer_currently_fails``
    so the bug stays visible.
    """


class _BareServicer(mtib_pb2_grpc.MtibV1Servicer):
    """No HealthCheck override at all — the framework returns
    ``StatusCode.UNIMPLEMENTED`` with details ``"Method not implemented!"``.
    The SDK's :meth:`MtibV1Client.connect` recognizes this via
    ``e.code() == UNIMPLEMENTED`` and proceeds, but the slot's second
    HealthCheck call relies on a substring match against the error
    string and does *not* recognize this case.
    """


class _NotReadyServicer(_BaseServicer):
    def HealthCheck(self, request, context):
        return mtib_pb2.HealthCheckResponse(ready=False, errors=["uart wedged"])


def _start_server(servicer: mtib_pb2_grpc.MtibV1Servicer, port: int):
    """Start a gRPC server on the given port. Returns the server
    handle; caller is responsible for ``server.stop()``.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    mtib_pb2_grpc.add_MtibV1Servicer_to_server(servicer, server)
    server.add_insecure_port(f"127.0.0.1:{port}")
    server.start()
    return server


# ────────────────────────────────────────────────────────────────────────
# Integration tests
# ────────────────────────────────────────────────────────────────────────


class TestSlotConnectAgainstLiveServer:
    """End-to-end SlotContext.connect ↔ MtibV1Client ↔ grpc.server."""

    def test_healthy_server_connects_successfully(self):
        port = _free_port()
        server = _start_server(_HealthyServicer(), port)
        try:
            slot = SlotContext(
                slot_id="slot-0", slot_index=0,
                mtib_address="127.0.0.1", mtib_port=port,
            )
            slot.connect()
            assert slot.mtib is not None
            # Real HealthCheck works against the live server.
            ready, errors, err = slot.mtib.HealthCheck()
            assert err is None
            assert ready is True
            assert list(errors) == []
            slot.disconnect()
        finally:
            server.stop(grace=0).wait()

    def test_unimplemented_healthcheck_is_lenient(self):
        """Older MTIB build that explicitly sets ``"UNIMPLEMENTED"`` in
        the gRPC details → slot connects anyway, mirroring the SDK's
        lenient behaviour. The slot does a substring match on the
        error string, so the details must literally contain the token.
        """
        port = _free_port()
        server = _start_server(_UnimplementedServicer(), port)
        try:
            slot = SlotContext(
                slot_id="slot-0", slot_index=0,
                mtib_address="127.0.0.1", mtib_port=port,
            )
            slot.connect()
            # Connection succeeded despite UNIMPLEMENTED at the HealthCheck RPC.
            assert slot.mtib is not None
            slot.disconnect()
        finally:
            server.stop(grace=0).wait()

    @pytest.mark.xfail(
        reason=(
            "SlotContext.connect uses a substring match on the error "
            "string (``'UNIMPLEMENTED' in err``) rather than the gRPC "
            "status code. When a server doesn't implement HealthCheck "
            "at all, gRPC auto-generates details='Method not "
            "implemented!' which does NOT contain the token. "
            "MtibV1Client.connect uses ``e.code() == UNIMPLEMENTED`` and "
            "handles this correctly; the slot's second HealthCheck "
            "call doesn't have access to the status code and so the "
            "lenient path is missed in this realistic case."
        ),
        strict=True,
    )
    def test_bare_unimplemented_servicer_currently_fails(self):
        """Documents the substring-match bug in SlotContext.connect.

        When the bug is fixed (e.g., by checking the gRPC status code
        directly instead of substring-matching ``err`` or by having
        ``MtibV1Client.HealthCheck`` recognize UNIMPLEMENTED leniently),
        this test will start passing — at which point flip the xfail
        to a regular test.
        """
        port = _free_port()
        server = _start_server(_BareServicer(), port)
        try:
            slot = SlotContext(
                slot_id="slot-0", slot_index=0,
                mtib_address="127.0.0.1", mtib_port=port,
            )
            # The contract: an older MTIB without HealthCheck should
            # still connect successfully. Today it raises.
            slot.connect()
            assert slot.mtib is not None
            slot.disconnect()
        finally:
            server.stop(grace=0).wait()

    def test_not_ready_server_eventually_raises(self):
        """ready=False on every attempt → ConnectionError with the
        error list surfaced.
        """
        port = _free_port()
        server = _start_server(_NotReadyServicer(), port)
        try:
            slot = SlotContext(
                slot_id="slot-9", slot_index=9,
                mtib_address="127.0.0.1", mtib_port=port,
            )
            with pytest.raises(ConnectionError) as exc_info:
                slot.connect()
            msg = str(exc_info.value)
            assert "slot-9" in msg
            assert "uart wedged" in msg
            assert f"failed after {slot_mod.CONNECT_MAX_ATTEMPTS} attempts" in msg
        finally:
            server.stop(grace=0).wait()

    def test_no_server_listening_retries_and_raises(self):
        """No server bound to the port → MtibV1Client returns the gRPC
        error string on every attempt, the retry loop exhausts and
        raises with attempt-count formatted error.
        """
        port = _free_port()  # nothing bound to it

        slot = SlotContext(
            slot_id="slot-0", slot_index=0,
            mtib_address="127.0.0.1", mtib_port=port,
        )
        with pytest.raises(ConnectionError) as exc_info:
            slot.connect()

        msg = str(exc_info.value)
        assert f"127.0.0.1:{port}" in msg
        assert f"failed after {slot_mod.CONNECT_MAX_ATTEMPTS} attempts" in msg

    def test_server_comes_up_after_initial_attempts(self, monkeypatch):
        """Server is down for the first 2 attempts, comes up before the
        3rd. The retry loop must catch the recovery rather than failing
        through to exhaustion.
        """
        port = _free_port()
        server_holder: dict = {"server": None}
        attempt_counter = {"n": 0}

        # Each invocation of MtibV1Client.connect counts as one attempt.
        # We hook ``time.sleep`` (the retry interval) to bring the server
        # up just before the 3rd attempt.
        def _maybe_start_server(_delay):
            attempt_counter["n"] += 1
            if attempt_counter["n"] == 2 and server_holder["server"] is None:
                server_holder["server"] = _start_server(_HealthyServicer(), port)
                # Small wait for the bind to settle.
                time.sleep(0.1)

        monkeypatch.setattr(slot_mod.time, "sleep", _maybe_start_server)

        try:
            slot = SlotContext(
                slot_id="slot-0", slot_index=0,
                mtib_address="127.0.0.1", mtib_port=port,
            )
            slot.connect()
            assert slot.mtib is not None
            slot.disconnect()
        finally:
            if server_holder["server"]:
                server_holder["server"].stop(grace=0).wait()

    def test_disconnect_closes_channel_cleanly(self):
        port = _free_port()
        server = _start_server(_HealthyServicer(), port)
        try:
            slot = SlotContext(
                slot_id="slot-0", slot_index=0,
                mtib_address="127.0.0.1", mtib_port=port,
            )
            slot.connect()
            client = slot.mtib
            # The client's channel should be open at this point.
            assert client.channel is not None
            slot.disconnect()
            # A subsequent HealthCheck call should error because the
            # channel is closed. This is the live-system way to verify
            # the disconnect actually closed something rather than
            # only mutating Python state.
            ready, errors, err = client.HealthCheck()
            assert err is not None
        finally:
            server.stop(grace=0).wait()
