zephyr_include_directories(include)
add_subdirectory(tal)
target_sources(app PRIVATE connection.c send.c recv.c error.c packet.c)
