// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Minimal JSON Builder Implementation
 */

#include "json_builder.h"

#include <string.h>
#include <stdio.h>

/* Internal state tracking for comma insertion */
#define MAX_DEPTH 8

static void append(struct icle_json_builder *jb, const char *str)
{
	size_t len;

	if (jb->error)
		return;

	len = strlen(str);
	if (jb->offset + len >= jb->buffer_size) {
		jb->error = true;
		return;
	}

	memcpy(jb->buffer + jb->offset, str, len);
	jb->offset += len;
	jb->buffer[jb->offset] = '\0';
}

static void append_char(struct icle_json_builder *jb, char c)
{
	if (jb->error)
		return;

	if (jb->offset + 1 >= jb->buffer_size) {
		jb->error = true;
		return;
	}

	jb->buffer[jb->offset++] = c;
	jb->buffer[jb->offset] = '\0';
}

static void append_escaped_string(struct icle_json_builder *jb, const char *str)
{
	append_char(jb, '"');

	while (*str && !jb->error) {
		switch (*str) {
		case '"':
			append(jb, "\\\"");
			break;
		case '\\':
			append(jb, "\\\\");
			break;
		case '\n':
			append(jb, "\\n");
			break;
		case '\r':
			append(jb, "\\r");
			break;
		case '\t':
			append(jb, "\\t");
			break;
		default:
			if ((unsigned char)*str < 0x20) {
				/* Control character - escape as hex */
				char hex[7];

				/* Buffer is exactly sized for \uXXXX + NUL; truncation impossible */
				(void)snprintf(hex, sizeof(hex), "\\u%04x", (unsigned char)*str);
				append(jb, hex);
			} else {
				append_char(jb, *str);
			}
			break;
		}
		str++;
	}

	append_char(jb, '"');
}

void icle_json_builder_init(struct icle_json_builder *jb, char *buffer, size_t buffer_size)
{
	jb->buffer = buffer;
	jb->buffer_size = buffer_size;
	jb->offset = 0;
	jb->error = false;
	jb->depth = 0;

	if (buffer_size > 0)
		buffer[0] = '\0';
}

void icle_json_obj_start(struct icle_json_builder *jb)
{
	append_char(jb, '{');
	jb->depth++;
}

void icle_json_obj_end(struct icle_json_builder *jb)
{
	/* Remove trailing comma if present */
	if (jb->offset > 0 && jb->buffer[jb->offset - 1] == ',') {
		jb->offset--;
		jb->buffer[jb->offset] = '\0';
	}

	append_char(jb, '}');
	jb->depth--;

	/* Add comma for next sibling */
	if (jb->depth > 0)
		append_char(jb, ',');
}

void icle_json_arr_start(struct icle_json_builder *jb)
{
	append_char(jb, '[');
	jb->depth++;
}

void icle_json_arr_end(struct icle_json_builder *jb)
{
	/* Remove trailing comma if present */
	if (jb->offset > 0 && jb->buffer[jb->offset - 1] == ',') {
		jb->offset--;
		jb->buffer[jb->offset] = '\0';
	}

	append_char(jb, ']');
	jb->depth--;

	/* Add comma for next sibling */
	if (jb->depth > 0)
		append_char(jb, ',');
}

void icle_json_add_str(struct icle_json_builder *jb, const char *key, const char *value)
{
	append_escaped_string(jb, key);
	append_char(jb, ':');
	if (value != NULL)
		append_escaped_string(jb, value);
	else
		append(jb, "null");

	append_char(jb, ',');
}

void icle_json_add_int(struct icle_json_builder *jb, const char *key, int32_t value)
{
	char num[16];

	/* Buffer is 16 bytes; INT32_MIN is 11 chars — truncation impossible */
	(void)snprintf(num, sizeof(num), "%d", value);

	append_escaped_string(jb, key);
	append_char(jb, ':');
	append(jb, num);
	append_char(jb, ',');
}

void icle_json_add_uint(struct icle_json_builder *jb, const char *key, uint32_t value)
{
	char num[16];

	/* Buffer is 16 bytes; UINT32_MAX is 10 chars — truncation impossible */
	(void)snprintf(num, sizeof(num), "%u", value);

	append_escaped_string(jb, key);
	append_char(jb, ':');
	append(jb, num);
	append_char(jb, ',');
}

void icle_json_add_bool(struct icle_json_builder *jb, const char *key, bool value)
{
	append_escaped_string(jb, key);
	append_char(jb, ':');
	append(jb, value ? "true" : "false");
	append_char(jb, ',');
}

void icle_json_add_null(struct icle_json_builder *jb, const char *key)
{
	append_escaped_string(jb, key);
	append_char(jb, ':');
	append(jb, "null");
	append_char(jb, ',');
}

void icle_json_add_obj(struct icle_json_builder *jb, const char *key)
{
	append_escaped_string(jb, key);
	append_char(jb, ':');
	icle_json_obj_start(jb);
}

void icle_json_add_arr(struct icle_json_builder *jb, const char *key)
{
	append_escaped_string(jb, key);
	append_char(jb, ':');
	icle_json_arr_start(jb);
}

void icle_json_arr_add_str(struct icle_json_builder *jb, const char *value)
{
	if (value != NULL)
		append_escaped_string(jb, value);
	else
		append(jb, "null");

	append_char(jb, ',');
}

void icle_json_arr_add_int(struct icle_json_builder *jb, int32_t value)
{
	char num[16];

	/* Buffer is 16 bytes; INT32_MIN is 11 chars — truncation impossible */
	(void)snprintf(num, sizeof(num), "%d", value);
	append(jb, num);
	append_char(jb, ',');
}

int icle_json_builder_finish(struct icle_json_builder *jb)
{
	/* Remove trailing comma if present */
	if (jb->offset > 0 && jb->buffer[jb->offset - 1] == ',') {
		jb->offset--;
		jb->buffer[jb->offset] = '\0';
	}

	if (jb->error)
		return -1;

	return (int)jb->offset;
}

bool icle_json_builder_error(struct icle_json_builder *jb)
{
	return jb->error;
}
