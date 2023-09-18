add_subdirectory(threads)

target_sources(app PRIVATE init.c
                           handshake.c
                           packet.c
                           serdes.c)

