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

K_HEAP_DEFINE(dns_heap, 50024);
static char dns_formatted_domain[DNS_NAME_MAX_LEN];

// TODO: Set socket timeout

// Assuming 2 bytes for type_covered, 1 byte each for algorithm and labels,
// 4 bytes each for original_ttl, signature_expiration, and signature_inception,
// and 2 bytes for key_tag, the minimum length is 18 bytes.
// The actual record will be longer due to the variable-length signer_name and signature.
#define RRSIG_RECORD_MINIMUM_LENGTH 18

typedef struct {
    uint16_t type_covered;
    uint8_t algorithm;
    uint8_t labels;
    uint32_t original_ttl;
    uint32_t signature_expiration;
    uint32_t signature_inception;
    uint16_t key_tag;
    uint8_t *signer_name;       // This field might require dynamic memory allocation.
    uint8_t *signature;         // This field might require dynamic memory allocation.
    uint16_t signature_length;  // This field is necessary to know the signature length.
} rrsig_record_t;

// Struct for DNSKEY record. You might already have something like this.
typedef struct {
    uint16_t flags;
    uint8_t protocol;
    uint8_t algorithm;
    uint8_t *public_key;  // Dynamically allocated.
    size_t key_length;    // Length of the public key data
    // ... any other fields you might need.
} dnskey_record_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Create Socket
 *---------------------------------------------------------------------------------------------------*/
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
dns_sec_error_t receive_dns_response(int sock, uint8_t *response_buffer, size_t buffer_size, struct sockaddr_in *dns_addr, size_t *response_size) {
    socklen_t sender_address_len = sizeof(*dns_addr);
    *response_size = recvfrom(sock, response_buffer, buffer_size, 0, (struct sockaddr *)dns_addr, &sender_address_len);
    if (*response_size < 0) {
        return DNS_SEC_RECV_ERR;
    }
    return DNS_SEC_SUCCESS;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Validate Response
 *---------------------------------------------------------------------------------------------------*/

// Helpers
static dns_sec_error_t parse_header(uint8_t *response_buffer, size_t buffer_size, dns_header_t *header);
static uint8_t *skip_name_field(uint8_t *cursor, const uint8_t *packet_start, const uint8_t *packet_end);

// Record parsers
static dns_sec_error_t parse_a_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res);
static dns_sec_error_t parse_ns_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res);
static dns_sec_error_t parse_cname_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res);
static dns_sec_error_t parse_soa_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res);
static dns_sec_error_t parse_ptr_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res);
static dns_sec_error_t parse_mx_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res);
static dns_sec_error_t parse_txt_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res);
static dns_sec_error_t parse_aaaa_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res);
static dns_sec_error_t parse_rrsig_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res);
static dns_sec_error_t parse_dnskey_record(const uint8_t *data, uint16_t data_len, dnskey_record_t *res);

dns_sec_error_t validate_dns_response(uint8_t *response, ssize_t response_size, dns_sec_query_t *query, struct addrinfo **res) {

    dns_header_t response_header = {0};
    dns_sec_error_t status = parse_header(response, response_size, &response_header);
    if (status != DNS_SEC_SUCCESS) {
        return status;
    }

    if (response_header.id != query->header.id) {
        LOG_WRN("DNS esponse ID %d does not match query's ID %d", response_header.id, query->header.id);
        return DNS_SEC_INVALID_RESPONSE;
    }

    uint8_t *cursor = response + sizeof(response_header);
    uint8_t *packet_end = response + response_size;

    // Skip query Section
    if (response_header.q_count > 0) {
        for (int i = 0; i < response_header.q_count; ++i) {
            cursor = skip_name_field(cursor, response, packet_end);
            if (!cursor) {
                LOG_ERR("Malformed record name or end of packet reached unexpectedly");
                return DNS_SEC_PARSE_ERR;
            }

            uint16_t qtype, qclass;

            memcpy(&qtype, cursor, sizeof(qtype));
            cursor += sizeof(qtype);
            memcpy(&qclass, cursor, sizeof(qclass));
            cursor += sizeof(qclass);

            qtype = ntohs(qtype);
            qclass = ntohs(qclass);
        }
    }

    *res = NULL;
    struct addrinfo *last_info = NULL;

    // Parse answer question
    if (response_header.ans_count > 0) {
        for (int i = 0; i < response_header.ans_count; ++i) {

            // Skip the name field in the answer section, accounting for possible name compression.
            cursor = skip_name_field(cursor, response, packet_end);
            if (!cursor) {
                LOG_DBG("Malformed record name or end of packet reached unexpectedly");
                return DNS_SEC_PARSE_ERR;
            }

            // Here, 'cursor' points to the beginning of a resource record header.
            if ((size_t)(packet_end - cursor) < sizeof(dns_resource_record_header_t)) {
                LOG_DBG("Packet too short for resource record header");
                return DNS_SEC_PARSE_ERR;
            }

            // Directly parse the RR header since we are already at the correct position after using skip_name_field.
            dns_resource_record_header_t rr_header;
            rr_header.type = ntohs(*(uint16_t *)(cursor));
            cursor += sizeof(uint16_t);

            rr_header.class = ntohs(*(uint16_t *)(cursor));
            cursor += sizeof(uint16_t);

            rr_header.ttl = ntohl(*(uint32_t *)(cursor));
            cursor += sizeof(uint32_t);

            rr_header.data_len = ntohs(*(uint16_t *)(cursor));
            cursor += sizeof(uint16_t);

            // Validate that we have the full data as specified in the record's data length
            if (cursor + rr_header.data_len > packet_end) {
                LOG_WRN("Record data exceeds packet boundary");
                return DNS_SEC_PARSE_ERR;
            }

            // Allocate a new addrinfo structure from the heap.
            struct addrinfo *ai = k_heap_alloc(&dns_heap, sizeof(struct addrinfo), K_NO_WAIT);
            if (!ai) {
                LOG_WRN("Memory allocation failed");
                return DNS_SEC_MEMORY_ERROR;  // Or appropriate error handling.
            }

            memset(ai, 0, sizeof(struct addrinfo));

            // Handle the record based on its type.
            dns_sec_error_t parse_result = DNS_SEC_SUCCESS;
            switch (rr_header.type) {
                case DNS_A_RECORD:
                    parse_result = parse_a_record(cursor, rr_header.data_len, ai);
                    break;
                case DNS_NS_RECORD:
                    parse_result = parse_ns_record(cursor, rr_header.data_len, ai);
                    break;
                case DNS_CNAME_RECORD:
                    parse_result = parse_cname_record(cursor, rr_header.data_len, ai);
                    break;
                case DNS_SOA_RECORD:
                    parse_result = parse_soa_record(cursor, rr_header.data_len, ai);
                    break;
                case DNS_PTR_RECORD:
                    parse_result = parse_ptr_record(cursor, rr_header.data_len, ai);
                    break;
                case DNS_MX_RECORD:
                    parse_result = parse_mx_record(cursor, rr_header.data_len, ai);
                    break;
                case DNS_TXT_RECORD:
                    parse_result = parse_txt_record(cursor, rr_header.data_len, ai);
                    break;
                case DNS_AAAA_RECORD:
                    parse_result = parse_aaaa_record(cursor, rr_header.data_len, ai);
                    break;
                case DNS_RRSIG_RECORD:
                    parse_result = parse_rrsig_record(cursor, rr_header.data_len, ai);
                    break;
                case DNS_DNSKEY_RECORD:
                    // parse_result = parse_dnskey_record(cursor, rr_header.data_len, ai);
                    break;
                default:
                    LOG_ERR("Unknown or unsupported record type: %u", rr_header.type);
                    return DNS_SEC_UNSUPPORTED_RECORD_TYPE;
            }

            if (parse_result != DNS_SEC_SUCCESS) {
                k_heap_free(&dns_heap, ai);
            } else {
                // Parsing was successful, link the new addrinfo to the list.
                if (last_info) {
                    last_info->ai_next = ai;
                } else {
                    *res = ai;
                }
                last_info = ai;
            }

            // Whether parsing is successful or not, advance the cursor past the record data for the next iteration.
            cursor += rr_header.data_len;

            // Check if the cursor doesn't exceed the packet boundary.
            if (cursor > packet_end) {
                LOG_ERR("Cursor has exceeded packet boundary");
                return DNS_SEC_PARSE_ERR;
            }
        }
    }

    return DNS_SEC_SUCCESS;
}

dns_sec_error_t get_dns_keys_from_response(uint8_t *response, ssize_t response_size, dnskey_record_t **res) {

    dns_header_t response_header = {0};
    dns_sec_error_t status = parse_header(response, response_size, &response_header);
    if (status != DNS_SEC_SUCCESS) {
        return status;
    }

    uint8_t *cursor = response + sizeof(response_header);
    uint8_t *packet_end = response + response_size;

    // Skip query Section
    if (response_header.q_count > 0) {
        for (int i = 0; i < response_header.q_count; ++i) {
            cursor = skip_name_field(cursor, response, packet_end);
            if (!cursor) {
                LOG_ERR("Malformed record name or end of packet reached unexpectedly");
                return DNS_SEC_PARSE_ERR;
            }

            uint16_t qtype, qclass;

            memcpy(&qtype, cursor, sizeof(qtype));
            cursor += sizeof(qtype);
            memcpy(&qclass, cursor, sizeof(qclass));
            cursor += sizeof(qclass);

            qtype = ntohs(qtype);
            qclass = ntohs(qclass);
        }
    }

    // Parse answer question
    if (response_header.ans_count > 0) {
        for (int i = 0; i < response_header.ans_count; ++i) {

            // Skip the name field in the answer section, accounting for possible name compression.
            cursor = skip_name_field(cursor, response, packet_end);
            if (!cursor) {
                LOG_DBG("Malformed record name or end of packet reached unexpectedly");
                return DNS_SEC_PARSE_ERR;
            }

            // Here, 'cursor' points to the beginning of a resource record header.
            if ((size_t)(packet_end - cursor) < sizeof(dns_resource_record_header_t)) {
                LOG_DBG("Packet too short for resource record header");
                return DNS_SEC_PARSE_ERR;
            }

            // Directly parse the RR header since we are already at the correct position after using skip_name_field.
            dns_resource_record_header_t rr_header;
            rr_header.type = ntohs(*(uint16_t *)(cursor));
            cursor += sizeof(uint16_t);

            rr_header.class = ntohs(*(uint16_t *)(cursor));
            cursor += sizeof(uint16_t);

            rr_header.ttl = ntohl(*(uint32_t *)(cursor));
            cursor += sizeof(uint32_t);

            rr_header.data_len = ntohs(*(uint16_t *)(cursor));
            cursor += sizeof(uint16_t);

            // Validate that we have the full data as specified in the record's data length
            if (cursor + rr_header.data_len > packet_end) {
                LOG_WRN("Record data exceeds packet boundary");
                return DNS_SEC_PARSE_ERR;
            }

            // Allocate a new addrinfo structure from the heap.
            dnskey_record_t *ai = k_heap_alloc(&dns_heap, sizeof(dnskey_record_t), K_NO_WAIT);
            if (!ai) {
                LOG_WRN("Memory allocation failed");
                return DNS_SEC_MEMORY_ERROR;  // Or appropriate error handling.
            }

            memset(ai, 0, sizeof(dnskey_record_t));

            // Handle the record based on its type.
            dns_sec_error_t parse_result = DNS_SEC_SUCCESS;
            switch (rr_header.type) {
                case DNS_DNSKEY_RECORD:
                    parse_result = parse_dnskey_record(cursor, rr_header.data_len, ai);
                    break;
                default:
                    LOG_ERR("Unknown or unsupported record type: %u", rr_header.type);
                    return DNS_SEC_UNSUPPORTED_RECORD_TYPE;
            }

            if (parse_result != DNS_SEC_SUCCESS) {
                k_heap_free(&dns_heap, ai);
            } else {
                res[i] = ai;
            }

            // Whether parsing is successful or not, advance the cursor past the record data for the next iteration.
            cursor += rr_header.data_len;

            // Check if the cursor doesn't exceed the packet boundary.
            if (cursor > packet_end) {
                LOG_ERR("Cursor has exceeded packet boundary");
                return DNS_SEC_PARSE_ERR;
            }
        }
    }

    return DNS_SEC_SUCCESS;
}

static dns_sec_error_t parse_header(uint8_t *response_buffer, size_t buffer_size, dns_header_t *header) {
    if (buffer_size < sizeof(dns_header_t)) {
        LOG_WRN("Packet too short to contain DNS header");
        return DNS_SEC_PARSE_ERR;
    }

    memcpy(header, response_buffer, sizeof(dns_header_t));

    header->id = ntohs(header->id);
    header->q_count = ntohs(header->q_count);
    header->ans_count = ntohs(header->ans_count);
    header->auth_count = ntohs(header->auth_count);
    header->add_count = ntohs(header->add_count);

    return DNS_SEC_SUCCESS;
}

static uint8_t *skip_name_field(uint8_t *cursor, const uint8_t *packet_start, const uint8_t *packet_end) {
    if (!cursor || !packet_start || !packet_end || cursor < packet_start || cursor >= packet_end) {
        // Basic sanity check to ensure our pointers are valid and within bounds.
        LOG_ERR("Error: Invalid parameters, cursor or packet boundaries are incorrect");
        return NULL;
    }

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

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       Record Parsers
 *---------------------------------------------------------------------------------------------------*/

static dns_sec_error_t parse_a_record(const uint8_t *data, uint16_t data_len, struct addrinfo *ai) {
    if (!data || !ai) {
        LOG_WRN("Invalid parameters passed to %s", __func__);
        return DNS_SEC_INVALID_PARAM_ERR;
    }

    if (data_len < sizeof(uint32_t)) {
        LOG_ERR("Invalid A record. Data length is less than expected.");
        return DNS_SEC_INVALID_RESPONSE;
    }

    // Allocate memory for the sockaddr structure.
    struct sockaddr_in *addr = k_heap_alloc(&dns_heap, sizeof(struct sockaddr_in), K_NO_WAIT);
    if (!addr) {
        LOG_ERR("Memory allocation for sockaddr_in failed");
        return DNS_SEC_MEMORY_ERROR;
    }

    // Clear the structure and set its values.
    memset(addr, 0, sizeof(struct sockaddr_in));
    addr->sin_family = AF_INET;
    memcpy(&(addr->sin_addr.s_addr), data, sizeof(uint32_t));  // Copy the IPv4 address.

    // Populate the addrinfo structure 'ai' given by the caller.
    ai->ai_family = AF_INET;
    ai->ai_socktype = SOCK_STREAM;  // Use hints or context to determine actual socktype.
    ai->ai_protocol = IPPROTO_TCP;  // Use hints or context to determine actual protocol.
    ai->ai_addrlen = sizeof(struct sockaddr_in);
    ai->ai_addr = (struct sockaddr *)addr;

    char ip_str[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, data, ip_str, sizeof(ip_str));
    LOG_DBG("Parsed A record successfully, IP: %s", ip_str);

    return DNS_SEC_SUCCESS;
}

static dns_sec_error_t parse_ns_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res) {
    LOG_WRN("%s not implemented, cant't parse response", __func__);
    return DNS_SEC_NOT_IMPLEMENTED;
}

static dns_sec_error_t parse_cname_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res) {
    LOG_WRN("%s not implemented, cant't parse response", __func__);
    return DNS_SEC_NOT_IMPLEMENTED;
}

static dns_sec_error_t parse_soa_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res) {
    LOG_WRN("%s not implemented, cant't parse response", __func__);
    return DNS_SEC_NOT_IMPLEMENTED;
}

static dns_sec_error_t parse_ptr_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res) {
    LOG_WRN("%s not implemented, cant't parse response", __func__);
    return DNS_SEC_NOT_IMPLEMENTED;
}

static dns_sec_error_t parse_mx_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res) {
    LOG_WRN("%s not implemented, cant't parse response", __func__);
    return DNS_SEC_NOT_IMPLEMENTED;
}

static dns_sec_error_t parse_txt_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res) {
    LOG_WRN("%s not implemented, cant't parse response", __func__);
    return DNS_SEC_NOT_IMPLEMENTED;
}

static dns_sec_error_t parse_aaaa_record(const uint8_t *data, uint16_t data_len, struct addrinfo *ai) {
    if (!data || !ai) {
        LOG_WRN("Invalid parameters passed to %s", __func__);
        return DNS_SEC_INVALID_PARAM_ERR;
    }

    // Check that the AAAA record length is correct, it should be 16 bytes for IPv6 address.
    if (data_len < 16) {
        LOG_ERR("Invalid AAAA record. Data length is less than expected.");
        return DNS_SEC_INVALID_RESPONSE;
    }

    // Allocate memory for the sockaddr structure.
    struct sockaddr_in6 *addr = k_heap_alloc(&dns_heap, sizeof(struct sockaddr_in6), K_NO_WAIT);
    if (!addr) {
        LOG_ERR("Memory allocation for sockaddr_in6 failed");
        return DNS_SEC_MEMORY_ERROR;
    }

    // Clear the structure and set its values.
    memset(addr, 0, sizeof(struct sockaddr_in6));
    addr->sin6_family = AF_INET6;
    memcpy(&(addr->sin6_addr.s6_addr), data, 16);  // Copy the IPv6 address.

    // Populate the addrinfo structure 'ai' given by the caller.
    ai->ai_family = AF_INET6;       // IPv6
    ai->ai_socktype = SOCK_STREAM;  // Default, this could be parameterized based on hints.
    ai->ai_protocol = IPPROTO_TCP;  // Default, this could be parameterized based on hints.
    ai->ai_addrlen = sizeof(struct sockaddr_in6);
    ai->ai_addr = (struct sockaddr *)addr;

    char ip_str[INET6_ADDRSTRLEN];
    inet_ntop(AF_INET6, &(addr->sin6_addr), ip_str, sizeof(ip_str));
    LOG_DBG("Parsed AAAA record successfully, IP: %s", ip_str);

    return DNS_SEC_SUCCESS;
}

static dns_sec_error_t parse_dnskey_record(const uint8_t *data, uint16_t data_len, dnskey_record_t *res) {
    if (data_len < 4) {  // The DNSKEY record must contain at least the flags (2 bytes), protocol (1 byte), and algorithm (1 byte).
        LOG_ERR("Invalid DNSKEY record, data length too short");
        return DNS_SEC_PARSE_ERR;
    }

    // Pointer to iterate over the data
    const uint8_t *cursor = data;

    // Parse the flags, protocol, and algorithm from the record
    res->flags = (uint16_t)(*cursor) << 8 | *(cursor + 1);  // Flags span two bytes
    cursor += 2;                                            // Move past the flags

    res->protocol = *cursor;  // Protocol is one byte
    cursor += 1;

    res->algorithm = *cursor;  // Algorithm is one byte
    cursor += 1;

    // Calculate the length of the public key data
    res->key_length = data_len - 4;  // Subtract the length of flags, protocol, and algorithm fields

    // Allocate memory for the public key
    res->public_key = k_heap_alloc(&dns_heap, res->key_length * sizeof(uint8_t), K_NO_WAIT);
    if (res->public_key == NULL) {
        LOG_ERR("Memory allocation for public key failed");
        return DNS_SEC_MEMORY_ERROR;
    }

    // Copy the public key data
    memcpy(res->public_key, cursor, res->key_length);

    // Optional: Log or handle the data, for example, printing the extracted information.
    LOG_INF("DNSKEY parsed: Flags=0x%04X, Protocol=%u, Algorithm=%u, Key Length=%zu",
            res->flags, res->protocol, res->algorithm, res->key_length);

    return DNS_SEC_SUCCESS;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                DNS SEC Record Parser
 *---------------------------------------------------------------------------------------------------*/

static dns_sec_error_t extract_rrsig_fields(const uint8_t *data, uint16_t data_len, rrsig_record_t *rrsig_record);
dns_sec_error_t validate_rrsig_record(const rrsig_record_t *rrsig, const uint8_t *original_record_data, size_t original_data_length);

// The main function to parse and validate the RRSIG record.
static dns_sec_error_t parse_rrsig_record(const uint8_t *data, uint16_t data_len, struct addrinfo *res) {
    if (!data || data_len < RRSIG_RECORD_MINIMUM_LENGTH) {  // Make sure to define the appropriate length based on the DNSSEC standard.
        LOG_WRN("Invalid RRSIG record data");
        return DNS_SEC_INVALID_PARAM_ERR;
    }

    dns_sec_error_t err;
    rrsig_record_t rrsig_record;  // You might need to handle dynamic memory allocation for some fields within this struct.

    // Extract RRSIG fields into the struct.
    err = extract_rrsig_fields(data, data_len, &rrsig_record);
    if (err != DNS_SEC_SUCCESS) {
        // Handle error, free memory if allocated.
        return err;
    }

    // Perform cryptographic validation using the filled struct.
    err = validate_rrsig_record(&rrsig_record, data, data_len);
    if (err != DNS_SEC_SUCCESS) {
        // Handle error, free memory if allocated.
        return err;
    }

    // Clean up, specifically ensure any dynamically allocated memory is properly released.
    // For example, if you allocated memory for 'signer_name' or 'signature', you should free it here.
    // ...

    LOG_DBG("RRSIG record parsed and validated successfully");

    return DNS_SEC_SUCCESS;
}

// Implementing the field extraction function.
static dns_sec_error_t extract_rrsig_fields(const uint8_t *data, uint16_t data_len, rrsig_record_t *rrsig_record) {

    const uint8_t *current_position = data;

    // Extract fixed-size fields with direct memcpy, converting byte order as necessary.
    memcpy(&(rrsig_record->type_covered), current_position, sizeof(rrsig_record->type_covered));
    rrsig_record->type_covered = ntohs(rrsig_record->type_covered);
    current_position += sizeof(rrsig_record->type_covered);

    memcpy(&(rrsig_record->algorithm), current_position, sizeof(rrsig_record->algorithm));
    current_position += sizeof(rrsig_record->algorithm);

    memcpy(&(rrsig_record->labels), current_position, sizeof(rrsig_record->labels));
    current_position += sizeof(rrsig_record->labels);

    memcpy(&(rrsig_record->original_ttl), current_position, sizeof(rrsig_record->original_ttl));
    rrsig_record->original_ttl = ntohl(rrsig_record->original_ttl);
    current_position += sizeof(rrsig_record->original_ttl);

    memcpy(&(rrsig_record->signature_expiration), current_position, sizeof(rrsig_record->signature_expiration));
    rrsig_record->signature_expiration = ntohl(rrsig_record->signature_expiration);
    current_position += sizeof(rrsig_record->signature_expiration);

    memcpy(&(rrsig_record->signature_inception), current_position, sizeof(rrsig_record->signature_inception));
    rrsig_record->signature_inception = ntohl(rrsig_record->signature_inception);
    current_position += sizeof(rrsig_record->signature_inception);

    memcpy(&(rrsig_record->key_tag), current_position, sizeof(rrsig_record->key_tag));
    rrsig_record->key_tag = ntohs(rrsig_record->key_tag);
    current_position += sizeof(rrsig_record->key_tag);

    // Skip the signer's name field. We're not extracting it, just moving the cursor position past this field.
    uint8_t *new_position = skip_name_field((uint8_t *)current_position, (uint8_t *)data, (uint8_t *)(data + data_len));
    if (new_position == NULL) {
        return DNS_SEC_PARSE_ERR;
    }

    current_position = new_position;

    // Now, you need to handle the signature. Since the signature is variable length and the last field,
    // you calculate the length by subtracting the current position from the end of the buffer.
    rrsig_record->signature_length = data_len - (current_position - data);

    if (rrsig_record->signature_length == 0) {
        LOG_WRN("Record signature length is 0");
        return DNS_SEC_INVALID_RESPONSE;
    }

    // Allocate memory for the signature and copy it from the buffer.
    rrsig_record->signature = k_heap_alloc(&dns_heap, rrsig_record->signature_length, K_NO_WAIT);  // TODO: free this cunt
    if (!rrsig_record->signature) {
        LOG_WRN("Malloc failed");
        return DNS_SEC_MEMORY_ERROR;
    }
    memcpy(rrsig_record->signature, current_position, rrsig_record->signature_length);

    return DNS_SEC_SUCCESS;
}

dns_sec_error_t retrieve_dnskey(const char *domain, dnskey_record_t **records);
dns_sec_error_t verify_rrsig_with_dnskey(const rrsig_record_t *rrsig, const dnskey_record_t *dnskey);

// Main function to validate an RRSIG record.
dns_sec_error_t validate_rrsig_record(const rrsig_record_t *rrsig, const uint8_t *original_record_data, size_t original_data_length) {
    if (!rrsig || !original_record_data) {
        return DNS_SEC_INVALID_PARAM_ERR;  // Or similar error code.
    }

    // dns_sec_error_t error = retrieve_dnskey(rrsig->signer_name, &dnskey);
    dnskey_record_t *records = NULL;
    dns_sec_error_t error = retrieve_dnskey("mateosegura.com", &records);
    if (error != DNS_SEC_SUCCESS) {
        // Handle error (e.g., DNSKEY not found, network error, etc.).
        return error;
    }

    // Now that we have the DNSKEY, we can verify the RRSIG's signature.
    for (size_t i = 0; i < 4; i++) {
        error = verify_rrsig_with_dnskey(rrsig, &records[i]);
        if (error != DNS_SEC_SUCCESS) {
            // Handle error (e.g., signature verification failed).
            return error;
        }
    }

    // If we reach here, it means the RRSIG record's signature is valid.
    return DNS_SEC_SUCCESS;
}

static void create_dns_query_header(dns_header_t *header) {
    // The beginning is standard for any DNS message.
    sys_rand_get(&header->id, sizeof(uint16_t));  // Query ID must be randomized
    header->rd = 1;                               // Recursion Desired: the client wants recursive resolution
    header->tc = 0;                               // This message is not truncated
    header->aa = 0;                               // Not Authoritative
    header->opcode = 0;                           // Standard query
    header->qr = 0;                               // This is a query
    // Omit rcode since it's not used in queries
    header->cd = 0;  // Checking Disabled. 0 indicates that the server should do DNSSEC validation for the reply.
    // Omit ad - it's used in responses, not in queries
    // Omit z - reserved for future use
    // Omit ra - it's used in responses, not in queries
    header->q_count = 1;  // We have only one question
    // Omit ans_count, auth_count, and add_count here; they are used in responses, not in queries

    // Now, for DNSSEC, you often use EDNS0 (indicated with an OPT record), which allows for DNSSEC data to be transmitted.
    // This means your message will actually have an additional section. Normally, you indicate this like so:
    header->add_count = 1;  // Indicates you have additional records, like OPT for EDNS0
}

dns_sec_error_t construct_dnskey_query(uint8_t *buffer, size_t buffer_size, uint16_t *query_size, const char *domain, dns_sec_query_t *query) {
    create_dns_query_header(&query->header);

    // Assure the domain is formatted correctly for DNS.
    static char dns_formatted_domain[DNS_NAME_MAX_LEN];  // Define the max size appropriately.
    format_domain_name(dns_formatted_domain, domain);
    query->domain = dns_formatted_domain;
    query->domain_length = strlen(dns_formatted_domain) + 1;  // Include space for the null terminator

    query->qtype = 48;  // 48 is for DNSKEY records
    query->qclass = 1;  // 1 is for Internet address (IN)

    create_opt_request_record(&query->opt_record);

    // Pack the query into the buffer for sending.
    return net_pack_dns_sec_query(buffer, buffer_size, query_size, query);
}

dns_sec_error_t retrieve_dnskey(const char *domain, dnskey_record_t **records) {
    if (!domain) {
        return DNS_SEC_INVALID_PARAM_ERR;  // Error code for invalid parameters
    }

    // Prepare the buffer for the DNS query.
    static uint8_t query_buffer[DNS_QUERY_SIZE];  // Define the max size appropriately.
    uint16_t query_size = 0;

    dns_sec_query_t dns_query;
    dns_sec_error_t error = construct_dnskey_query(query_buffer, sizeof(query_buffer), &query_size, domain, &dns_query);
    if (error != DNS_SEC_SUCCESS) {
        return error;
    }

    // Send the DNS query.
    const struct dns_resolve_context *ctx = dns_resolve_get_default();
    struct sockaddr_in *dns_addr = (struct sockaddr_in *)&ctx->servers[0].dns_server;
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);  // Or use an existing socket.
    error = send_dns_query(sock, query_buffer, query_size, dns_addr);
    if (error != DNS_SEC_SUCCESS) {
        close(sock);  // Or the appropriate function to close your socket.
        return error;
    }

    socklen_t sender_address_len = sizeof(*dns_addr);
    size_t response_size = recvfrom(sock, query_buffer, sizeof(query_buffer), 0, (struct sockaddr *)dns_addr, &sender_address_len);
    if (response_size < 0) {
        return DNS_SEC_RECV_ERR;
    }

    get_dns_keys_from_response(query_buffer, response_size, records);

    close(sock);  // Or the appropriate function to close your socket after handling the response.

    return DNS_SEC_SUCCESS;  // Or the appropriate error code.
}

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
// Include headers for your cryptographic library here.

// Assuming you have an enum or defined constants for DNS security errors.

// Function to verify the RRSIG using the DNSKEY.
dns_sec_error_t verify_rrsig_with_dnskey(const rrsig_record_t *rrsig, const dnskey_record_t *dnskey) {
    if (!rrsig || !dnskey) {
        return DNS_SEC_INVALID_PARAM_ERR;  // Or similar error code.
    }

    // Validate the algorithm.
    if (rrsig->algorithm != dnskey->algorithm) {
        LOG_WRN("Algorithm mismatch error");
        return DNS_SEC_ALGORITHM_MISMATCH_ERR;  // Or similar error code.
    }

    // Here you would set up your cryptographic library and prepare it for verification.
    // This involves loading the public key, setting up the signature, and preparing any
    // other cryptographic parameters based on the 'algorithm' field.

    // Pseudo-code for setting up the cryptographic context.
    // crypto_context_t context;
    // if (!crypto_context_init(&context, dnskey->algorithm, dnskey->public_key, dnskey->key_length)) {
    //     return DNS_SEC_CRYPTO_SETUP_ERR;  // Or similar error code.
    // }

    // Next, you'd prepare the data that was signed. This is usually the original record data
    // and some additional metadata, all formatted according to the DNSSEC specifications.
    // The exact preparation method will depend on those specifications and your cryptographic library.

    // Pseudo-code for preparing the signed data.
    // uint8_t *signed_data;
    // size_t signed_data_length;
    // if (!prepare_signed_data(rrsig, original_record_data, original_data_length, &signed_data, &signed_data_length)) {
    //     crypto_context_cleanup(&context);
    //     return DNS_SEC_SIGNED_DATA_ERR;  // Or similar error code.
    // }

    // Now you would actually verify the signature. This step will again depend greatly on your
    // cryptographic library and the specifics of the DNSSEC algorithm you're implementing.

    // Pseudo-code for verifying the signature.
    // bool verification_successful = crypto_verify_signature(&context, signed_data, signed_data_length, rrsig->signature, rrsig->signature_length);

    // Cleanup the cryptographic context and any other resources.
    // crypto_context_cleanup(&context);
    // free(signed_data);

    // Check the result of the verification and return the appropriate status.
    // if (!verification_successful) {
    //     return DNS_SEC_VERIFICATION_FAILED;  // Signature did not match.
    // }

    return DNS_SEC_SUCCESS;  // Signature is valid.
}
