cmake_minimum_required(VERSION 3.20.0)
set(LIBS_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../..")
list(APPEND ZEPHYR_EXTRA_MODULES ${LIBS_ROOT}/iface ${LIBS_ROOT}/cipher ${LIBS_ROOT}/ck_analyzer)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(esp32_wifi_node)
# ESP32 RAM is tight (WiFi ~50KB); shrink the cipher packet-pipeline heaps.
zephyr_compile_definitions(CONFIG_NET_PACKETS_COUNT=6 CONFIG_LOCAL_PACKETS_COUNT=8)
target_sources(app PRIVATE src/main.c)
