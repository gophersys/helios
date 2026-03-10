"""POST (Power-On Self Test) manufacturing tests.

Runs after firmware flash to verify device functionality:
    - Chip ID verification (comms + app processors)
    - BMS / gas gauge
    - Battery charger
    - GPS module
    - Modem firmware version
    - IMEI / ICCID
    - External flash
    - Device personalization (CoreOps)
    - IPC rekey

Tests are marked with @pytest.mark.sequential to ensure they run in order.
Shared data (IMEI, ICCIDs) is passed between tests via the slot.shared_data dict.
"""
