// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Minimal JSON Builder
 *
 * Simple JSON serialization without external dependencies.
 */

#ifndef ICLE_JSON_BUILDER_H_
#define ICLE_JSON_BUILDER_H_

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief JSON builder context
 */
struct icle_json_builder {
	char *buffer;
	size_t buffer_size;
	size_t offset;
	bool error;
	int depth;
};

/**
 * @brief Initialize JSON builder
 *
 * @param jb JSON builder context
 * @param buffer Output buffer
 * @param buffer_size Buffer size
 */
void icle_json_builder_init(struct icle_json_builder *jb, char *buffer, size_t buffer_size);

/**
 * @brief Begin JSON object
 *
 * @param jb JSON builder context
 */
void icle_json_obj_start(struct icle_json_builder *jb);

/**
 * @brief End JSON object
 *
 * @param jb JSON builder context
 */
void icle_json_obj_end(struct icle_json_builder *jb);

/**
 * @brief Begin JSON array
 *
 * @param jb JSON builder context
 */
void icle_json_arr_start(struct icle_json_builder *jb);

/**
 * @brief End JSON array
 *
 * @param jb JSON builder context
 */
void icle_json_arr_end(struct icle_json_builder *jb);

/**
 * @brief Add string field
 *
 * @param jb JSON builder context
 * @param key Field name
 * @param value String value
 */
void icle_json_add_str(struct icle_json_builder *jb, const char *key, const char *value);

/**
 * @brief Add integer field
 *
 * @param jb JSON builder context
 * @param key Field name
 * @param value Integer value
 */
void icle_json_add_int(struct icle_json_builder *jb, const char *key, int32_t value);

/**
 * @brief Add unsigned integer field
 *
 * @param jb JSON builder context
 * @param key Field name
 * @param value Unsigned integer value
 */
void icle_json_add_uint(struct icle_json_builder *jb, const char *key, uint32_t value);

/**
 * @brief Add boolean field
 *
 * @param jb JSON builder context
 * @param key Field name
 * @param value Boolean value
 */
void icle_json_add_bool(struct icle_json_builder *jb, const char *key, bool value);

/**
 * @brief Add null field
 *
 * @param jb JSON builder context
 * @param key Field name
 */
void icle_json_add_null(struct icle_json_builder *jb, const char *key);

/**
 * @brief Add nested object start
 *
 * @param jb JSON builder context
 * @param key Field name for the object
 */
void icle_json_add_obj(struct icle_json_builder *jb, const char *key);

/**
 * @brief Add nested array start
 *
 * @param jb JSON builder context
 * @param key Field name for the array
 */
void icle_json_add_arr(struct icle_json_builder *jb, const char *key);

/**
 * @brief Add string to array (no key)
 *
 * @param jb JSON builder context
 * @param value String value
 */
void icle_json_arr_add_str(struct icle_json_builder *jb, const char *value);

/**
 * @brief Add integer to array (no key)
 *
 * @param jb JSON builder context
 * @param value Integer value
 */
void icle_json_arr_add_int(struct icle_json_builder *jb, int32_t value);

/**
 * @brief Finalize and get length
 *
 * @param jb JSON builder context
 * @return Length of JSON string, or negative on error
 */
int icle_json_builder_finish(struct icle_json_builder *jb);

/**
 * @brief Check if builder encountered an error
 *
 * @param jb JSON builder context
 * @return true if error occurred
 */
bool icle_json_builder_error(struct icle_json_builder *jb);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_JSON_BUILDER_H_ */
