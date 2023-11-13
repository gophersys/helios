cmake_minimum_required(VERSION 3.20.0)

list(APPEND ZEPHYR_EXTRA_MODULES
  ${CMAKE_CURRENT_SOURCE_DIR}/dns_sec   
  )

find_package(Zephyr)
project(dns-sec)

target_sources(app PRIVATE src/main.c)