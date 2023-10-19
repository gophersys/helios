#ifndef DNSSEC_PRV_H
#define DNSSEC_PRV_H

// Standard includes
#include <stdint.h>
#include <stdio.h>

// DNS Sec includes
#include "../dnssec_err.h"

// Zephyr includes
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

/**
 * @struct dns_header_t
 * @brief A structure to represent the DNS message header.
 *
 * This structure follows the format of a standard DNS header as defined in RFC 1035.
 * Each field represents specific information about the DNS message being sent or received.
 */
typedef struct __attribute__((packed)) {
    uint16_t id;         /**< A 16-bit identifier assigned by the program to request identification. */
    uint8_t rd : 1;      /**< Recursion Desired: This bit directs the server to pursue the query recursively. */
    uint8_t tc : 1;      /**< Truncation: Specifies that this message was truncated due to length greater than that permitted on the transmission channel. */
    uint8_t aa : 1;      /**< Authoritative Answer: This bit indicates that the responding name server is an authority for the domain name in the question section. */
    uint8_t opcode : 4;  /**< A 4-bit field that specifies the kind of query in this message. This value is set by the originator of the query. */
    uint8_t qr : 1;      /**< Query/Response flag: Specifies whether this message is a query (0) or a response (1). */
    uint8_t rcode : 4;   /**< Response code: This 4-bit field is set in responses, and it specifies the completion status of the request. */
    uint8_t cd : 1;      /**< Checking Disabled: Used with DNSSEC, specifying that the resolver MUST NOT perform DNSSEC validation for responses. */
    uint8_t ad : 1;      /**< Authenticated Data: Indicates that the data in the response has been verified by the server according to the policies of that server. */
    uint8_t z : 1;       /**< Reserved for future use. Must be zero in all queries and responses. */
    uint8_t ra : 1;      /**< Recursion Available: This bit is set or cleared in a response and denotes whether recursive query support is available in the name server. */
    uint16_t q_count;    /**< Specifies the number of entries in the question section. */
    uint16_t ans_count;  /**< Specifies the number of resource records in the answer section. */
    uint16_t auth_count; /**< Specifies the number of resource records in the authority section. */
    uint16_t add_count;  /**< Specifies the number of resource records in the additional records section. */
} dns_header_t;

/**
 * @enum dns_record_type_t
 * @brief Enumeration of DNS record types.
 *
 * This enumeration represents the various types of records in the Domain Name System (DNS).
 * Each member corresponds to a specific kind of data that can be included in a DNS record.
 */
typedef enum {
    DNS_A_RECORD = 1,       /**< Specifies an IPv4 address record associated with a host name. */
    DNS_NS_RECORD = 2,      /**< Indicates a Name Server record, which delegates a DNS zone to use the given authoritative name servers. */
    DNS_CNAME_RECORD = 5,   /**< Canonical Name record, used to alias one name to another. A CNAME record points to an A (or AAAA) record. */
    DNS_SOA_RECORD = 6,     /**< Start Of Authority record, signifies the start of a zone of authority and contains authoritative information about a DNS zone. */
    DNS_PTR_RECORD = 12,    /**< Pointer record, often used for reverse DNS lookups, mapping an IPv4 or IPv6 address to a host name. */
    DNS_MX_RECORD = 15,     /**< Mail Exchange record, directing mail to an email server. */
    DNS_TXT_RECORD = 16,    /**< Text record, typically carrying machine-readable data such as SPF information. */
    DNS_AAAA_RECORD = 28,   /**< Specifies an IPv6 address record associated with a host name. */
    DNS_RRSIG_RECORD = 46,  /**< DNSSEC signature, containing the cryptographic signature that DNSSEC-capable resolvers use for validation. */
    DNS_DNSKEY_RECORD = 48, /**< DNS Key record, used in DNSSEC. It contains the public key for a zone, allowing resolvers to verify DNS data integrity. */
} dns_record_type_t;

/**
 * @struct dns_resource_record_header_t
 * @brief Header structure for DNS Resource Records.
 *
 * This packed structure represents the header part of a resource record (RR) within a DNS message.
 * It follows the format specified in RFC 1035 and includes the type, class, TTL, and data length fields
 * which are common to all RRs. The actual data for the record follows this header in the message.
 */
typedef struct __attribute__((packed)) {
    uint16_t type;     /**< @dns_record_type_t The type of the DNS record, which indicates the type of data contained in the record */
    uint16_t class;    /**< The class of the data, typically representing the type of network. The most common class is IN (1) for the Internet. */
    uint32_t ttl;      /**< Time to Live (TTL) for the DNS record, in seconds. This specifies how long the record is considered valid by a DNS resolver. */
    uint16_t data_len; /**< The length of the data field following this header. It specifies the size of the actual data or RDATA portion of the resource record. */
} dns_resource_record_header_t;

/**
 * @struct dns_edns_opt_record_t
 * @brief A structure to represent the DNS OPT resource record, used for enabling extended DNS features.
 *
 * This structure encapsulates fields specific to the OPT RR type, which is part of the Extension Mechanisms
 * for DNS (EDNS). It's utilized to communicate extended RDATA information that doesn't fit in the standard
 * DNS record, improving the ability to support enhanced functionality.
 */
typedef struct __attribute__((packed)) {
    uint8_t name;                /**< Root domain: this field is always set to 0 for OPT records, indicating it pertains to the root domain. */
    uint16_t type;               /**< Type of DNS record, set to OPT (41) for Extension mechanisms for DNS (EDNS). */
    uint16_t udp_payload_size;   /**< Maximum payload size for UDP packets that the sender of the message is able to accept. */
    uint8_t extended_rcode;      /**< Extended RCODE field: used to extend the RCODE part of the DNS message header from 4 bits to 12 bits.
                                      This field is set to 0 for no error condition on messages using EDNS0. */
    uint8_t version;             /**< EDNS version that the sender of the message supports. Should be 0 for EDNS0 (the only version currently standardized). */
    uint16_t z;                  /**< Option flags, used for various flags extended by EDNS. For instance, the DNSSEC OK (DO) bit is one such flag. */
    uint16_t data_length;        /**< Length of the RDATA field, which includes any options appended to the OPT RR. */
    uint16_t option_code;        /**< Specifies the EDNS option included in the RDATA. For instance, a COOKIE, represented typically by the value 10. */
    uint16_t option_data_length; /**< Length of the COOKIE data in bytes. This represents the size of the 'cookie' field in this structure. */
    uint8_t cookie[8];           /**< The COOKIE data itself, a security feature used to resist DNS Denial-of-Service (DoS) attacks.
                                      It's a client-selected value that the server must include in its response. */
} dns_edns_opt_record_t;

typedef struct {
    dns_header_t header;
    char *domain;
    size_t domain_length;
    uint16_t qtype;
    uint16_t qclass;
    dns_edns_opt_record_t opt_record;
} dns_sec_query_t;

dns_sec_error_t create_connected_socket(const char *dns_resolver_addr, int *sock);
dns_sec_error_t construct_dns_query(uint8_t *buffer, size_t buffer_size, uint16_t *query_size, const char *domain, dns_sec_query_t *query);
dns_sec_error_t send_dns_query(int sock, const uint8_t *query, size_t query_size, const struct sockaddr_in *dns_addr);
dns_sec_error_t receive_dns_response(int sock, uint8_t *response_buffer, size_t buffer_size, struct sockaddr_in *sender_address,
                                     ssize_t *response_size);
dns_sec_error_t validate_dns_response(const uint8_t *response, ssize_t response_size, struct addrinfo **res);

void print_dns_query_packet(const uint8_t *packet, size_t packet_len);
void print_dns_response_packet(const uint8_t *packet, size_t packet_len);

#endif  // DNSSEC_PRV_H