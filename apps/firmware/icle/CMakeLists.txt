# SPDX-License-Identifier: Apache-2.0
# ICLE Zephyr Firmware for ESP32
#
# CoreKinect In-Circuit Loop-back Equipment (ICLE) v1.0
# ESP32-WROOM-32 based test fixture for DUT validation

cmake_minimum_required(VERSION 3.20.0)

# Custom board directory for icle_v1_0 board
# Uncomment when custom board definition is finalized:
# list(APPEND BOARD_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../libs/embedded/ck_board)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(icle_zephyr VERSION 1.0.0)

# =============================================================================
# Source Files - Organized by Directory
# =============================================================================

# Application layer - state machine and events
set(APP_SOURCES
    src/main_new.c
    src/app/events.c
    src/app/state_machine.c
)

# Network layer - WiFi (via netctl) and heartbeat
set(NET_SOURCES
    src/net/wifi.c
    src/net/heartbeat.c
)

# Network Control Service (ported from Helios runtime)
set(NETCTL_SOURCES
    src/services/netctl/netctl.c
    src/services/netctl/profile.c
    src/services/netctl/arbiter.c
    src/services/netctl/wifi/wifi_sta.c
)

# HAL layer - hardware abstraction
set(HAL_SOURCES
    src/hal/gpio.c
    src/hal/power_monitor.c
    src/hal/button.c
    src/hal/storage.c
)

# Services layer - business logic
set(SERVICES_SOURCES
    src/services/logger.c
    src/services/config_manager.c
    src/services/ota.c
    src/services/http.c
    src/services/pm.c
    src/services/shell_cmds.c
)

# Utilities
set(UTIL_SOURCES
    src/util/json_builder.c
)

# Combine all sources
target_sources(app PRIVATE
    ${APP_SOURCES}
    ${NET_SOURCES}
    ${NETCTL_SOURCES}
    ${HAL_SOURCES}
    ${SERVICES_SOURCES}
    ${UTIL_SOURCES}
)

# =============================================================================
# Include Directories
# =============================================================================

target_include_directories(app PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# =============================================================================
# Compiler Definitions
# =============================================================================

target_compile_definitions(app PRIVATE
    ICLE_VERSION_MAJOR=${PROJECT_VERSION_MAJOR}
    ICLE_VERSION_MINOR=${PROJECT_VERSION_MINOR}
    ICLE_VERSION_PATCH=${PROJECT_VERSION_PATCH}
)
