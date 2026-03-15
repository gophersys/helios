"""Product-specific shell command interfaces over MTIB UART.

Each shell class wraps an MtibV1Client and exposes firmware-specific
manufacturing shell commands as clean Python functions returning dataclasses.

Architecture:
    MtibV1Client (gRPC transport) → ShellCommander (line assembly) → ProductShell (commands)

Usage:
    from corekinect.shells.alpha_app import AlphaAppShell
    from corekinect.shells.comms_coproc import CommsCoprocShell

    app = AlphaAppShell(mtib_client)
    comms = CommsCoprocShell(mtib_client)

    app.lock()
    app.debug_off()
    ids = app.get_chip_ids()
    print(ids.ble_mac)

    comms.lock()
    comms.debug_off()
    sim = comms.get_sim_info()
    print(sim.imei)
"""

from corekinect.shells.alpha_app import AlphaAppShell
from corekinect.shells.comms_coproc import CommsCoprocShell

__all__ = ["AlphaAppShell", "CommsCoprocShell"]
