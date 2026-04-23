"""MTIB v1 gRPC client — public surface.

Use :class:`MtibV1Client` as the entry point; configure via
:class:`NetConfig` for transport and :class:`AdcConfig` /
:class:`GpioConfig` when wiring per-pin defaults. Type re-exports
come from :mod:`.client.types` so callers can refer to ``HostType``,
``GpioDirection``, etc. without importing a nested path.
"""

from .client.core import MtibV1Client
from .client.config import AdcConfig, GpioConfig, NetConfig
from .client.types import *  # re-export proto-derived enums; see types.py for the full list

__all__ = [
    "MtibV1Client",
    "NetConfig",
    "AdcConfig",
    "GpioConfig",
]
# ``types`` re-exports its own public names via its own ``__all__``;
# don't duplicate them here so the two stay in sync automatically.
