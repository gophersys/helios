"""Background accelerometer data collection for validation telemetry.

Reads accelerometer data from the MTIB at a configurable rate (~10Hz default)
and pushes each sample to the TelemetryStreamer on the "accel" channel.

Analogous to the power polling loop in TestContext, but encapsulated as a
standalone class for reuse and cleaner lifecycle management.

Usage:
    profiler = AccelerationProfiler(mtib=client, streamer=telemetry)
    if profiler.probe():
        profiler.start()
        # ... tests run, accel data flows to telemetry ...
        profiler.stop()
"""

import threading
from typing import Optional

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.utils import Logger

from .telemetry import TelemetryStreamer

log = Logger(log_name="accel_profiler")


class AccelerationProfiler:
    """Background accelerometer sampler that feeds the telemetry streamer.

    Runs a daemon thread that calls ``client.AccelRead()`` at a configurable
    rate and pushes each (x, y, z) sample to the telemetry streamer's
    ``"accel"`` channel.

    Args:
        mtib: Connected MtibV1Client instance.
        streamer: TelemetryStreamer to push samples to.
        interval_s: Seconds between reads (default 0.05 = 20 Hz).
    """

    def __init__(
        self,
        mtib: MtibV1Client,
        streamer: TelemetryStreamer,
        interval_s: float = 0.05,
    ):
        self._mtib = mtib
        self._streamer = streamer
        self._interval = interval_s

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        # Diagnostics
        self._sample_count = 0
        self._error_count = 0

    # ── Capability probe ──────────────────────────────────────

    def probe(self) -> bool:
        """Check whether the MTIB has a working accelerometer.

        Performs a single AccelRead and returns True if it succeeds.
        Call this before start() to avoid spinning a thread on hardware
        that has no accelerometer.

        Returns:
            True if AccelRead returned valid data, False otherwise.
        """
        try:
            x, y, z, err = self._mtib.AccelRead()
            if err:
                log.info("Accelerometer not available: %s", err)
                return False
            log.info("Accelerometer probe OK (x=%.3fg, y=%.3fg, z=%.3fg)", x, y, z)
            return True
        except Exception as e:
            log.info("Accelerometer probe failed: %s", e)
            return False

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Start the background sampling thread."""
        if self._running:
            log.warning("AccelerationProfiler already running")
            return

        self._stop_event.clear()
        self._sample_count = 0
        self._error_count = 0
        self._running = True

        self._thread = threading.Thread(
            target=self._sample_loop,
            daemon=True,
            name="accel-profiler",
        )
        self._thread.start()
        log.info("Acceleration profiler started (interval=%.0fms)", self._interval * 1000)

    def stop(self) -> None:
        """Stop the background sampling thread and log diagnostics."""
        if not self._running:
            return

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

        self._running = False
        self._thread = None

        log.info(
            "Acceleration profiler stopped (%d samples, %d errors)",
            self._sample_count,
            self._error_count,
        )

    @property
    def sample_count(self) -> int:
        """Total number of successful samples collected."""
        return self._sample_count

    @property
    def error_count(self) -> int:
        """Total number of read errors encountered."""
        return self._error_count

    @property
    def running(self) -> bool:
        """Whether the profiler is currently sampling."""
        return self._running

    # ── Internal ──────────────────────────────────────────────

    # IIO accelerometer drivers return m/s², not g. The LIS2DE12 driver
    # docstring says "g" but raw * scale actually gives m/s² (at rest Z ≈ 9.81).
    # The correct long-term fix is in the MTIB driver (lis2de12.py), but that
    # requires an edge redeploy. Convert here for now.
    _MS2_TO_G = 9.80665

    def _sample_loop(self) -> None:
        """Background thread: read accelerometer and push to telemetry."""
        while not self._stop_event.wait(self._interval):
            try:
                x, y, z, err = self._mtib.AccelRead()
                if err:
                    self._error_count += 1
                    # Log sparingly — every 100th error to avoid flooding
                    if self._error_count % 100 == 1:
                        log.warning("AccelRead error (#%d): %s", self._error_count, err)
                    continue

                # Convert m/s² → g (see class comment above)
                self._streamer.push("accel", {
                    "x": round(x / self._MS2_TO_G, 4),
                    "y": round(y / self._MS2_TO_G, 4),
                    "z": round(z / self._MS2_TO_G, 4),
                })
                self._sample_count += 1

            except Exception as e:
                self._error_count += 1
                if self._error_count % 100 == 1:
                    log.warning("AccelRead exception (#%d): %s", self._error_count, e)
