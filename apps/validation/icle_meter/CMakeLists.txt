cmake_minimum_required(VERSION 3.20.0)

# Project info
set(PROJECT_NAME icle_meter)

# Drivers
set(DRIVERS
    wifi
    iface
    cipher
)

# Protocols
set(PROTOS 
)

# Set Monorepo root
set(MONOREPO_ROOT "/workspaces/concord")
set(MONOREPO_ROOT ${MONOREPO_ROOT} CACHE INTERNAL "Monorepo root directory")

# Append drivers
foreach(DRIVER IN LISTS DRIVERS)
    list(APPEND ZEPHYR_EXTRA_MODULES "${MONOREPO_ROOT}/libs/zephyr/${DRIVER}")
endforeach()

# Find Zephyr, this also pulls in project() which defines 'app' target
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(cipher-scratchpad)

# Include the base directory for protocol buffers.
target_include_directories(app PRIVATE "${MONOREPO_ROOT}/libs")

# Append protocols
foreach(subdir IN LISTS PROTOS)
    # Automatically include all .c files from the specified Protobuf directories
    file(GLOB_RECURSE subdir_proto_sources "${MONOREPO_ROOT}/libs/protos/${subdir}/*.c")

    # If there are any sources found, add them to the target
    if(subdir_proto_sources)
        target_sources(app PRIVATE ${subdir_proto_sources})
    endif()

    # Ensure the directory itself is included so the compiler can find the headers
    target_include_directories(app PRIVATE "${MONOREPO_ROOT}/libs/protos/${subdir}")
endforeach()

# App sources
file(GLOB app_sources src/*.c)

target_include_directories(app PRIVATE src)

# Add the manually specified source files to your target
target_sources(app PRIVATE ${app_sources})
