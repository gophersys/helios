// Standard includes
#include <stdbool.h>
#include <stdio.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Application includes
#include <corekinect/module/vsm/vsm.h>

LOG_MODULE_REGISTER(test_reflectivity, 4);

/**
 * @brief Process and display reflectivity test results
 *
 * @param result The reflectivity test results to process
 * @param is_golden_unit Whether this was a golden unit test
 */
static void process_reflectivity_results(const vsm_test_reflectivity_result_t *result, bool is_golden_unit) {
    if (!result) {
        LOG_ERR("Invalid reflectivity test result");
        return;
    }

    LOG_INF("=== Reflectivity Test Results ===");
    LOG_INF("Test mode: %s", is_golden_unit ? "GOLDEN UNIT CALIBRATION" : "REGULAR UNIT TEST");
    LOG_INF("Overall test result: %s", result->passed ? "PASSED" : "FAILED");

    // Display per-channel results
    LOG_INF("=== Per-Channel Results ===");

    // Green channel
    LOG_INF("Green Channel:");
    LOG_INF("  ADC PPG Level: %.2f counts", (double)result->green.adc_ppg_level);
    LOG_INF("  ADC Max: %.2f counts", (double)result->green.adc_max);
    LOG_INF("  IPD Max: %.2f uA", (double)result->green.ipd_max_ua);
    LOG_INF("  ILED: %.2f mA", (double)result->green.iled_ma);
    LOG_INF("  IPD: %.2f uA", (double)result->green.ipd_ua);
    LOG_INF("  Reflectivity: %.4f uA/mA", (double)result->green.reflectivity);
    if (!is_golden_unit) {
        LOG_INF("  Golden Reflectivity: %.4f uA/mA", (double)result->green.golden_reflectivity);
    }
    LOG_INF("  Status: %s", result->green.passed ? "PASSED" : "FAILED");

    // Red channel
    LOG_INF("Red Channel:");
    LOG_INF("  ADC PPG Level: %.2f counts", (double)result->red.adc_ppg_level);
    LOG_INF("  ADC Max: %.2f counts", (double)result->red.adc_max);
    LOG_INF("  IPD Max: %.2f uA", (double)result->red.ipd_max_ua);
    LOG_INF("  ILED: %.2f mA", (double)result->red.iled_ma);
    LOG_INF("  IPD: %.2f uA", (double)result->red.ipd_ua);
    LOG_INF("  Reflectivity: %.4f uA/mA", (double)result->red.reflectivity);
    if (!is_golden_unit) {
        LOG_INF("  Golden Reflectivity: %.4f uA/mA", (double)result->red.golden_reflectivity);
    }
    LOG_INF("  Status: %s", result->red.passed ? "PASSED" : "FAILED");

    // IR channel
    LOG_INF("IR Channel:");
    LOG_INF("  ADC PPG Level: %.2f counts", (double)result->ir.adc_ppg_level);
    LOG_INF("  ADC Max: %.2f counts", (double)result->ir.adc_max);
    LOG_INF("  IPD Max: %.2f uA", (double)result->ir.ipd_max_ua);
    LOG_INF("  ILED: %.2f mA", (double)result->ir.iled_ma);
    LOG_INF("  IPD: %.2f uA", (double)result->ir.ipd_ua);
    LOG_INF("  Reflectivity: %.4f uA/mA", (double)result->ir.reflectivity);
    if (!is_golden_unit) {
        LOG_INF("  Golden Reflectivity: %.4f uA/mA", (double)result->ir.golden_reflectivity);
    }
    LOG_INF("  Status: %s", result->ir.passed ? "PASSED" : "FAILED");

    // Detailed analysis
    LOG_INF("=== Detailed Analysis ===");

    if (is_golden_unit) {
        LOG_INF("Golden Unit Mode - Recording reference values:");
        LOG_INF("  Green: %.4f uA/mA", (double)result->green.reflectivity);
        LOG_INF("  Red: %.4f uA/mA", (double)result->red.reflectivity);
        LOG_INF("  IR: %.4f uA/mA", (double)result->ir.reflectivity);
        LOG_INF("These values should be used as golden references for regular unit testing.");
    } else {
        LOG_INF("Regular Unit Mode - Comparing to golden values:");

        // Green channel comparison
        if (result->green.passed) {
            LOG_INF("✓ Green: %.4f uA/mA (within tolerance of %.4f uA/mA)",
                    (double)result->green.reflectivity, (double)result->green.golden_reflectivity);
        } else {
            LOG_ERR("✗ Green: %.4f uA/mA (outside tolerance of %.4f uA/mA)",
                    (double)result->green.reflectivity, (double)result->green.golden_reflectivity);
        }

        // Red channel comparison
        if (result->red.passed) {
            LOG_INF("✓ Red: %.4f uA/mA (within tolerance of %.4f uA/mA)",
                    (double)result->red.reflectivity, (double)result->red.golden_reflectivity);
        } else {
            LOG_ERR("✗ Red: %.4f uA/mA (outside tolerance of %.4f uA/mA)",
                    (double)result->red.reflectivity, (double)result->red.golden_reflectivity);
        }

        // IR channel comparison
        if (result->ir.passed) {
            LOG_INF("✓ IR: %.4f uA/mA (within tolerance of %.4f uA/mA)",
                    (double)result->ir.reflectivity, (double)result->ir.golden_reflectivity);
        } else {
            LOG_ERR("✗ IR: %.4f uA/mA (outside tolerance of %.4f uA/mA)",
                    (double)result->ir.reflectivity, (double)result->ir.golden_reflectivity);
        }
    }

    // Summary
    LOG_INF("=== Summary ===");
    if (result->passed) {
        if (is_golden_unit) {
            LOG_INF("✓ Golden unit calibration completed successfully");
        } else {
            LOG_INF("✓ Reflectivity test PASSED - All channels within tolerance");
        }
    } else {
        if (is_golden_unit) {
            LOG_ERR("✗ Golden unit calibration failed");
        } else {
            LOG_ERR("✗ Reflectivity test FAILED - One or more channels outside tolerance");
        }
    }
}

int main(void) {
    LOG_INF("Reflectivity Test Application Starting...");

    // For demonstration, we will run only golden unit test
    // In practice, we will choose one mode based on our needs,
    // once the golden unit test is completed.
    LOG_INF("=== Running Golden Unit Test ===");
    static const vsm_test_reflectivity_config_t golden_config = {
        .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
        .is_golden_unit = true,
        .golden_reflectivity_green = 0.0f,  // Not used in golden mode
        .golden_reflectivity_red = 0.0f,    // Not used in golden mode
        .golden_reflectivity_ir = 0.0f,     // Not used in golden mode
    };

    LOG_INF("Starting golden unit reflectivity test...");
    LOG_INF("Prerequisites:");
    LOG_INF("- Device is placed in SNR test fixture");
    LOG_INF("- Reflective screen is at fixed position");
    LOG_INF("- Fixture and environment should be stable");
    LOG_INF("- Measurement duration: ~10 seconds");

    vsm_test_reflectivity_result_t golden_result = vsm_test_reflectivity(&golden_config);
    process_reflectivity_results(&golden_result, true);

    LOG_INF("Reflectivity test application completed!");

    return 0;
}
