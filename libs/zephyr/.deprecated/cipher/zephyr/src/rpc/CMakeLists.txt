zephyr_include_directories(include)
zephyr_library_sources(api.c
                           init.c
                           rpc.c
                           local.c
                           packet.c
                           ctrl.c
                           worker.c)