try:
    from .config import (
        TestConfig,
        ManufacturingTestConfig,
        ValidationTestConfig,
        CompatibleManufacturingTestConfig,
        CompatibleValidationTestConfig,
    )

    from .runtime import ValidationTest
    from .step import TestStepConfig, TestStepInfo, TestStepData, PassTestStep, FailTestStep, ErrorTestStep, TestStep
except ImportError:
    # mtib_runner not available — legacy test infrastructure not installed.
    # Validation subpackage (corekinect.test.validation) works independently.
    pass
