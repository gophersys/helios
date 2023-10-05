zephyr_include_directories(include)
add_subdirectory(tal)
target_sources(app PRIVATE connection.c
                           error.c
                           handshake.c
                           recv.c
                           send.c)
