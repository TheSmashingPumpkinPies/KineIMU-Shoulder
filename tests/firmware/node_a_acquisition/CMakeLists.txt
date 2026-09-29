# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(kineimu_node_a_acquisition_tests)

set(NODE_A_SOURCE_DIR
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../firmware/xiao_nrf52840_sense/node_a_bringup/src)

target_include_directories(app PRIVATE ${NODE_A_SOURCE_DIR})
target_sources(app PRIVATE src/test_acquisition.c)
target_sources(app PRIVATE src/test_ble_codec.c)
target_sources(app PRIVATE src/test_ble_advertising_work.c)
target_sources(app PRIVATE src/test_ble_transport_policy.c)
target_sources(app PRIVATE src/test_ble_tx_queue.c)
target_sources(app PRIVATE src/test_ble_tx_completion.c)
target_sources(app PRIVATE src/test_ble_tx_diagnostics.c)
target_sources(app PRIVATE src/test_register_snapshot.c)
target_sources(app PRIVATE src/test_ble_identity.c)
target_sources(app PRIVATE src/test_m1_conn_param_experiment.c)
target_sources(app PRIVATE src/test_m1_conn_param_control.c)

# Exercise the same explicit Node-B build selection used by the physical
# compatibility image. Packet golden vectors use an explicit node ID where
# they are testing the codec rather than the application identity.
target_compile_definitions(app PRIVATE KINEIMU_NODE_ID=2)

# Include production modules when available; acquisition tests retain weak
# fallbacks only for components outside their focused build configuration.
if(EXISTS ${NODE_A_SOURCE_DIR}/acquisition.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/acquisition.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/acquisition_trace.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/acquisition_trace.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/timestamp.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/timestamp.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/counters.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/counters.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/sample_queue.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/sample_queue.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/lsm6dsl_raw.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/lsm6dsl_raw.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/lsm6dsl_fifo.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/lsm6dsl_fifo.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/packet.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/packet.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/identity.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/identity.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/m1_ble_codec.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_ble_codec.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/m1_ble_advertising.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_ble_advertising.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/m1_ble_transport_policy.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_ble_transport_policy.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/m1_ble_tx_queue.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_ble_tx_queue.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/m1_ble_tx_completion.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_ble_tx_completion.c)
endif()

target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_ble_tx_diagnostics.c)

if(EXISTS ${NODE_A_SOURCE_DIR}/m1_conn_param_experiment.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_conn_param_experiment.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/m1_conn_param_control.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_conn_param_control.c)
endif()

if(EXISTS ${NODE_A_SOURCE_DIR}/m1_ble_identity.c)
  target_sources(app PRIVATE ${NODE_A_SOURCE_DIR}/m1_ble_identity.c)
endif()
