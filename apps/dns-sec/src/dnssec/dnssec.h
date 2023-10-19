#ifndef DNSSEC_H
#define DNSSEC_H

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// DNSSEC includes
#include "dnssec_err.h"

// TODO: Finish documentation

#define DNS_DEFAULT_PORT 53
#define DNS_NAME_MAX_LEN 255  // Maximum length of a domain name in DNS
#define DNS_QUERY_SIZE 1500

/**
 * @brief Resolve a domain name to one or more network addresses, using DNSSEC extensions
 *
 * @param host
 * @param service
 * @param hints
 * @param res
 * @return dns_sec_error_t
 */
dns_sec_error_t getsecaddrinfo(const char *host, const char *service, const struct addrinfo *hints,
                               struct addrinfo **res);

#endif