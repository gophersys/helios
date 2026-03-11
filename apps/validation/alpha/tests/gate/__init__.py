"""Gate tests - Stage 5: PR validation + FUOTA.

This is the merge blocker that runs on every PR.
Total duration: < 15 minutes (hard limit).

Test sequence:
    GATE-ALPHA-001: Flash firmware (nRF52840 → modem → nRF9151)
    GATE-ALPHA-002: Verify boot
    GATE-ALPHA-003: Personalize device
    GATE-ALPHA-004: Cloud check-in
    GATE-ALPHA-005: FUOTA upload
    GATE-ALPHA-006: FUOTA plan and assign
    GATE-ALPHA-007: FUOTA delivery
    GATE-ALPHA-008: Post-FUOTA boot

Run with:
    pytest tests/gate/ -v --timeout=900
"""
