"""Power measurement via MTIB for power budget tests.

    profiler = PowerProfiler(mtib)
    measurement = profiler.measure(channel=0, duration_s=10)
    print(f"Avg: {measurement.avg_current_ma:.1f} mA")
"""

import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.types import PowerChannel
from corekinect.utils import Logger

log = Logger(log_name="power_profiler")


@dataclass
class PowerMeasurement:
    """Aggregated power stats from a measurement window."""
    avg_current_ma: float
    peak_current_ma: float
    min_current_ma: float
    avg_voltage_mv: float
    energy_mwh: float
    duration_s: float
    samples: int
    avg_current_na: float = 0.0   # Nanoamp resolution (Joulescope only)
    min_current_na: float = 0.0
    max_current_na: float = 0.0


@dataclass
class PowerTrace:
    """Power trace with individual samples and computed stats."""
    samples: List[Tuple[float, float, float]] = field(default_factory=list)
    """(timestamp_s, voltage_mv, current_ma) tuples."""

    measurement: Optional[PowerMeasurement] = None
    """Stats computed by compute_stats()."""

    def compute_stats(self) -> PowerMeasurement:
        """Compute aggregate stats from the sample buffer."""
        if not self.samples:
            self.measurement = PowerMeasurement(
                avg_current_ma=0, peak_current_ma=0, min_current_ma=0,
                avg_voltage_mv=0, energy_mwh=0, duration_s=0, samples=0,
            )
            return self.measurement

        currents = [s[2] for s in self.samples]
        voltages = [s[1] for s in self.samples]
        timestamps = [s[0] for s in self.samples]
        duration = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0

        avg_v = sum(voltages) / len(voltages)
        avg_i = sum(currents) / len(currents)
        avg_power_mw = avg_v * avg_i / 1000  # mV * mA / 1000 = mW
        energy_mwh = avg_power_mw * (duration / 3600) if duration > 0 else 0

        self.measurement = PowerMeasurement(
            avg_current_ma=avg_i,
            peak_current_ma=max(currents),
            min_current_ma=min(currents),
            avg_voltage_mv=avg_v,
            energy_mwh=energy_mwh,
            duration_s=duration,
            samples=len(self.samples),
        )
        return self.measurement


class PowerProfiler:
    """Power measurement via MTIB.

    Two modes: measure() for bounded readings, or start_continuous() /
    stop_continuous() for long-duration streaming (sleep mode tests).
    """

    def __init__(self, mtib: MtibV1Client):
        self._mtib = mtib
        self._trace: Optional[PowerTrace] = None
        self._streaming = False
        self._stream_thread: Optional[threading.Thread] = None

    def measure(self, channel: int = 0, duration_s: float = 10) -> PowerMeasurement:
        """Take a bounded power measurement (~100Hz sampling).

        Args:
            channel: 0=DUT, 1=charger.
        """
        result, err = self._mtib.PowerMeasure(channel=channel, duration_s=duration_s)
        if err:
            raise RuntimeError(f"PowerMeasure failed: {err}")

        return PowerMeasurement(
            avg_current_ma=result.average_ma,
            peak_current_ma=result.max_ma,
            min_current_ma=result.min_ma,
            avg_voltage_mv=result.average_mv,
            energy_mwh=0,  # not provided by server
            duration_s=result.duration_s,
            samples=result.sample_count,
            avg_current_na=result.average_na,
            min_current_na=result.min_na,
            max_current_na=result.max_na,
        )

    def start_continuous(self, channel: int = 0) -> None:
        """Start continuous power sampling in a background thread.

        Call stop_continuous() to get the trace with computed stats.
        """
        if self._streaming:
            raise RuntimeError("Continuous measurement already in progress")

        self._trace = PowerTrace()
        self._streaming = True
        self._stream_thread = threading.Thread(
            target=self._stream_loop,
            args=(channel,),
            daemon=True,
            name="power-stream",
        )
        self._stream_thread.start()
        log.info("Continuous power sampling started on channel %d", channel)

    def stop_continuous(self) -> PowerTrace:
        """Stop continuous sampling and return full trace with computed stats."""
        if not self._streaming:
            raise RuntimeError("No continuous measurement in progress")

        self._streaming = False
        if self._stream_thread:
            self._stream_thread.join(timeout=5)
            self._stream_thread = None

        trace = self._trace
        self._trace = None

        if trace:
            trace.compute_stats()
            log.info(
                "Power trace: %d samples over %.1fs, avg=%.1fmA",
                len(trace.samples),
                trace.measurement.duration_s if trace.measurement else 0,
                trace.measurement.avg_current_ma if trace.measurement else 0,
            )

        return trace

    def _stream_loop(self, channel: int) -> None:
        """Background thread consuming PowerStream responses."""
        try:
            start_time = time.monotonic()
            for resp in self._mtib.PowerStream(channel=channel):
                if not self._streaming:
                    break
                if hasattr(resp, "samples"):
                    for sample in resp.samples:
                        ts = time.monotonic() - start_time
                        self._trace.samples.append((
                            ts,
                            sample.voltage_mv,
                            sample.current_ma,
                        ))
        except Exception as e:
            if self._streaming:
                log.error("Power stream error: %s", e)

    def measure_joulescope(self, duration_s: float = 10) -> PowerMeasurement:
        """Take a Joulescope power measurement with nanoamp resolution.

        Args:
            duration_s: Measurement window in seconds.

        Raises:
            RuntimeError: If Joulescope is not connected or measurement fails.
        """
        return self.measure(channel=PowerChannel.JOULESCOPE, duration_s=duration_s)

    def quick_read(self, channel: int = 0) -> Tuple[float, float, float]:
        """Return (voltage_mv, current_ma, power_mw) from a single read."""
        result, err = self._mtib.PowerRead(channel=channel)
        if err:
            raise RuntimeError(f"PowerRead failed: {err}")
        return (result.voltage_v * 1000, result.current_ma, result.power_mw)
