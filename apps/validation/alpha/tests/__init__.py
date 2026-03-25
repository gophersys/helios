"""Alpha validation tests.

Organized by validation stage (one stage per container run):

    smoke/       Software tests on native_sim — no hardware required
    silicon/     Driver hardware tests on dev kits
    integration/ Subsystem integration tests with harness instrumentation
    nightly/     Comprehensive product validation — nightly runs
    fuota/       Over-the-air firmware update verification — blocks merge
    common/      Shared utilities (timing, assertions)

Run specific stage:
    pytest tests/fuota/ -v -s --timeout=7200
    pytest tests/nightly/ -v --timeout=3600
    pytest tests/integration/ -v --timeout=1800

See catalog.yaml for the complete test catalog.
"""
