/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_M1_CONN_PARAM_EXPERIMENT_H_
#define KINEIMU_NODE_A_M1_CONN_PARAM_EXPERIMENT_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum node_a_conn_param_request_mode {
	NODE_A_CONN_PARAM_REQUEST_OFF = 0,
	NODE_A_CONN_PARAM_REQUEST_ON = 1,
};

struct node_a_conn_param_experiment_request {
	uint32_t transaction_id;
	char session_nonce[17];
	enum node_a_conn_param_request_mode mode;
};

struct node_a_conn_param_control_session {
	bool active;
	char nonce[17];
	uint32_t last_transaction_id;
};

typedef int (*node_a_conn_param_update_request_fn)(void *connection,
							 void *context);

int node_a_conn_param_experiment_parse_command(
	const char *command, size_t command_length,
	enum node_a_conn_param_request_mode *mode);

int node_a_conn_param_experiment_parse_transaction_command(
	const char *command, size_t command_length,
	struct node_a_conn_param_experiment_request *request);

int node_a_conn_param_experiment_accept_hello(
	struct node_a_conn_param_control_session *session,
	const char *command, size_t command_length);

int node_a_conn_param_experiment_parse_session_command(
	const char *command, size_t command_length,
	struct node_a_conn_param_experiment_request *request);

bool node_a_conn_param_experiment_session_matches(
	const struct node_a_conn_param_control_session *session,
	const struct node_a_conn_param_experiment_request *request);

int node_a_conn_param_experiment_set_mode(
	enum node_a_conn_param_request_mode *current_mode,
	enum node_a_conn_param_request_mode requested_mode, bool connected);

int node_a_conn_param_experiment_on_connect(
	enum node_a_conn_param_request_mode mode, void *connection,
	node_a_conn_param_update_request_fn request_update, void *context,
	bool *request_invoked);

const char *node_a_conn_param_experiment_mode_name(
	enum node_a_conn_param_request_mode mode);

#endif /* KINEIMU_NODE_A_M1_CONN_PARAM_EXPERIMENT_H_ */
