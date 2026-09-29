/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "m1_conn_param_experiment.h"

#define NODE_A_CONN_PARAM_COMMAND_PREFIX "conn_param_request="
#define NODE_A_CONN_PARAM_TRANSACTION_PREFIX "conn_param_request tx="
#define NODE_A_CONN_PARAM_HELLO_PREFIX "HELLO session="
#define NODE_A_CONN_PARAM_SESSION_COMMAND_PREFIX "SET session="
#define NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH 16U

static bool nonce_is_valid(const char *nonce, size_t length)
{
	if ((nonce == NULL) || (length != NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH)) {
		return false;
	}
	for (size_t index = 0U; index < length; index++) {
		if (!((nonce[index] >= '0' && nonce[index] <= '9') ||
		      (nonce[index] >= 'a' && nonce[index] <= 'f'))) {
			return false;
		}
	}
	return true;
}

static bool mode_is_valid(enum node_a_conn_param_request_mode mode)
{
	return mode == NODE_A_CONN_PARAM_REQUEST_OFF ||
		mode == NODE_A_CONN_PARAM_REQUEST_ON;
}

int node_a_conn_param_experiment_parse_command(
	const char *command, size_t command_length,
	enum node_a_conn_param_request_mode *mode)
{
	static const char off_value[] = "OFF";
	static const char on_value[] = "ON";
	const size_t prefix_length = sizeof(NODE_A_CONN_PARAM_COMMAND_PREFIX) - 1U;
	const char *value;
	size_t value_length;

	if ((command == NULL) || (mode == NULL) ||
	    (command_length < prefix_length) ||
	    (memcmp(command, NODE_A_CONN_PARAM_COMMAND_PREFIX,
		    prefix_length) != 0)) {
		return -EINVAL;
	}

	value = &command[prefix_length];
	value_length = command_length - prefix_length;
	if ((value_length == sizeof(off_value) - 1U) &&
	    (memcmp(value, off_value, sizeof(off_value) - 1U) == 0)) {
		*mode = NODE_A_CONN_PARAM_REQUEST_OFF;
		return 0;
	}
	if ((value_length == sizeof(on_value) - 1U) &&
	    (memcmp(value, on_value, sizeof(on_value) - 1U) == 0)) {
		*mode = NODE_A_CONN_PARAM_REQUEST_ON;
		return 0;
	}

	return -EINVAL;
}

int node_a_conn_param_experiment_parse_transaction_command(
	const char *command, size_t command_length,
	struct node_a_conn_param_experiment_request *request)
{
	static const char mode_separator[] = " mode=";
	static const char off_value[] = "OFF";
	static const char on_value[] = "ON";
	const size_t prefix_length =
		sizeof(NODE_A_CONN_PARAM_TRANSACTION_PREFIX) - 1U;
	const size_t separator_length = sizeof(mode_separator) - 1U;
	struct node_a_conn_param_experiment_request parsed = {0};
	size_t index = prefix_length;
	size_t mode_length;

	if ((command == NULL) || (request == NULL) ||
	    (command_length <= prefix_length) ||
	    (memcmp(command, NODE_A_CONN_PARAM_TRANSACTION_PREFIX,
		    prefix_length) != 0)) {
		return -EINVAL;
	}

	if ((command[index] < '0') || (command[index] > '9')) {
		return -EINVAL;
	}
	while ((index < command_length) &&
	       (command[index] >= '0') && (command[index] <= '9')) {
		const uint32_t digit = (uint32_t)(command[index] - '0');

		if (parsed.transaction_id > (UINT32_MAX - digit) / 10U) {
			return -EINVAL;
		}
		parsed.transaction_id = parsed.transaction_id * 10U + digit;
		index++;
	}
	if ((parsed.transaction_id == 0U) ||
	    (command_length - index <= separator_length) ||
	    (memcmp(&command[index], mode_separator, separator_length) != 0)) {
		return -EINVAL;
	}

	index += separator_length;
	mode_length = command_length - index;
	if ((mode_length == sizeof(off_value) - 1U) &&
	    (memcmp(&command[index], off_value, sizeof(off_value) - 1U) == 0)) {
		parsed.mode = NODE_A_CONN_PARAM_REQUEST_OFF;
	} else if ((mode_length == sizeof(on_value) - 1U) &&
		   (memcmp(&command[index], on_value,
			   sizeof(on_value) - 1U) == 0)) {
		parsed.mode = NODE_A_CONN_PARAM_REQUEST_ON;
	} else {
		return -EINVAL;
	}

	*request = parsed;
	return 0;
}

int node_a_conn_param_experiment_accept_hello(
	struct node_a_conn_param_control_session *session,
	const char *command, size_t command_length)
{
	static const char prefix[] = NODE_A_CONN_PARAM_HELLO_PREFIX;
	const size_t prefix_length = sizeof(prefix) - 1U;
	char nonce[NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH + 1U];

	if ((session == NULL) || (command == NULL) ||
	    (command_length != prefix_length +
			NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH) ||
	    (memcmp(command, prefix, prefix_length) != 0)) {
		return -EINVAL;
	}
	if (!nonce_is_valid(&command[prefix_length],
			    NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH)) {
		return -EINVAL;
	}
	memcpy(nonce, &command[prefix_length],
	       NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH);
	nonce[NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH] = '\0';
	memcpy(session->nonce, nonce, sizeof(nonce));
	session->active = true;
	session->last_transaction_id = 0U;
	return 0;
}

int node_a_conn_param_experiment_parse_session_command(
	const char *command, size_t command_length,
	struct node_a_conn_param_experiment_request *request)
{
	static const char tx_separator[] = " tx=";
	static const char mode_separator[] = " mode=";
	static const char off_value[] = "OFF";
	static const char on_value[] = "ON";
	const size_t prefix_length =
		sizeof(NODE_A_CONN_PARAM_SESSION_COMMAND_PREFIX) - 1U;
	const size_t tx_separator_length = sizeof(tx_separator) - 1U;
	const size_t mode_separator_length = sizeof(mode_separator) - 1U;
	struct node_a_conn_param_experiment_request parsed = {0};
	size_t index = prefix_length;
	size_t mode_length;

	if ((command == NULL) || (request == NULL) ||
	    (command_length <= prefix_length +
			NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH) ||
	    (memcmp(command, NODE_A_CONN_PARAM_SESSION_COMMAND_PREFIX,
		    prefix_length) != 0)) {
		return -EINVAL;
	}
	if (!nonce_is_valid(&command[index],
			    NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH)) {
		return -EINVAL;
	}
	memcpy(parsed.session_nonce, &command[index],
	       NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH);
	parsed.session_nonce[NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH] = '\0';
	index += NODE_A_CONN_PARAM_SESSION_NONCE_LENGTH;
	if ((command_length - index <= tx_separator_length) ||
	    (memcmp(&command[index], tx_separator, tx_separator_length) != 0)) {
		return -EINVAL;
	}
	index += tx_separator_length;
	if ((index >= command_length) || (command[index] < '0') ||
	    (command[index] > '9')) {
		return -EINVAL;
	}
	while ((index < command_length) && (command[index] >= '0') &&
	       (command[index] <= '9')) {
		const uint32_t digit = (uint32_t)(command[index] - '0');

		if (parsed.transaction_id > (UINT32_MAX - digit) / 10U) {
			return -EINVAL;
		}
		parsed.transaction_id = parsed.transaction_id * 10U + digit;
		index++;
	}
	if ((parsed.transaction_id == 0U) ||
	    (command_length - index <= mode_separator_length) ||
	    (memcmp(&command[index], mode_separator,
		    mode_separator_length) != 0)) {
		return -EINVAL;
	}
	index += mode_separator_length;
	mode_length = command_length - index;
	if ((mode_length == sizeof(off_value) - 1U) &&
	    (memcmp(&command[index], off_value, sizeof(off_value) - 1U) == 0)) {
		parsed.mode = NODE_A_CONN_PARAM_REQUEST_OFF;
	} else if ((mode_length == sizeof(on_value) - 1U) &&
		   (memcmp(&command[index], on_value,
			   sizeof(on_value) - 1U) == 0)) {
		parsed.mode = NODE_A_CONN_PARAM_REQUEST_ON;
	} else {
		return -EINVAL;
	}

	*request = parsed;
	return 0;
}

bool node_a_conn_param_experiment_session_matches(
	const struct node_a_conn_param_control_session *session,
	const struct node_a_conn_param_experiment_request *request)
{
	return (session != NULL) && (request != NULL) && session->active &&
		(strcmp(session->nonce, request->session_nonce) == 0);
}

int node_a_conn_param_experiment_set_mode(
	enum node_a_conn_param_request_mode *current_mode,
	enum node_a_conn_param_request_mode requested_mode, bool connected)
{
	if ((current_mode == NULL) || !mode_is_valid(requested_mode)) {
		return -EINVAL;
	}
	if (connected) {
		return -EBUSY;
	}
	*current_mode = requested_mode;
	return 0;
}

int node_a_conn_param_experiment_on_connect(
	enum node_a_conn_param_request_mode mode, void *connection,
	node_a_conn_param_update_request_fn request_update, void *context,
	bool *request_invoked)
{
	if ((request_invoked == NULL) || !mode_is_valid(mode)) {
		return -EINVAL;
	}
	*request_invoked = false;
	if (mode == NODE_A_CONN_PARAM_REQUEST_OFF) {
		return 0;
	}
	if ((connection == NULL) || (request_update == NULL)) {
		return -EINVAL;
	}

	*request_invoked = true;
	return request_update(connection, context);
}

const char *node_a_conn_param_experiment_mode_name(
	enum node_a_conn_param_request_mode mode)
{
	if (mode == NODE_A_CONN_PARAM_REQUEST_OFF) {
		return "OFF";
	}
	if (mode == NODE_A_CONN_PARAM_REQUEST_ON) {
		return "ON";
	}
	return "INVALID";
}
