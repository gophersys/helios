// Package cipher is the Go implementation of the CoreKinect cipher
// networking protocol — wire-compatible with the Zephyr cipher library
// (gophersys/zephyr-cipher). Encoded packets are network byte-order;
// header layout and bit packing match serdes exactly.
package cipher

import (
	"encoding/binary"
	"fmt"
)

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Protocol
 *---------------------------------------------------------------------------------------------------*/

// ProtocolVersion is exchanged during the connection handshake
// (CIPHER_CONFIG_PROTOCOL_VERSION in the firmware).
const ProtocolVersion uint16 = 1

// MaxPayloadSize bounds a single encoded packet (CONFIG_MAX_PAYLOAD_SIZE).
const MaxPayloadSize = 1024

// ServiceMaxNameLength matches CONFIG_CK_CIPHER_SERVICE_MAX_NAME_LEN.
const ServiceMaxNameLength = 32

// HeaderSize is the encoded header length on the wire:
// u16 source + u16 destination + u32 packed + u16 packed + u8 flags + u8 hops.
const HeaderSize = 12

// PacketType enumerates cipher packet types.
type PacketType uint8

const (
	PacketTypeAdmin PacketType = iota
	PacketTypeSD
	PacketTypeRPC
	PacketTypeEvent
	PacketTypeStream
)

func (t PacketType) String() string {
	switch t {
	case PacketTypeAdmin:
		return "ADMIN"
	case PacketTypeSD:
		return "SD"
	case PacketTypeRPC:
		return "RPC"
	case PacketTypeEvent:
		return "EVENT"
	case PacketTypeStream:
		return "STREAM"
	default:
		return "?"
	}
}

// Flags carried in the header flags byte.
const (
	FlagRPCRequest  uint8 = 1 << 0
	FlagRPCResponse uint8 = 1 << 1
	FlagRPCError    uint8 = 1 << 2
	FlagSDBroadcast uint8 = 1 << 3
)

// Broadcast destination: every device on the network.
const DeviceIDBroadcast uint16 = 0xFFFF

// Header is the decoded cipher packet header (cipher_header_t).
type Header struct {
	SourceID      uint16     // Up to 65536 devices on a single network
	DestinationID uint16     // Up to 65536 devices on a single network
	ServiceID     uint16     // Up to 16384 services (14 bits on the wire)
	OperationID   uint8      // Up to 256 operations per service
	PayloadLength uint16     // Header + payload never exceed 1024 bytes (10 bits)
	SequenceNum   uint16     // Up to 8192 sequences (13 bits)
	Type          PacketType // 3 bits
	Flags         uint8      // Protocol/admin level flags
	HopCount      uint8      // Number of hops the packet has had
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Serdes
 *---------------------------------------------------------------------------------------------------*/

// EncodeHeader writes the 12-byte network-byte-order header into buffer,
// with the identical bit packing serdes_encode_header uses:
//
//	u32: service_id(0..13) | operation_id(14..21) | payload_len(22..31)
//	u16: sequence_num(0..12) | type(13..15)
func (h *Header) EncodeHeader(buffer []byte) error {
	if len(buffer) < HeaderSize {
		return fmt.Errorf("cipher: buffer too small for header: %d < %d", len(buffer), HeaderSize)
	}

	binary.BigEndian.PutUint16(buffer[0:2], h.SourceID)
	binary.BigEndian.PutUint16(buffer[2:4], h.DestinationID)

	packed32 := uint32(h.ServiceID&0x3FFF) |
		uint32(h.OperationID)<<14 |
		uint32(h.PayloadLength&0x3FF)<<22
	binary.BigEndian.PutUint32(buffer[4:8], packed32)

	packed16 := (h.SequenceNum & 0x1FFF) | uint16(h.Type&0x7)<<13
	binary.BigEndian.PutUint16(buffer[8:10], packed16)

	buffer[10] = h.Flags
	buffer[11] = h.HopCount

	return nil
}

// DecodeHeader parses a 12-byte wire header.
func DecodeHeader(buffer []byte) (Header, error) {
	if len(buffer) < HeaderSize {
		return Header{}, fmt.Errorf("cipher: buffer too small for header: %d < %d", len(buffer), HeaderSize)
	}

	packed32 := binary.BigEndian.Uint32(buffer[4:8])
	packed16 := binary.BigEndian.Uint16(buffer[8:10])

	return Header{
		SourceID:      binary.BigEndian.Uint16(buffer[0:2]),
		DestinationID: binary.BigEndian.Uint16(buffer[2:4]),
		ServiceID:     uint16(packed32 & 0x3FFF),
		OperationID:   uint8((packed32 >> 14) & 0xFF),
		PayloadLength: uint16((packed32 >> 22) & 0x3FF),
		SequenceNum:   packed16 & 0x1FFF,
		Type:          PacketType((packed16 >> 13) & 0x7),
		Flags:         buffer[10],
		HopCount:      buffer[11],
	}, nil
}

// String renders the header the same way the ck_analyzer log backend does.
func (h Header) String() string {
	return fmt.Sprintf("0x%04x->0x%04x svc=%d op=%d %s len=%d flags=0x%02x hops=%d",
		h.SourceID, h.DestinationID, h.ServiceID, h.OperationID,
		h.Type, h.PayloadLength, h.Flags, h.HopCount)
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                           Service Discovery Payloads
 *---------------------------------------------------------------------------------------------------*/

// SDBroadcast mirrors cipher_payload_sd_broadcast_t: the 39-byte service
// advertisement (1 alive + 32 name + 2 service + 2 device + 1 ops + 1 hops).
type SDBroadcast struct {
	Alive       bool
	Name        string // Truncated/padded to ServiceMaxNameLength on the wire
	ServiceID   uint16
	DeviceID    uint16
	NumOps      uint8
	AllowedHops uint8
}

// SDBroadcastSize is the encoded payload length.
const SDBroadcastSize = 1 + ServiceMaxNameLength + 2 + 2 + 1 + 1

// Encode writes the SD broadcast payload (network byte order, per-field —
// exactly encode_payload_sd_broadcast).
func (p *SDBroadcast) Encode(buffer []byte) error {
	if len(buffer) < SDBroadcastSize {
		return fmt.Errorf("cipher: buffer too small for sd broadcast: %d", len(buffer))
	}

	if p.Alive {
		buffer[0] = 1
	} else {
		buffer[0] = 0
	}

	name := make([]byte, ServiceMaxNameLength)
	copy(name, p.Name)
	copy(buffer[1:1+ServiceMaxNameLength], name)

	position := 1 + ServiceMaxNameLength
	binary.BigEndian.PutUint16(buffer[position:position+2], p.ServiceID)
	binary.BigEndian.PutUint16(buffer[position+2:position+4], p.DeviceID)
	buffer[position+4] = p.NumOps
	buffer[position+5] = p.AllowedHops

	return nil
}

// DecodeSDBroadcast parses a 39-byte SD broadcast payload.
func DecodeSDBroadcast(buffer []byte) (SDBroadcast, error) {
	if len(buffer) < SDBroadcastSize {
		return SDBroadcast{}, fmt.Errorf("cipher: sd broadcast too short: %d", len(buffer))
	}

	name := buffer[1 : 1+ServiceMaxNameLength]
	end := 0
	for end < len(name) && name[end] != 0 {
		end++
	}

	position := 1 + ServiceMaxNameLength
	return SDBroadcast{
		Alive:       buffer[0] != 0,
		Name:        string(name[:end]),
		ServiceID:   binary.BigEndian.Uint16(buffer[position : position+2]),
		DeviceID:    binary.BigEndian.Uint16(buffer[position+2 : position+4]),
		NumOps:      buffer[position+4],
		AllowedHops: buffer[position+5],
	}, nil
}
