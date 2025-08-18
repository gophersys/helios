// Standard includes
#include <stdbool.h>
#include <stdio.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Application includes
#include <corekinect/module/vsm/vsm.h>

LOG_MODULE_REGISTER(test_snr, 4);

// Global variables
static bool g_test_stopped = false;

/**
 * @brief Callback function for SNR test steps
 *
 * This callback is called after each step of the SNR test to notify the user
 * to move the mirror to the next position.
 *
 * @param current_step The current step of the test
 * @param total_steps The total number of steps in the test
 * @param stop_test A pointer to a boolean that can be set to true to stop the test
 */
static void snr_test_step_callback(int current_step, int total_steps, bool *stop_test) {
    LOG_INF("SNR Test Step %d/%d completed", current_step, total_steps);

    if (current_step < total_steps) {
        LOG_INF("Please move the mirror to position %d and press any key to continue...", current_step + 1);
        // In a real implementation, we will wait for user input here once they've moved the mirror

        k_sleep(K_MSEC(10000));  // For now, we'll just wait some time
    } else {
        LOG_INF("SNR test completed!");
    }

    // Check if test should be stopped
    if (g_test_stopped) {
        *stop_test = true;
        LOG_WRN("SNR test stopped by user");
    }
}

/**
 * @brief Process and display SNR test results
 *
 * @param result The SNR test results to process
 */
static void process_snr_results(const vsm_test_snr_result_t *result) {
    if (!result) {
        LOG_ERR("Invalid SNR test result");
        return;
    }

    LOG_INF("=== SNR Test Results ===");
    LOG_INF("Overall test result: %s", result->passed ? "PASSED" : "FAILED");
    LOG_INF("Number of steps measured: %d", result->num_steps);
    LOG_INF("Maximum SNR observed: %.2f dB", (double)result->max_snr_db);

    if (result->snr_db_at_10ua > 0.0f) {
        LOG_INF("SNR at 10uA: %.2f dB", (double)result->snr_db_at_10ua);
    }

    // Display per-step results
    if (result->steps && result->num_steps > 0) {
        LOG_INF("=== Per-Step Results ===");
        for (int i = 0; i < result->num_steps; i++) {
            const vsm_test_snr_step_result_t *step = &result->steps[i];
            LOG_INF("Step %d: Mean=%.2f, StdDev=%.2f, SNR=%.2f dB",
                    step->step_index,
                    (double)step->mean_signal,
                    (double)step->stddev_signal,
                    (double)step->snr_db);
        }
    }

    // Check passing criteria
    LOG_INF("=== Passing Criteria Check ===");
    if (result->max_snr_db >= 80.0f) {
        LOG_INF("✓ Green channel SNR >= 80dB: %.2f dB", (double)result->max_snr_db);
    } else {
        LOG_ERR("✗ Green channel SNR < 80dB: %.2f dB", (double)result->max_snr_db);
    }

    if (result->max_snr_db >= 85.0f) {
        LOG_INF("✓ Red/IR channel SNR >= 85dB: %.2f dB", (double)result->max_snr_db);
    } else {
        LOG_ERR("✗ Red/IR channel SNR < 85dB: %.2f dB", (double)result->max_snr_db);
    }
}

int main(void) {
    LOG_INF("SNR Test Application Starting...");

    // Configure SNR test
    static const vsm_test_snr_config_t snr_config = {
        .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
        .callback = snr_test_step_callback,
    };

    LOG_INF("Starting SNR test...");
    LOG_INF("Prerequisites:");
    LOG_INF("- Ensure DUT is correctly setup in SNR test fixture");
    LOG_INF("- Ensure fixture is closed and aligned to spec");
    LOG_INF("- Prepare to move mirror to different positions");

    // Run the SNR test
    vsm_test_snr_result_t result = vsm_test_snr(&snr_config);

    // Process and display results
    process_snr_results(&result);

    // Clean up if needed (free allocated memory for steps array)
    if (result.steps) {
        LOG_INF("Cleaning up test results...");
        if (!vsm_test_snr_free_memory(&result)) {
            LOG_ERR("Failed to free test results");
        }
    }

    LOG_INF("SNR test application completed!");

    return 0;
}
