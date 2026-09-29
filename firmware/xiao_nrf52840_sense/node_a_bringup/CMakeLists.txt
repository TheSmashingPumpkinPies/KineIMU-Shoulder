cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(kineimu_shoulder_node_a_bringup)

set(KINEIMU_NODE_ID "1" CACHE STRING
	"Logical node identity: 1 for Node A or 2 for Node B")
if(NOT KINEIMU_NODE_ID STREQUAL "1" AND NOT KINEIMU_NODE_ID STREQUAL "2")
	message(FATAL_ERROR "KINEIMU_NODE_ID must be 1 (A) or 2 (B)")
endif()

target_compile_definitions(app PRIVATE KINEIMU_NODE_ID=${KINEIMU_NODE_ID})

target_sources(app PRIVATE src/main.c src/acquisition.c src/counters.c
	       src/identity.c src/lsm6dsl_fifo.c src/lsm6dsl_raw.c src/packet.c
	       src/sample_queue.c
	       src/timestamp.c)
