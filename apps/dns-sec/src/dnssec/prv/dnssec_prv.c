// https://dnssec-debugger.verisignlabs.com/

#include "dnssec_prv.h"

#include "../dnssec_err.h"

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

LOG_MODULE_DECLARE(dnssec);

#define DNS_DEFAULT_PORT 53
#define DNS_OPT_REQUEST_TYPE 41
#define DNS_NAME_MAX_LEN 255  // Maximum length of a domain name in DNS
#define DNS_QUERY_SIZE 1500

static char dns_formatted_domain[DNS_NAME_MAX_LEN];

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Create Socket
 *---------------------------------------------------------------------------------------------------*/
/**
 * @brief Create a UDP socket and attempt a connection to the resolver address
 *
 * @param dns_resolver_addr The IP addr of the DNS resolver of choice
 * @return int errno, from socket calls
 */
dns_sec_error_t create_connected_socket(const char *dns_resolver_addr, int *sock) {
    struct sockaddr_in server;  // For IPv4
    int ret;

    *sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        LOG_WRN("Could not create socket: %s", strerror(errno));
        return DNS_SEC_SOCK_ERR;
    }

    server.sin_family = AF_INET;
    server.sin_port = htons(DNS_DEFAULT_PORT);
    inet_pton(AF_INET, dns_resolver_addr, &server.sin_addr);
    ret = connect(*sock, (struct sockaddr *)&server, sizeof(server));
    if (ret < 0) {
        LOG_WRN("Could not connect: %s", strerror(errno));
        close(*sock);
        return DNS_SEC_CONN_ERR;
    }

    return DNS_SEC_SUCCESS;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Construct Query
 *---------------------------------------------------------------------------------------------------*/
// Helpers
static void create_query_header(dns_header_t *header);
static void format_domain_name(char *dns_formatted, const char *domain);
static void create_opt_request_record(dns_edns_opt_record_t *opt_rr);
static dns_sec_error_t net_pack_dns_sec_query(uint8_t *buffer, size_t buffer_size, uint16_t *query_size, dns_sec_query_t *query);

/**
 * @brief Create a DNS query with the right fields setup in the header and payload for DNSSEC
 *
 * @param buffer The network buffer to store the created query
 * @param buffer_size The size of the network buffer
 * @param domain The domain to put in the query's question
 * @return dns_sec_error_t The corresponding error for any one step. a WRN will also be printed
 */
dns_sec_error_t construct_dns_query(uint8_t *buffer, size_t buffer_size, uint16_t *query_size, const char *domain, dns_sec_query_t *query) {

    create_query_header(&query->header);

    format_domain_name(dns_formatted_domain, domain);
    query->domain = dns_formatted_domain;
    query->domain_length = strlen(dns_formatted_domain) + 1;  // Include space for the null terminator

    query->qtype = 1;   // 1 is for A records (host addresses)
    query->qclass = 1;  // 1 is for Internet address (IN)

    create_opt_request_record(&query->opt_record);

    return net_pack_dns_sec_query(buffer, buffer_size, query_size, query);
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

static void create_query_header(dns_header_t *header) {

    sys_rand_get(&header->id, sizeof(uint16_t));  // Query ID must be randomized
    header->rd = 1;                               // Recursion Desired: the client wants recursive resolution
    header->tc = 0;                               // This message is not truncated
    header->aa = 0;                               // Not Authoritative
    header->opcode = 0;                           // Standard query
    header->qr = 0;                               // This is a query
    // Omit rcode
    header->cd = 0;  // Signature checking enabled
    // Omit ad
    // Omit z
    // Omit ra
    header->q_count = 1;  // We have only one question
    // Omit ans_count
    // Omit auth_count
    header->add_count = 1;  // 1 addition resource record for DNSSEC
}

static void create_opt_request_record(dns_edns_opt_record_t *opt_rr) {

    opt_rr->name = 0;                                     // Root domain
    opt_rr->type = DNS_OPT_REQUEST_TYPE;                  // OPT
    opt_rr->udp_payload_size = CONFIG_NET_RX_STACK_SIZE;  // Max network buffer of device
    opt_rr->extended_rcode = 0;
    opt_rr->version = 0;
    opt_rr->z = 0x8000;              // DNSSEC OK (DO) bit set
    opt_rr->data_length = 12;        // 2 bytes option code + 2 bytes option data length + 8 bytes cookie
    opt_rr->option_code = 10;        // COOKIE
    opt_rr->option_data_length = 8;  // Length of the cookie data

    // Create a random cookie
    for (int i = 0; i < 8; i++) {
        sys_rand_get(&opt_rr->cookie[i], sizeof(uint8_t));
    }
}

static dns_sec_error_t net_pack_dns_sec_query(uint8_t *buffer, size_t buffer_size, uint16_t *query_size, dns_sec_query_t *query) {

    *query_size = sizeof(query->header) + query->domain_length + sizeof(query->qtype) + sizeof(query->qclass) + sizeof(query->opt_record);
    if (buffer_size < *query_size) {
        LOG_WRN("Query size is %d bytes, and buffer passed is %d bytes", *query_size, buffer_size);
        return DNS_SEC_MEMORY_ERROR;
    }

    dns_header_t header = {0};
    memcpy(&header, &query->header, sizeof(header));
    header.id = htons(query->header.id);
    header.q_count = htons(query->header.q_count);
    header.ans_count = htons(query->header.ans_count);
    header.add_count = htons(query->header.add_count);

    uint16_t qtype = htons(query->qtype);
    uint16_t qclass = htons(query->qclass);

    dns_edns_opt_record_t opt_rr = {0};
    memcpy(&opt_rr, &query->opt_record, sizeof(opt_rr));
    opt_rr.type = htons(query->opt_record.type);
    opt_rr.udp_payload_size = htons(query->opt_record.udp_payload_size);
    opt_rr.z = htons(query->opt_record.z);
    opt_rr.data_length = htons(query->opt_record.data_length);
    opt_rr.option_code = htons(query->opt_record.option_code);
    opt_rr.option_data_length = htons(query->opt_record.option_data_length);

    // Copy the query info into the network buffer
    memcpy(buffer, &header, sizeof(header));
    memcpy(buffer + sizeof(header), query->domain, query->domain_length);
    memcpy(buffer + sizeof(header) + query->domain_length, &qtype, sizeof(qtype));
    memcpy(buffer + sizeof(header) + query->domain_length + sizeof(qtype), &qclass, sizeof(qclass));
    memcpy(buffer + sizeof(header) + query->domain_length + sizeof(qtype) + sizeof(qclass), &opt_rr, sizeof(dns_edns_opt_record_t));

    return DNS_SEC_SUCCESS;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Send Query
 *---------------------------------------------------------------------------------------------------*/

// Function to send a DNS query over a socket
dns_sec_error_t send_dns_query(int sock, const uint8_t *query, size_t query_size, const struct sockaddr_in *dns_addr) {
    // LOG_HEXDUMP_INF(query, query_size, "Query: ");

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

dns_sec_error_t receive_dns_response(int sock, uint8_t *response_buffer, size_t buffer_size, struct sockaddr_in *sender_address, ssize_t *response_size) {
    socklen_t sender_address_len = sizeof(*sender_address);
    *response_size = recvfrom(sock, response_buffer, buffer_size, 0, (struct sockaddr *)sender_address, &sender_address_len);
    if (*response_size < 0) {
        return DNS_SEC_RECV_ERR;  // Error code for failing to receive
    }
    return DNS_SEC_SUCCESS;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Validate Response
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Parses the DNS message header and checks for errors.
 *
 * This function inspects the header fields of a DNS message to ensure the integrity
 * and correctness of the response received.
 *
 * @param dns_header Pointer to the DNS header structure.
 * @return DNS security error code indicating the status of the operation.
 */
static dns_sec_error_t parse_dns_header(const dns_header_t *dns_header) {
    // Verify that the response is a DNS reply
    if (dns_header->qr == 0) {  // In a response, this should be set to 1
        return DNS_SEC_INVALID_RESPONSE;
    }

    // Check for a valid response code (e.g., No error condition)
    if (dns_header->rcode != 0) {
        return DNS_SEC_SERVER_FAILURE;  // You might want more specific error codes based on rcode
    }

    // Additional checks can be added here (e.g., validating the transaction ID matches the request)

    return DNS_SEC_SUCCESS;
}

dns_sec_error_t validate_dns_response(const uint8_t *response, ssize_t response_size, struct addrinfo **res) {
    if (response_size < sizeof(dns_header_t)) {
        return DNS_SEC_PARSE_ERR;  // The response size is smaller than the header size
    }

    const dns_header_t *dns_header = (const dns_header_t *)response;

    // Parse the header and check for errors
    dns_sec_error_t status = parse_dns_header(dns_header);
    if (status != DNS_SEC_SUCCESS) {
        return status;
    }

    // // Check the number of answers (simplified, actual check might require more validation)
    // uint16_t answer_count = ntohs(dns_header->ans_count);
    // if (answer_count == 0) {
    //     return DNS_SEC_NO_RECORDS;  // No records found
    // }

    // // Skip the question section, the function now needs the start of the buffer to handle possible name compression.
    // const uint8_t *current_position = skip_question_section(response, response + sizeof(dns_header_t), dns_header);
    // if (current_position == NULL) {
    //     return DNS_SEC_PARSE_ERR;  // Error skipping question section
    // }

    // // Process the answer section, also passing the start of the response to handle name compression.
    // return process_answer_section(response, current_position, answer_count, res);
}

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
