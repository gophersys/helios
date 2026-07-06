#ifndef CK_NETDBG_H
#define CK_NETDBG_H
#ifdef CK_NETDBG
void ck_netdbg(const char *msg);
#else
#define ck_netdbg(msg) ((void)0)
#endif
#endif
