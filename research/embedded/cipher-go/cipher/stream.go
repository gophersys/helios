package cipher

import (
	"encoding/binary"
	"fmt"
	"log"
	"time"

	"github.com/gophersys/cipher-go/iface"
)

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Checksum
 *---------------------------------------------------------------------------------------------------*/

const (
	fnv1aOffsetBasis uint32 = 2166136261
	fnv1aPrime       uint32 = 16777619
)

// FNV1a matches cipher_stream_fnv1a so a Go sender and a firmware receiver
// (and vice versa) agree on the stream checksum.
func FNV1a(seed uint32, data []byte) uint32 {
	hash := seed
	for _, b := range data {
		hash ^= uint32(b)
		hash *= fnv1aPrime
	}
	return hash
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                 Send
 *---------------------------------------------------------------------------------------------------*/

// SendStream chunks data into ordered STREAM packets (START / DATA×N / END),
// wire-identical to cipher_stream_send. Control payloads are little-endian to
// match the firmware's raw-struct framing. Returns bytes sent.
func (d *Daemon) SendStream(deviceID, streamID uint16, data []byte, chunkSize int) (int, error) {
	transport := d.route(deviceID)
	if transport == nil {
		return 0, fmt.Errorf("cipher: no route to device 0x%04x", deviceID)
	}

	maxChunk := MaxPayloadSize - HeaderSize - 4
	if chunkSize <= 0 || chunkSize > maxChunk {
		chunkSize = maxChunk
	}

	// START: total length + stream id
	start := make([]byte, 6)
	binary.LittleEndian.PutUint32(start[0:4], uint32(len(data)))
	binary.LittleEndian.PutUint16(start[4:6], streamID)
	if err := d.sendStreamPacket(transport, deviceID, streamID, FlagStreamStart, 0, start); err != nil {
		return 0, err
	}

	// DATA: ordered chunks
	sent := 0
	seq := uint16(1)
	for sent < len(data) {
		n := chunkSize
		if remaining := len(data) - sent; remaining < n {
			n = remaining
		}
		if err := d.sendStreamPacket(transport, deviceID, streamID, FlagStreamData, seq, data[sent:sent+n]); err != nil {
			return sent, err
		}
		sent += n
		seq++
	}

	// END: declared length + checksum for verification
	end := make([]byte, 8)
	binary.LittleEndian.PutUint32(end[0:4], uint32(len(data)))
	binary.LittleEndian.PutUint32(end[4:8], FNV1a(fnv1aOffsetBasis, data))
	if err := d.sendStreamPacket(transport, deviceID, streamID, FlagStreamEnd, seq, end); err != nil {
		return sent, err
	}

	return sent, nil
}

func (d *Daemon) sendStreamPacket(transport *iface.Interface, dst, streamID uint16,
	flag uint8, seq uint16, payload []byte) error {
	header := Header{
		SourceID:      d.config.DeviceID,
		DestinationID: dst,
		ServiceID:     streamID, // carries the stream id for correlation
		Type:          PacketTypeStream,
		Flags:         flag,
		SequenceNum:   seq,
	}
	return d.sendPacket(transport, header, payload)
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Receive (Reassy)
 *---------------------------------------------------------------------------------------------------*/

// StreamStats mirrors cipher_stream_rx_stats_t.
type StreamStats struct {
	CompletionID uint32 // monotonic per receiving daemon, so readers can dedupe
	StreamID     uint16
	TotalLen     uint32
	ReceivedLen  uint32
	NumChunks    uint32
	Checksum     uint32
	ChecksumOK   bool
	DurationMs   int64
}

type streamReassembly struct {
	streamID  uint16
	totalLen  uint32
	received  uint32
	numChunks uint32
	checksum  uint32
	start     time.Time
}

// streamKey scopes a reassembly to the sending device AND the stream id.
// Keying by stream id alone let two peers streaming the same id clobber each
// other's in-flight reassembly.
func streamKey(sourceID, streamID uint16) uint32 {
	return uint32(sourceID)<<16 | uint32(streamID)
}

func (d *Daemon) handleStreamPacket(header Header, payload []byte) {
	d.streamMutex.Lock()
	defer d.streamMutex.Unlock()

	key := streamKey(header.SourceID, header.ServiceID)

	switch {
	case header.Flags&FlagStreamStart != 0:
		if len(payload) < 6 {
			return
		}
		d.streamRx[key] = &streamReassembly{
			streamID: binary.LittleEndian.Uint16(payload[4:6]),
			totalLen: binary.LittleEndian.Uint32(payload[0:4]),
			checksum: fnv1aOffsetBasis,
			start:    time.Now(),
		}

	case header.Flags&FlagStreamData != 0:
		if reassembly := d.streamRx[key]; reassembly != nil {
			reassembly.received += uint32(len(payload))
			reassembly.numChunks++
			reassembly.checksum = FNV1a(reassembly.checksum, payload)
		}

	case header.Flags&FlagStreamEnd != 0:
		reassembly := d.streamRx[key]
		if reassembly == nil || len(payload) < 8 {
			return
		}
		declaredLen := binary.LittleEndian.Uint32(payload[0:4])
		declaredChecksum := binary.LittleEndian.Uint32(payload[4:8])

		stats := StreamStats{
			StreamID:    reassembly.streamID,
			TotalLen:    reassembly.totalLen,
			ReceivedLen: reassembly.received,
			NumChunks:   reassembly.numChunks,
			Checksum:    reassembly.checksum,
			ChecksumOK:  reassembly.checksum == declaredChecksum && reassembly.received == declaredLen,
			DurationMs:  time.Since(reassembly.start).Milliseconds(),
		}
		d.streamCompletions++
		stats.CompletionID = d.streamCompletions
		d.lastStreamRx = stats
		d.lastStreamSet = true
		delete(d.streamRx, key)

		kibs := int64(0)
		if stats.DurationMs > 0 {
			kibs = int64(stats.ReceivedLen) * 1000 / stats.DurationMs / 1024
		}
		log.Printf("stream %d END: %d bytes / %d chunks in %d ms = %d KiB/s, checksum %v",
			stats.StreamID, stats.ReceivedLen, stats.NumChunks, stats.DurationMs, kibs, stats.ChecksumOK)
	}
}

// LastStreamRx returns stats for the most recently completed inbound stream.
func (d *Daemon) LastStreamRx() (StreamStats, bool) {
	d.streamMutex.Lock()
	defer d.streamMutex.Unlock()
	return d.lastStreamRx, d.lastStreamSet
}
