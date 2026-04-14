"""Per-slot rich test context for multi-slot fixtures.

Wraps a SlotContext (mtib + fixture + shared_data) with per-slot UART
capture, power profiling, telemetry, and artifact collection. This gives
multi-slot tests the same infrastructure that TestContext gives
single-slot tests.

    slot_ctx = SlotTestContext.from_slot(slot, telemetry=streamer)
    slot_ctx.connect()
    # ... run tests against slot_ctx.mtib, slot_ctx.uart, slot_ctx.power ...
    slot_ctx.disconnect()

Delegates SlotContext attributes (mtib, shared_data, serial_number, etc.)
so existing tests that access slot.mtib or slot.shared_data keep working.
"""

import os
import threading
import time
from typing import Any, Callable, Optional

from corekinect.utils import Logger

from .artifact_writer import ArtifactWriter
from .power_profiler import PowerProfiler
from .slot import SlotContext
from .telemetry import TelemetryStreamer
from .uart_demuxer import UartDemuxer

log = Logger(log_name="slot_context")


class SlotTestContext:
    """Per-slot test infrastructure wrapping a connected SlotContext.

    Attributes:
        slot: The underlying SlotContext (mtib, fixture, shared_data).
        uart: Per-slot UART demuxer (app + comms targets).
        power: Per-slot power profiler.
        telemetry: Shared telemetry streamer (pushes tagged by slot_id).
        artifact_writer: Per-slot artifact writer (uploads to slot prefix).
    """

    def __init__(
        self,
        slot: SlotContext,
        uart: Optional[UartDemuxer] = None,
        power: Optional[PowerProfiler] = None,
        telemetry: Optional[TelemetryStreamer] = None,
        artifact_writer: Optional[ArtifactWriter] = None,
    ):
        self.slot = slot
        self.uart = uart
        self.power = power
        self.telemetry = telemetry
        self.artifact_writer = artifact_writer or ArtifactWriter()

        self._power_poll_stop: Optional[threading.Event] = None
        self._power_poll_thread: Optional[threading.Thread] = None

    # ── Delegate SlotContext attributes ───────────────────────────────

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying SlotContext.

        This lets tests use slot_ctx.mtib, slot_ctx.shared_data,
        slot_ctx.serial_number, etc. without knowing about the wrapper.
        """
        return getattr(self.slot, name)

    # ── Factory ──────────────────────────────────────────────────────

    @classmethod
    def from_slot(
        cls,
        slot: SlotContext,
        telemetry: Optional[TelemetryStreamer] = None,
    ) -> "SlotTestContext":
        """Build a SlotTestContext from a connected SlotContext.

        The slot must already have a connected MTIB client (slot.mtib).
        UART and power are created from the slot's MTIB.
        """
        uart = UartDemuxer(mtib=slot.mtib) if slot.mtib else None
        power = PowerProfiler(mtib=slot.mtib) if slot.mtib else None

        return cls(
            slot=slot,
            uart=uart,
            power=power,
            telemetry=telemetry,
        )

    # ── Lifecycle ────────────────────────────────────────────────────

    def connect(self) -> None:
        """Start per-slot UART capture, power polling, and telemetry wiring."""
        if self.uart:
            self.uart.start()
            log.info("Slot %s: UART capture started", self.slot.slot_id)

        # Wire UART to telemetry for live streaming
        if self.uart and self.telemetry:
            self.uart.on_line = self.telemetry.push_uart

        # Start background power polling
        if self.power:
            self._power_poll_stop = threading.Event()
            self._power_poll_thread = threading.Thread(
                target=self._power_poll_loop,
                daemon=True,
                name=f"power-{self.slot.slot_id}",
            )
            self._power_poll_thread.start()

    def disconnect(self) -> None:
        """Stop per-slot services."""
        if self._power_poll_stop:
            self._power_poll_stop.set()
            if self._power_poll_thread and self._power_poll_thread.is_alive():
                self._power_poll_thread.join(timeout=3)

        if self.uart:
            self.uart.stop()

        log.info("Slot %s: disconnected test services", self.slot.slot_id)

    # ── Per-test lifecycle ───────────────────────────────────────────

    def setup_test(self, test_name: Optional[str] = None, module: Optional[str] = None) -> None:
        """Clear UART buffer and mark test start in telemetry."""
        if self.uart:
            self.uart.clear()
        if self.telemetry and test_name:
            self.telemetry.set_test(test_name, module=module)

    def teardown_test(self, test_name: str, artifacts_dir: Optional[str] = None) -> None:
        """Dump per-slot UART log to local artifacts dir and upload to MinIO.

        Local path: {artifacts_dir}/{slot_id}/{test_name}_uart.log
        MinIO path: sessions/{run_id}/logs/{serial_number}/{test_name}_uart.log
        """
        if not self.uart:
            return

        # Dump to local filesystem
        if artifacts_dir:
            slot_dir = os.path.join(artifacts_dir, self.slot.slot_id)
            os.makedirs(slot_dir, exist_ok=True)
            log_path = os.path.join(slot_dir, f"{test_name}_uart.log")
            self.uart.dump_to_file(log_path)

            # Upload to MinIO via ArtifactWriter if available
            if self.artifact_writer and os.path.isfile(log_path):
                serial = self.slot.serial_number or self.slot.slot_id
                object_path = f"{serial}/{test_name}_uart.log"
                try:
                    with open(log_path, "rb") as f:
                        self.artifact_writer.write_bytes(object_path, f.read())
                except Exception as e:
                    log.warning("Slot %s: failed to upload UART log: %s", self.slot.slot_id, e)

    # ── Power polling ────────────────────────────────────────────────

    def _power_poll_loop(self) -> None:
        """Poll power at ~2 Hz and push to telemetry (tagged by slot_id)."""
        from corekinect.mtib_client.v1.client.types import PowerChannel

        while not self._power_poll_stop.wait(0.5):
            try:
                ts = time.time()
                ch0, err0 = self.slot.mtib.PowerRead(channel=PowerChannel.DUT)
                if not err0 and ch0:
                    if self.telemetry:
                        self.telemetry.push_power(ts, ch0.current_ma, ch0.voltage_v * 1000)

                ch1, err1 = self.slot.mtib.PowerRead(channel=PowerChannel.CHARGER)
                if not err1 and ch1 and self.telemetry:
                    self.telemetry.push(
                        "power_chg",
                        {"mA": round(ch1.current_ma, 2), "mV": round(ch1.voltage_v * 1000, 1)},
                    )
            except Exception as exc:
                log.debug("Slot %s power poll error: %s", self.slot.slot_id, exc)
