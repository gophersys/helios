zephyr_include_directories(include)
target_sources(app PRIVATE api.c
                           init.c
                           rpc.c
                           local.c
                           packet.c
                           ctrl.c
                           worker.c)