
// https://dnssec-debugger.verisignlabs.com/

#include "../dnssec_err.h"
#include "dnssec_prv.h"

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
    if (header.add_count > 0 && (size_t)(cursor - packet) + sizeof(dns_edns_opt_record_t) <= packet_len) {
        dns_edns_opt_record_t opt_rr;
        memcpy(&opt_rr, cursor, sizeof(opt_rr));

        // Convert relevant fields from network byte order
        opt_rr.type = ntohs(opt_rr.type);
        opt_rr.udp_payload_size = ntohs(opt_rr.udp_payload_size);
        opt_rr.z = ntohs(opt_rr.z);

        LOG_INF("EDNS0 OPT Pseudo-RR:");
        LOG_RAW("\t\t\tType: %u (OPT)\n", opt_rr.type);
        LOG_RAW("\t\t\tUDP payload size: %u\n", opt_rr.udp_payload_size);
        LOG_RAW("\t\t\tExtended RCODE: %u\n", opt_rr.extended_rcode);
        LOG_RAW("\t\t\tEDNS0 version: %u\n", opt_rr.version);
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

void parse_cname_record(const uint8_t *record_data, size_t record_len) {
    LOG_ERR("CNAME not yet supported");
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

    const uint8_t *cursor = packet + sizeof(header);
    const uint8_t *packet_end = packet + packet_len;  // Calculate the end of the packet data.

    // Question Section
    if (header.q_count > 0) {
        for (int i = 0; i < header.q_count; ++i) {
            // Attempt to skip the name field and point to the RR header.
            cursor = skip_name_field(cursor, packet, packet_end);
            if (!cursor) {
                LOG_DBG("Error: Malformed record name or end of packet reached unexpectedly");
                return;  // End the entire function because the packet is malformed
            }

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

    if (header.ans_count > 0) {
        LOG_INF("Answer Section:");

        for (int i = 0; i < header.ans_count; ++i) {

            // Skip the name field in the answer section, accounting for possible name compression.
            cursor = skip_name_field(cursor, packet, packet_end);
            if (!cursor) {
                LOG_DBG("Error: Malformed record name or end of packet reached unexpectedly");
                return;  // End the entire function because the packet is malformed
            }

            // Here, 'cursor' points to the beginning of a resource record header.
            // You need to ensure there's enough remaining length for a resource record header.
            if ((size_t)(packet_end - cursor) < sizeof(dns_resource_record_header_t)) {
                LOG_DBG("Error: Packet too short for resource record header");
                return;  // End the entire function because the packet is truncated
            }

            // Account for compression pointer
            // cursor += sizeof(uint16_t);

            // Directly parse the RR header since we are already at the correct position after using skip_name_field.
            dns_resource_record_header_t rr_header;
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
            // cursor += sizeof(dns_resource_record_header_t);

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
                case DNS_RRSIG_RECORD:
                    parse_rrsig_record(cursor, rr_header.data_len);
                    break;
                case DNS_CNAME_RECORD:
                    parse_cname_record(cursor, rr_header.data_len);
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
