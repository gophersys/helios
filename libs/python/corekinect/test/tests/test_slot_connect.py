"""Tests for :class:`corekinect.test.slot.SlotContext` connection behaviour.

These tests focus on the resilience contract of ``SlotContext.connect()`` —
specifically that the slot remains functional when the MTIB server is on
an older build that doesn't expose the ``HealthCheck`` RPC. The contract
mirrors the lenient behaviour of :meth:`MtibV1Client.connect`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import grpc
import pytest

import corekinect.test.slot as slot_mod
from corekinect.test.slot import SlotContext


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
        # First, the SDK-level connect() returns success.
        mock_mtib.connect.return_value = None
        # The slot then performs its own HealthCheck() call. An older
        # MTIB build does not implement it — return the SDK convention
        # for "UNIMPLEMENTED": ready=None, error string mentions
        # UNIMPLEMENTED.
        mock_mtib.HealthCheck.return_value = (
            None,
            None,
            "gRPC error for HealthCheck at 10.0.0.1. Error: UNIMPLEMENTED",
        )
        mock_client_cls.return_value = mock_mtib

        slot = SlotContext(
            slot_id="slot-0",
            slot_index=0,
            mtib_address="10.0.0.1",
            mtib_port=50053,
        )

        # Should not raise.
        slot.connect()
        # The slot now has an MTIB attached.
        assert slot.mtib is mock_mtib
