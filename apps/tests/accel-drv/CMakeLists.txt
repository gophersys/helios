cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr)

project(accel-drv)

# Hardcoded root path
set(MONOREPO_ROOT "/workspaces/concord")
set(MONOREPO_ROOT ${MONOREPO_ROOT} CACHE INTERNAL "Monorepo root directory")

# Cipher Library
zephyr_include_directories(${MONOREPO_ROOT}/libs/cipher/include)
zephyr_include_directories(${MONOREPO_ROOT}/libs/cipher/test/include)
add_subdirectory(${MONOREPO_ROOT}/libs/cipher ${CMAKE_CURRENT_BINARY_DIR}/_libs/cipher)

# Services
zephyr_include_directories(${MONOREPO_ROOT}/services/fixtures/motion-bed/c)
add_subdirectory(${MONOREPO_ROOT}/services/fixtures/motion-bed/c ${CMAKE_CURRENT_BINARY_DIR}/_services/motion-bed)

target_sources(app PRIVATE src/main.c)