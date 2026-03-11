"""Integration tests - Stage 3: Instrumented firmware testing.

Uses concord_harness module in firmware to observe and control
internal state. Requires instrumented firmware build.

Test categories:
    INTEG-ALPHA-SM-*   : State machine transitions
    INTEG-ALPHA-IPC-*  : Inter-processor communication
    INTEG-ALPHA-ORCH-* : Sensor orchestration timing
    INTEG-ALPHA-CFG-*  : Configuration propagation

Prerequisites:
    - Firmware built with CONFIG_CONCORD_HARNESS=y
    - UART access for harness commands

Run with:
    pytest tests/integration/ -v
"""
