add_subdirectory(stack)
zephyr_library_sources( create.c
                        set_opt.c
                        connect.c
                        accept.c
                        send.c
                        recv.c
                        close.c
                        common.c)

