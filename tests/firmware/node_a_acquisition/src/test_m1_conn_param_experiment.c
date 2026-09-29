/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/sys/util.h>
#include <zephyr/ztest.h>

#include "m1_conn_param_experiment.h"

struct update_request_stub {
	void *expected_connection;
	unsigned int calls;
	int return_code;
};

static int note_update_request(void *connection, void *context)
{
	struct update_request_stub *stub = context;

	if (connection != stub->expected_connection) {
		return -EINVAL;
	}
	stub->calls++;
	return stub->return_code;
}

ZTEST(node_a_conn_param_experiment, test_parses_off_and_on_commands)
{
	enum node_a_conn_param_request_mode mode =
		NODE_A_CONN_PARAM_REQUEST_ON;

	zassert_ok(node_a_conn_param_experiment_parse_command(
		"conn_param_request=OFF", strlen("conn_param_request=OFF"),
		&mode), NULL);
	zassert_equal(mode, NODE_A_CONN_PARAM_REQUEST_OFF);
	zassert_ok(node_a_conn_param_experiment_parse_command(
		"conn_param_request=ON", strlen("conn_param_request=ON"),
		&mode), NULL);
	zassert_equal(mode, NODE_A_CONN_PARAM_REQUEST_ON);
}

ZTEST(node_a_conn_param_experiment,
	test_rejects_other_commands_without_changing_output_mode)
{
	enum node_a_conn_param_request_mode mode =
		NODE_A_CONN_PARAM_REQUEST_ON;

	zassert_equal(node_a_conn_param_experiment_parse_command(
		"conn_param_request=TRUE", strlen("conn_param_request=TRUE"),
		&mode), -EINVAL, NULL);
	zassert_equal(mode, NODE_A_CONN_PARAM_REQUEST_ON);
}

ZTEST(node_a_conn_param_experiment,
	test_parses_transaction_id_and_mode_from_control_command)
{
	struct node_a_conn_param_experiment_request request = {
		.transaction_id = 0U,
		.mode = NODE_A_CONN_PARAM_REQUEST_OFF,
	};
	static const char command[] =
		"conn_param_request tx=4294967295 mode=ON";

	zassert_ok(node_a_conn_param_experiment_parse_transaction_command(
		command, sizeof(command) - 1U, &request), NULL);
	zassert_equal(request.transaction_id, UINT32_MAX);
	zassert_equal(request.mode, NODE_A_CONN_PARAM_REQUEST_ON);
}

ZTEST(node_a_conn_param_experiment,
	test_rejects_invalid_transaction_command_without_mutating_output)
{
	struct node_a_conn_param_experiment_request request = {
		.transaction_id = 7U,
		.mode = NODE_A_CONN_PARAM_REQUEST_ON,
	};
	static const char *const invalid_commands[] = {
		"conn_param_request tx=0 mode=OFF",
		"conn_param_request tx=4294967296 mode=ON",
		"conn_param_request tx=7 mode=INVALID",
		"conn_param_request tx=7 mode=OFF trailing",
		"conn_param_request tx=-7 mode=OFF",
	};

	for (size_t index = 0U;
	     index < ARRAY_SIZE(invalid_commands); index++) {
		zassert_equal(
			node_a_conn_param_experiment_parse_transaction_command(
				invalid_commands[index], strlen(invalid_commands[index]),
				&request),
			-EINVAL, "accepted invalid command: %s",
			invalid_commands[index]);
		zassert_equal(request.transaction_id, 7U);
		zassert_equal(request.mode, NODE_A_CONN_PARAM_REQUEST_ON);
	}
}

ZTEST(node_a_conn_param_experiment,
	test_new_hello_replaces_session_and_rejects_old_session_command)
{
	static const char hello_a[] = "HELLO session=0123456789abcdef";
	static const char hello_b[] = "HELLO session=fedcba9876543210";
	static const char command_a[] =
		"SET session=0123456789abcdef tx=1 mode=OFF";
	static const char command_b[] =
		"SET session=fedcba9876543210 tx=1 mode=ON";
	struct node_a_conn_param_control_session session = {0};
	struct node_a_conn_param_experiment_request request = {0};

	zassert_ok(node_a_conn_param_experiment_accept_hello(
		&session, hello_a, sizeof(hello_a) - 1U), NULL);
	zassert_true(session.active);
	zassert_str_equal(session.nonce, "0123456789abcdef");
	zassert_ok(node_a_conn_param_experiment_parse_session_command(
		command_a, sizeof(command_a) - 1U, &request), NULL);
	zassert_true(node_a_conn_param_experiment_session_matches(
		&session, &request));

	/* A HELLO on the same boot starts a new session even when tx restarts at 1. */
	zassert_ok(node_a_conn_param_experiment_accept_hello(
		&session, hello_b, sizeof(hello_b) - 1U), NULL);
	zassert_str_equal(session.nonce, "fedcba9876543210");
	zassert_false(node_a_conn_param_experiment_session_matches(
		&session, &request));
	zassert_ok(node_a_conn_param_experiment_parse_session_command(
		command_b, sizeof(command_b) - 1U, &request), NULL);
	zassert_equal(request.transaction_id, 1U);
	zassert_true(node_a_conn_param_experiment_session_matches(
		&session, &request));
}

ZTEST(node_a_conn_param_experiment,
	test_session_protocol_rejects_legacy_and_malformed_commands)
{
	struct node_a_conn_param_experiment_request request = {
		.transaction_id = 17U,
		.mode = NODE_A_CONN_PARAM_REQUEST_OFF,
	};
	static const char *const invalid_commands[] = {
		"conn_param_request tx=1 mode=ON",
		"SET session=0123456789abcdeg tx=1 mode=ON",
		"SET session=0123456789abcdef tx=0 mode=OFF",
		"SET session=0123456789abcdef tx=4294967296 mode=ON",
		"SET session=0123456789abcdef tx=1 mode=TRUE",
		"SET session=0123456789abcdef tx=1 mode=OFF trailing",
	};

	for (size_t index = 0U;
	     index < ARRAY_SIZE(invalid_commands); index++) {
		zassert_equal(
			node_a_conn_param_experiment_parse_session_command(
				invalid_commands[index], strlen(invalid_commands[index]),
				&request),
			-EINVAL, "accepted invalid command: %s",
			invalid_commands[index]);
		zassert_equal(request.transaction_id, 17U);
		zassert_equal(request.mode, NODE_A_CONN_PARAM_REQUEST_OFF);
	}
}

ZTEST(node_a_conn_param_experiment,
	test_mode_change_is_rejected_while_connected)
{
	enum node_a_conn_param_request_mode mode =
		NODE_A_CONN_PARAM_REQUEST_ON;

	zassert_ok(node_a_conn_param_experiment_set_mode(
		&mode, NODE_A_CONN_PARAM_REQUEST_OFF, false), NULL);
	zassert_equal(mode, NODE_A_CONN_PARAM_REQUEST_OFF);
	zassert_equal(node_a_conn_param_experiment_set_mode(
		&mode, NODE_A_CONN_PARAM_REQUEST_ON, true), -EBUSY, NULL);
	zassert_equal(mode, NODE_A_CONN_PARAM_REQUEST_OFF);
}

ZTEST(node_a_conn_param_experiment,
	test_duplicate_mode_changes_are_allowed_only_while_disconnected)
{
	enum node_a_conn_param_request_mode mode =
		NODE_A_CONN_PARAM_REQUEST_OFF;

	zassert_ok(node_a_conn_param_experiment_set_mode(
		&mode, NODE_A_CONN_PARAM_REQUEST_ON, false), NULL);
	zassert_ok(node_a_conn_param_experiment_set_mode(
		&mode, NODE_A_CONN_PARAM_REQUEST_ON, false), NULL);
	zassert_equal(mode, NODE_A_CONN_PARAM_REQUEST_ON);
	zassert_equal(node_a_conn_param_experiment_set_mode(
		&mode, NODE_A_CONN_PARAM_REQUEST_OFF, true), -EBUSY, NULL);
	zassert_equal(mode, NODE_A_CONN_PARAM_REQUEST_ON);
}

ZTEST(node_a_conn_param_experiment,
	test_off_connection_does_not_call_update_api)
{
	struct update_request_stub stub = {
		.expected_connection = (void *)0x1234U,
		.return_code = 0,
	};
	bool invoked = true;

	zassert_ok(node_a_conn_param_experiment_on_connect(
		NODE_A_CONN_PARAM_REQUEST_OFF, stub.expected_connection,
		note_update_request, &stub, &invoked), NULL);
	zassert_false(invoked);
	zassert_equal(stub.calls, 0U);
}

ZTEST(node_a_conn_param_experiment,
	test_on_connection_calls_update_api_once_and_preserves_result)
{
	struct update_request_stub stub = {
		.expected_connection = (void *)0x5678U,
		.return_code = -EALREADY,
	};
	bool invoked = false;

	zassert_equal(node_a_conn_param_experiment_on_connect(
		NODE_A_CONN_PARAM_REQUEST_ON, stub.expected_connection,
		note_update_request, &stub, &invoked), -EALREADY, NULL);
	zassert_true(invoked);
	zassert_equal(stub.calls, 1U);
}

ZTEST_SUITE(node_a_conn_param_experiment, NULL, NULL, NULL, NULL, NULL);
