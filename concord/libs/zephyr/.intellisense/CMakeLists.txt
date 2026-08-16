cmake_minimum_required(VERSION 3.20.0)

# Paths
set(MONOREPO_ROOT "/workspaces/concord")
set(MONOREPO_ROOT ${MONOREPO_ROOT} CACHE INTERNAL "Monorepo root directory")

list(APPEND ZEPHYR_EXTRA_MODULES
  ${MONOREPO_ROOT}/libs/zephyr/iface
  ${MONOREPO_ROOT}/libs/zephyr/cipher
  ${MONOREPO_ROOT}/libs/zephyr/dns_sec
)

find_package(Zephyr)
project(intellisense)

target_sources(app PRIVATE src/main.c)