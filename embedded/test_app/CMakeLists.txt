cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr)

set(BOARD esp32s3_devkitm)
set(EXTRA_ZEPHYR_MODULES path_to_your_module)

project(test_app)

target_sources(app PRIVATE src/main.c)
