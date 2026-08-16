"""Unit tests for ADC handler.

Tests AdcRead, AdcReadAll, AdcStream, and snapshot.
ADS1015 driver is mocked — no hardware required.

Run with:
    cd apps/edge/mtib-server
    PYTHONPATH=src:../../../libs/python:../../../libs/protocols:../../../libs \
        pytest tests/test_adc_handler.py -v
"""

import unittest
from unittest.mock import MagicMock, patch

from src.shared.types import AdcReadRequest, AdcStreamRequest, Empty
from src.handlers.adc import AdcHandler


def _make_handler(read_raw_side_effect=None, calculate_voltage_fn=None):
    """Construct an AdcHandler with ADS1015 mocked.

    read_raw_side_effect: side_effect for ads1015.read_raw (list or callable).
                          Default: returns (None, 1000) for any channel.
    calculate_voltage_fn: side_effect for ads1015.calculate_real_voltage.
                          Default: returns raw_value * 0.001 (trivial mapping).
    """
    logger = MagicMock()
    logger.from_parent.return_value = logger

    with patch("src.handlers.adc.ADS1015") as mock_ads_cls:
        mock_ads = MagicMock()
        mock_ads_cls.return_value = mock_ads

        if read_raw_side_effect is not None:
            mock_ads.read_raw.side_effect = read_raw_side_effect
        else:
            mock_ads.read_raw.return_value = (None, 1000)

        if calculate_voltage_fn is not None:
            mock_ads.calculate_real_voltage.side_effect = calculate_voltage_fn
        else:
            # Default: raw * 0.001 → e.g. 1000 raw → 1.0 V
            mock_ads.calculate_real_voltage.side_effect = lambda raw, ch: raw * 0.001

        handler = AdcHandler(logger=logger)
        handler._mock_ads = mock_ads

    return handler


class TestAdcRead(unittest.TestCase):
    """Test AdcRead RPC (single channel)."""

    def _make_ctx(self):
        return MagicMock()

    def test_read_channel_0_success(self):
        handler = _make_handler()
        req = AdcReadRequest(channel=0)
        resp = handler.read(req, self._make_ctx())

        assert resp.success is True
        assert resp.message == ""
        assert abs(resp.voltage_v - 1.0) < 0.001  # 1000 raw * 0.001

    def test_read_channel_7_success(self):
        handler = _make_handler()
        req = AdcReadRequest(channel=7)
        resp = handler.read(req, self._make_ctx())

        assert resp.success is True

    def test_read_all_valid_channels(self):
        """All channels 0-7 should succeed."""
        handler = _make_handler()
        ctx = self._make_ctx()
        for ch in range(8):
            req = AdcReadRequest(channel=ch)
            resp = handler.read(req, ctx)
            assert resp.success is True, f"Channel {ch} failed: {resp.message}"

    def test_read_invalid_channel_below_range(self):
        handler = _make_handler()
        req = AdcReadRequest(channel=-1)
        resp = handler.read(req, self._make_ctx())

        assert resp.success is False
        assert "Invalid channel" in resp.message

    def test_read_invalid_channel_above_range(self):
        handler = _make_handler()
        req = AdcReadRequest(channel=8)
        resp = handler.read(req, self._make_ctx())

        assert resp.success is False
        assert "Invalid channel" in resp.message

    def test_read_driver_error_propagated(self):
        """ADS1015 read errors are returned as failure response."""
        reads = [("i2c bus error", 0)]
        handler = _make_handler(read_raw_side_effect=reads)

        req = AdcReadRequest(channel=0)
        resp = handler.read(req, self._make_ctx())

        assert resp.success is False
        assert "i2c bus error" in resp.message
        assert resp.voltage_v == 0.0

    def test_read_voltage_computed_from_raw(self):
        """Verify that calculate_real_voltage is called with the raw value."""
        reads = [(None, 2048)]
        handler = _make_handler(read_raw_side_effect=reads)

        req = AdcReadRequest(channel=3)
        resp = handler.read(req, self._make_ctx())

        assert resp.success is True
        handler._mock_ads.calculate_real_voltage.assert_called_once_with(2048, 3)

    def test_read_delegates_to_ads1015_physical_channel(self):
        """Channel number passed to read_raw matches the request channel directly."""
        reads = [(None, 500)]
        handler = _make_handler(read_raw_side_effect=reads)

        req = AdcReadRequest(channel=5)
        handler.read(req, self._make_ctx())

        handler._mock_ads.read_raw.assert_called_once_with(5)


class TestAdcReadAll(unittest.TestCase):
    """Test AdcReadAll RPC (all 8 channels)."""

    def _make_ctx(self):
        return MagicMock()

    def test_read_all_returns_8_voltages(self):
        handler = _make_handler()
        req = Empty()
        resp = handler.read_all(req, self._make_ctx())

        assert resp.success is True
        assert len(resp.voltages_v) == 8

    def test_read_all_calls_all_channels(self):
        handler = _make_handler()
        req = Empty()
        handler.read_all(req, self._make_ctx())

        assert handler._mock_ads.read_raw.call_count == 8
        called_channels = [call.args[0] for call in handler._mock_ads.read_raw.call_args_list]
        assert sorted(called_channels) == list(range(8))

    def test_read_all_voltages_are_computed_correctly(self):
        """Verify each voltage is the result of calculate_real_voltage."""
        # Return distinct raw values per channel
        side_effect = [(None, ch * 100) for ch in range(8)]
        handler = _make_handler(read_raw_side_effect=side_effect)

        req = Empty()
        resp = handler.read_all(req, self._make_ctx())

        assert resp.success is True
        for ch, voltage in enumerate(resp.voltages_v):
            expected = ch * 100 * 0.001  # raw * scale
            assert abs(voltage - expected) < 0.0001, f"Channel {ch}: expected {expected}, got {voltage}"

    def test_read_all_channel_error_returns_failure(self):
        """If any channel fails, read_all returns failure immediately."""
        # Channel 3 fails
        reads = [
            (None, 100),   # ch 0
            (None, 200),   # ch 1
            (None, 300),   # ch 2
            ("adc fault", 0),  # ch 3 fails
        ]
        handler = _make_handler(read_raw_side_effect=reads)

        req = Empty()
        resp = handler.read_all(req, self._make_ctx())

        assert resp.success is False
        assert "channel 3" in resp.message.lower() or "3" in resp.message
        assert resp.voltages_v == []

    def test_read_all_first_channel_error_returns_failure(self):
        """Failure on channel 0 returns immediately."""
        reads = [("channel 0 dead", 0)]
        handler = _make_handler(read_raw_side_effect=reads)

        req = Empty()
        resp = handler.read_all(req, self._make_ctx())

        assert resp.success is False
        assert resp.voltages_v == []


class TestAdcSnapshot(unittest.TestCase):
    """Test get_snapshot_data helper."""

    def test_snapshot_returns_8_entries_on_success(self):
        handler = _make_handler()
        data = handler.get_snapshot_data()

        assert len(data) == 8
        channels = [d.channel for d in data]
        assert sorted(channels) == list(range(8))

    def test_snapshot_skips_failed_channels(self):
        """Channels with read errors are omitted from snapshot."""
        # Channels 0 and 4 fail
        def read_side_effect(channel):
            if channel in (0, 4):
                return ("error", 0)
            return (None, 1000)

        handler = _make_handler(read_raw_side_effect=read_side_effect)
        data = handler.get_snapshot_data()

        present_channels = {d.channel for d in data}
        assert 0 not in present_channels
        assert 4 not in present_channels
        assert len(data) == 6

    def test_snapshot_voltage_values_computed(self):
        """Snapshot voltages use calculate_real_voltage."""
        handler = _make_handler()
        data = handler.get_snapshot_data()

        # With default mock: raw=1000, voltage = 1000 * 0.001 = 1.0 V
        for entry in data:
            assert abs(entry.voltage_v - 1.0) < 0.001


class TestAdcStream(unittest.TestCase):
    """Test AdcStream RPC (server-streaming)."""

    def _make_ctx(self, active_count=3):
        """Context that becomes inactive after active_count calls to is_active."""
        ctx = MagicMock()
        call_count = [0]

        def is_active():
            call_count[0] += 1
            return call_count[0] <= active_count

        ctx.is_active.side_effect = is_active
        return ctx

    def test_stream_yields_samples(self):
        handler = _make_handler()
        ctx = self._make_ctx(active_count=2)

        req = AdcStreamRequest(channels=[0, 1], interval_ms=1)
        results = list(handler.stream(req, ctx))

        assert len(results) > 0
        assert len(results[0].samples) > 0

    def test_stream_default_channels_reads_all(self):
        """No channels specified → all 8 channels are streamed."""
        handler = _make_handler()
        ctx = self._make_ctx(active_count=1)

        req = AdcStreamRequest(channels=[], interval_ms=1)
        results = list(handler.stream(req, ctx))

        if results:
            sample_channels = {s.channel for r in results for s in r.samples}
            assert sample_channels == set(range(8))

    def test_stream_skips_invalid_channels(self):
        """Out-of-range channels in the request are silently skipped."""
        handler = _make_handler()
        ctx = self._make_ctx(active_count=1)

        req = AdcStreamRequest(channels=[0, 99, 3], interval_ms=1)
        results = list(handler.stream(req, ctx))

        if results:
            sample_channels = {s.channel for r in results for s in r.samples}
            assert 99 not in sample_channels
            assert sample_channels.issubset({0, 3})

    def test_stream_skips_failed_channel_reads(self):
        """ADS1015 errors during stream are silently skipped."""
        reads = [("read error", 0), (None, 1000), ("read error", 0), (None, 1000)]
        handler = _make_handler(read_raw_side_effect=reads)
        ctx = self._make_ctx(active_count=1)

        req = AdcStreamRequest(channels=[0, 1], interval_ms=1)
        # Should not raise; bad channels are omitted
        results = list(handler.stream(req, ctx))
        assert isinstance(results, list)

    def test_stream_stops_when_context_inactive(self):
        """Stream generator exits when context.is_active() returns False."""
        handler = _make_handler()
        ctx = MagicMock()
        ctx.is_active.return_value = False  # immediately inactive

        req = AdcStreamRequest(channels=[0], interval_ms=1)
        results = list(handler.stream(req, ctx))

        assert results == []


if __name__ == "__main__":
    unittest.main()
