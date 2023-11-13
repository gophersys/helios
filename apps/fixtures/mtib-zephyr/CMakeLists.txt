cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr)
project(dns-sec)

target_sources(app PRIVATE src/main.c)

# Hardcoded root path
set(MONOREPO_ROOT "/workspaces/concord")
set(MONOREPO_ROOT ${MONOREPO_ROOT} CACHE INTERNAL "Monorepo root directory")

# Cipher Library
zephyr_include_directories(${MONOREPO_ROOT}/libs/cipher/include)
zephyr_include_directories(${MONOREPO_ROOT}/libs/cipher/test/include)
add_subdirectory(${MONOREPO_ROOT}/libs/cipher ${CMAKE_CURRENT_BINARY_DIR}/_libs/cipher)