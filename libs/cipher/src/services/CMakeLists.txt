zephyr_include_directories(include)
target_sources(app PRIVATE conn_event.c 
                           disconn_event.c
                           packet_event.c
                           services.c
                           helpers.c)