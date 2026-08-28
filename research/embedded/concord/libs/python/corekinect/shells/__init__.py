"""Product-specific shell command interfaces over MTIB UART.

Each shell class wraps an MtibV1Client and provides manufacturing shell
commands for a specific processor target (app or comms).

Architecture:
    MtibV1Client (gRPC transport) → ShellCommander (line assembly) → Shell (commands)

Shells are split by processor target, not product:
    - app shells:   AlphaAppShell, ThetaAppShell, Sigma5AppShell
    - comms shells: CommsCoprocShell (shared across products)

Usage:
    app = AlphaAppShell(mtib_client)
    comms = CommsCoprocShell(mtib_client)

    app.start()
    comms.start()

    app.lock()
    comms.lock()

    ids, err = app.get_chip_ids()
    sim, err = comms.get_sim_info()
"""

from corekinect.shells.alpha_app import AlphaAppShell
from corekinect.shells.comms_coproc import CommsCoprocShell
from corekinect.shells.theta import ThetaAppShell
from corekinect.shells.sigma5 import Sigma5AppShell

__all__ = [
    "AlphaAppShell",
    "CommsCoprocShell",
    "ThetaAppShell",
    "Sigma5AppShell",
]
