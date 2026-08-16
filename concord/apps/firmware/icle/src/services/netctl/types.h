// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Network Control Service - Types
 *
 * Ported from Helios runtime netctl module.
 */

#ifndef ICLE_SERVICES_NETCTL_TYPES_H
#define ICLE_SERVICES_NETCTL_TYPES_H

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/wifi_mgmt.h>

/*
 * Configuration defaults
 */
#ifndef CONFIG_ICLE_NETCTL_MAX_PROFILES
#define CONFIG_ICLE_NETCTL_MAX_PROFILES 4
#endif

#ifndef CONFIG_ICLE_NETCTL_PROFILE_NAME_MAX
#define CONFIG_ICLE_NETCTL_PROFILE_NAME_MAX 32
#endif

#ifndef CONFIG_ICLE_NETCTL_THREAD_STACK_SIZE
#define CONFIG_ICLE_NETCTL_THREAD_STACK_SIZE 4096
#endif

#ifndef CONFIG_ICLE_NETCTL_EVENT_QUEUE_SIZE
#define CONFIG_ICLE_NETCTL_EVENT_QUEUE_SIZE 16
#endif

#ifndef CONFIG_ICLE_NETCTL_WIFI_SCAN_MAX_RESULTS
#define CONFIG_ICLE_NETCTL_WIFI_SCAN_MAX_RESULTS 20
#endif

/*
 * Constants
 */
#define NETCTL_IPV4_ADDR_LEN 16
#define NETCTL_WIFI_SSID_MAX_LEN 33
#define NETCTL_WIFI_PSK_MAX_LEN 65

/*
 * Interface types
 */
typedef enum {
	NETCTL_IFACE_WIFI_STA,
	NETCTL_IFACE_WIFI_AP,
	NETCTL_IFACE_MAX
} netctl_iface_t;

/*
 * Per-interface states (FSM)
 */
typedef enum {
	NETCTL_STATE_DISABLED,      /* Interface not initialized */
	NETCTL_STATE_IDLE,          /* Ready but not connected */
	NETCTL_STATE_CONNECTING,    /* Connection in progress */
	NETCTL_STATE_CONNECTED,     /* Connected, IP obtained */
	NETCTL_STATE_DISCONNECTING, /* Disconnect in progress */
	NETCTL_STATE_ERROR,         /* Error state, needs reset */
	NETCTL_STATE_MAX
} netctl_state_t;

/*
 * Event types
 */
typedef enum {
	/* State changes */
	NETCTL_EVENT_STATE_CHANGED,

	/* Connection events */
	NETCTL_EVENT_CONNECTED,
	NETCTL_EVENT_DISCONNECTED,
	NETCTL_EVENT_CONNECTION_FAILED,

	/* IP events */
	NETCTL_EVENT_IP_ACQUIRED,
	NETCTL_EVENT_IP_LOST,

	/* Scan events (WiFi) */
	NETCTL_EVENT_SCAN_RESULT,
	NETCTL_EVENT_SCAN_DONE,

	/* Errors */
	NETCTL_EVENT_ERROR,

	NETCTL_EVENT_MAX
} netctl_event_type_t;

/*
 * Event data structures
 */
typedef struct {
	netctl_iface_t iface;
	netctl_state_t old_state;
	netctl_state_t new_state;
} netctl_event_state_changed_t;

typedef struct {
	netctl_iface_t iface;
	char ip_addr[NETCTL_IPV4_ADDR_LEN];
	char gateway[NETCTL_IPV4_ADDR_LEN];
	char netmask[NETCTL_IPV4_ADDR_LEN];
} netctl_event_ip_acquired_t;

typedef struct {
	char ssid[NETCTL_WIFI_SSID_MAX_LEN];
	int8_t rssi;
	uint8_t channel;
	uint8_t security;
} netctl_event_scan_result_t;

typedef struct {
	netctl_iface_t iface;
	int error_code;
	const char *message;
} netctl_event_error_t;

/*
 * Unified event structure
 */
typedef struct {
	netctl_event_type_t type;
	union {
		netctl_event_state_changed_t state_changed;
		netctl_event_ip_acquired_t ip_acquired;
		netctl_event_scan_result_t scan_result;
		netctl_event_error_t error;
	} data;
} netctl_event_t;

/*
 * WiFi credentials
 */
typedef struct {
	char ssid[NETCTL_WIFI_SSID_MAX_LEN];
	char password[NETCTL_WIFI_PSK_MAX_LEN];
	uint8_t security; /* WIFI_SECURITY_TYPE_* */
} netctl_wifi_creds_t;

/*
 * Connection profile
 */
typedef struct {
	char name[CONFIG_ICLE_NETCTL_PROFILE_NAME_MAX];
	netctl_iface_t iface;
	uint8_t priority; /* Lower = higher priority */
	union {
		netctl_wifi_creds_t wifi;
	} credentials;
} netctl_profile_t;

/*
 * Event callback type
 */
struct netctl;
typedef void (*netctl_event_cb_t)(const netctl_event_t *event, void *user_data);

/*
 * Event subscriber entry
 */
typedef struct {
	netctl_event_cb_t cb;
	void *user_data;
} netctl_subscriber_t;

/* Default if not configured */
#ifndef CONFIG_ICLE_NETCTL_MAX_SUBSCRIBERS
#define CONFIG_ICLE_NETCTL_MAX_SUBSCRIBERS 4
#endif

/*
 * WiFi scan result storage
 */
typedef struct {
	netctl_event_scan_result_t results[CONFIG_ICLE_NETCTL_WIFI_SCAN_MAX_RESULTS];
	size_t count;
	bool scan_in_progress;
	struct k_sem scan_done_sem;
} netctl_wifi_scan_t;

/*
 * Main netctl handle
 *
 * Field ordering: pointer/struct-sized types first, then arrays, then
 * smaller scalar types (uint8_t, bool) last to minimise implicit padding.
 * The compiler must not reorder struct fields; we do it explicitly here.
 */
typedef struct netctl {
	/* Pointer-sized: active profile reference */
	const netctl_profile_t *active_profile;

	/* Thread — k_thread contains pointer-sized members internally */
	struct k_thread thread;
	k_tid_t thread_id;

	/* Stack — must be a struct member via K_KERNEL_STACK_MEMBER */
	K_KERNEL_STACK_MEMBER(thread_stack, CONFIG_ICLE_NETCTL_THREAD_STACK_SIZE);

	/* Event queue struct and its backing buffer (4-byte aligned) */
	struct k_msgq event_queue;
	char __aligned(4) event_queue_buf[CONFIG_ICLE_NETCTL_EVENT_QUEUE_SIZE * sizeof(netctl_event_t)];

	/* Synchronization mutex */
	struct k_mutex lock;

	/* Event subscribers array (each entry holds two pointers) */
	netctl_subscriber_t subscribers[CONFIG_ICLE_NETCTL_MAX_SUBSCRIBERS];

	/* Profile storage */
	netctl_profile_t profiles[CONFIG_ICLE_NETCTL_MAX_PROFILES];

	/* Per-interface FSM state (enum = int32) */
	netctl_state_t iface_state[NETCTL_IFACE_MAX];

	/* WiFi-specific — WiFi structs contain pointer-sized fields */
#ifdef CONFIG_ICLE_NETCTL_WIFI
	struct net_if *wifi_iface;
	struct net_mgmt_event_callback wifi_mgmt_cb;
	struct net_mgmt_event_callback wifi_ipv4_cb;
	netctl_wifi_scan_t wifi_scan;
	struct k_sem wifi_connect_sem;
	struct k_sem wifi_disconnect_sem;
	struct k_sem wifi_ip_sem;
	struct k_mutex wifi_lock;
#endif

	/* uint8_t scalars — grouped together to avoid inter-field padding */
	uint8_t subscriber_count;
	uint8_t profile_count;

	/* bool fields last — 1-byte types cause least padding at the tail */
	bool initialized;
#ifdef CONFIG_ICLE_NETCTL_WIFI
	bool wifi_connected;
#endif

} netctl_t;

#endif /* ICLE_SERVICES_NETCTL_TYPES_H */
