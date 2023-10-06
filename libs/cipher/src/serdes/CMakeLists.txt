zephyr_include_directories(include)

target_sources(app PRIVATE header.c 
                           serdes.c
                           helpers.c
                           sd.c
                           rpc.c)
