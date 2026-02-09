from typing import Iterator, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    PowerConfig,
    PowerDisableRequest,
    PowerEnableRequest,
    PowerMeasureRequest,
    PowerStatusRequest,
    PowerStreamRequest,
)

from ._base import BaseClient
from ..types.power import PowerMeasurement, PowerSample, PowerStatus


class PowerMixin(BaseClient):
    """Power measurement and control operations."""

    def power_enable(
        self,
        channel: int = 0,
        voltage_v: float = 3.3,
        current_limit_ma: float = 500.0,
        sample_rate_hz: int = 1000,
    ) -> Optional[str]:
        """Enable power on a channel.

        Args:
            channel: Power channel enum value (0=MAIN, 1=VBAT, 2=3V3, 3=1V8).
            voltage_v: Source voltage in volts (0 for measure-only mode).
            current_limit_ma: Current limit in milliamps.
            sample_rate_hz: Sampling rate for monitoring.

        Returns:
            Error message string, or None on success.
        """
        try:
            config = PowerConfig(
                channel=channel,
                voltage_v=voltage_v,
                current_limit_ma=current_limit_ma,
                sample_rate_hz=sample_rate_hz,
            )
            resp = self._call("PowerEnable", PowerEnableRequest(config=config))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"power_enable error: {e}"

    def power_disable(self, channel: int = 0) -> Optional[str]:
        """Disable power on a channel.

        Args:
            channel: Power channel enum value.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call("PowerDisable", PowerDisableRequest(channel=channel))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"power_disable error: {e}"

    def power_status(self, channel: int = 0) -> Tuple[Optional[str], Optional[PowerStatus]]:
        """Get current power status for a channel.

        Args:
            channel: Power channel enum value.

        Returns:
            (error, PowerStatus) tuple. error is None on success.
        """
        try:
            resp = self._call("PowerStatus", PowerStatusRequest(channel=channel))
            if not resp.success:
                return resp.message, None
            return None, PowerStatus(
                enabled=resp.enabled,
                voltage_v=resp.voltage_v,
                current_ma=resp.current_ma,
                power_mw=resp.power_mw,
            )
        except Exception as e:
            return f"power_status error: {e}", None

    def power_stream(
        self, channel: int = 0, sample_rate_hz: int = 1000, timeout: float = None
    ) -> Iterator:
        """Stream power measurement samples.

        Args:
            channel: Power channel enum value.
            sample_rate_hz: Desired sample rate in Hz.
            timeout: Stream timeout in seconds.

        Returns:
            Iterator of PowerStreamResponse messages with batched samples.
        """
        return self._server_stream(
            "PowerStream",
            PowerStreamRequest(channel=channel, sample_rate_hz=sample_rate_hz),
            timeout=timeout,
        )

    def power_measure(
        self, channel: int = 0, duration_s: float = 1.0, sample_rate_hz: int = 1000
    ) -> Tuple[Optional[str], Optional[PowerMeasurement]]:
        """Measure power over a duration and get statistics.

        Args:
            channel: Power channel enum value.
            duration_s: Measurement duration in seconds.
            sample_rate_hz: Sample rate in Hz.

        Returns:
            (error, PowerMeasurement) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "PowerMeasure",
                PowerMeasureRequest(
                    channel=channel, duration_s=duration_s, sample_rate_hz=sample_rate_hz
                ),
            )
            if not resp.success:
                return resp.message, None
            samples = [
                PowerSample(
                    timestamp_s=s.timestamp.seconds if s.timestamp else 0,
                    timestamp_ns=s.timestamp.nanos if s.timestamp else 0,
                    current_ua=s.current_ua,
                    voltage_mv=s.voltage_mv,
                )
                for s in resp.samples
            ]
            return None, PowerMeasurement(
                duration_s=resp.duration_s,
                average_ua=resp.average_ua,
                min_ua=resp.min_ua,
                max_ua=resp.max_ua,
                energy_uj=resp.energy_uj,
                sample_count=resp.sample_count,
                samples=samples,
            )
        except Exception as e:
            return f"power_measure error: {e}", None
