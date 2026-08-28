zephyr_include_directories(include)
zephyr_library_sources(conn_event.c 
                           disconn_event.c
                           packet_event.c
                           services.c
                           helpers.c)