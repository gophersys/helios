zephyr_include_directories(include)
target_sources(app PRIVATE rpc.c
                           local.c
                           event.c
                           packet.c)