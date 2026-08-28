package cipher

import (
	"bytes"
	"testing"
)

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       Golden Vectors
 *---------------------------------------------------------------------------------------------------*/

// TestHeaderGoldenVector encodes the exact SD broadcast header observed live
// from the firmware downlink (device 0x0001 -> broadcast, type SD,
// flags SD_BROADCAST, len 39) and checks the wire bytes bit by bit against
// the serdes layout: u32 = svc(0..13) | op(14..21) | len(22..31), BE.
func TestHeaderGoldenVector(t *testing.T) {
	header := Header{
		SourceID:      0x0001,
		DestinationID: 0xFFFF,
		ServiceID:     0,
		OperationID:   0,
		PayloadLength: 39,
		SequenceNum:   0,
		Type:          PacketTypeSD,
		Flags:         FlagSDBroadcast,
		HopCount:      0,
	}

	wire := make([]byte, HeaderSize)
	if err := header.EncodeHeader(wire); err != nil {
		t.Fatalf("encode: %v", err)
	}

	// u32 packed: len 39 << 22 = 0x09C00000 (svc=0, op=0)
	// u16 packed: type SD(1) << 13 = 0x2000
	expected := []byte{
		0x00, 0x01, // source
		0xFF, 0xFF, // destination (broadcast)
		0x09, 0xC0, 0x00, 0x00, // svc|op|len packed, big endian
		0x20, 0x00, // seq|type packed
		0x08, // flags: SD_BROADCAST
		0x00, // hops
	}
	if !bytes.Equal(wire, expected) {
		t.Fatalf("wire mismatch:\n got %x\nwant %x", wire, expected)
	}
}

func TestHeaderRoundTrip(t *testing.T) {
	original := Header{
		SourceID:      0x0102,
		DestinationID: 0x0304,
		ServiceID:     0x3FFF, // max 14 bits
		OperationID:   0xFF,   // max 8 bits
		PayloadLength: 0x3FF,  // max 10 bits
		SequenceNum:   0x1FFF, // max 13 bits
		Type:          PacketTypeStream,
		Flags:         0xA5,
		HopCount:      7,
	}

	wire := make([]byte, HeaderSize)
	if err := original.EncodeHeader(wire); err != nil {
		t.Fatalf("encode: %v", err)
	}
	decoded, err := DecodeHeader(wire)
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	if decoded != original {
		t.Fatalf("round trip mismatch:\n got %+v\nwant %+v", decoded, original)
	}
}

func TestSDBroadcastRoundTrip(t *testing.T) {
	original := SDBroadcast{
		Alive:       true,
		Name:        "demo-echo",
		ServiceID:   42,
		DeviceID:    0x0001,
		NumOps:      0,
		AllowedHops: 1,
	}

	wire := make([]byte, SDBroadcastSize)
	if err := original.Encode(wire); err != nil {
		t.Fatalf("encode: %v", err)
	}
	if len(wire) != 39 {
		t.Fatalf("SD broadcast must be 39 bytes on the wire, got %d", len(wire))
	}

	decoded, err := DecodeSDBroadcast(wire)
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	if decoded != original {
		t.Fatalf("round trip mismatch:\n got %+v\nwant %+v", decoded, original)
	}
}
