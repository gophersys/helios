/**
 * @brief LSM6DSO Subscription API Test
 *
 * Exercises the subscription-based feature management by cycling through
 * every combination of FIFO and motion detection, with pauses between
 * each phase so you can observe the behaviour on the serial console and
 * with a current meter / logic analyser.
 *
 * Phase 1  – FIFO only            (LP,  ~26 samples/500ms at 52 Hz)
 * Phase 2  – FIFO + Motion        (LP,  samples + motion interrupts)
 * Phase 3  – Motion only, dur=40  (LP,  motion interrupts, 0 FIFO samples)
 * Phase 4  – Nothing              (ULP, silence)
 * Phase 5  – Motion only, dur=40  (LP,  motion interrupts at 26 Hz ODR)
 * Phase 6  – FIFO + Motion        (LP,  both, ODR bumped back to 52 Hz)
 * Phase 7  – Disable motion       (LP,  FIFO only)
 * Phase 8  – Disable FIFO         (ULP, silence)
 * Phase 9  – Motion only, dur=0   (ULP, motion interrupts)
 * Phase 10 – Set duration=40ms    (LP,  reconfigure triggered)
 * Phase 11 – Set duration=0       (ULP, reconfigure triggered)
 * Phase 12 – Disable motion       (ULP, all disabled, ODR=0)
 *
 * Each phase runs for PHASE_DURATION_MS.  A FIFO consumer thread and a
 * motion consumer thread run the entire time; they simply report what
 * they receive.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <corekinect/sensors/lsm6dso/lsm6dso.h>

LOG_MODULE_REGISTER(lsm6dso_test, LOG_LEVEL_INF);

/*============================================================================
 * Configuration
 *============================================================================*/

#define FIFO_POLL_INTERVAL_MS  500
#define PHASE_DURATION_MS      5000

#define MOTION_THRESHOLD_MG    200
#define MOTION_DURATION_MS     40

#define FIFO_THREAD_STACK_SIZE   1024
#define FIFO_THREAD_PRIORITY     7
#define MOTION_THREAD_STACK_SIZE 1024
#define MOTION_THREAD_PRIORITY   6

/*============================================================================
 * Shared State
 *============================================================================*/

static K_THREAD_STACK_DEFINE(fifo_stack, FIFO_THREAD_STACK_SIZE);
static K_THREAD_STACK_DEFINE(motion_stack, MOTION_THREAD_STACK_SIZE);
static struct k_thread fifo_thread_data;
static struct k_thread motion_thread_data;

static struct k_sem motion_sem;
static const struct device *imu_dev;

/*============================================================================
 * FIFO Consumer Thread
 *============================================================================*/

static void fifo_thread_entry(void *p1, void *p2, void *p3)
{
    ARG_UNUSED(p1);
    ARG_UNUSED(p2);
    ARG_UNUSED(p3);

    struct sensor_value sample_count;
    uint32_t total_samples = 0;

    LOG_INF("FIFO thread started - polling every %d ms", FIFO_POLL_INTERVAL_MS);

    while (1) {
        k_msleep(FIFO_POLL_INTERVAL_MS);

        int ret = sensor_sample_fetch(imu_dev);
        if (ret < 0) {
            LOG_ERR("FIFO: fetch failed: %d", ret);
            continue;
        }

        ret = sensor_channel_get(imu_dev,
                                 (enum sensor_channel)SENSOR_CHAN_LSM6DSO_SAMPLE_COUNT,
                                 &sample_count);
        if (ret < 0) {
            LOG_ERR("FIFO: channel_get failed: %d", ret);
            continue;
        }

        int count = sample_count.val1;
        total_samples += count;
        LOG_INF("FIFO: %d samples this poll (total: %u)", count, total_samples);
    }
}

/*============================================================================
 * Motion Consumer Thread
 *============================================================================*/

static void motion_trigger_handler(const struct device *dev,
                                   const struct sensor_trigger *trig)
{
    ARG_UNUSED(dev);
    ARG_UNUSED(trig);
    k_sem_give(&motion_sem);
}

static void motion_thread_entry(void *p1, void *p2, void *p3)
{
    ARG_UNUSED(p1);
    ARG_UNUSED(p2);
    ARG_UNUSED(p3);

    uint32_t motion_count = 0;

    LOG_INF("Motion thread started");

    while (1) {
        k_sem_take(&motion_sem, K_FOREVER);
        motion_count++;
        LOG_INF("MOTION: detected (count: %u)", motion_count);
    }
}

/*============================================================================
 * Subscription Helpers
 *============================================================================*/

static int fifo_enable(uint16_t odr_hz)
{
    int ret;
    struct sensor_value val;

    val.val1 = odr_hz;
    val.val2 = 0;
    ret = sensor_attr_set(imu_dev, SENSOR_CHAN_ACCEL_XYZ,
                          (enum sensor_attribute)SENSOR_ATTR_LSM6DSO_FIFO_ODR, &val);
    if (ret < 0) {
        LOG_ERR("  FIFO ODR set failed: %d", ret);
        return ret;
    }

    val.val1 = 1;
    ret = sensor_attr_set(imu_dev, SENSOR_CHAN_ACCEL_XYZ,
                          (enum sensor_attribute)SENSOR_ATTR_LSM6DSO_FIFO_EN, &val);
    if (ret < 0) {
        LOG_ERR("  FIFO enable failed: %d", ret);
    }
    return ret;
}

static int fifo_disable(void)
{
    struct sensor_value val = { .val1 = 0 };
    int ret = sensor_attr_set(imu_dev, SENSOR_CHAN_ACCEL_XYZ,
                              (enum sensor_attribute)SENSOR_ATTR_LSM6DSO_FIFO_EN, &val);
    if (ret < 0) {
        LOG_ERR("  FIFO disable failed: %d", ret);
    }
    return ret;
}

static struct sensor_trigger motion_trig = {
    .type = SENSOR_TRIG_MOTION,
    .chan = SENSOR_CHAN_ACCEL_XYZ,
};

static int motion_enable(void)
{
    int ret;
    struct sensor_value val;

    val.val1 = MOTION_THRESHOLD_MG;
    val.val2 = 0;
    ret = sensor_attr_set(imu_dev, SENSOR_CHAN_ACCEL_XYZ,
                          SENSOR_ATTR_SLOPE_TH, &val);
    if (ret < 0) {
        LOG_WRN("  Motion threshold set failed: %d", ret);
    }

    val.val1 = MOTION_DURATION_MS;
    ret = sensor_attr_set(imu_dev, SENSOR_CHAN_ACCEL_XYZ,
                          SENSOR_ATTR_SLOPE_DUR, &val);
    if (ret < 0) {
        LOG_WRN("  Motion duration set failed: %d", ret);
    }

    ret = sensor_trigger_set(imu_dev, &motion_trig, motion_trigger_handler);
    if (ret < 0) {
        LOG_ERR("  Motion trigger_set failed: %d", ret);
    }
    return ret;
}

static int motion_disable(void)
{
    int ret = sensor_trigger_set(imu_dev, &motion_trig, NULL);
    if (ret < 0) {
        LOG_ERR("  Motion trigger_set(NULL) failed: %d", ret);
    }
    return ret;
}

static int motion_enable_instant(void)
{
    int ret;
    struct sensor_value val;

    val.val1 = MOTION_THRESHOLD_MG;
    val.val2 = 0;
    ret = sensor_attr_set(imu_dev, SENSOR_CHAN_ACCEL_XYZ,
                          SENSOR_ATTR_SLOPE_TH, &val);
    if (ret < 0) {
        LOG_WRN("  Motion threshold set failed: %d", ret);
    }

    val.val1 = 0;
    ret = sensor_attr_set(imu_dev, SENSOR_CHAN_ACCEL_XYZ,
                          SENSOR_ATTR_SLOPE_DUR, &val);
    if (ret < 0) {
        LOG_WRN("  Motion duration set failed: %d", ret);
    }

    ret = sensor_trigger_set(imu_dev, &motion_trig, motion_trigger_handler);
    if (ret < 0) {
        LOG_ERR("  Motion trigger_set failed: %d", ret);
    }
    return ret;
}

static int motion_set_duration(int32_t duration_ms)
{
    struct sensor_value val;

    val.val1 = duration_ms;
    val.val2 = 0;
    int ret = sensor_attr_set(imu_dev, SENSOR_CHAN_ACCEL_XYZ,
                              SENSOR_ATTR_SLOPE_DUR, &val);
    if (ret < 0) {
        LOG_ERR("  Motion duration set failed: %d", ret);
    }
    return ret;
}

/*============================================================================
 * Test Phases
 *============================================================================*/

static void run_phase(const char *name, int phase_num)
{
    LOG_INF("========================================");
    LOG_INF("Phase %d: %s  (%d ms)", phase_num, name, PHASE_DURATION_MS);
    LOG_INF("========================================");
    k_msleep(PHASE_DURATION_MS);
}

int main(void)
{
    LOG_INF("LSM6DSO Subscription API Test");
    LOG_INF("========================================");

    imu_dev = DEVICE_DT_GET(DT_NODELABEL(lsm6dso0));
    if (!device_is_ready(imu_dev)) {
        LOG_ERR("IMU device not ready");
        return -ENODEV;
    }

    LOG_INF("IMU device ready");

    k_sem_init(&motion_sem, 0, K_SEM_MAX_LIMIT);

    /* Start consumer threads - they run for the entire test */
    k_thread_create(&fifo_thread_data, fifo_stack, FIFO_THREAD_STACK_SIZE,
                    fifo_thread_entry, NULL, NULL, NULL,
                    FIFO_THREAD_PRIORITY, 0, K_NO_WAIT);
    k_thread_name_set(&fifo_thread_data, "fifo");

    k_thread_create(&motion_thread_data, motion_stack, MOTION_THREAD_STACK_SIZE,
                    motion_thread_entry, NULL, NULL, NULL,
                    MOTION_THREAD_PRIORITY, 0, K_NO_WAIT);
    k_thread_name_set(&motion_thread_data, "motion");

    LOG_INF("Consumer threads running");

    /* ---- Phase 1: FIFO only ---- */
    LOG_INF("Enabling FIFO at 52 Hz...");
    fifo_enable(52);
    run_phase("FIFO only (52 Hz)", 1);

    /* ---- Phase 2: FIFO + Motion ---- */
    LOG_INF("Enabling motion detection...");
    motion_enable();
    run_phase("FIFO + Motion", 2);

    /* ---- Phase 3: Motion only ---- */
    LOG_INF("Disabling FIFO (motion stays)...");
    fifo_disable();
    run_phase("Motion only (26 Hz accel)", 3);

    /* ---- Phase 4: Nothing ---- */
    LOG_INF("Disabling motion...");
    motion_disable();
    run_phase("All disabled (ULP)", 4);

    /* ---- Phase 5: Motion only (re-enable) ---- */
    LOG_INF("Re-enabling motion...");
    motion_enable();
    run_phase("Motion only (re-enabled)", 5);

    /* ---- Phase 6: FIFO + Motion ---- */
    LOG_INF("Enabling FIFO again at 52 Hz...");
    fifo_enable(52);
    run_phase("FIFO + Motion (combined)", 6);

    /* ---- Phase 7: FIFO only (disable motion) ---- */
    LOG_INF("Disabling motion (FIFO stays)...");
    motion_disable();
    run_phase("FIFO only (motion disabled)", 7);

    /* ---- Phase 8: Nothing ---- */
    LOG_INF("Disabling FIFO...");
    fifo_disable();
    run_phase("All disabled (ULP)", 8);

    /* ---- Phase 9: Motion only, duration=0 (ULP) ---- */
    LOG_INF("Enabling motion with instant trigger (duration=0)...");
    motion_enable_instant();
    run_phase("Motion only, dur=0 (ULP)", 9);

    /* ---- Phase 10: Change duration to 40ms (LP) ---- */
    LOG_INF("Setting motion duration to 40 ms...");
    motion_set_duration(MOTION_DURATION_MS);
    run_phase("Motion only, dur=40ms (LP)", 10);

    /* ---- Phase 11: Change duration back to 0 (ULP) ---- */
    LOG_INF("Setting motion duration back to 0 ms...");
    motion_set_duration(0);
    run_phase("Motion only, dur=0 (ULP)", 11);

    /* ---- Phase 12: Disable motion ---- */
    LOG_INF("Disabling motion...");
    motion_disable();
    run_phase("All disabled (ULP, ODR=0)", 12);

    LOG_INF("========================================");
    LOG_INF("Test complete. Sleeping forever.");
    LOG_INF("========================================");

    while (1) {
        k_sleep(K_FOREVER);
    }

    return 0;
}
