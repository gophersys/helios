#ifndef DNSSEC_ERR_H
#define DNSSEC_ERR_H

typedef enum {
    DNS_SEC_SUCCESS = 0,       // No error occurred
    DNS_SEC_SOCK_ERR,          // Socket creation
    DNS_SEC_CONN_ERR,          // Socket connect()
    DNS_SEC_MEMORY_ERROR,      // Internal buffer overflow
    DNS_SEC_SEND_ERR,          // Error sending DNS query
    DNS_SEC_SEND_SIZE_ERR,     // Bytes sent don't match query size
    DNS_SEC_RECV_ERR,          // Error receiving DNS response
    DNS_SEC_PARSE_ERR,         // Response parsing error
    DNS_SEC_INVALID_RESPONSE,  // DNS query formatting error
    DNS_SEC_NOT_IMPLEMENTED,
    DNS_SEC_INVALID_PARAM_ERR,

    DNS_SEC_NO_RECORDS,
    DNS_SEC_SERVER_FAILURE,

    DNS_SEC_UNSUPPORTED_RECORD_TYPE,
    DNS_SEC_INVALID_PARAM,

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

#endif