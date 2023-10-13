cmake_minimum_required(VERSION 3.20.0)

# Library
list(APPEND ZEPHYR_EXTRA_MODULES
  ${CMAKE_CURRENT_SOURCE_DIR}/alt_drv   
  )

find_package(Zephyr)
set(DTS_ROOT  ${CMAKE_CURRENT_SOURCE_DIR})

project(alt-test)

# Hardcoded root path
set(MONOREPO_ROOT "/workspaces/concord")
set(MONOREPO_ROOT ${MONOREPO_ROOT} CACHE INTERNAL "Monorepo root directory")

# Cipher Library
zephyr_include_directories(${MONOREPO_ROOT}/libs/cipher/include)
zephyr_include_directories(${MONOREPO_ROOT}/libs/cipher/test/include)
add_subdirectory(${MONOREPO_ROOT}/libs/cipher ${CMAKE_CURRENT_BINARY_DIR}/_libs/cipher)

# Local Services (offered)
zephyr_include_directories(${MONOREPO_ROOT}/services/tests/alt-drv-test-srvc/c)
add_subdirectory(${MONOREPO_ROOT}/services/tests/alt-drv-test-srvc/c ${CMAKE_CURRENT_BINARY_DIR}/_services/alt-drv-test-srvc)

# Remote Services (consumed)
zephyr_include_directories(${MONOREPO_ROOT}/services/fixtures/alt-sim-srvc/c)
add_subdirectory(${MONOREPO_ROOT}/services/fixtures/alt-sim-srvc/c ${CMAKE_CURRENT_BINARY_DIR}/_services/alt-sim-srvc)

target_sources(app PRIVATE src/main.c src/test/test.c src/test/rpc.c src/config/config.c)