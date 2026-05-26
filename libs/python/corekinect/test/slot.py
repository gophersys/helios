"""Multi-slot fixture support for manufacturing and validation.

Provides SlotContext (per-DUT hardware context) and TestBedContext
(multi-slot manager) for test suites that run against fixtures with
one or more MTIBs.

Single-slot (typical validation):

    fixture_ctx = TestBedContext.from_env(testbed_factory=AlphaB0TestBed)
    # fixture_ctx.slots has 1 entry

Multi-slot (manufacturing panel, multi-DUT validation):

    fixture_ctx = TestBedContext.from_env(testbed_factory=AlphaB0MfgTestBed)
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
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.test.slot_context import SlotTestContext
from corekinect.test.slot_env import _parse_address, resolve_slot_bindings
from corekinect.utils import Logger

log = Logger(log_name="test_slot")

# Connect retry defaults — MTIBs can be momentarily unavailable after restarts
# or during hardware hiccups. Short retry loop hides transient failures.
CONNECT_MAX_ATTEMPTS = int(os.environ.get("MTIB_CONNECT_MAX_ATTEMPTS", "5"))
CONNECT_RETRY_DELAY_S = float(os.environ.get("MTIB_CONNECT_RETRY_DELAY_S", "2"))


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
    testbed: Optional[Any] = field(default=None, repr=False)

    # Optional hook that returns a one-word K8s pod state (e.g.
    # ``"ImagePullBackOff"``, ``"CrashLoopBackOff"``, ``"Pending"``)
    # for the MTIB backing this slot. When set, connect() consults it
    # after the second failure so the final error message tells the
    # operator *why* the gRPC channel won't open instead of a generic
    # "connection refused". A runner pod that lacks K8s read access
    # simply leaves this unset and falls back to the historic message.
    pod_state_lookup: Optional[Callable[[], Optional[str]]] = field(
        default=None, repr=False
    )

    def connect(self, testbed_factory: Optional[Callable] = None) -> None:
        """Connect MTIB client and create fixture controller.

        Retries on transient failures (e.g., MTIB mid-restart, gRPC
        connection reset). Gives up after CONNECT_MAX_ATTEMPTS attempts.
        """
        last_err: Optional[str] = None
        pod_state: Optional[str] = None
        for attempt in range(1, CONNECT_MAX_ATTEMPTS + 1):
            try:
                config = MtibV1Client.Config(
                    net=NetConfig(addr=self.mtib_address, port=self.mtib_port)
                )
                self.mtib = MtibV1Client(config)
                err = self.mtib.connect()
                if err:
                    raise ConnectionError(f"connect() returned error: {err}")

                ready, errors, err = self.mtib.HealthCheck()
                if err:
                    # Older MTIB builds may not implement the
                    # HealthCheck RPC yet — match the lenient
                    # behaviour of MtibV1Client.connect() and proceed
                    # with a warning instead of refusing to bind.
                    if "UNIMPLEMENTED" in err:
                        log.warning(
                            "Slot %s: HealthCheck not implemented by MTIB at %s:%d — "
                            "proceeding without server-side readiness check",
                            self.slot_id, self.mtib_address, self.mtib_port,
                        )
                    else:
                        raise ConnectionError(f"HealthCheck returned error: {err}")
                elif not ready:
                    raise ConnectionError(f"MTIB not ready: {errors}")

                if testbed_factory:
                    self.testbed = testbed_factory(self.mtib)

                log.info(
                    "Slot %s connected: %s:%d (snr=%s)%s",
                    self.slot_id, self.mtib_address, self.mtib_port,
                    self.serial_number or "n/a",
                    f" [attempt {attempt}/{CONNECT_MAX_ATTEMPTS}]" if attempt > 1 else "",
                )
                return
            except Exception as e:
                last_err = str(e)
                # Drop stale client before retrying
                if self.mtib:
                    try:
                        self.mtib.disconnect()
                    except Exception:
                        pass
                    self.mtib = None
                # On the 2nd+ failure, ask the operator-supplied hook
                # whether the underlying pod is wedged in a non-Running
                # state. Doing this from attempt 2 (rather than 1)
                # keeps a transient single failure cheap — the typical
                # MTIB-mid-restart case doesn't need a K8s round trip.
                if attempt >= 2 and pod_state is None and self.pod_state_lookup is not None:
                    try:
                        pod_state = self.pod_state_lookup()
                    except Exception as lookup_exc:
                        log.debug(
                            "Slot %s pod_state_lookup raised %s — ignoring",
                            self.slot_id, lookup_exc,
                        )
                        pod_state = None
                if attempt < CONNECT_MAX_ATTEMPTS:
                    log.warning(
                        "Slot %s connect attempt %d/%d failed (%s) — retrying in %.1fs",
                        self.slot_id, attempt, CONNECT_MAX_ATTEMPTS, last_err,
                        CONNECT_RETRY_DELAY_S,
                    )
                    time.sleep(CONNECT_RETRY_DELAY_S)

        pod_state_suffix = f" [pod state: {pod_state}]" if pod_state else ""
        raise ConnectionError(
            f"Slot {self.slot_id}: MTIB connection to "
            f"{self.mtib_address}:{self.mtib_port} failed after "
            f"{CONNECT_MAX_ATTEMPTS} attempts: {last_err}{pod_state_suffix}"
        )

    def ensure_connected(self, testbed_factory: Optional[Callable] = None) -> bool:
        """Health-check the current connection, reconnect if stale.

        Call this before running tests on a slot whose MTIB may have
        restarted since the runner started up. Returns True if the slot
        is healthy (reconnected if needed).
        """
        if self.mtib:
            try:
                ready, _errors, err = self.mtib.HealthCheck()
                if not err and ready:
                    return True
                log.warning(
                    "Slot %s stale connection (healthcheck err=%s, ready=%s) — reconnecting",
                    self.slot_id, err, ready,
                )
            except Exception as e:
                log.warning("Slot %s healthcheck raised %s — reconnecting", self.slot_id, e)
            try:
                self.mtib.disconnect()
            except Exception:
                pass
            self.mtib = None

        try:
            self.connect(testbed_factory=testbed_factory)
            return True
        except Exception as e:
            log.error("Slot %s reconnect failed: %s", self.slot_id, e)
            return False

    def disconnect(self) -> None:
        """Disconnect MTIB client."""
        if self.mtib:
            err = self.mtib.disconnect()
            if err:
                log.warning("Slot %s disconnect error: %s", self.slot_id, err)
            log.info("Slot %s disconnected", self.slot_id)


@dataclass
class TestBedContext:
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
        testbed_factory: Optional[Callable] = None,
    ) -> "TestBedContext":
        """Build from environment variables or config file.

        Resolution order:
            1. FIXTURE_CONFIG_PATH — JSON with full slot definitions
            2. MTIB_HOSTS — comma-separated addresses (multi-slot)
            3. MTIB_ADDRESS / MTIB_HOST — single address (single-slot)

        Multi-slot env parsing delegates to
        :func:`corekinect.test.slot_env.resolve_slot_bindings` so this
        class shares a single source of truth with the autoconf
        collection-time attribution step.
        """
        config_path = os.environ.get("FIXTURE_CONFIG_PATH")
        if config_path:
            return cls._from_config_file(config_path)

        if os.environ.get("MTIB_HOSTS", "").strip():
            return cls._from_slot_bindings()

        return cls._from_single_env()

    @classmethod
    def _from_slot_bindings(cls) -> "TestBedContext":
        """Build from :func:`resolve_slot_bindings` — MTIB_HOSTS path.

        Honours ``SLOT_FILTER`` / ``SLOT_SNRS`` / ``SLOT_DEVICE_IDS``
        exactly as the autoconf item-stash attribution does. One env
        parser, two consumers, zero drift.
        """
        bindings = resolve_slot_bindings()
        slots: Dict[str, SlotContext] = {}
        for b in bindings:
            slot_id = f"slot-{b.slot_index}"
            slots[slot_id] = SlotContext(
                slot_id=slot_id,
                slot_index=b.slot_index,
                mtib_address=b.mtib_host,
                mtib_port=b.mtib_port,
                serial_number=b.serial_number or "",
                device_id=b.device_id or "",
            )
        log.info(
            "Loaded %d slots from MTIB_HOSTS: %s",
            len(slots),
            [f"{s.mtib_address}:{s.mtib_port}" for s in slots.values()],
        )
        return cls(slots=slots)

    @classmethod
    def _from_config_file(cls, config_path: str) -> "TestBedContext":
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
    def _from_single_env(cls) -> "TestBedContext":
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

    def connect_all(self, testbed_factory: Optional[Callable] = None) -> None:
        """Connect all slots. Raises on first failure."""
        for slot in self.slots.values():
            slot.connect(testbed_factory=testbed_factory)
        log.info("All %d slots connected", len(self.slots))

    def connect_available(self, testbed_factory: Optional[Callable] = None) -> int:
        """Connect as many slots as possible, skipping failures.

        Used by the manufacturing runner at startup — connects all MTIBs
        that are reachable. Per-run SLOT_FILTER then validates only the
        needed slots before test execution.

        Returns the number of successfully connected slots.
        """
        connected = 0
        for slot in self.slots.values():
            try:
                slot.connect(testbed_factory=testbed_factory)
                connected += 1
            except Exception as e:
                log.warning("Slot %s connection failed (skipping): %s", slot.slot_id, e)
        log.info("Connected %d/%d slots", connected, len(self.slots))
        return connected

    def ensure_all_connected(self, testbed_factory: Optional[Callable] = None) -> int:
        """Health-check every slot, reconnect any that are stale.

        Returns count of slots currently healthy. Used by the runner before
        starting a panel run to self-heal after MTIB restarts.
        """
        healthy = 0
        for slot in self.slots.values():
            if slot.ensure_connected(testbed_factory=testbed_factory):
                healthy += 1
        log.info("Ensured connections: %d/%d slots healthy", healthy, len(self.slots))
        return healthy

    def disconnect_all(self) -> None:
        """Disconnect all slots (best-effort, logs errors)."""
        for slot in self.slots.values():
            try:
                slot.disconnect()
            except Exception as e:
                log.warning("Error disconnecting slot %s: %s", slot.slot_id, e)
        log.info("All slots disconnected")

    def build_slot_test_contexts(self, telemetry=None,
                                   target_ids: Optional[Dict[str, str]] = None,
                                   ) -> Dict[str, "SlotTestContext"]:
        """Wrap each connected SlotContext in a SlotTestContext with UART/power/artifacts.

        Args:
            telemetry: Shared TelemetryStreamer instance.
            target_ids: Mapping of slot_id → RunTarget ID for per-slot
                telemetry routing. Each slot's UART/power samples will
                include the target_id so the frontend can route them.

        Returns a dict keyed by slot_id. Only wraps slots that have a connected MTIB.
        Call connect() on each returned SlotTestContext to start per-slot services.
        """
        target_ids = target_ids or {}
        result = {}
        for slot_id, slot in self.slots.items():
            if slot.mtib:
                tid = target_ids.get(slot_id)
                result[slot_id] = SlotTestContext.from_slot(
                    slot, telemetry=telemetry, target_id=tid,
                )
        return result


# ── Public Utilities ─────────────────────────────────────────────────────


def get_slot_ids_from_env() -> List[str]:
    """Determine which slot IDs should be used for test parametrization.

    Derived from :func:`corekinect.test.slot_env.resolve_slot_bindings`
    so the slot fixture's parametrization is always in lockstep with
    the binding stash (set at collection time by autoconf) and the
    :class:`TestBedContext` MTIB connections (set at fixture-setup
    time). One source of truth means MTIB ↔ slot ↔ SNR alignment is
    a property of the resolver, not a coincidence between three
    parsers.

    Falls back to ``["slot-0"]`` for the FIXTURE_CONFIG_PATH (JSON
    fixture config) path and the single-slot validation case where
    ``MTIB_HOSTS`` is empty but ``MTIB_HOST`` / ``MTIB_ADDRESS`` is
    set — those configurations don't go through the resolver but
    still need a slot id for parametrization.
    """
    bindings = resolve_slot_bindings()
    if bindings:
        return [f"slot-{b.slot_index}" for b in bindings]

    config_path = os.environ.get("FIXTURE_CONFIG_PATH", "").strip()
    if config_path and os.path.isfile(config_path):
        with open(config_path) as f:
            data = json.load(f)
        slot_count = len(data.get("slots", []))
        if slot_count:
            return [f"slot-{i}" for i in range(slot_count)]

    return ["slot-0"]
