zephyr_include_directories(include)
target_sources(app PRIVATE connection.c send.c recv.c error.c)