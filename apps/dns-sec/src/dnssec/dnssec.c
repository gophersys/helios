#include "dnssec.h"

// https://dnssec-debugger.verisignlabs.com/

// Zephyr includes
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/dns_resolve.h>
#include <zephyr/net/net_config.h>
#include <zephyr/net/net_context.h>
#include <zephyr/net/net_core.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/socket.h>
#include <zephyr/random/rand32.h>

#include "prv/dnssec_prv.h"

LOG_MODULE_REGISTER(dnssec, LOG_LEVEL_DBG);

static uint8_t dns_net_buffer[DNS_QUERY_SIZE] = {0};

// TODO: Cycle through default DNS if not reach out to known dns

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Types
 *---------------------------------------------------------------------------------------------------*/

dns_sec_error_t getsecaddrinfo(const char *host, const char *service, const struct addrinfo *hints, struct addrinfo **response) {

    // Step 1: Get the DNS resolver address
    const struct dns_resolve_context *ctx = dns_resolve_get_default();
    struct sockaddr_in *dns_addr = (struct sockaddr_in *)&ctx->servers[0].dns_server;
    char buf[NET_IPV4_ADDR_LEN];
    char *dns_addr_str = net_addr_ntop(AF_INET, &dns_addr->sin_addr, buf, sizeof(buf));
    LOG_DBG("Resolving %s using DNS server at %s", host, dns_addr_str);

    // Step 2: Establish a UDP socket connection
    int dns_server_sock = 0;
    dns_sec_error_t status = create_connected_socket(dns_addr_str, &dns_server_sock);
    if (status != DNS_SEC_SUCCESS) {
        return status;
    }
    LOG_DBG("Succesful connection to DNS server at %s:%d", dns_addr_str, DNS_DEFAULT_PORT);

    // Step 3: Construct the DNS query
    dns_sec_query_t query = {0};
    uint16_t query_size = 0;
    status = construct_dns_query(dns_net_buffer, sizeof(dns_net_buffer), &query_size, host, &query);
    if (query_size < 0) {
        close(dns_server_sock);
        return status;
    }
    LOG_DBG("Succesfully constructed DNS query, length %d bytes", query_size);
    // print_dns_query_packet(query_net_buffer, query_size);

    // Step 4: Send the DNS query
    status = send_dns_query(dns_server_sock, dns_net_buffer, query_size, dns_addr);
    if (status != DNS_SEC_SUCCESS) {
        close(dns_server_sock);
        return status;
    }
    LOG_DBG("Succesfully sent DNS query");

    // Step 5: Receive the DNS response
    struct sockaddr_in sender_address;
    size_t response_size;
    status = receive_dns_response(dns_server_sock, dns_net_buffer, sizeof(dns_net_buffer), &sender_address, &response_size);
    if (status != DNS_SEC_SUCCESS) {
        close(dns_server_sock);
        return status;  // Propagate the error code
    }
    LOG_DBG("Succesfully received DNS query response, length %d", response_size);
    // print_dns_response_packet(dns_net_buffer, response_size);

    // Step 6: Parse and validate response
    status = validate_dns_response(dns_net_buffer, response_size, &query, response);
    if (status != DNS_SEC_SUCCESS) {
        close(dns_server_sock);
        return status;
    }

    return DNS_SEC_SUCCESS;
}