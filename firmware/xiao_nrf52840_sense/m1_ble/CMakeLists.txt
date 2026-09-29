cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(kineimu_shoulder_m1_ble)

set(KINEIMU_NODE_ID "1" CACHE STRING
	"Logical node identity: 1 for Node A or 2 for Node B")
if(NOT KINEIMU_NODE_ID STREQUAL "1" AND NOT KINEIMU_NODE_ID STREQUAL "2")
	message(FATAL_ERROR "KINEIMU_NODE_ID must be 1 (A) or 2 (B)")
endif()

option(KINEIMU_CONN_PARAM_EXPERIMENT
	"Enable the USB CDC connection-parameter root-cause control" OFF)

execute_process(
	COMMAND git -C ${CMAKE_CURRENT_SOURCE_DIR} rev-parse HEAD
	OUTPUT_VARIABLE KINEIMU_GIT_COMMIT
	OUTPUT_STRIP_TRAILING_WHITESPACE
	RESULT_VARIABLE KINEIMU_GIT_RESULT)
if(NOT KINEIMU_GIT_RESULT EQUAL 0)
	message(FATAL_ERROR "Unable to resolve the firmware Git commit")
endif()
string(LENGTH "${KINEIMU_GIT_COMMIT}" KINEIMU_GIT_COMMIT_LENGTH)
if(NOT KINEIMU_GIT_COMMIT_LENGTH EQUAL 40 OR
	   NOT KINEIMU_GIT_COMMIT MATCHES "^[0-9a-fA-F]+$")
	message(FATAL_ERROR "Firmware Git commit must be a 40-character SHA-1")
endif()

set(NODE_A_SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../node_a_bringup/src)

target_compile_definitions(app PRIVATE
	KINEIMU_NODE_ID=${KINEIMU_NODE_ID}
	KINEIMU_FIRMWARE_GIT_COMMIT_HEX="${KINEIMU_GIT_COMMIT}")
if(KINEIMU_CONN_PARAM_EXPERIMENT)
	target_compile_definitions(app PRIVATE KINEIMU_CONN_PARAM_EXPERIMENT=1)
	target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_conn_param_experiment.c)
	target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_conn_param_control.c)
endif()
target_include_directories(app PRIVATE ${NODE_A_SOURCE_DIR})
target_sources(app PRIVATE
	src/main.c
	${NODE_A_SOURCE_DIR}/acquisition.c
	${NODE_A_SOURCE_DIR}/acquisition_trace.c
	${NODE_A_SOURCE_DIR}/counters.c
	${NODE_A_SOURCE_DIR}/identity.c
	${NODE_A_SOURCE_DIR}/lsm6dsl_fifo.c
	${NODE_A_SOURCE_DIR}/lsm6dsl_raw.c
	${NODE_A_SOURCE_DIR}/m1_ble_codec.c
	${NODE_A_SOURCE_DIR}/m1_ble_advertising.c
	${NODE_A_SOURCE_DIR}/m1_ble_identity.c
	${NODE_A_SOURCE_DIR}/m1_ble_service.c
	${NODE_A_SOURCE_DIR}/m1_ble_tx_completion.c
	${NODE_A_SOURCE_DIR}/m1_ble_tx_diagnostics.c
	${NODE_A_SOURCE_DIR}/m1_ble_tx_queue.c
	${NODE_A_SOURCE_DIR}/m1_ble_transport_policy.c
	${NODE_A_SOURCE_DIR}/packet.c
	${NODE_A_SOURCE_DIR}/sample_queue.c
	${NODE_A_SOURCE_DIR}/timestamp.c)
