"""Passive GPIO state tracker updated by GpioHandler operations."""

import threading
import time
from typing import Dict, List, Optional

from corekinect.utils import Logger


class GpioStateTracker:
    """Maintains a map of GPIO pin states, updated by GpioHandler.

    Supports an optional refresh callback that reads live hardware values
    before returning state — set via set_refresh_callback().
    """

    def __init__(self, logger: Logger):
        self.logger = logger
        self._states: Dict[int, dict] = {}
        self._lock = threading.Lock()
        self._refresh_cb: Optional[callable] = None

    def set_refresh_callback(self, cb: callable) -> None:
        """Register a callback that reads live pin values into the tracker."""
        self._refresh_cb = cb

    def update_config(self, pin: int, direction: int) -> None:
        """Record a pin configuration change.

        Args:
            pin: Logical GPIO pin number.
            direction: GpioDirection enum value (0=INPUT, 1=OUTPUT).
        """
        now = time.time()
        with self._lock:
            state = self._states.get(pin, {
                "pin": pin,
                "direction": 0,
                "value": False,
                "configured": False,
                "last_changed": now,
            })
            state["direction"] = direction
            state["configured"] = True
            state["last_changed"] = now
            self._states[pin] = state

    def update_value(self, pin: int, value: bool) -> None:
        """Record a pin value change (from write or read).

        Args:
            pin: Logical GPIO pin number.
            value: Current pin value.
        """
        now = time.time()
        with self._lock:
            state = self._states.get(pin, {
                "pin": pin,
                "direction": 0,
                "value": False,
                "configured": False,
                "last_changed": now,
            })
            state["value"] = value
            state["last_changed"] = now
            self._states[pin] = state

    def get_state(self, pin: int) -> Optional[dict]:
        """Return the tracked state for a single pin, or None."""
        with self._lock:
            return self._states.get(pin)

    def get_all_states(self) -> List[dict]:
        """Return tracked states for all pins, refreshing from hardware first."""
        if self._refresh_cb:
            try:
                self._refresh_cb()
            except Exception as e:
                self.logger.debug(f"GpioStateTracker: refresh callback error: {e}")
        with self._lock:
            return list(self._states.values())
