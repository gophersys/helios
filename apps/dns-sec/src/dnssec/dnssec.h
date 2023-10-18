#ifndef DNSSEC_H
#define DNSSEC_H

#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

typedef enum {
    DNS_SEC_SUCCESS = 0,  // No error occurred
    DNS_SEC_SOCK_ERR,     // Socket creation or operation error
    DNS_SEC_SEND_SIZE_ERR,
    DNS_SEC_PARSE_ERR,
    DNS_SEC_NO_RECORDS,
    DNS_SEC_SERVER_FAILURE,
    DNS_SEC_INVALID_RESPONSE,
    DNS_SEC_UNSUPPORTED_RECORD_TYPE,
    DNS_SEC_INVALID_PARAM,
    DNS_SEC_MEMORY_ERROR,
    DNS_SEC_SOCK_CONN_ERR,   // Error in socket connection
    DNS_SEC_SEND_ERR,        // Error sending DNS query
    DNS_SEC_RECV_ERR,        // Error receiving DNS response
    DNS_SEC_DNS_FORMAT_ERR,  // DNS query formatting error
    DNS_SEC_DNSSEC_INVALID,  // Received DNSSEC data is invalid
    DNS_SEC_NO_DATA,         // No record found or no response
    DNS_SEC_FAIL,            // Unspecified failure
    DNS_SEC_BADFLAGS,        // Invalid value for `ai_flags` field
    DNS_SEC_FAMILY,          // `ai_family` not supported
    DNS_SEC_MEMORY,          // Memory allocation failure
    DNS_SEC_OVERFLOW,        // Buffer overflow
    DNS_SEC_SYSTEM,          // System error (check errno)
} dns_sec_error_t;

dns_sec_error_t getsecaddrinfo(const char *host, const char *service, const struct addrinfo *hints,
                               struct addrinfo **res);

#endif