cmake_minimum_required(VERSION 3.20.0)

# Drivers
set(DRIVERS
    vsm_drv
)

# Set Monorepo root
set(MONOREPO_ROOT "/workspaces/concord")
set(MONOREPO_ROOT ${MONOREPO_ROOT} CACHE INTERNAL "Monorepo root directory")

# Set the paths to the DTS and BOARD
set(DTS_ROOT ${MONOREPO_ROOT}/libs/zephyr/ck_boards/current)
set(BOARD_ROOT ${MONOREPO_ROOT}/libs/zephyr/ck_boards/current)
set(BOARD theta_b0/nrf52840)

# Append drivers
foreach(DRIVER IN LISTS DRIVERS)
    list(APPEND ZEPHYR_EXTRA_MODULES "${MONOREPO_ROOT}/libs/zephyr/${DRIVER}")
endforeach()

# DRIVERS FOR SOME REASON HAVE TO GO HERE?
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(alpha)

# Get the library hex file path from the VSM driver module
set(LIBRARY_HEX_PATH ${VSM_PSP_HEX_PATH})

# Get the PAH8151 HRD library path from the VSM driver module
set(PAH8151_HRD_LIB_PATH ${VSM_PAH8151_HRD_LIB_PATH})

# Define the merged hex file path
set(MERGED_HEX_PATH "${CMAKE_BINARY_DIR}/merged.hex")

# Custom target to merge and flash both hex files
if(EXISTS ${LIBRARY_HEX_PATH})
    add_custom_target(merge_hex ALL
        COMMAND ${CMAKE_COMMAND} -E echo "Merging application and library hex files..."
        COMMAND mergehex -m ${CMAKE_BINARY_DIR}/zephyr/zephyr.hex ${LIBRARY_HEX_PATH} -o ${MERGED_HEX_PATH}
        DEPENDS ${CMAKE_BINARY_DIR}/zephyr/zephyr.hex
        COMMENT "Merging hex files: application and library"
    )

    # Flash the merged hex file
    add_custom_target(flash_merged ALL
        COMMAND west flash --hex-file ${MERGED_HEX_PATH} --skip-rebuild
        DEPENDS merge_hex
        COMMENT "Flashing merged hex file"
    )
else()
    message(WARNING "Library hex file not found at: ${LIBRARY_HEX_PATH}. Ensure the vsm_drv module is included correctly.")
endif()

target_sources(app PRIVATE src/main.c)
# target_sources(app PRIVATE src/main_9160.c)
# target_sources(app PRIVATE src/test.c)
# target_sources(app PRIVATE src/test_temp.c)
# target_sources(app PRIVATE src/test_snr.c)
# target_sources(app PRIVATE src/test_cross_talk.c)
# target_sources(app PRIVATE src/test_reflectivity.c)