"""Alpha validation tests.

Organized by validation stage:

    gate/        PR validation (< 15 min, blocks merge)
    nightly/     Comprehensive validation (30-60 min, nightly cron)
    integration/ Instrumented firmware (15-30 min, requires harness)
    fuota/       Firmware update over the air (up to 2h, LTE-M wake cycle)
    common/      Shared utilities (timing, assertions)

Run specific stage:
    pytest tests/gate/ -v --timeout=900
    pytest tests/nightly/ -v --timeout=3600
    pytest tests/integration/ -v --timeout=1800
    pytest tests/fuota/ -v -s --timeout=7200

See catalog.yaml for the complete test catalog.
"""
