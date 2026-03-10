cmake_minimum_required(VERSION 3.20.0)

# Set Monorepo root
set(MONOREPO_ROOT "/workspaces/concord")
set(MONOREPO_ROOT ${MONOREPO_ROOT} CACHE INTERNAL "Monorepo root directory")

# Set the paths to the DTS and BOARD
set(DTS_ROOT ${MONOREPO_ROOT}/libs/zephyr/ck_boards/current)
set(BOARD_ROOT ${MONOREPO_ROOT}/libs/zephyr/ck_boards/current)
set(BOARD iwsck_a1/nrf54l15/cpuapp)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(iwsck_bringup)

target_sources(app PRIVATE
  src/main.c
  src/rs232.c
  src/led.c
  src/ble.c
  src/fuel.c
  src/power.c
)
