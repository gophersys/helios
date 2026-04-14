"""Multi-slot fixture support for manufacturing and validation.

Provides SlotContext (per-DUT hardware context) and FixtureContext
(multi-slot manager) for test suites that run against fixtures with
one or more MTIBs.

Single-slot (typical validation):

    fixture_ctx = FixtureContext.from_env(fixture_factory=AlphaB0Fixture)
    # fixture_ctx.slots has 1 entry

Multi-slot (manufacturing panel, multi-DUT validation):

    fixture_ctx = FixtureContext.from_env(fixture_factory=AlphaB0MfgFixture)
    # fixture_ctx.slots has N entries (one per MTIB_HOSTS address)

Environment variables:

    Single-slot mode (validation default):
        MTIB_ADDRESS or MTIB_HOST    Single MTIB address (host or host:port)
        DEVICE_ID                    Device hex ID
        DEVICE_SNR                   J-Link probe serial number

    Multi-slot mode (manufacturing):
        MTIB_HOSTS                   Comma-separated MTIB addresses
        SLOT_SNRS                    Comma-separated J-Link serial numbers (optional)
        SLOT_DEVICE_IDS              Comma-separated device IDs (optional)

    Common:
        MTIB_PORT                    Default gRPC port (50053)
        FIXTURE_CONFIG_PATH          JSON config with full slot definitions (overrides env vars)
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.utils import Logger

log = Logger(log_name="test_slot")


@dataclass
class SlotContext:
    """Per-DUT context within a multi-slot fixture.

    Each slot maps to one MTIB and one physical DUT. The slot holds the
    MTIB client, product-specific fixture controller, and shared state
    that tests use to pass data between steps (e.g., IMEI from POST
    step 7 used in personalization step 9).
    """

    slot_id: str
    slot_index: int
    mtib_address: str
    mtib_port: int = 50053
    serial_number: str = ""
    device_id: str = ""
    shared_data: Dict[str, Any] = field(default_factory=dict)

    # Set during connect()
    mtib: Optional[MtibV1Client] = field(default=None, repr=False)
    fixture: Optional[Any] = field(default=None, repr=False)

    def connect(self, fixture_factory: Optional[Callable] = None) -> None:
        """Connect MTIB client and create fixture controller."""
        config = MtibV1Client.Config(
            net=NetConfig(addr=self.mtib_address, port=self.mtib_port)
        )
        self.mtib = MtibV1Client(config)
        err = self.mtib.connect()
        if err:
            raise ConnectionError(
                f"Slot {self.slot_id}: MTIB connection to {self.mtib_address}:{self.mtib_port} failed: {err}"
            )

        ready, errors, err = self.mtib.HealthCheck()
        if err:
            raise ConnectionError(f"Slot {self.slot_id}: MTIB health check failed: {err}")
        if not ready:
            raise ConnectionError(f"Slot {self.slot_id}: MTIB not ready: {errors}")

        if fixture_factory:
            self.fixture = fixture_factory(self.mtib)

        log.info(
            "Slot %s connected: %s:%d (snr=%s)",
            self.slot_id, self.mtib_address, self.mtib_port, self.serial_number or "n/a",
        )

    def disconnect(self) -> None:
        """Disconnect MTIB client."""
        if self.mtib:
            err = self.mtib.disconnect()
            if err:
                log.warning("Slot %s disconnect error: %s", self.slot_id, err)
            log.info("Slot %s disconnected", self.slot_id)


@dataclass
class FixtureContext:
    """Multi-slot fixture manager.

    Wraps N SlotContexts for fixtures with one or more MTIBs.
    Provides connect_all/disconnect_all lifecycle management.
    """

    slots: Dict[str, SlotContext] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    @property
    def slot_count(self) -> int:
        return len(self.slots)

    @property
    def slot_ids(self) -> List[str]:
        return sorted(self.slots.keys())

    def __getitem__(self, key: str) -> SlotContext:
        return self.slots[key]

    def __len__(self) -> int:
        return len(self.slots)

    def __iter__(self):
        return iter(self.slots.values())

    @classmethod
    def from_env(
        cls,
        fixture_factory: Optional[Callable] = None,
    ) -> "FixtureContext":
        """Build from environment variables or config file.

        Resolution order:
            1. FIXTURE_CONFIG_PATH — JSON with full slot definitions
            2. MTIB_HOSTS — comma-separated addresses (multi-slot)
            3. MTIB_ADDRESS / MTIB_HOST — single address (single-slot)
        """
        config_path = os.environ.get("FIXTURE_CONFIG_PATH")
        if config_path:
            return cls._from_config_file(config_path)

        mtib_hosts = os.environ.get("MTIB_HOSTS", "").strip()
        if mtib_hosts:
            return cls._from_hosts_env(mtib_hosts)

        return cls._from_single_env()

    @classmethod
    def _from_config_file(cls, config_path: str) -> "FixtureContext":
        """Build from fixture config JSON file.

        Expected format:
            {
                "slots": [
                    {"mtib_address": "10.4.45.33", "serial_number": "0964", "device_id": "..."},
                    ...
                ],
                "config": { ... }
            }
        """
        with open(config_path) as f:
            data = json.load(f)

        default_port = int(os.environ.get("MTIB_PORT", "50053"))
        slots = {}
        for i, slot_data in enumerate(data.get("slots", [])):
            slot_id = f"slot-{i}"
            slots[slot_id] = SlotContext(
                slot_id=slot_id,
                slot_index=i,
                mtib_address=slot_data["mtib_address"],
                mtib_port=slot_data.get("mtib_port", default_port),
                serial_number=slot_data.get("serial_number", ""),
                device_id=slot_data.get("device_id", ""),
            )

        config = data.get("config", {})
        log.info("Loaded %d slots from config file: %s", len(slots), config_path)
        return cls(slots=slots, config=config)

    @classmethod
    def _from_hosts_env(cls, mtib_hosts: str) -> "FixtureContext":
        """Build from MTIB_HOSTS comma-separated addresses.

        If SLOT_FILTER is set (comma-separated slot indices), only builds
        SlotContexts for those indices. This allows the manufacturing runner
        to target specific slots per run (panel vs standalone).
        """
        default_port = int(os.environ.get("MTIB_PORT", "50053"))
        addresses = [addr.strip() for addr in mtib_hosts.split(",") if addr.strip()]

        # SLOT_FILTER: only include specific slot indices (e.g., "0,1,2" or "4")
        slot_filter_str = os.environ.get("SLOT_FILTER", "").strip()
        if slot_filter_str:
            allowed_indices = {int(x.strip()) for x in slot_filter_str.split(",") if x.strip()}
            log.info("SLOT_FILTER active: only slots %s", sorted(allowed_indices))
        else:
            allowed_indices = None  # no filter = all slots

        # Validate SNR/device_id count against filtered slot count (not all hosts)
        filtered_count = len(allowed_indices) if allowed_indices else len(addresses)
        snrs = _split_env("SLOT_SNRS", filtered_count)
        device_ids = _split_env("SLOT_DEVICE_IDS", filtered_count)

        slots = {}
        filtered_idx = 0
        for i, addr in enumerate(addresses):
            if allowed_indices is not None and i not in allowed_indices:
                continue
            host, port = _parse_address(addr, default_port)
            slot_id = f"slot-{i}"
            slots[slot_id] = SlotContext(
                slot_id=slot_id,
                slot_index=i,
                mtib_address=host,
                mtib_port=port,
                serial_number=snrs[filtered_idx] if filtered_idx < len(snrs) else "",
                device_id=device_ids[filtered_idx] if filtered_idx < len(device_ids) else "",
            )
            filtered_idx += 1

        log.info("Loaded %d slots from MTIB_HOSTS: %s", len(slots),
                 [f"{s.mtib_address}:{s.mtib_port}" for s in slots.values()])
        return cls(slots=slots)

    @classmethod
    def _from_single_env(cls) -> "FixtureContext":
        """Build single-slot context from MTIB_ADDRESS/MTIB_HOST."""
        mtib_addr = os.environ.get("MTIB_ADDRESS") or os.environ.get("MTIB_HOST")
        if not mtib_addr:
            raise ValueError(
                "One of FIXTURE_CONFIG_PATH, MTIB_HOSTS, MTIB_ADDRESS, or MTIB_HOST must be set"
            )

        default_port = int(os.environ.get("MTIB_PORT", "50053"))
        host, port = _parse_address(mtib_addr, default_port)

        slot = SlotContext(
            slot_id="slot-0",
            slot_index=0,
            mtib_address=host,
            mtib_port=port,
            serial_number=os.environ.get("DEVICE_SNR", ""),
            device_id=os.environ.get("DEVICE_ID", ""),
        )

        log.info("Single-slot mode: %s:%d", host, port)
        return cls(slots={"slot-0": slot})

    def connect_all(self, fixture_factory: Optional[Callable] = None) -> None:
        """Connect all slots. Raises on first failure."""
        for slot in self.slots.values():
            slot.connect(fixture_factory=fixture_factory)
        log.info("All %d slots connected", len(self.slots))

    def connect_available(self, fixture_factory: Optional[Callable] = None) -> int:
        """Connect as many slots as possible, skipping failures.

        Used by the manufacturing runner at startup — connects all MTIBs
        that are reachable. Per-run SLOT_FILTER then validates only the
        needed slots before test execution.

        Returns the number of successfully connected slots.
        """
        connected = 0
        for slot in self.slots.values():
            try:
                slot.connect(fixture_factory=fixture_factory)
                connected += 1
            except Exception as e:
                log.warning("Slot %s connection failed (skipping): %s", slot.slot_id, e)
        log.info("Connected %d/%d slots", connected, len(self.slots))
        return connected

    def disconnect_all(self) -> None:
        """Disconnect all slots (best-effort, logs errors)."""
        for slot in self.slots.values():
            try:
                slot.disconnect()
            except Exception as e:
                log.warning("Error disconnecting slot %s: %s", slot.slot_id, e)
        log.info("All slots disconnected")

    def build_slot_test_contexts(self, telemetry=None) -> Dict[str, "SlotTestContext"]:
        """Wrap each connected SlotContext in a SlotTestContext with UART/power/artifacts.

        Returns a dict keyed by slot_id. Only wraps slots that have a connected MTIB.
        Call connect() on each returned SlotTestContext to start per-slot services.
        """
        from .slot_context import SlotTestContext

        result = {}
        for slot_id, slot in self.slots.items():
            if slot.mtib:
                result[slot_id] = SlotTestContext.from_slot(slot, telemetry=telemetry)
        return result


# ── Public Utilities ─────────────────────────────────────────────────────


def get_slot_ids_from_env() -> List[str]:
    """Determine which slot IDs should be used for test parametrization.

    Called at pytest collection time by product conftest files.
    Respects SLOT_FILTER (set per-run by the manufacturing runner),
    MTIB_HOSTS (multi-slot), MTIB_HOST (single-slot), and
    FIXTURE_CONFIG_PATH. Centralizes the logic so product conftest
    files don't need to re-implement it.
    """
    # SLOT_FILTER takes priority — set by the manufacturing runner per run
    slot_filter = os.environ.get("SLOT_FILTER", "").strip()
    if slot_filter:
        indices = sorted(int(x.strip()) for x in slot_filter.split(",") if x.strip())
        return [f"slot-{i}" for i in indices]

    mtib_hosts = os.environ.get("MTIB_HOSTS", "").strip()
    if mtib_hosts:
        count = len([a for a in mtib_hosts.split(",") if a.strip()])
        return [f"slot-{i}" for i in range(count)]

    config_path = os.environ.get("FIXTURE_CONFIG_PATH", "").strip()
    if config_path and os.path.isfile(config_path):
        import json
        with open(config_path) as f:
            data = json.load(f)
        slot_count = len(data.get("slots", []))
        if slot_count:
            return [f"slot-{i}" for i in range(slot_count)]

    if os.environ.get("MTIB_ADDRESS") or os.environ.get("MTIB_HOST"):
        return ["slot-0"]

    return ["slot-0"]


# ── Helpers ──────────────────────────────────────────────────────────────


def _parse_address(addr: str, default_port: int) -> tuple:
    """Parse 'host' or 'host:port' into (host, port)."""
    if ":" in addr:
        host, port_str = addr.rsplit(":", 1)
        return host, int(port_str)
    return addr, default_port


def _split_env(var_name: str, expected: int) -> List[str]:
    """Split a comma-separated env var, return empty list if unset."""
    val = os.environ.get(var_name, "").strip()
    if not val:
        return []
    parts = [p.strip() for p in val.split(",") if p.strip()]
    if len(parts) != expected:
        log.warning(
            "%s has %d values but %d slots — ignoring", var_name, len(parts), expected
        )
        return []
    return parts
