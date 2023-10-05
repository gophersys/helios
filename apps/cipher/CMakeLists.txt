cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr)

project(cipher)

# Including the 'include' directory for the protocol
zephyr_include_directories(../../libs/cipher/include)
zephyr_include_directories(../../libs/cipher/test/include)

target_sources(app PRIVATE src/main.c)

add_subdirectory(src/autogen)