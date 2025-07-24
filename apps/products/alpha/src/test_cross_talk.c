// Standard includes
#include <stdbool.h>
#include <stdio.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Application includes
#include <corekinect/module/vsm/vsm.h>

LOG_MODULE_REGISTER(test_cross_talk, 4);

// ANSI color codes for terminal output
#define ANSI_RED "\033[31m"
#define ANSI_GREEN "\033[32m"
#define ANSI_YELLOW "\033[33m"
#define ANSI_BLUE "\033[34m"
#define ANSI_MAGENTA "\033[35m"
#define ANSI_CYAN "\033[36m"
#define ANSI_RESET "\033[0m"
#define ANSI_BOLD "\033[1m"

/**
 * @brief Process and display cross-talk test results
 *
 * @param result The cross-talk test results to process
 */
static void process_cross_talk_results(const vsm_test_cross_talk_result_t *result) {
    if (!result) {
        LOG_ERR("Invalid cross-talk test result");
        return;
    }

    LOG_INF("=== Cross-Talk Test Results ===");
    if (result->passed) {
        LOG_INF("%s%sOverall test result: PASSED%s", ANSI_BOLD, ANSI_GREEN, ANSI_RESET);
    } else {
        LOG_ERR("%s%sOverall test result: FAILED%s", ANSI_BOLD, ANSI_RED, ANSI_RESET);
    }

    // Display per-channel results
    LOG_INF("=== Per-Channel Results ===");

    // Green channel
    LOG_INF("Green Channel:");
    LOG_INF("  Raw count: %ld", (long)result->green.raw_count);
    LOG_INF("  Threshold: %ld", (long)result->green.threshold);
    if (result->green.passed) {
        LOG_INF("  Status: %s%sPASSED%s", ANSI_BOLD, ANSI_GREEN, ANSI_RESET);
    } else {
        LOG_ERR("  Status: %s%sFAILED%s", ANSI_BOLD, ANSI_RED, ANSI_RESET);
    }

    // Red channel
    LOG_INF("Red Channel:");
    LOG_INF("  Raw count: %ld", (long)result->red.raw_count);
    LOG_INF("  Threshold: %ld", (long)result->red.threshold);
    if (result->red.passed) {
        LOG_INF("  Status: %s%sPASSED%s", ANSI_BOLD, ANSI_GREEN, ANSI_RESET);
    } else {
        LOG_ERR("  Status: %s%sFAILED%s", ANSI_BOLD, ANSI_RED, ANSI_RESET);
    }

    // IR channel
    LOG_INF("IR Channel:");
    LOG_INF("  Raw count: %ld", (long)result->ir.raw_count);
    LOG_INF("  Threshold: %ld", (long)result->ir.threshold);
    if (result->ir.passed) {
        LOG_INF("  Status: %s%sPASSED%s", ANSI_BOLD, ANSI_GREEN, ANSI_RESET);
    } else {
        LOG_ERR("  Status: %s%sFAILED%s", ANSI_BOLD, ANSI_RED, ANSI_RESET);
    }

    // Display passing criteria values
    LOG_INF("=== Passing Criteria Values ===");
    LOG_INF("Green LED threshold: %ld", (long)result->pass_green_led_value);
    LOG_INF("Red & IR LED threshold: %ld", (long)result->pass_red_and_ir_led_value);

    // Detailed analysis
    LOG_INF("=== Detailed Analysis ===");

    // Green channel analysis
    if (result->green.raw_count < result->green.threshold) {
        LOG_INF("%s%s✓ Green channel: Raw count (%ld) < threshold (%ld)%s",
                ANSI_BOLD, ANSI_GREEN, (long)result->green.raw_count, (long)result->green.threshold, ANSI_RESET);
    } else {
        LOG_ERR("%s%s✗ Green channel: Raw count (%ld) >= threshold (%ld)%s",
                ANSI_BOLD, ANSI_RED, (long)result->green.raw_count, (long)result->green.threshold, ANSI_RESET);
    }

    // Red channel analysis
    if (result->red.raw_count < result->red.threshold) {
        LOG_INF("%s%s✓ Red channel: Raw count (%ld) < threshold (%ld)%s",
                ANSI_BOLD, ANSI_GREEN, (long)result->red.raw_count, (long)result->red.threshold, ANSI_RESET);
    } else {
        LOG_ERR("%s%s✗ Red channel: Raw count (%ld) >= threshold (%ld)%s",
                ANSI_BOLD, ANSI_RED, (long)result->red.raw_count, (long)result->red.threshold, ANSI_RESET);
    }

    // IR channel analysis
    if (result->ir.raw_count < result->ir.threshold) {
        LOG_INF("%s%s✓ IR channel: Raw count (%ld) < threshold (%ld)%s",
                ANSI_BOLD, ANSI_GREEN, (long)result->ir.raw_count, (long)result->ir.threshold, ANSI_RESET);
    } else {
        LOG_ERR("%s%s✗ IR channel: Raw count (%ld) >= threshold (%ld)%s",
                ANSI_BOLD, ANSI_RED, (long)result->ir.raw_count, (long)result->ir.threshold, ANSI_RESET);
    }

    // Summary
    LOG_INF("=== Summary ===");
    if (result->passed) {
        LOG_INF("%s%s✓ Cross-talk test PASSED - All channels below threshold%s", ANSI_BOLD, ANSI_GREEN, ANSI_RESET);
    } else {
        LOG_ERR("%s%s✗ Cross-talk test FAILED - One or more channels above threshold%s", ANSI_BOLD, ANSI_RED, ANSI_RESET);
    }
}

int main(void) {
    LOG_INF("Cross-Talk Test Application Starting...");

    // Configure cross-talk test
    static const vsm_test_cross_talk_config_t cross_talk_config = {
        .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
    };

    LOG_INF("Starting cross-talk test...");
    LOG_INF("Prerequisites:");
    LOG_INF("- Device must be covered by a black rubber piece");
    LOG_INF("- Black rubber must cover the sensor assembly entirely");
    LOG_INF("- Fixture and environment should be stable");
    LOG_INF("- Measurement duration: ~30 seconds");

    vsm_test_cross_talk_result_t result = vsm_test_cross_talk(&cross_talk_config);

    // Process and display results
    process_cross_talk_results(&result);

    LOG_INF("Cross-talk test application completed!");

    return 0;
}
