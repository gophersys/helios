/**
 * @file bq35100.h
 * @brief BQ35100 Primary Battery Fuel Gauge Driver for Zephyr RTOS
 *
 * Copyright (c) 2024 CoreKinect Inc.
 *
 * This driver provides support for the Texas Instruments BQ35100 primary
 * battery fuel gauge. The BQ35100 supports Li-SOCl2 and Li-MnO2 chemistries
 * with three gauging modes: Accumulator (coulomb counting), State-of-Health
 * (voltage correlation), and End-of-Service (impedance tracking).
 *
 * Features:
 * - Host-controlled power via GE pin (50 nA shutdown)
 * - Battery voltage, current, temperature measurement
 * - Accumulated capacity (coulomb counting)
 * - State-of-Health percentage
 * - Cell impedance measurement (EOS mode)
 * - Configurable ALERT interrupt
 * - Seal/Unseal security modes
 * - Data flash read/write access
 * - SHA-1/HMAC battery authentication
 */

#ifndef COREKINECT_GAUGE_BQ35100_H_
#define COREKINECT_GAUGE_BQ35100_H_

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------ */
/* I2C Address                                                         */
/* ------------------------------------------------------------------ */

#define BQ35100_I2C_ADDR 0x55

/* ------------------------------------------------------------------ */
/* Standard Data Commands (Register Map)                               */
/* ------------------------------------------------------------------ */

#define BQ35100_REG_CONTROL            0x00 /* R/W 2B — subcommand interface */
#define BQ35100_REG_ACCUMULATED_CAP    0x02 /* R   4B — accumulated capacity (uAh) */
#define BQ35100_REG_TEMPERATURE        0x06 /* R   2B — temperature (0.1 K) */
#define BQ35100_REG_VOLTAGE            0x08 /* R   2B — voltage (mV) */
#define BQ35100_REG_BATTERY_STATUS     0x0A /* R   1B — status flags */
#define BQ35100_REG_BATTERY_ALERT      0x0B /* R   1B — alert flags */
#define BQ35100_REG_CURRENT            0x0C /* R   2B — current (mA, signed) */
#define BQ35100_REG_SCALED_R           0x16 /* R   2B — scaled resistance (mohm) */
#define BQ35100_REG_MEASURED_Z         0x22 /* R   2B — measured impedance (mohm) */
#define BQ35100_REG_INTERNAL_TEMP      0x28 /* R   2B — internal die temp (0.1 K) */
#define BQ35100_REG_SOH                0x2E /* R   1B — state of health (%) */
#define BQ35100_REG_DESIGN_CAPACITY    0x3C /* R   2B — design capacity (mAh) */
#define BQ35100_REG_MAC                0x3E /* R/W 2B — MAC subcommand */
#define BQ35100_REG_MAC_DATA           0x40 /* R/W 32B — MAC data block */
#define BQ35100_REG_MAC_DATA_SUM       0x60 /* R/W 1B — MAC checksum */
#define BQ35100_REG_MAC_DATA_LEN       0x61 /* R/W 1B — MAC data length */
#define BQ35100_REG_CAL_COUNT          0x79 /* R   1B — calibration counter */
#define BQ35100_REG_CAL_CURRENT        0x7A /* R   2B — raw cal current */
#define BQ35100_REG_CAL_VOLTAGE        0x7C /* R   2B — raw cal voltage */
#define BQ35100_REG_CAL_TEMPERATURE    0x7E /* R   2B — raw cal temperature */

/* ------------------------------------------------------------------ */
/* Control Subcommands (written to REG_CONTROL or REG_MAC)             */
/* ------------------------------------------------------------------ */

#define BQ35100_CNTL_CONTROL_STATUS    0x0000
#define BQ35100_CNTL_DEVICE_TYPE       0x0001
#define BQ35100_CNTL_FW_VERSION        0x0002
#define BQ35100_CNTL_HW_VERSION        0x0003
#define BQ35100_CNTL_STATIC_CHEM_CHKSUM 0x0005
#define BQ35100_CNTL_CHEM_ID           0x0006
#define BQ35100_CNTL_PREV_MACWRITE     0x0007
#define BQ35100_CNTL_BOARD_OFFSET      0x0009
#define BQ35100_CNTL_CC_OFFSET         0x000A
#define BQ35100_CNTL_CC_OFFSET_SAVE    0x000B
#define BQ35100_CNTL_GAUGE_START       0x0011
#define BQ35100_CNTL_GAUGE_STOP        0x0012
#define BQ35100_CNTL_SEALED            0x0020
#define BQ35100_CNTL_CAL_ENABLE        0x002D
#define BQ35100_CNTL_LT_ENABLE         0x002E
#define BQ35100_CNTL_RESET             0x0041
#define BQ35100_CNTL_EXIT_CAL          0x0080
#define BQ35100_CNTL_ENTER_CAL         0x0081
#define BQ35100_CNTL_NEW_BATTERY       0xA613

/* ------------------------------------------------------------------ */
/* CONTROL_STATUS Bits                                                 */
/* ------------------------------------------------------------------ */

#define BQ35100_CS_GA            BIT(0)  /* Gauge Active */
#define BQ35100_CS_SOH_ERR       BIT(5)  /* SOH overflow */
#define BQ35100_CS_G_DONE        BIT(6)  /* Gauge done, safe to power down */
#define BQ35100_CS_INITCOMP      BIT(7)  /* Initialization complete */
#define BQ35100_CS_OCVFAIL       BIT(8)  /* Initial OCV failed */
#define BQ35100_CS_LTEN          BIT(9)  /* Lifetime data enabled */
#define BQ35100_CS_CCA           BIT(10) /* CC calibration active */
#define BQ35100_CS_BCA           BIT(11) /* Board calibration active */
#define BQ35100_CS_CALMODE       BIT(12) /* Calibration mode */
#define BQ35100_CS_SEC0          BIT(13) /* Security bit 0 */
#define BQ35100_CS_SEC1          BIT(14) /* Security bit 1 */
#define BQ35100_CS_FLASHF        BIT(15) /* Flash failure */

#define BQ35100_CS_SEC_MASK      (BQ35100_CS_SEC1 | BQ35100_CS_SEC0)
#define BQ35100_CS_SEC_FULL      BQ35100_CS_SEC0
#define BQ35100_CS_SEC_UNSEALED  BQ35100_CS_SEC1
#define BQ35100_CS_SEC_SEALED    (BQ35100_CS_SEC1 | BQ35100_CS_SEC0)

/* ------------------------------------------------------------------ */
/* BatteryStatus Bits (0x0A)                                           */
/* ------------------------------------------------------------------ */

#define BQ35100_BSTAT_DSG        BIT(0) /* Discharge detected */
#define BQ35100_BSTAT_ALERT      BIT(2) /* ALERT pin active */

/* ------------------------------------------------------------------ */
/* BatteryAlert Bits (0x0B)                                            */
/* ------------------------------------------------------------------ */

#define BQ35100_BALERT_INITCOMP  BIT(0) /* Init complete */
#define BQ35100_BALERT_G_DONE    BIT(1) /* Gauge done */
#define BQ35100_BALERT_EOS       BIT(3) /* End of service */
#define BQ35100_BALERT_SOH_LOW   BIT(4) /* SOH below threshold */
#define BQ35100_BALERT_TEMPHIGH  BIT(5) /* Over temperature */
#define BQ35100_BALERT_TEMPLOW   BIT(6) /* Under temperature */
#define BQ35100_BALERT_BATLOW    BIT(7) /* Battery low voltage */

/* ------------------------------------------------------------------ */
/* Data Flash Addresses                                                */
/* ------------------------------------------------------------------ */

#define BQ35100_DF_OPERATION_CFG_A   0x41B1
#define BQ35100_DF_ALERT_CONFIG      0x41B2
#define BQ35100_DF_DESIGN_CAP_MAH    0x41FE
#define BQ35100_DF_DESIGN_VOLTAGE    0x4202
#define BQ35100_DF_TERMINATE_VOLTAGE 0x4204
#define BQ35100_DF_UNSEAL_KEY1       0x41CC
#define BQ35100_DF_UNSEAL_KEY2       0x41CE
#define BQ35100_DF_DEVICE_NAME       0x4060

/* Default unseal keys */
#define BQ35100_UNSEAL_KEY1      0x0414
#define BQ35100_UNSEAL_KEY2      0x3672

/* ------------------------------------------------------------------ */
/* Operation Config A Bits                                             */
/* ------------------------------------------------------------------ */

#define BQ35100_OPCFG_GMSEL_MASK  0x03
#define BQ35100_OPCFG_GMSEL_ACC   0x00
#define BQ35100_OPCFG_GMSEL_SOH   0x01
#define BQ35100_OPCFG_GMSEL_EOS   0x02
#define BQ35100_OPCFG_TEMPS       BIT(7) /* 1=external NTC, 0=internal */
#define BQ35100_OPCFG_WRTEMP      BIT(5) /* 1=host can write temp */

/* ------------------------------------------------------------------ */
/* Expected device type                                                */
/* ------------------------------------------------------------------ */

#define BQ35100_DEVICE_TYPE      0x0100

/* ------------------------------------------------------------------ */
/* Custom Sensor Channels                                              */
/* ------------------------------------------------------------------ */

/**
 * @brief Custom sensor channels for BQ35100-specific measurements
 *
 * These extend the standard Zephyr sensor channels to provide access
 * to BQ35100-specific data not covered by SENSOR_CHAN_* defaults.
 */
enum sensor_channel_bq35100 {
	/** State of Health percentage (0-100%) — val1 = integer % */
	SENSOR_CHAN_BQ35100_SOH = SENSOR_CHAN_PRIV_START,
	/** Accumulated capacity since GAUGE_START — val1 = uAh (high 16), val2 = uAh (low 16) */
	SENSOR_CHAN_BQ35100_ACCUMULATED_CAP,
	/** Cell impedance in milliohms (EOS mode) — val1 = mohm */
	SENSOR_CHAN_BQ35100_IMPEDANCE,
	/** Scaled resistance in milliohms (EOS mode) — val1 = mohm */
	SENSOR_CHAN_BQ35100_SCALED_R,
	/** Internal die temperature — val1 = degrees C, val2 = fractional */
	SENSOR_CHAN_BQ35100_INTERNAL_TEMP,
	/** Design capacity — val1 = mAh */
	SENSOR_CHAN_BQ35100_DESIGN_CAP,
	/** Battery status flags — val1 = raw BatteryStatus byte */
	SENSOR_CHAN_BQ35100_BATTERY_STATUS,
	/** Battery alert flags — val1 = raw BatteryAlert byte */
	SENSOR_CHAN_BQ35100_BATTERY_ALERT,
	/** Control status word — val1 = raw 16-bit CONTROL_STATUS */
	SENSOR_CHAN_BQ35100_CONTROL_STATUS,
};

/* ------------------------------------------------------------------ */
/* Custom Sensor Attributes                                            */
/* ------------------------------------------------------------------ */

/**
 * @brief Custom sensor attributes for BQ35100 configuration
 */
enum sensor_attribute_bq35100 {
	/** Start active gauging (write any value) */
	SENSOR_ATTR_BQ35100_GAUGE_START = SENSOR_ATTR_PRIV_START,
	/** Stop gauging (write any value) */
	SENSOR_ATTR_BQ35100_GAUGE_STOP,
	/** Enable GE pin (write any value) */
	SENSOR_ATTR_BQ35100_ENABLE,
	/** Disable GE pin (write any value) */
	SENSOR_ATTR_BQ35100_DISABLE,
	/** Unseal device (write any value, uses default keys) */
	SENSOR_ATTR_BQ35100_UNSEAL,
	/** Seal device (write any value) */
	SENSOR_ATTR_BQ35100_SEAL,
	/** Reset for new battery (write any value) */
	SENSOR_ATTR_BQ35100_NEW_BATTERY,
	/** Device reset (write any value) */
	SENSOR_ATTR_BQ35100_RESET,
};

/* ------------------------------------------------------------------ */
/* Custom Sensor Triggers                                              */
/* ------------------------------------------------------------------ */

/**
 * @brief Custom trigger types for BQ35100 ALERT events
 */
enum sensor_trigger_type_bq35100 {
	/** Triggered on any ALERT pin assertion */
	SENSOR_TRIG_BQ35100_ALERT = SENSOR_TRIG_PRIV_START,
};

/* ------------------------------------------------------------------ */
/* Gauging Mode                                                        */
/* ------------------------------------------------------------------ */

enum bq35100_gauging_mode {
	BQ35100_MODE_ACCUMULATOR = 0,
	BQ35100_MODE_SOH = 1,
	BQ35100_MODE_EOS = 2,
};

/* ------------------------------------------------------------------ */
/* Driver Structures                                                   */
/* ------------------------------------------------------------------ */

/**
 * @brief BQ35100 device configuration (from devicetree)
 */
struct bq35100_config {
	struct i2c_dt_spec i2c;
	struct gpio_dt_spec enable_gpio;
#ifdef CONFIG_CK_BQ35100_TRIGGER
	struct gpio_dt_spec alert_gpio;
#endif
	uint16_t design_capacity_mah;
	enum bq35100_gauging_mode gauging_mode;
	uint16_t power_up_delay_ms;
};

/**
 * @brief BQ35100 driver runtime data
 */
struct bq35100_data {
	const struct device *dev;

	/* Cached sensor readings (populated by sample_fetch) */
	uint16_t voltage_mv;
	int16_t  current_ma;
	uint16_t temperature_01k;     /* 0.1 K units */
	uint16_t internal_temp_01k;   /* 0.1 K units */
	uint32_t accumulated_cap_uah;
	uint8_t  soh_pct;
	uint16_t impedance_mohm;
	uint16_t scaled_r_mohm;
	uint16_t design_cap_mah;
	uint8_t  battery_status;
	uint8_t  battery_alert;
	uint16_t control_status;

	/* State tracking */
	bool     enabled;       /* GE pin state */
	bool     gauge_active;  /* GAUGE_START sent */

#ifdef CONFIG_CK_BQ35100_TRIGGER
	struct gpio_callback alert_cb;
	const struct sensor_trigger *alert_trigger;
	sensor_trigger_handler_t alert_handler;
	struct k_work alert_work;
#endif
};

/* ------------------------------------------------------------------ */
/* Public API                                                          */
/* ------------------------------------------------------------------ */

/**
 * @brief Enable the BQ35100 (assert GE pin)
 * @param dev Pointer to the device structure
 * @return 0 on success, negative errno on failure
 */
int bq35100_enable(const struct device *dev);

/**
 * @brief Disable the BQ35100 (deassert GE pin)
 * @param dev Pointer to the device structure
 * @return 0 on success, negative errno on failure
 */
int bq35100_disable(const struct device *dev);

/**
 * @brief Start active gauging
 * @param dev Pointer to the device structure
 * @return 0 on success, negative errno on failure
 */
int bq35100_gauge_start(const struct device *dev);

/**
 * @brief Stop gauging and wait for G_DONE
 * @param dev Pointer to the device structure
 * @return 0 on success, negative errno on failure
 */
int bq35100_gauge_stop(const struct device *dev);

/**
 * @brief Send a control subcommand
 * @param dev Pointer to the device structure
 * @param subcmd Subcommand code (e.g., BQ35100_CNTL_DEVICE_TYPE)
 * @return 0 on success, negative errno on failure
 */
int bq35100_control_cmd(const struct device *dev, uint16_t subcmd);

/**
 * @brief Send a control subcommand and read the response
 * @param dev Pointer to the device structure
 * @param subcmd Subcommand code
 * @param result Pointer to store 16-bit result
 * @return 0 on success, negative errno on failure
 */
int bq35100_control_read(const struct device *dev, uint16_t subcmd, uint16_t *result);

/**
 * @brief Unseal the device using default keys
 * @param dev Pointer to the device structure
 * @return 0 on success, negative errno on failure
 */
int bq35100_unseal(const struct device *dev);

/**
 * @brief Seal the device
 * @param dev Pointer to the device structure
 * @return 0 on success, negative errno on failure
 */
int bq35100_seal(const struct device *dev);

/**
 * @brief Read data flash
 * @param dev Pointer to the device structure
 * @param addr Data flash address (0x4000-0x43FF)
 * @param buf Buffer to store data
 * @param len Number of bytes to read (1-32)
 * @return 0 on success, negative errno on failure
 */
int bq35100_df_read(const struct device *dev, uint16_t addr, uint8_t *buf, uint8_t len);

/**
 * @brief Write data flash (device must be unsealed)
 * @param dev Pointer to the device structure
 * @param addr Data flash address
 * @param data Data to write
 * @param len Number of bytes (1-32)
 * @return 0 on success, negative errno on failure
 */
int bq35100_df_write(const struct device *dev, uint16_t addr, const uint8_t *data, uint8_t len);

/**
 * @brief Get CONTROL_STATUS register
 * @param dev Pointer to the device structure
 * @param status Pointer to store 16-bit status
 * @return 0 on success, negative errno on failure
 */
int bq35100_get_control_status(const struct device *dev, uint16_t *status);

/**
 * @brief Reset for new battery installation
 * @param dev Pointer to the device structure
 * @return 0 on success, negative errno on failure
 */
int bq35100_new_battery(const struct device *dev);

#ifdef __cplusplus
}
#endif

#endif /* COREKINECT_GAUGE_BQ35100_H_ */
