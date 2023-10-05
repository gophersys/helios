cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr)

project(cipher)

zephyr_include_directories(include)
zephyr_include_directories(test/include)
add_subdirectory(src)
add_subdirectory(test)