# SPDX-License-Identifier: Apache-2.0
# CoreKinect WiFi Library - Zephyr module build

if(CONFIG_CK_WIFI)
  zephyr_library()
  zephyr_library_sources(${CMAKE_CURRENT_SOURCE_DIR}/../ck_wifi.c)
  zephyr_include_directories(${CMAKE_CURRENT_SOURCE_DIR}/..)
endif()
