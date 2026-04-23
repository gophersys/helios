# Copyright (c) 2024 CoreKinect Inc.
# SPDX-License-Identifier: Apache-2.0

if(CONFIG_CK_BQ35100)
    zephyr_include_directories(drivers)
    add_subdirectory(drivers)
endif()
