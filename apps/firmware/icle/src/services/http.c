/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE HTTP Client Implementation
 *
 * HTTP client for syncing logs to Concord backend.
 * Uses Zephyr BSD sockets with programmatic thread creation.
 */

#include "services/http.h"
#include "hal/storage.h"
#include "net/wifi.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_http, CONFIG_LOG_DEFAULT_LEVEL);

#include <zephyr/net/socket.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/net/dns_resolve.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* Configuration */
#define HTTP_DEFAULT_TIMEOUT_MS    30000
#define HTTP_DEFAULT_PORT          80
#define HTTP_RECV_BUFFER_SIZE      1024
#define HTTP_SEND_BUFFER_SIZE      512
#define HTTP_MAX_URL_LEN           128
#define HTTP_MAX_DEVICE_ID_LEN     32
#define HTTP_MAX_API_KEY_LEN       64
#define HTTP_MAX_RETRIES           3
#define HTTP_INITIAL_BACKOFF_MS    1000
#define HTTP_MAX_BACKOFF_MS        30000
#define HTTP_FILE_CHUNK_SIZE       512

/* HTTP sync thread configuration */
#define HTTP_SYNC_THREAD_STACK_SIZE 4096
#define HTTP_SYNC_THREAD_PRIORITY   6

/* Module state */
struct icle_http_context {
	/* Configuration */
	char base_url[HTTP_MAX_URL_LEN];
	char device_id[HTTP_MAX_DEVICE_ID_LEN];
	char api_key[HTTP_MAX_API_KEY_LEN];
	uint32_t timeout_ms;
	uint8_t max_retries;
	uint32_t backoff_ms;

	/* Parsed URL components */
	char host[64];
	uint16_t port;
	char path[64];
	bool use_tls;

	/* State */
	enum icle_http_state state;
	bool initialized;
	bool sync_in_progress;
	bool sync_cancel_requested;

	/* Current sync operation */
	char current_file[64];
	uint32_t current_file_size;
	uint32_t current_bytes_sent;

	/* Synchronization - created programmatically */
	struct k_mutex mutex;
	struct k_sem http_complete_sem;

	/* Callbacks */
	icle_sync_progress_cb_t progress_cb;
	void *progress_user_data;
	icle_sync_complete_cb_t complete_cb;
	void *complete_user_data;

	/* HTTP sync thread */
	struct k_thread sync_thread;
	k_thread_stack_t *sync_stack;
	bool sync_thread_running;
	struct k_sem sync_request_sem;

	/* Buffers */
	char recv_buffer[HTTP_RECV_BUFFER_SIZE];
	char send_buffer[HTTP_SEND_BUFFER_SIZE];

	/* Last response */
	struct icle_http_response last_response;
};

static struct icle_http_context http_ctx;

/* Thread stack allocated at init */
static K_THREAD_STACK_DEFINE(http_sync_stack, HTTP_SYNC_THREAD_STACK_SIZE);

/* Forward declarations */
static int http_connect(int *sock);
static int http_send_request(int sock, const char *method, const char *path,
			     const char *content_type, const void *body,
			     size_t body_len);
static int http_recv_response(int sock, struct icle_http_response *response,
			      char *body_buffer, size_t buffer_size);
static int http_parse_url(const char *url);
static void http_sync_thread_fn(void *p1, void *p2, void *p3);
static int http_do_request_with_retry(const char *method, const char *path,
				      const char *content_type,
				      const void *body, size_t body_len,
				      char *response_body, size_t response_size);

/**
 * @brief State name lookup table
 */
static const char *state_names[] = {
	[ICLE_HTTP_STATE_IDLE] = "idle",
	[ICLE_HTTP_STATE_CONNECTING] = "connecting",
	[ICLE_HTTP_STATE_SENDING] = "sending",
	[ICLE_HTTP_STATE_RECEIVING] = "receiving",
	[ICLE_HTTP_STATE_ERROR] = "error",
};

int icle_http_init(void)
{
	if (http_ctx.initialized) {
		return 0;
	}

	memset(&http_ctx, 0, sizeof(http_ctx));

	/* Initialize synchronization primitives programmatically */
	k_mutex_init(&http_ctx.mutex);
	k_sem_init(&http_ctx.http_complete_sem, 0, 1);
	k_sem_init(&http_ctx.sync_request_sem, 0, 1);

	/* Set defaults */
	http_ctx.timeout_ms = HTTP_DEFAULT_TIMEOUT_MS;
	http_ctx.max_retries = HTTP_MAX_RETRIES;
	http_ctx.backoff_ms = HTTP_INITIAL_BACKOFF_MS;
	http_ctx.port = HTTP_DEFAULT_PORT;
	http_ctx.state = ICLE_HTTP_STATE_IDLE;

	/* Create sync thread */
	http_ctx.sync_stack = http_sync_stack;
	k_thread_create(&http_ctx.sync_thread, http_ctx.sync_stack,
			HTTP_SYNC_THREAD_STACK_SIZE,
			http_sync_thread_fn, NULL, NULL, NULL,
			HTTP_SYNC_THREAD_PRIORITY, 0, K_NO_WAIT);
	k_thread_name_set(&http_ctx.sync_thread, "http_sync");
	http_ctx.sync_thread_running = true;

	http_ctx.initialized = true;
	LOG_INF("HTTP client initialized");

	return 0;
}

int icle_http_deinit(void)
{
	if (!http_ctx.initialized) {
		return 0;
	}

	/* Cancel any pending sync */
	icle_http_cancel_sync();

	/* Stop sync thread */
	http_ctx.sync_thread_running = false;
	k_sem_give(&http_ctx.sync_request_sem);
	k_thread_join(&http_ctx.sync_thread, K_FOREVER);

	http_ctx.initialized = false;
	LOG_INF("HTTP client deinitialized");

	return 0;
}

int icle_http_set_base_url(const char *base_url)
{
	int ret;

	if (!base_url || strlen(base_url) >= HTTP_MAX_URL_LEN) {
		return -EINVAL;
	}

	k_mutex_lock(&http_ctx.mutex, K_FOREVER);

	strncpy(http_ctx.base_url, base_url, sizeof(http_ctx.base_url) - 1);
	http_ctx.base_url[sizeof(http_ctx.base_url) - 1] = '\0';

	ret = http_parse_url(base_url);
	if (ret < 0) {
		LOG_ERR("Failed to parse URL: %d", ret);
		http_ctx.base_url[0] = '\0';
	} else {
		LOG_INF("Base URL set: %s (host=%s, port=%d)",
			http_ctx.base_url, http_ctx.host, http_ctx.port);
	}

	k_mutex_unlock(&http_ctx.mutex);
	return ret;
}

int icle_http_set_device_id(const char *device_id)
{
	if (!device_id || strlen(device_id) >= HTTP_MAX_DEVICE_ID_LEN) {
		return -EINVAL;
	}

	k_mutex_lock(&http_ctx.mutex, K_FOREVER);
	strncpy(http_ctx.device_id, device_id, sizeof(http_ctx.device_id) - 1);
	http_ctx.device_id[sizeof(http_ctx.device_id) - 1] = '\0';
	k_mutex_unlock(&http_ctx.mutex);

	LOG_INF("Device ID set: %s", device_id);
	return 0;
}

int icle_http_set_api_key(const char *api_key)
{
	if (!api_key || strlen(api_key) >= HTTP_MAX_API_KEY_LEN) {
		return -EINVAL;
	}

	k_mutex_lock(&http_ctx.mutex, K_FOREVER);
	strncpy(http_ctx.api_key, api_key, sizeof(http_ctx.api_key) - 1);
	http_ctx.api_key[sizeof(http_ctx.api_key) - 1] = '\0';
	k_mutex_unlock(&http_ctx.mutex);

	LOG_INF("API key configured");
	return 0;
}

/**
 * @brief Parse URL into components
 */
static int http_parse_url(const char *url)
{
	const char *p = url;
	const char *host_start;
	const char *port_start = NULL;
	const char *path_start;
	size_t host_len;

	/* Check scheme */
	if (strncmp(p, "https://", 8) == 0) {
		http_ctx.use_tls = true;
		http_ctx.port = 443;
		p += 8;
	} else if (strncmp(p, "http://", 7) == 0) {
		http_ctx.use_tls = false;
		http_ctx.port = 80;
		p += 7;
	} else {
		/* Assume http if no scheme */
		http_ctx.use_tls = false;
		http_ctx.port = 80;
	}

	host_start = p;

	/* Find end of host (port or path) */
	while (*p && *p != ':' && *p != '/') {
		p++;
	}
	host_len = p - host_start;

	if (host_len == 0 || host_len >= sizeof(http_ctx.host)) {
		return -EINVAL;
	}

	memcpy(http_ctx.host, host_start, host_len);
	http_ctx.host[host_len] = '\0';

	/* Check for port */
	if (*p == ':') {
		p++;
		port_start = p;
		while (*p && *p != '/') {
			p++;
		}
		http_ctx.port = (uint16_t)atoi(port_start);
	}

	/* Get path */
	if (*p == '/') {
		path_start = p;
		strncpy(http_ctx.path, path_start, sizeof(http_ctx.path) - 1);
		http_ctx.path[sizeof(http_ctx.path) - 1] = '\0';
	} else {
		strcpy(http_ctx.path, "/");
	}

	return 0;
}

/**
 * @brief Establish TCP connection to server
 */
static int http_connect(int *sock)
{
	struct sockaddr_in addr;
	int ret;
	int fd;

	fd = zsock_socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
	if (fd < 0) {
		LOG_ERR("Failed to create socket: %d", errno);
		return -errno;
	}

	/* Set socket timeout */
	struct timeval tv;
	tv.tv_sec = http_ctx.timeout_ms / 1000;
	tv.tv_usec = (http_ctx.timeout_ms % 1000) * 1000;

	ret = zsock_setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
	if (ret < 0) {
		LOG_WRN("Failed to set receive timeout: %d", errno);
	}

	ret = zsock_setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
	if (ret < 0) {
		LOG_WRN("Failed to set send timeout: %d", errno);
	}

	/* Resolve hostname using DNS or direct IP */
	memset(&addr, 0, sizeof(addr));
	addr.sin_family = AF_INET;
	addr.sin_port = htons(http_ctx.port);

	ret = zsock_inet_pton(AF_INET, http_ctx.host, &addr.sin_addr);
	if (ret != 1) {
		/* Try DNS resolution */
		struct zsock_addrinfo hints = {0};
		struct zsock_addrinfo *result = NULL;

		hints.ai_family = AF_INET;
		hints.ai_socktype = SOCK_STREAM;

		ret = zsock_getaddrinfo(http_ctx.host, NULL, &hints, &result);
		if (ret != 0 || result == NULL) {
			LOG_ERR("DNS resolution failed for %s: %d",
				http_ctx.host, ret);
			zsock_close(fd);
			return -EHOSTUNREACH;
		}

		memcpy(&addr.sin_addr,
		       &((struct sockaddr_in *)result->ai_addr)->sin_addr,
		       sizeof(addr.sin_addr));
		zsock_freeaddrinfo(result);
	}

	http_ctx.state = ICLE_HTTP_STATE_CONNECTING;

	ret = zsock_connect(fd, (struct sockaddr *)&addr, sizeof(addr));
	if (ret < 0) {
		LOG_ERR("Failed to connect to %s:%d: %d",
			http_ctx.host, http_ctx.port, errno);
		zsock_close(fd);
		http_ctx.state = ICLE_HTTP_STATE_ERROR;
		return -errno;
	}

	LOG_DBG("Connected to %s:%d", http_ctx.host, http_ctx.port);
	*sock = fd;
	return 0;
}

/**
 * @brief Send HTTP request
 */
static int http_send_request(int sock, const char *method, const char *path,
			     const char *content_type, const void *body,
			     size_t body_len)
{
	int ret;
	int len;

	http_ctx.state = ICLE_HTTP_STATE_SENDING;

	/* Build request headers */
	len = snprintf(http_ctx.send_buffer, sizeof(http_ctx.send_buffer),
		       "%s %s%s HTTP/1.1\r\n"
		       "Host: %s:%d\r\n"
		       "User-Agent: ICLE/1.0\r\n"
		       "Connection: close\r\n",
		       method, http_ctx.path, path,
		       http_ctx.host, http_ctx.port);

	if (len < 0 || len >= sizeof(http_ctx.send_buffer)) {
		return -ENOMEM;
	}

	/* Add device ID header if set */
	if (http_ctx.device_id[0] != '\0') {
		len += snprintf(http_ctx.send_buffer + len,
				sizeof(http_ctx.send_buffer) - len,
				"X-Device-ID: %s\r\n", http_ctx.device_id);
	}

	/* Add API key header if set */
	if (http_ctx.api_key[0] != '\0') {
		len += snprintf(http_ctx.send_buffer + len,
				sizeof(http_ctx.send_buffer) - len,
				"Authorization: Bearer %s\r\n", http_ctx.api_key);
	}

	/* Add content headers if body present */
	if (body && body_len > 0) {
		if (content_type) {
			len += snprintf(http_ctx.send_buffer + len,
					sizeof(http_ctx.send_buffer) - len,
					"Content-Type: %s\r\n", content_type);
		}
		len += snprintf(http_ctx.send_buffer + len,
				sizeof(http_ctx.send_buffer) - len,
				"Content-Length: %zu\r\n", body_len);
	}

	/* End headers */
	len += snprintf(http_ctx.send_buffer + len,
			sizeof(http_ctx.send_buffer) - len, "\r\n");

	/* Send headers */
	ret = zsock_send(sock, http_ctx.send_buffer, len, 0);
	if (ret < 0) {
		LOG_ERR("Failed to send headers: %d", errno);
		return -errno;
	}

	/* Send body if present */
	if (body && body_len > 0) {
		ret = zsock_send(sock, body, body_len, 0);
		if (ret < 0) {
			LOG_ERR("Failed to send body: %d", errno);
			return -errno;
		}
	}

	LOG_DBG("Request sent: %s %s%s (%zu bytes body)",
		method, http_ctx.path, path, body_len);

	return 0;
}

/**
 * @brief Receive and parse HTTP response
 */
static int http_recv_response(int sock, struct icle_http_response *response,
			      char *body_buffer, size_t buffer_size)
{
	int ret;
	size_t total_received = 0;
	char *header_end;
	char *status_line;
	char *content_length_str;
	bool headers_parsed = false;

	http_ctx.state = ICLE_HTTP_STATE_RECEIVING;

	memset(response, 0, sizeof(*response));
	memset(http_ctx.recv_buffer, 0, sizeof(http_ctx.recv_buffer));

	/* Receive data */
	while (total_received < sizeof(http_ctx.recv_buffer) - 1) {
		ret = zsock_recv(sock, http_ctx.recv_buffer + total_received,
				 sizeof(http_ctx.recv_buffer) - 1 - total_received,
				 0);
		if (ret <= 0) {
			if (ret == 0) {
				/* Connection closed */
				break;
			}
			if (errno == EAGAIN || errno == EWOULDBLOCK) {
				/* Timeout */
				if (total_received > 0) {
					break;
				}
				LOG_ERR("Receive timeout");
				return -ETIMEDOUT;
			}
			LOG_ERR("Receive error: %d", errno);
			return -errno;
		}

		total_received += ret;

		/* Check for end of headers */
		if (!headers_parsed) {
			header_end = strstr(http_ctx.recv_buffer, "\r\n\r\n");
			if (header_end) {
				headers_parsed = true;
			}
		}

		/* If we have headers and some body, we might be done */
		if (headers_parsed && response->content_length > 0) {
			size_t body_offset = header_end + 4 - http_ctx.recv_buffer;
			size_t body_received = total_received - body_offset;
			if (body_received >= response->content_length) {
				break;
			}
		}
	}

	http_ctx.recv_buffer[total_received] = '\0';

	/* Parse status line */
	status_line = http_ctx.recv_buffer;
	if (strncmp(status_line, "HTTP/1.", 7) == 0) {
		/* Skip to status code */
		char *code_start = strchr(status_line, ' ');
		if (code_start) {
			response->status_code = atoi(code_start + 1);
		}
	}

	/* Parse Content-Length */
	content_length_str = strstr(http_ctx.recv_buffer, "Content-Length:");
	if (!content_length_str) {
		content_length_str = strstr(http_ctx.recv_buffer, "content-length:");
	}
	if (content_length_str) {
		response->content_length = atoi(content_length_str + 15);
	}

	/* Parse Content-Type */
	char *content_type_str = strstr(http_ctx.recv_buffer, "Content-Type:");
	if (!content_type_str) {
		content_type_str = strstr(http_ctx.recv_buffer, "content-type:");
	}
	if (content_type_str) {
		content_type_str += 13;
		while (*content_type_str == ' ') content_type_str++;
		char *end = strstr(content_type_str, "\r\n");
		if (end) {
			size_t len = end - content_type_str;
			if (len >= sizeof(response->content_type)) {
				len = sizeof(response->content_type) - 1;
			}
			memcpy(response->content_type, content_type_str, len);
			response->content_type[len] = '\0';
		}
	}

	/* Copy body to output buffer if provided */
	if (body_buffer && buffer_size > 0) {
		header_end = strstr(http_ctx.recv_buffer, "\r\n\r\n");
		if (header_end) {
			char *body_start = header_end + 4;
			size_t body_len = total_received - (body_start - http_ctx.recv_buffer);
			if (body_len > buffer_size - 1) {
				body_len = buffer_size - 1;
			}
			memcpy(body_buffer, body_start, body_len);
			body_buffer[body_len] = '\0';
			response->body_received = body_len;
		}
	}

	LOG_DBG("Response: %d, Content-Length: %zu",
		response->status_code, response->content_length);

	http_ctx.state = ICLE_HTTP_STATE_IDLE;
	return 0;
}

/**
 * @brief Perform HTTP request with retry logic
 */
static int http_do_request_with_retry(const char *method, const char *path,
				      const char *content_type,
				      const void *body, size_t body_len,
				      char *response_body, size_t response_size)
{
	int ret;
	int sock;
	int attempts = 0;
	uint32_t backoff = http_ctx.backoff_ms;
	struct icle_http_response response;

	while (attempts <= http_ctx.max_retries) {
		attempts++;

		ret = http_connect(&sock);
		if (ret < 0) {
			LOG_WRN("Connect failed (attempt %d/%d): %d",
				attempts, http_ctx.max_retries + 1, ret);
			goto retry;
		}

		ret = http_send_request(sock, method, path, content_type,
					body, body_len);
		if (ret < 0) {
			zsock_close(sock);
			LOG_WRN("Send failed (attempt %d/%d): %d",
				attempts, http_ctx.max_retries + 1, ret);
			goto retry;
		}

		ret = http_recv_response(sock, &response, response_body,
					 response_size);
		zsock_close(sock);

		if (ret < 0) {
			LOG_WRN("Receive failed (attempt %d/%d): %d",
				attempts, http_ctx.max_retries + 1, ret);
			goto retry;
		}

		/* Store last response */
		memcpy(&http_ctx.last_response, &response, sizeof(response));

		/* Check for server errors (5xx) - retry */
		if (response.status_code >= 500 && response.status_code < 600) {
			LOG_WRN("Server error %d (attempt %d/%d)",
				response.status_code, attempts,
				http_ctx.max_retries + 1);
			goto retry;
		}

		/* Success or client error (don't retry 4xx) */
		if (response.status_code >= 200 && response.status_code < 300) {
			return 0;
		}

		/* Client error - don't retry */
		LOG_ERR("HTTP error: %d", response.status_code);
		return response.status_code;

retry:
		if (attempts <= http_ctx.max_retries) {
			LOG_INF("Retrying in %d ms...", backoff);
			/* Use k_busy_wait for short delays since k_sleep
			 * with timeouts hangs on this ESP32. Cap at 5s. */
			uint32_t wait_ms = MIN(backoff, 5000);
			k_busy_wait(wait_ms * 1000);
			backoff = MIN(backoff * 2, HTTP_MAX_BACKOFF_MS);
		}
	}

	http_ctx.state = ICLE_HTTP_STATE_ERROR;
	return -ETIMEDOUT;
}

bool icle_http_is_syncing(void)
{
	return http_ctx.sync_in_progress;
}

int icle_http_cancel_sync(void)
{
	k_mutex_lock(&http_ctx.mutex, K_FOREVER);

	if (!http_ctx.sync_in_progress) {
		k_mutex_unlock(&http_ctx.mutex);
		return -ENOENT;
	}

	http_ctx.sync_cancel_requested = true;
	k_mutex_unlock(&http_ctx.mutex);

	LOG_INF("Sync cancel requested");
	return 0;
}

enum icle_http_state icle_http_get_state(void)
{
	return http_ctx.state;
}

void icle_http_set_timeout(uint32_t timeout_ms)
{
	k_mutex_lock(&http_ctx.mutex, K_FOREVER);
	http_ctx.timeout_ms = timeout_ms;
	k_mutex_unlock(&http_ctx.mutex);
}

void icle_http_set_retry_config(uint8_t max_retries, uint32_t backoff_ms)
{
	k_mutex_lock(&http_ctx.mutex, K_FOREVER);
	http_ctx.max_retries = max_retries;
	http_ctx.backoff_ms = backoff_ms;
	k_mutex_unlock(&http_ctx.mutex);
}

const char *icle_http_state_name(enum icle_http_state state)
{
	if (state >= ARRAY_SIZE(state_names)) {
		return "unknown";
	}
	return state_names[state];
}

int icle_http_ping(uint32_t timeout_ms)
{
	int ret;
	int sock;
	struct icle_http_response response;
	uint32_t saved_timeout;

	if (!http_ctx.initialized) {
		return -ENODEV;
	}

	saved_timeout = http_ctx.timeout_ms;
	http_ctx.timeout_ms = timeout_ms;

	ret = http_connect(&sock);
	if (ret < 0) {
		http_ctx.timeout_ms = saved_timeout;
		return ret;
	}

	ret = http_send_request(sock, "GET", "/api/health", NULL, NULL, 0);
	if (ret < 0) {
		zsock_close(sock);
		http_ctx.timeout_ms = saved_timeout;
		return ret;
	}

	ret = http_recv_response(sock, &response, NULL, 0);
	zsock_close(sock);

	http_ctx.timeout_ms = saved_timeout;

	if (ret < 0) {
		return ret;
	}

	if (response.status_code >= 200 && response.status_code < 300) {
		return 0;
	}

	return -EIO;
}

/**
 * @brief HTTP sync thread - processes async file uploads
 */
static void http_sync_thread_fn(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	LOG_INF("HTTP sync thread started");

	while (http_ctx.sync_thread_running) {
		/* Wait for sync request */
		int ret = k_sem_take(&http_ctx.sync_request_sem, K_FOREVER);
		if (ret < 0) {
			continue;
		}

		if (!http_ctx.sync_thread_running) {
			break;
		}

		/* Check if we have a file to sync */
		k_mutex_lock(&http_ctx.mutex, K_FOREVER);
		char filename[64];
		if (http_ctx.current_file[0] != '\0') {
			strncpy(filename, http_ctx.current_file, sizeof(filename) - 1);
			filename[sizeof(filename) - 1] = '\0';
		} else {
			k_mutex_unlock(&http_ctx.mutex);
			continue;
		}
		k_mutex_unlock(&http_ctx.mutex);

		/* Perform sync */
		LOG_INF("Async sync starting: %s", filename);
		/* File sync would be implemented here */
	}

	LOG_INF("HTTP sync thread exiting");
}
