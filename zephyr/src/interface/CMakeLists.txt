zephyr_include_directories(include)
zephyr_library_sources(connection.c
                           error.c
                           handshake.c
                           recv.c
                           send.c
    netdbg.c)
