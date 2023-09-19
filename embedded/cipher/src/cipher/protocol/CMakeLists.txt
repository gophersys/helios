add_subdirectory(init)
add_subdirectory(interface)
add_subdirectory(threads)

zephyr_include_directories(include)

target_sources(app PRIVATE handshake.c
                           packet.c
                           serdes.c)

