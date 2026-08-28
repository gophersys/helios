zephyr_include_directories(include)

zephyr_library_sources(header.c 
                           serdes.c
                           helpers.c
                           sd.c
                           rpc.c
                           stream.c)
