cmake_minimum_required(VERSION 3.20.0)

set(LIBS_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../..")
list(APPEND ZEPHYR_EXTRA_MODULES
    ${LIBS_ROOT}/iface
    ${LIBS_ROOT}/cipher
)

find_package(Zephyr)
project(cipher-eth_uplink)

target_sources(app PRIVATE src/main.c)
