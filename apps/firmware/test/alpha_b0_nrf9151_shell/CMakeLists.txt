cmake_minimum_required(VERSION 3.20.0)

# Set Monorepo root
set(MONOREPO_ROOT "/workspaces/concord")

# Set the paths to the DTS and BOARD
set(DTS_ROOT ${MONOREPO_ROOT}/libs/zephyr/ck_boards/current)
set(BOARD_ROOT ${MONOREPO_ROOT}/libs/zephyr/ck_boards/current)
set(BOARD alpha_b0/nrf9151_ns)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(alpha_b0_nrf9151_shell_test)

target_sources(app PRIVATE src/main.c)
