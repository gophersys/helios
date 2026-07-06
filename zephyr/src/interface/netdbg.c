#include <string.h>
#include <stdio.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>
#include "netdbg.h"

#ifdef CK_NETDBG
static int dbg_sock = -1;
static struct sockaddr_in dbg_dest;

void ck_netdbg(const char *msg)
{
    if (dbg_sock < 0) {
        dbg_sock = zsock_socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if (dbg_sock < 0) return;
        memset(&dbg_dest, 0, sizeof(dbg_dest));
        dbg_dest.sin_family = AF_INET;
        dbg_dest.sin_port = htons(9998);
        zsock_inet_pton(AF_INET, "10.168.0.225", &dbg_dest.sin_addr);
    }
    (void)zsock_sendto(dbg_sock, msg, strlen(msg), 0,
                       (struct sockaddr *)&dbg_dest, sizeof(dbg_dest));
}
#endif
