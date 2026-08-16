cmake_minimum_required(VERSION 3.20.0)

# You should include this library in your project like so
# list(APPEND ZEPHYR_EXTRA_MODULES
#   ${CMAKE_CURRENT_SOURCE_DIR}/iface  
#   )

# In this example we append it simply as a local import
set(LIB_RELATIVE_ROOT "../../../") # Set the relative path to the repository root
list(APPEND ZEPHYR_EXTRA_MODULES
    ${CMAKE_CURRENT_SOURCE_DIR}/${LIB_RELATIVE_ROOT}/iface
)

find_package(Zephyr)
project(iface-socket-server)

target_sources(app PRIVATE src/main.c)