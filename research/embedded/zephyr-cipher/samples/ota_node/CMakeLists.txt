cmake_minimum_required(VERSION 3.20.0)
set(LIBS_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../..")
list(APPEND ZEPHYR_EXTRA_MODULES ${LIBS_ROOT}/iface ${LIBS_ROOT}/cipher ${LIBS_ROOT}/ck_analyzer)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(ota_node)

if(BOARD MATCHES "esp32")
  zephyr_compile_definitions(CONFIG_NET_PACKETS_COUNT=3 CONFIG_LOCAL_PACKETS_COUNT=4)
endif()

# Firmware version stamped into the running image (override at build: -DEXTRA... )
if(NOT DEFINED OTA_VERSION)
  set(OTA_VERSION "v1")
endif()
target_compile_definitions(app PRIVATE APP_VERSION_STR="${OTA_VERSION}")

target_sources(app PRIVATE src/main.c)
