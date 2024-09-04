cmake_minimum_required(VERSION 3.20.0)

set(DTS_ROOT ${CMAKE_CURRENT_LIST_DIR}/../../../libs)
set(BOARD_ROOT ${CMAKE_CURRENT_LIST_DIR}/../../../libs)
set(BOARD corekinect_alpha)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(alpha)

# # Path to the library hex file
# set(LIBRARY_HEX_PATH "${CMAKE_SOURCE_DIR}/lib/bin/psp.hex")
# # Define the merged hex file path
# set(MERGED_HEX_PATH "${CMAKE_BINARY_DIR}/merged.hex")

# # Custom target to merge and flash both hex files
# if(EXISTS ${LIBRARY_HEX_PATH})
#     add_custom_target(merge_hex ALL
#         COMMAND ${CMAKE_COMMAND} -E echo "Merging application and library hex files..."
#         COMMAND mergehex -m ${CMAKE_BINARY_DIR}/zephyr/zephyr.hex ${LIBRARY_HEX_PATH} -o ${MERGED_HEX_PATH}
#         DEPENDS ${CMAKE_BINARY_DIR}/zephyr/zephyr.hex
#         COMMENT "Merging hex files: application and library"
#     )

#     # Flash the merged hex file
#     add_custom_target(flash_merged ALL
#         COMMAND west flash --hex-file ${MERGED_HEX_PATH} --skip-rebuild
#         DEPENDS merge_hex
#         COMMENT "Flashing merged hex file"
#     )
# else()
#     message(WARNING "Library hex file not found. Ensure the correct path is provided.")
# endif()
# target_sources(app PRIVATE src/main.c lib/inc/psp.c)

target_sources(app PRIVATE src/main.c)
