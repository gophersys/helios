zephyr_library_sources(iface.c)

zephyr_library_include_directories(${CMAKE_CURRENT_SOURCE_DIR})

add_subdirectory(utils)

if(CONFIG_CK_IFACE_LIB_UART)
    add_subdirectory(uart)
endif()

if(CONFIG_CK_IFACE_LIB_SOCKETS)
    add_subdirectory(socket)
endif()

if(CONFIG_CK_IFACE_WIFI_CONNECTIVITY)
    add_subdirectory(wifi)
endif()
