#include "dnssec.h"

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

LOG_MODULE_REGISTER(dnssec, LOG_LEVEL_DBG);

#define DNS_DEFAULT_PORT 53
#define DNS_NAME_MAX_LEN 255  // Maximum length of a domain name in DNS
#define DNS_QUERY_SIZE 512

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Types
 *---------------------------------------------------------------------------------------------------*/
/**
 * @struct dns_header_t
 * @brief A structure to represent the DNS message header.
 *
 * This structure follows the format of a standard DNS header as defined in RFC 1035.
 * Each field represents specific information about the DNS message being sent or received.
 */
typedef struct __attribute__((packed)) {
    uint16_t id; /**< A 16-bit identifier assigned by the program to request identification. */

    uint8_t rd : 1;     /**< Recursion Desired: This bit directs the server to pursue the query recursively. */
    uint8_t tc : 1;     /**< Truncation: Specifies that this message was truncated due to length greater
                             than that permitted on the transmission channel. */
    uint8_t aa : 1;     /**< Authoritative Answer: This bit indicates that the responding name server is an
                             authority for the domain name in the question section. */
    uint8_t opcode : 4; /**< A 4-bit field that specifies the kind of query in this message. This value is
                             set by the originator of the query. */
    uint8_t qr : 1;     /**< Query/Response flag: Specifies whether this message is a query (0) or a response (1). */

    uint8_t rcode : 4; /**< Response code: This 4-bit field is set in responses, and it specifies the completion
                            status of the request. */
    uint8_t cd : 1;    /**< Checking Disabled: Used with DNSSEC, specifying that the resolver MUST NOT perform
                            DNSSEC validation for responses. */
    uint8_t ad : 1;    /**< Authenticated Data: Indicates that the data in the response has been verified by the
                            server according to the policies of that server. */
    uint8_t z : 1;     /**< Reserved for future use. Must be zero in all queries and responses. */
    uint8_t ra : 1;    /**< Recursion Available: This bit is set or cleared in a response and denotes whether recursive
                            query support is available in the name server. */

    uint16_t q_count;    /**< Specifies the number of entries in the question section. */
    uint16_t ans_count;  /**< Specifies the number of resource records in the answer section. */
    uint16_t auth_count; /**< Specifies the number of resource records in the authority section. */
    uint16_t add_count;  /**< Specifies the number of resource records in the additional records section. */
} dns_header_t;

typedef struct __attribute__((packed)) {
    uint16_t name;              // Must be 0 (root domain)
    uint16_t type;              // For OPT, this should be 41
    uint16_t udp_payload_size;  // Recommended 4096 for DNSSEC (or at least as large as your network allows)
    uint8_t extended_rcode;     // Extended RCODE (usually 0)
    uint8_t edns0_version;      // EDNS0 version (usually 0)
    uint16_t z;                 // Lower 15 bits are reserved for future use, the highest bit is the DO bit
    uint16_t data_length;       // The length of the RDATA (should be 0; no RDATA for DNSSEC)
} opt_rr_t;

typedef enum {
    DNS_A_RECORD = 1,        // a host address
    DNS_NS_RECORD = 2,       // an authoritative name server
    DNS_CNAME_RECORD = 5,    // the canonical name for an alias
    DNS_SOA_RECORD = 6,      // marks the start of a zone of authority
    DNS_PTR_RECORD = 12,     // a domain name pointer
    DNS_MX_RECORD = 15,      // mail exchange
    DNS_TXT_RECORD = 16,     // text strings
    DNS_RRSIG_RECORD = 46,   // DNSSEC signature
    DNS_DNSKEY_RECORD = 48,  // DNS key used in DNSSEC
    DNS_AAAA_RECORD = 28,    // IPv6 host address
    // ... add other record types as needed
} dns_record_type_t;

typedef struct __attribute__((packed)) {
    // These fields come after the name field in a DNS resource record.
    uint16_t type;      // Type of DNS record (A, AAAA, MX, etc.)
    uint16_t class;     // Class of data (usually 1 for Internet data)
    uint32_t ttl;       // Time to live in seconds
    uint16_t data_len;  // Data length, indicates the length of the data field coming after this header
} dns_rr_header_t;

void print_dns_query_packet(const uint8_t *packet, size_t packet_len);
void print_dns_response_packet(const uint8_t *packet, size_t packet_len);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Types
 *---------------------------------------------------------------------------------------------------*/
static int create_connected_socket(const char *dns_resolver_addr);
static int construct_dns_query(uint8_t *buffer, size_t buffer_size, const char *domain);
static dns_sec_error_t send_dns_query(int sock, const uint8_t *query, size_t query_size, const struct sockaddr_in *dns_addr);
static dns_sec_error_t receive_dns_response(int sock, uint8_t *response_buffer, size_t buffer_size, struct sockaddr_in *sender_address, ssize_t *response_size);
// static dns_sec_error_t parse_dns_response(const uint8_t *response, ssize_t response_size, struct addrinfo **res);

dns_sec_error_t getsecaddrinfo(const char *host, const char *service, const struct addrinfo *hints, struct addrinfo **res) {

    // Step 1: Get the DNS resolver address
    const struct dns_resolve_context *ctx = dns_resolve_get_default();
    struct sockaddr_in *dns_addr = (struct sockaddr_in *)&ctx->servers[0].dns_server;
    char buf[NET_IPV4_ADDR_LEN];
    char *dns_addr_str = net_addr_ntop(AF_INET, &dns_addr->sin_addr, buf, sizeof(buf));
    LOG_DBG("Resolving %s using DNS server at %s", host, dns_addr_str);

    // Step 2: Establish a UDP socket connection
    int dns_server_sock = create_connected_socket(dns_addr_str);
    if (dns_server_sock < 0) {
        LOG_WRN("Could not connect to DNS server  at %s:%d", dns_addr_str, DNS_DEFAULT_PORT);
        return DNS_SEC_SOCK_ERR;
    }
    LOG_DBG("Succesful connection to DNS server at %s:%d", dns_addr_str, DNS_DEFAULT_PORT);

    // Step 3: Construct the DNS query
    uint8_t dns_query_buffer[DNS_QUERY_SIZE] = {0};  // TODO: malloc from a heap pool
    int query_size = construct_dns_query(dns_query_buffer, sizeof(dns_query_buffer), host);
    if (query_size < 0) {
        close(dns_server_sock);
        return DNS_SEC_DNS_FORMAT_ERR;  // Error code for DNS query formatting issues
    }
    LOG_DBG("Succesfully constructed DNS query, length %d bytes", query_size);

    print_dns_query_packet(dns_query_buffer, query_size);

    // Step 4: Send the DNS query
    dns_sec_error_t status = send_dns_query(dns_server_sock, dns_query_buffer, query_size, dns_addr);
    if (status != DNS_SEC_SUCCESS) {
        close(dns_server_sock);
        return status;  // Propagate the error code
    }
    LOG_DBG("Succesfully sent DNS query");

    // Step 5: Receive the DNS response
    uint8_t dns_response_buffer[DNS_QUERY_SIZE];
    struct sockaddr_in sender_address;
    size_t response_size;
    status = receive_dns_response(dns_server_sock, dns_response_buffer, sizeof(dns_response_buffer), &sender_address, &response_size);
    if (status != DNS_SEC_SUCCESS) {
        close(dns_server_sock);
        return status;  // Propagate the error code
    }
    LOG_DBG("Succesfully received DNS query response, length %d", response_size);

    print_dns_response_packet(dns_response_buffer, response_size);

    // /* Step 6: Parse the DNS response
    //  * - Analyze the DNS response message to extract the relevant information
    //  * - This typically includes interpreting the various sections (header, question, answer, etc.)
    //  * - Check for any flags indicating errors or issues in the response
    //  * - Extract the returned IP address(es) or other relevant information
    //  */
    // dns_sec_error_t parse_status = parse_dns_response(dns_response_buffer, response_size, res);
    // if (parse_status != DNS_SEC_SUCCESS) {
    //     close(sock);
    //     return parse_status;  // Propagate the error code
    // }

    /* Step 7: Validate the DNSSEC information
     * - If DNSSEC information is included in the response, perform necessary validation
     * - This could involve verifying digital signatures, checking the authenticity of records, etc.
     * - Handle the possible outcomes of the validation (success, failure, non-authentic data, etc.)
     */

    // dns_sec_error_t dnssec_status = validate_dnssec_information(dns_response_buffer, response_size, hints);
    // if (dnssec_status != DNS_SEC_SUCCESS) {
    //     close(sock);
    //     return dnssec_status;  // Propagate the error code from the DNSSEC validation
    // }

    /* Step 8: Handle the results
     * - Based on the received and validated information, perform the necessary next steps
     * - This could be returning the obtained information, logging results, triggering other functions, etc.
     * - Clean up resources such as closing the socket and freeing allocated memory
     */

    // Result handling and resource cleanup code here

    return DNS_SEC_SUCCESS;  // Simplified success indicator; actual implementation should return meaningful status codes
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Create Socket
 *---------------------------------------------------------------------------------------------------*/
/**
 * @brief Create a connected socket object
 *
 * @param dns_resolver_addr
 * @return int
 */
static int create_connected_socket(const char *dns_resolver_addr) {

    /* - Create a UDP socket using socket()
     * - Configure the socket as necessary for your specific application requirements
     * - The DNS server's address and port number (typically 53) should be configured
     * - Connect the socket to the server with connect()
     */
    struct sockaddr_in server;  // For IPv4
    int sock;
    int ret;

    // Create a socket
    sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        LOG_ERR("Failed to create socket: %d", errno);
        return -errno;
    }

    // Configure server address
    server.sin_family = AF_INET;
    server.sin_port = htons(DNS_DEFAULT_PORT);                // Standard DNS server port
    inet_pton(AF_INET, dns_resolver_addr, &server.sin_addr);  // Convert IP address from text to binary form

    // Connect the socket
    ret = connect(sock, (struct sockaddr *)&server, sizeof(server));
    if (ret < 0) {
        LOG_ERR("Failed to connect: %d", errno);
        close(sock);
        return -errno;
    }

    return sock;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Construct Query
 *---------------------------------------------------------------------------------------------------*/
// Helpers
static void format_domain_name(char *dns_formatted, const char *domain);

/**
 * @brief
 *
 * @param buffer
 * @param buffer_size
 * @param domain
 * @return int
 */
static int construct_dns_query(uint8_t *buffer, size_t buffer_size, const char *domain) {
    /* - Format the domain name in the DNS label format
     * - Create a DNS query message according to the protocol standards
     * - This includes setting various fields in the DNS header and question section
     * - For DNSSEC, set the appropriate flags, such as DNSSEC OK (DO) bit, and handle EDNS0
     */
    dns_header_t header;
    memset(&header, 0, sizeof(header));

    // Set up various fields in the DNS message header
    header.id = htons((uint16_t)rand());
    header.qr = 0;              // This is a query
    header.opcode = 0;          // Standard query
    header.aa = 0;              // Not Authoritative
    header.tc = 0;              // This message is not truncated
    header.rd = 1;              // Recursion Desired: the client wants recursive resolution
    header.ra = 0;              // Recursion not available (set by the server)
    header.z = 0;               // Reserved
    header.ad = 0;              // Not authenticated (set by the server)
    header.cd = 0;              // No signature checking
    header.q_count = htons(1);  // We have only one question

    // Format the domain name in the DNS message format
    char dns_formatted_domain[DNS_NAME_MAX_LEN];  // TODO: malloc from a heap pool
    format_domain_name(dns_formatted_domain, domain);
    // LOG_DBG("Domain \"%s\" formatted to \"%s\"", domain, dns_formatted_domain);

    // Check if the buffer is large enough to hold the query
    size_t domain_length = strlen(dns_formatted_domain) + 1;  // Include space for the null terminator

    // Additional space for EDNS0 OPT pseudo-RR
    size_t total_query_size = sizeof(header) + domain_length + 4 + sizeof(opt_rr_t);
    if (buffer_size < total_query_size) {
        return -ENOMEM;  // Insufficient buffer size
    }

    // Construct the actual DNS query message in binary format
    memcpy(buffer, &header, sizeof(header));                               // Copy the header
    memcpy(buffer + sizeof(header), dns_formatted_domain, domain_length);  // Copy the formatted domain name

    // Append QTYPE and QCLASS after the domain name
    // TODO: improve this to be a bit more dynamic
    uint16_t qtype = htons(1);   // For example, 1 is for A records (host addresses)
    uint16_t qclass = htons(1);  // 1 is for Internet address (IN)
    memcpy(buffer + sizeof(header) + domain_length, &qtype, sizeof(qtype));
    memcpy(buffer + sizeof(header) + domain_length + sizeof(qtype), &qclass, sizeof(qclass));

    // Add the EDNS0 OPT record after the standard query to indicate DNSSEC support
    opt_rr_t opt_rr;
    memset(&opt_rr, 0, sizeof(opt_rr));
    opt_rr.type = htons(41);                // Type OPT
    opt_rr.udp_payload_size = htons(4096);  // Suggesting a larger buffer size to accommodate DNSSEC data
    opt_rr.z = htons(0x8000);               // Set the DO bit (DNSSEC OK)

    // Copy OPT RR to buffer
    memcpy(buffer + sizeof(header) + domain_length + 4, &opt_rr, sizeof(opt_rr));  // 4 bytes for QTYPE and QCLASS

    // Adjust the additional count to indicate the presence of the OPT RR
    header.add_count = htons(1);              // One additional record (the OPT RR)
    memcpy(buffer, &header, sizeof(header));  // Copy the modified header back to the buffer

    return total_query_size;  // Return the size of the constructed message
}

static void format_domain_name(char *dns_formatted, const char *domain) {
    const char *segment_begin = domain;
    const char *segment_end;
    char *output_ptr = dns_formatted;

    while (*segment_begin) {
        // Determine the length of the current segment (subdomain).
        segment_end = segment_begin + strcspn(segment_begin, ".");

        // Calculate segment length
        size_t segment_length = segment_end - segment_begin;

        // Write the length of the current segment as a single byte, followed by the segment itself.
        *output_ptr++ = (char)segment_length;  // Safe as long as segment_length < 255
        memcpy(output_ptr, segment_begin, segment_length);
        output_ptr += segment_length;

        // If we're not at the end of the string, skip over the '.'
        if (*segment_end) {
            segment_begin = segment_end + 1;  // Move past the '.'
        } else {
            break;  // End of the domain name.
        }
    }

    *output_ptr = 0;  // Null-terminate the formatted domain name
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Send Query
 *---------------------------------------------------------------------------------------------------*/
// Function to send a DNS query over a socket
static dns_sec_error_t send_dns_query(int sock, const uint8_t *query, size_t query_size, const struct sockaddr_in *dns_addr) {
    ssize_t bytes_sent = sendto(sock, query, query_size, 0, (struct sockaddr *)dns_addr, sizeof(*dns_addr));
    if (bytes_sent < 0) {
        return DNS_SEC_SEND_ERR;  // Error code for failing to send
    } else if (bytes_sent != query_size) {
        return DNS_SEC_SEND_SIZE_ERR;  // Error code for mismatch in expected size
    }
    return DNS_SEC_SUCCESS;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Recv Query
 *---------------------------------------------------------------------------------------------------*/
// Function to receive a DNS response from a socket
static dns_sec_error_t receive_dns_response(int sock, uint8_t *response_buffer, size_t buffer_size, struct sockaddr_in *sender_address, ssize_t *response_size) {
    socklen_t sender_address_len = sizeof(*sender_address);
    *response_size = recvfrom(sock, response_buffer, buffer_size, 0, (struct sockaddr *)sender_address, &sender_address_len);
    if (*response_size < 0) {
        return DNS_SEC_RECV_ERR;  // Error code for failing to receive
    }
    return DNS_SEC_SUCCESS;
}

// /**
//  * @brief Parses the DNS message header and checks for errors.
//  *
//  * This function inspects the header fields of a DNS message to ensure the integrity
//  * and correctness of the response received.
//  *
//  * @param dns_header Pointer to the DNS header structure.
//  * @return DNS security error code indicating the status of the operation.
//  */
// static dns_sec_error_t parse_dns_header(const dns_header_t *dns_header) {
//     // Verify that the response is a DNS reply
//     if (dns_header->qr == 0) {  // In a response, this should be set to 1
//         return DNS_SEC_INVALID_RESPONSE;
//     }

//     // Check for a valid response code (e.g., No error condition)
//     if (dns_header->rcode != 0) {
//         return DNS_SEC_SERVER_FAILURE;  // You might want more specific error codes based on rcode
//     }

//     // Additional checks can be added here (e.g., validating the transaction ID matches the request)

//     return DNS_SEC_SUCCESS;
// }

// /**
//  * @brief Skips over the question section of the DNS message.
//  *
//  * Given that the question section's length can vary, this function correctly advances
//  * the pointer to the start of the answer section. It also handles the compression of names.
//  *
//  * @param response_start Pointer to the start of the DNS message.
//  * @param current_position Pointer to the current position in the DNS message, right at the start of the question section.
//  * @param dns_header Pointer to the DNS header to understand the structure of the message.
//  * @return A pointer to the new position in the DNS message, right after the question section, or NULL if an error occurs.
//  */
// static const uint8_t *skip_question_section(const uint8_t *response_start, const uint8_t *current_position, const dns_header_t *dns_header) {
//     // Assume the DNS question follows the format: [qname][qtype][qclass]
//     // We need to skip over these fields for each question.

//     for (int i = 0; i < ntohs(dns_header->q_count); ++i) {
//         // The function "decode_dns_name" should return the number of bytes traversed in the original message
//         // to decode the compressed name, or -1 in case of an error. It handles the parsing of a possibly compressed qname.
//         int name_field_length = decode_dns_name(response_start, current_position);
//         if (name_field_length < 0) {
//             return NULL;  // Error in parsing the compressed name field
//         }

//         current_position += name_field_length;  // Advance the position by the length of the qname field.

//         // Skip the qtype and qclass fields. These are always 2 bytes each.
//         current_position += 4;  // 2 bytes for qtype and 2 bytes for qclass
//     }

//     // At this point, current_position should be at the start of the answer section.
//     return current_position;
// }

// /**
//  * Helper function to parse a potentially compressed domain name from a DNS message.
//  *
//  * @param[in] msg_start The start of the DNS message (for handling pointers in compression).
//  * @param[in] current_position The current position within the DNS message.
//  * @param[out] output The buffer where the domain name should be written.
//  * @return The number of bytes processed in the current_position to read the name, or -1 on error.
//  */
// int parse_dns_name(const uint8_t *msg_start, const uint8_t *current_position, char *output) {
//     const uint8_t *cursor = current_position;
//     char *output_cursor = output;
//     const uint8_t *output_end = output + DNS_NAME_MAX_LEN - 1;  // Leave room for the null terminator
//     int total_bytes_processed = 0;
//     int was_compressed = 0;  // Flag to check if the message was compressed

//     while (*cursor) {           // Continue until we reach the zero length octet
//         if (*cursor >= 0xC0) {  // Check for compression (top two bits are set)
//             if (was_compressed) {
//                 // We've already jumped due to compression, but have hit another pointer.
//                 // This shouldn't happen with a well-formed message and suggests a loop.
//                 return -1;
//             }
//             was_compressed = 1;

//             // Calculate the offset from the start of the message
//             uint16_t offset = ((*cursor) << 8 | *(cursor + 1)) & 0x3FFF;  // Offset is lower 14 bits
//             cursor = msg_start + offset;

//             // If we haven't moved (i.e., offset was zero), there's a problem
//             if (cursor == current_position) {
//                 return -1;
//             }

//             total_bytes_processed += 2;  // Adjust for the two-byte jump
//         } else {
//             uint8_t label_len = *cursor;
//             cursor++;  // Move past the length octet

//             // Check for potential buffer overflow in the output
//             if (output_cursor + label_len >= output_end) {
//                 return -1;
//             }

//             // Copy the label to the output buffer
//             for (int i = 0; i < label_len; i++) {
//                 *output_cursor = *cursor;
//                 output_cursor++;
//                 cursor++;
//             }

//             *output_cursor = '.';  // Labels are separated by dots in the output
//             output_cursor++;

//             // Adjust the total length processed if we weren't compressed
//             if (!was_compressed) {
//                 total_bytes_processed += label_len + 1;  // The label plus the length octet
//             }
//         }
//     }

//     if (!was_compressed) {
//         total_bytes_processed++;  // Account for the zero length octet at the end
//     }

//     *output_cursor = '\0';  // Null terminate the string

//     return total_bytes_processed;
// }

// /**
//  * @brief Parses a single resource record from the DNS response.
//  *
//  * This function reads and interprets a resource record from the current position in the DNS message.
//  * It handles specifics such as DNS message compression and byte order differences.
//  *
//  * @param current_position Pointer to the current position in the DNS message.
//  * @param record Pointer to a dns_resource_record_t structure where the parsed record data will be stored.
//  * @return DNS security error code indicating the status of the operation.
//  */
// static dns_sec_error_t parse_resource_record(const uint8_t *msg_start, const uint8_t *current_position, dns_resource_record_t *record) {
//     // The parsing logic, including decompressing the DNS name and reading values, goes here.
//     // We'll need to carefully manage the pointer within the response packet, adjust for network byte order, and handle the DNS message compression.
//     // This example assumes a simplistic scenario and might not cover all edge cases.

//     // Parse the NAME field (which may be compressed).
//     int name_len = parse_dns_name(msg_start, current_position, record->name);  // This function should handle DNS name compression.
//     if (name_len < 0) {
//         // An error occurred during parsing the name.
//         // Handle the error appropriately, such as logging it or returning an error code.
//         return DNS_SEC_PARSE_ERR;  // This is a hypothetical error code. You should use what's appropriate for your system.
//     }
//     current_position += name_len;

//     // Parse TYPE, CLASS, TTL, and RDLENGTH (considering network byte order for each 16/32-bit value).
//     record->type = ntohs(*((uint16_t *)current_position));
//     current_position += 2;

//     record->class = ntohs(*((uint16_t *)current_position));
//     current_position += 2;

//     record->ttl = ntohl(*((uint32_t *)current_position));
//     current_position += 4;

//     record->rd_length = ntohs(*((uint16_t *)current_position));
//     current_position += 2;

//     // The RDATA field needs to be processed based on the record type.
//     switch (record->type) {
//         case DNS_A_RECORD:
//             // Parse the IPv4 address.
//             memcpy(&(record->rdata.ipv4_address), current_position, sizeof(record->rdata.ipv4_address));
//             break;
//         case DNS_AAAA_RECORD:
//             // Parse the IPv6 address.
//             memcpy(&(record->rdata.ipv6_address), current_position, sizeof(record->rdata.ipv6_address));
//             break;
//             // Other cases for various DNS record types can be added here.
//     }

//     return DNS_SEC_SUCCESS;  // Or appropriate error code, if any part of the parsing fails.
// }

// /**
//  * @brief Construct an addrinfo structure from a DNS resource record.
//  *
//  * This function translates the information contained in a DNS resource record into
//  * an addrinfo structure, which is commonly used for network operations in C.
//  * Depending on the record type (A or AAAA), this function populates the addrinfo
//  * structure with the appropriate IP address, and sets up other relevant information
//  * such as the socket type and protocol. This constructed addrinfo can then be used
//  * directly in creating sockets, establishing connections, and other network operations.
//  *
//  * @param record A pointer to the dns_resource_record_t structure which contains
//  *               the DNS record details retrieved from the DNS response. It should
//  *               be of type A (IPv4) or AAAA (IPv6), as these types contain the IP
//  *               address information necessary for the addrinfo structure.
//  * @param res    A double pointer to the addrinfo structure to be constructed. This
//  *               function will allocate memory for the addrinfo and its associated
//  *               structures, and the caller is responsible for freeing this memory
//  *               using freeaddrinfo() when it is no longer needed.
//  * @return       Returns DNS_SEC_SUCCESS if the addrinfo structure was successfully
//  *               constructed, or an appropriate error code if the function encountered
//  *               an error. The error code is a member of the dns_sec_error_t enumeration,
//  *               informing the caller about the nature of the error, whether it be a
//  *               memory allocation failure, unsupported record type, or any other issue
//  *               that prevents successful execution.
//  */
// static dns_sec_error_t construct_addrinfo(const dns_resource_record_t *record, struct addrinfo **res) {
//     // Create a new addrinfo structure.
//     struct addrinfo *ai = (struct addrinfo *)calloc(1, sizeof(struct addrinfo));
//     if (!ai) {
//         return DNS_SEC_MEMORY_ERROR;  // Memory allocation failure.
//     }

//     // Fill in the appropriate fields based on the DNS record type.
//     ai->ai_socktype = SOCK_STREAM;  // Or SOCK_DGRAM depending on use case.
//     ai->ai_protocol = IPPROTO_TCP;  // Or IPPROTO_UDP, consistent with socktype.

//     // Handle different record types (A or AAAA records).
//     if (record->type == DNS_A_RECORD) {
//         ai->ai_family = AF_INET;
//         struct sockaddr_in *addr = (struct sockaddr_in *)calloc(1, sizeof(struct sockaddr_in));
//         if (!addr) {
//             free(ai);  // Don't forget to free previously allocated memory to avoid leaks.
//             return DNS_SEC_MEMORY_ERROR;
//         }

//         addr->sin_family = AF_INET;
//         addr->sin_port = 0;  // You might set this later, based on the service you're working with.
//         memcpy(&(addr->sin_addr), &(record->rdata.ipv4_address), sizeof(record->rdata.ipv4_address));

//         ai->ai_addr = (struct sockaddr *)addr;
//         ai->ai_addrlen = sizeof(struct sockaddr_in);
//     } else if (record->type == DNS_AAAA_RECORD) {
//         ai->ai_family = AF_INET6;
//         struct sockaddr_in6 *addr = (struct sockaddr_in6 *)calloc(1, sizeof(struct sockaddr_in6));
//         if (!addr) {
//             free(ai);  // Don't forget to free previously allocated memory to avoid leaks.
//             return DNS_SEC_MEMORY_ERROR;
//         }

//         addr->sin6_family = AF_INET6;
//         addr->sin6_port = 0;  // You might set this later, based on the service you're working with.
//         memcpy(&(addr->sin6_addr), &(record->rdata.ipv6_address), sizeof(record->rdata.ipv6_address));

//         ai->ai_addr = (struct sockaddr *)addr;
//         ai->ai_addrlen = sizeof(struct sockaddr_in6);
//     } else {
//         // Unsupported record type.
//         free(ai);
//         return DNS_SEC_UNSUPPORTED_RECORD_TYPE;
//     }

//     // If you have multiple records, you may link them in a list. Here we assume res points to a valid object.
//     ai->ai_next = *res;
//     *res = ai;

//     return DNS_SEC_SUCCESS;
// }

// /**
//  * @brief Processes the answer section of the DNS response.
//  *
//  * This function iterates through each resource record in the answer section, parses each one, and performs
//  * the necessary processing based on the record type.
//  *
//  * @param current_position Pointer to the current position in the DNS message (start of the answer section).
//  * @param answer_count The number of records in the answer section.
//  * @param res Pointer to a linked list of addrinfo structures to be filled with the relevant records.
//  * @return DNS security error code indicating the status of the operation.
//  */
// static dns_sec_error_t process_answer_section(const uint8_t *msg_start, const uint8_t *current_position, uint16_t answer_count, struct addrinfo **res) {
//     for (uint16_t i = 0; i < answer_count; ++i) {
//         dns_resource_record_t record;

//         // Parse the current resource record.
//         dns_sec_error_t err = parse_resource_record(msg_start, current_position, &record);
//         if (err != DNS_SEC_SUCCESS) {
//             return err;  // Stop processing if the record parsing fails.
//         }

//         // Process the record based on its type.
//         err = construct_addrinfo(&record, res);
//         if (err != DNS_SEC_SUCCESS) {
//             return err;  // Stop processing if the construction of addrinfo fails.
//         }

//         // Calculate the total length of the record, including the RDATA.
//         // It includes the length of the NAME, TYPE, CLASS, TTL, RDLENGTH, and RDATA itself.
//         size_t name_length = strlen(record.name) + 1;                      // Considering a non-compressed name. Adjust if needed for actual length.
//         size_t total_record_length = name_length + 10 + record.rd_length;  // 10 bytes for TYPE, CLASS, TTL, and RDLENGTH.
//         current_position += total_record_length;

//         // Here, you would need to ensure that the length calculation is accurate, especially when dealing with compressed names.
//         // The actual length of the NAME field may be different due to compression, and you may need to adjust your logic to handle this.
//     }

//     return DNS_SEC_SUCCESS;
// }

// // Helper function to parse the received server response
// static dns_sec_error_t parse_dns_response(const uint8_t *response, ssize_t response_size, struct addrinfo **res) {
//     if (response_size < sizeof(dns_header_t)) {
//         return DNS_SEC_PARSE_ERR;  // The response size is smaller than the header size
//     }

//     const dns_header_t *dns_header = (const dns_header_t *)response;

//     // Parse the header and check for errors
//     dns_sec_error_t status = parse_dns_header(dns_header);
//     if (status != DNS_SEC_SUCCESS) {
//         return status;
//     }

//     // Check the number of answers (simplified, actual check might require more validation)
//     uint16_t answer_count = ntohs(dns_header->ans_count);
//     if (answer_count == 0) {
//         return DNS_SEC_NO_RECORDS;  // No records found
//     }

//     // Skip the question section, the function now needs the start of the buffer to handle possible name compression.
//     const uint8_t *current_position = skip_question_section(response, response + sizeof(dns_header_t), dns_header);
//     if (current_position == NULL) {
//         return DNS_SEC_PARSE_ERR;  // Error skipping question section
//     }

//     // Process the answer section, also passing the start of the response to handle name compression.
//     return process_answer_section(response, current_position, answer_count, res);
// }

// /**
//  * @brief Extract DNSSEC-related records from the DNS response.
//  *
//  * This function parses the DNS response to identify and extract records
//  * related to DNS Security Extensions (DNSSEC), including but not limited
//  * to RRSIG (signatures), DNSKEY (public keys), NSEC/NSEC3 (authenticated
//  * denial of existence), etc. These records are essential for the subsequent
//  * validation of the response to ensure its authenticity and integrity.
//  *
//  * @param dns_response Pointer to the buffer containing the DNS response.
//  * @param response_size Size of the DNS response in bytes.
//  * @return dns_sec_error_t Returns DNS_SEC_SUCCESS on successful extraction,
//  *                         or a specific error code representing the failure
//  *                         encountered during the process.
//  */
// dns_sec_error_t extract_dnssec_records(const uint8_t *dns_response, ssize_t response_size) {
//     // Check if the response pointer is valid
//     if (!dns_response) {
//         return DNS_SEC_INVALID_PARAM;  // Or the appropriate error code for invalid parameters
//     }

//     // TODO: Implement this bitch

//     // Here, you would parse the DNS response, typically starting from the DNS header
//     // and then proceeding through the different sections (Answer, Authority, Additional).

//     // Placeholder for actual parsing. The specific steps you take might vary depending
//     // on the format of a DNS message and how you handle DNS records.
//     // You would look for specific record types related to DNSSEC.

//     // For example:
//     // 1. Parse the DNS header to get information like the total number of records.
//     // 2. Iterate through the Answer section to find and extract RRSIG, DNSKEY records.
//     // 3. Depending on your DNSSEC strategy, you might need to check the Authority section for NSEC/NSEC3 records.
//     // 4. Validate the consistency and correctness of the records (e.g., matching signature with the corresponding RRSIG).

//     // This is a non-trivial process and involves understanding the DNS protocol and DNSSEC extension deeply,
//     // especially under different scenarios and response types.

//     // If extraction is successful, return success status
//     return DNS_SEC_SUCCESS;
// }

// // dns_sec_error_t validate_dnssec_information(const uint8_t *dns_response, ssize_t response_size, const struct addrinfo *hints) {
// //     dns_sec_error_t validation_status;

// //     // Step 7.1: Extract DNSSEC records
// //     // This step involves parsing the response to extract RRSIG, DNSKEY, NSEC, or NSEC3 records necessary for validation.
// //     validation_status = extract_dnssec_records(dns_response, response_size);
// //     if (validation_status != DNS_SEC_SUCCESS) {
// //         // Handle error in extracting DNSSEC records
// //         return validation_status;
// //     }

// //     // Step 7.2: Verify DNSSEC signatures
// //     // Use the cryptographic library to verify the signatures in the RRSIG records against the corresponding DNSKEY records.
// //     validation_status = verify_dnssec_signatures();
// //     if (validation_status != DNS_SEC_SUCCESS) {
// //         // Handle error in verifying signatures
// //         return validation_status;
// //     }

// //     // Step 7.3: Check for authenticated denial of existence
// //     // This involves using NSEC or NSEC3 records to securely indicate that certain records do not exist.
// //     validation_status = check_authenticated_denial_of_existence();
// //     if (validation_status != DNS_SEC_SUCCESS) {
// //         // Handle error in authenticated denial of existence
// //         return validation_status;
// //     }

// //     // Step 7.4: Finalize DNSSEC validation
// //     // Consider any additional steps or checks that your application requires upon successful DNSSEC validation.
// //     validation_status = finalize_dnssec_validation();
// //     if (validation_status != DNS_SEC_SUCCESS) {
// //         // Handle error in finalizing DNSSEC validation
// //         return validation_status;
// //     }

// //     return DNS_SEC_SUCCESS;
// // }

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Print Helpers
 *---------------------------------------------------------------------------------------------------*/
// Assuming LOG_RAW is a macro that works similarly to printf,
// you might need to adjust the usage according to its actual behavior.

void print_formatted_domain(const uint8_t *data, size_t max_len) {
    if (!data || max_len == 0) {
        LOG_RAW("Invalid data or length\n");
        return;
    }

    // Current position within the data buffer.
    const uint8_t *cursor = data;
    // Remaining length of the data buffer.
    size_t remaining_len = max_len;

    while (remaining_len > 0 && *cursor != 0) {
        // Length of the current label.
        int label_len = *cursor++;
        --remaining_len;

        // Prevent reading past the end of the buffer.
        if (label_len > remaining_len) {
            LOG_RAW("Malformed data\n");
            return;
        }

        // Check for valid label length.
        if (label_len == 0 || label_len > 63) {  // DNS labels are 63 octets or less.
            break;
        }

        // Print the characters in the current label.
        for (int i = 0; i < label_len; ++i) {
            if (remaining_len == 0) {
                LOG_RAW("Buffer ends unexpectedly\n");
                return;
            }
            char ch = (char)*cursor++;
            LOG_RAW("%c", ch);  // Assume LOG_RAW can handle single characters.
            --remaining_len;
        }

        // Add a dot between labels but not at the end.
        if (remaining_len > 1 && *cursor != 0) {
            LOG_RAW(".");
        }
    }
}

void print_dns_query_packet(const uint8_t *packet, size_t packet_len) {
    if (packet_len < sizeof(dns_header_t)) {
        LOG_DBG("Error: Packet too short to contain DNS header");
        return;
    }

    dns_header_t header;
    memcpy(&header, packet, sizeof(header));

    // Convert fields from network byte order to host byte order
    header.id = ntohs(header.id);
    header.q_count = ntohs(header.q_count);
    header.add_count = ntohs(header.add_count);

    // Start printing the header fields
    LOG_INF("DNS Query Header:");
    LOG_RAW("\t\t\tID: %u\n", header.id);
    LOG_RAW("\t\t\tQR: %u\n", header.qr);
    LOG_RAW("\t\t\tOpcode: %u\n", header.opcode);
    LOG_RAW("\t\t\tAA: %u\n", header.aa);
    LOG_RAW("\t\t\tTC: %u\n", header.tc);
    LOG_RAW("\t\t\tRD: %u\n", header.rd);
    LOG_RAW("\t\t\tRA: %u\n", header.ra);
    LOG_RAW("\t\t\tZ: %u\n", header.z);
    LOG_RAW("\t\t\tAD: %u\n", header.ad);
    LOG_RAW("\t\t\tCD: %u\n", header.cd);
    LOG_RAW("\t\t\tQCount: %u\n", header.q_count);
    LOG_RAW("\t\t\tAddCount: %u\n", header.add_count);
    LOG_RAW("\t\t\tAnsCount: %u\n", header.ans_count);
    LOG_RAW("\t\t\tAuthCount: %u\n", header.auth_count);

    // Move past the header to the question section
    const uint8_t *cursor = packet + sizeof(header);

    // For this example, we're only processing one question.
    if (header.q_count > 0) {
        LOG_INF("Question Section:");

        // Print the domain name
        LOG_RAW("\t\t\tDomain: ");
        print_formatted_domain(cursor, packet_len - sizeof(header));  // Assumes well-formatted input
        LOG_RAW("\n");

        // Skip past the domain name in the question section
        size_t domain_len = strlen((const char *)cursor) + 1;  // for the zero byte
        cursor += domain_len;

        if (packet + packet_len > cursor + 4) {  // check for QTYPE and QCLASS
            uint16_t qtype, qclass;

            memcpy(&qtype, cursor, sizeof(qtype));
            cursor += sizeof(qtype);
            memcpy(&qclass, cursor, sizeof(qclass));
            cursor += sizeof(qclass);

            // Convert from network byte order to host byte order
            qtype = ntohs(qtype);
            qclass = ntohs(qclass);

            LOG_RAW("\t\t\tQTYPE: %u\n", qtype);
            LOG_RAW("\t\t\tQCLASS: %u\n", qclass);
        }
    }

    // If we have additional records, it might be the OPT RR for EDNS0
    if (header.add_count > 0 && (size_t)(cursor - packet) + sizeof(opt_rr_t) <= packet_len) {
        opt_rr_t opt_rr;
        memcpy(&opt_rr, cursor, sizeof(opt_rr));

        // Convert relevant fields from network byte order
        opt_rr.type = ntohs(opt_rr.type);
        opt_rr.udp_payload_size = ntohs(opt_rr.udp_payload_size);
        opt_rr.z = ntohs(opt_rr.z);

        LOG_INF("EDNS0 OPT Pseudo-RR:");
        LOG_RAW("\t\t\tType: %u (OPT)\n", opt_rr.type);
        LOG_RAW("\t\t\tUDP payload size: %u\n", opt_rr.udp_payload_size);
        LOG_RAW("\t\t\tExtended RCODE: %u\n", opt_rr.extended_rcode);
        LOG_RAW("\t\t\tEDNS0 version: %u\n", opt_rr.edns0_version);
        LOG_RAW("\t\t\tZ: 0x%04X\n", opt_rr.z);
        LOG_RAW("\t\t\tDO bit: %s\n", (opt_rr.z & 0x8000) ? "Set" : "Not set");
    }
}

void parse_a_record(const uint8_t *record, size_t record_len) {
    // Make sure the record is at least large enough for an IPv4 address.
    if (record_len < 4) {
        LOG_DBG("Error: A record too short");
        return;
    }

    // The A record simply contains an IPv4 address in network byte order.
    char ip_str[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, record, ip_str, sizeof(ip_str));

    LOG_INF("A Record: IPv4 address %s", ip_str);
}

void parse_aaaa_record(const uint8_t *record, size_t record_len) {
    // Make sure the record is at least large enough for an IPv6 address.
    if (record_len < 16) {
        LOG_DBG("Error: AAAA record too short");
        return;
    }

    // The AAAA record simply contains an IPv6 address in network byte order.
    char ip_str[INET6_ADDRSTRLEN];
    inet_ntop(AF_INET6, record, ip_str, sizeof(ip_str));

    LOG_INF("AAAA Record: IPv6 address %s", ip_str);
}

void parse_rrsig_record(const uint8_t *record, size_t record_len) {
    // Simplified: You'd need to parse various fields in the RRSIG record, including
    // the type covered, algorithm, labels, original TTL, expiration, inception,
    // key tag, signer's name, and the signature.

    // Given the complexity, we'll just log for now. Proper implementation would require
    // DNSSEC knowledge and careful parsing according to the RFC.

    LOG_INF("RRSIG Record (simplified)");
}

void parse_dnskey_record(const uint8_t *record, size_t record_len) {
    // Simplified: You'd need to parse the flags, protocol, algorithm, and the public key itself.
    // This is non-trivial and requires proper DNSSEC understanding.

    // We'll just log for this simplified example.
    LOG_INF("DNSKEY Record (simplified)");
}

const uint8_t *skip_name_field(const uint8_t *cursor, const uint8_t *packet_start, const uint8_t *packet_end) {
    if (!cursor || !packet_start || !packet_end || cursor < packet_start || cursor >= packet_end) {
        // Basic sanity check to ensure our pointers are valid and within bounds.
        LOG_ERR("Error: Invalid parameters, cursor or packet boundaries are incorrect");
        return NULL;
    }

    bool is_compressed = false;  // Flag to keep track if compression was used.

    // Loop through the bytes to construct the domain name or skip over it.
    while (cursor < packet_end) {
        uint8_t length_or_pointer = *cursor;

        if (length_or_pointer == 0) {
            // Zero byte indicates the end of this domain name.
            cursor++;  // Move past this null byte.
            break;     // Exit the loop as the name field has ended.
        } else if ((length_or_pointer & 0xC0) == 0xC0) {
            // This is a compression pointer.
            cursor += 2;  // Move past these two bytes, as they represent the pointer.

            // Regardless of whether we encountered previous pointers, we should always end the name field here.
            // There should not be multiple pointers or any bytes after a pointer in a well-formed packet.
            break;
        } else {
            // This is a length value indicating a label follows.
            size_t label_length = (size_t)length_or_pointer;

            if (cursor + 1 + label_length >= packet_end) {
                // Ensure we don't exceed the packet boundary.
                LOG_ERR("Error: Malformed packet, label exceeds packet boundary");
                return NULL;
            }

            // Move past the length byte and the label itself.
            cursor += 1 + label_length;
        }
    }

    // One last check after processing the loop.
    if (cursor > packet_end) {
        // The cursor went beyond the allowed boundary. The packet is malformed.
        LOG_ERR("Error: Malformed packet, cursor moved past packet end");
        return NULL;
    }

    // Return the updated cursor position after completely skipping the name field.
    // We've handled all scenarios: normal labels, a terminating zero, and a pointer.
    return cursor;
}

void print_dns_response_packet(const uint8_t *packet, size_t packet_len) {
    if (packet_len < sizeof(dns_header_t)) {
        LOG_DBG("Error: Packet too short to contain DNS header");
        return;
    }

    dns_header_t header;
    memcpy(&header, packet, sizeof(header));

    // Convert fields from network byte order to host byte order
    header.id = ntohs(header.id);
    header.q_count = ntohs(header.q_count);
    header.ans_count = ntohs(header.ans_count);
    header.auth_count = ntohs(header.auth_count);
    header.add_count = ntohs(header.add_count);

    // Start printing the header fields
    LOG_INF("DNS Response Header:");
    LOG_RAW("\t\t\tID: %u\n", header.id);
    LOG_RAW("\t\t\tQR: %u\n", header.qr);
    LOG_RAW("\t\t\tOpcode: %u\n", header.opcode);
    LOG_RAW("\t\t\tAA: %u\n", header.aa);
    LOG_RAW("\t\t\tTC: %u\n", header.tc);
    LOG_RAW("\t\t\tRD: %u\n", header.rd);
    LOG_RAW("\t\t\tRA: %u\n", header.ra);
    LOG_RAW("\t\t\tZ: %u\n", header.z);
    LOG_RAW("\t\t\tAD: %u\n", header.ad);
    LOG_RAW("\t\t\tCD: %u\n", header.cd);
    LOG_RAW("\t\t\tQCount: %u\n", header.q_count);
    LOG_RAW("\t\t\tAddCount: %u\n", header.add_count);
    LOG_RAW("\t\t\tAnsCount: %u\n", header.ans_count);
    LOG_RAW("\t\t\tAuthCount: %u\n", header.auth_count);

    // Move past the header to the question section
    const uint8_t *cursor = packet + sizeof(header);
    const uint8_t *packet_end = packet + packet_len;  // Calculate the end of the packet data.

    if (header.ans_count > 0) {
        LOG_INF("Answer Section:");

        for (int i = 0; i < header.ans_count; ++i) {
            // Attempt to skip the name field and point to the RR header.
            LOG_DBG("Pre-name skip, position: %d", cursor - packet);
            cursor = skip_name_field(cursor, packet, packet_end);
            if (!cursor) {
                LOG_DBG("Error: Malformed record name or end of packet reached unexpectedly");
                return;  // End the entire function because the packet is malformed
            }
            LOG_DBG("Post-name skip, position: %d", cursor - packet);

            // Here, 'cursor' points to the beginning of a resource record header.
            // You need to ensure there's enough remaining length for a resource record header.
            if ((size_t)(packet_end - cursor) < sizeof(dns_rr_header_t)) {
                LOG_DBG("Error: Packet too short for resource record header");
                return;  // End the entire function because the packet is truncated
            }

            cursor += sizeof(uint16_t);  // TODO: pointer to domain name of question?
            cursor += sizeof(uint16_t);  // TODO: pointer to domain name of question?
            cursor += sizeof(uint16_t);  // TODO: pointer to domain name of question?

            // Directly parse the RR header since we are already at the correct position after using skip_name_field.
            dns_rr_header_t rr_header;
            rr_header.type = ntohs(*(uint16_t *)(cursor));
            LOG_DBG("RR type: %u", rr_header.type);
            cursor += sizeof(uint16_t);

            rr_header.class = ntohs(*(uint16_t *)(cursor));
            LOG_DBG("RR class: %u", rr_header.class);
            cursor += sizeof(uint16_t);

            rr_header.ttl = ntohl(*(uint32_t *)(cursor));
            LOG_DBG("RR TTL: %u", rr_header.ttl);
            cursor += sizeof(uint32_t);

            rr_header.data_len = ntohs(*(uint16_t *)(cursor));
            LOG_DBG("RR data length: %u", rr_header.data_len);
            cursor += sizeof(uint16_t);

            // Move the cursor past the RR header to the RR data.
            // cursor += sizeof(dns_rr_header_t);

            // Validate that we have the full data as specified in the record's data length
            if (cursor + rr_header.data_len > packet_end) {
                LOG_ERR("Error: Record data exceeds packet boundary");
                break;
            }

            LOG_DBG("RR data starts at position: %d, ends at: %d", cursor - packet, cursor - packet + rr_header.data_len);

            // Handle the record based on its type.
            switch (rr_header.type) {
                case DNS_A_RECORD:
                    parse_a_record(cursor, rr_header.data_len);
                    break;
                case DNS_AAAA_RECORD:
                    parse_aaaa_record(cursor, rr_header.data_len);
                    break;
                case DNS_DNSKEY_RECORD:
                    parse_dnskey_record(cursor, rr_header.data_len);
                    break;
                default:
                    LOG_ERR("Unknown or unsupported record type: %u", rr_header.type);
            }

            // Advance the cursor past the record data for the next iteration.
            cursor += rr_header.data_len;
        }
    }

    if (header.auth_count > 0) {
        LOG_INF("Authority Section:");
        // As with the answer section, you would need to parse different types of authority records.
        // ...
    }

    // If we have additional records, they might include the OPT RR for EDNS0 among others.
    if (header.add_count > 0) {
        LOG_INF("Additional Section:");
        // Here you would check for various types of additional records, such as OPT for EDNS0.
        // The handling of EDNS0 could be similar to how you processed it in the query.
        // There could also be other records related to DNSSEC or other data.
        // ...
    }

    // The function would continue to parse through the packet data, handling the various sections.
    // Keep in mind that proper error checking, bounds checking, and robust handling of different
    // record types are crucial for a production-grade parser.
}
