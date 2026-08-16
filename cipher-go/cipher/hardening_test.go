package cipher

import (
	"encoding/binary"
	"net"
	"runtime"
	"strconv"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/cipher-go/iface"
)

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Test Helpers
 *---------------------------------------------------------------------------------------------------*/

// freePort returns a currently-unused TCP port on the loopback interface.
func freePort(t *testing.T) uint16 {
	t.Helper()
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("freePort: %v", err)
	}
	port := listener.Addr().(*net.TCPAddr).Port
	_ = listener.Close()
	return uint16(port)
}

// connectedPair returns a server-side and client-side Interface joined over a
// loopback TCP connection, plus a cleanup that closes both.
func connectedPair(t *testing.T) (server, client *iface.Interface, cleanup func()) {
	t.Helper()
	port := freePort(t)

	server = &iface.Interface{Type: iface.TypeSocket, Link: iface.LinkTypeServer, Port: port}
	if err := server.Create(); err != nil {
		t.Fatalf("server create: %v", err)
	}
	accepted := make(chan error, 1)
	go func() {
		_, err := server.Accept()
		accepted <- err
	}()

	client = &iface.Interface{Type: iface.TypeSocket, Link: iface.LinkTypeClient, Host: "127.0.0.1", Port: port}
	if err := client.Create(); err != nil {
		t.Fatalf("client create: %v", err)
	}
	if _, err := client.Connect(); err != nil {
		t.Fatalf("client connect: %v", err)
	}
	if err := <-accepted; err != nil {
		t.Fatalf("server accept: %v", err)
	}

	return server, client, func() {
		_ = client.Close()
		_ = server.Close()
	}
}

// rawPacket encodes header+payload the way the wire carries them.
func rawPacket(t *testing.T, header Header, payload []byte) []byte {
	t.Helper()
	header.PayloadLength = uint16(len(payload))
	buf := make([]byte, HeaderSize+len(payload))
	if err := header.EncodeHeader(buf); err != nil {
		t.Fatalf("encode header: %v", err)
	}
	copy(buf[HeaderSize:], payload)
	return buf
}

// sdPacketBytes builds a complete SD broadcast packet (header + payload).
func sdPacketBytes(t *testing.T, src, svc, dev uint16, name string) []byte {
	t.Helper()
	header := Header{SourceID: src, DestinationID: DeviceIDBroadcast, Type: PacketTypeSD, Flags: FlagSDBroadcast}
	payload := make([]byte, SDBroadcastSize)
	sd := SDBroadcast{Alive: true, Name: name, ServiceID: svc, DeviceID: dev, AllowedHops: 1}
	if err := sd.Encode(payload); err != nil {
		t.Fatalf("encode sd: %v", err)
	}
	return rawPacket(t, header, payload)
}

func patternBytes(n int, seed byte) []byte {
	b := make([]byte, n)
	for i := range b {
		b[i] = byte(i)*31 + seed
	}
	return b
}

func streamHdr(src, streamID uint16, flag uint8) Header {
	return Header{SourceID: src, ServiceID: streamID, Type: PacketTypeStream, Flags: flag}
}

func streamStartPayload(total int, streamID uint16) []byte {
	p := make([]byte, 6)
	binary.LittleEndian.PutUint32(p[0:4], uint32(total))
	binary.LittleEndian.PutUint16(p[4:6], streamID)
	return p
}

func streamEndPayload(data []byte) []byte {
	p := make([]byte, 8)
	binary.LittleEndian.PutUint32(p[0:4], uint32(len(data)))
	binary.LittleEndian.PutUint32(p[4:8], FNV1a(fnv1aOffsetBasis, data))
	return p
}

// feedStream pushes a whole stream (START/DATA*/END) through handleStreamPacket.
func feedStream(d *Daemon, src, streamID uint16, data []byte, chunk int) {
	d.handleStreamPacket(streamHdr(src, streamID, FlagStreamStart), streamStartPayload(len(data), streamID))
	for off := 0; off < len(data); off += chunk {
		end := off + chunk
		if end > len(data) {
			end = len(data)
		}
		d.handleStreamPacket(streamHdr(src, streamID, FlagStreamData), data[off:end])
	}
	d.handleStreamPacket(streamHdr(src, streamID, FlagStreamEnd), streamEndPayload(data))
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                          M7 — Payload Length Overflow
 *---------------------------------------------------------------------------------------------------*/

func TestEncodeHeaderRejectsOversizedPayload(t *testing.T) {
	tests := []struct {
		name    string
		length  uint16
		wantErr bool
	}{
		{"zero", 0, false},
		{"max-10-bit", MaxPacketPayload, false},  // 1023 fits
		{"one-over", MaxPacketPayload + 1, true}, // 1024 would truncate to 0
		{"way-over", 4095, true},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			h := Header{SourceID: 1, PayloadLength: tc.length, Type: PacketTypeRPC}
			buf := make([]byte, HeaderSize)
			err := h.EncodeHeader(buf)
			if tc.wantErr && err == nil {
				t.Fatalf("EncodeHeader(len=%d): expected error, got nil", tc.length)
			}
			if !tc.wantErr && err != nil {
				t.Fatalf("EncodeHeader(len=%d): unexpected error: %v", tc.length, err)
			}
			// When accepted, the length must survive the round trip (no truncation).
			if !tc.wantErr {
				decoded, derr := DecodeHeader(buf)
				if derr != nil {
					t.Fatalf("decode: %v", derr)
				}
				if decoded.PayloadLength != tc.length {
					t.Fatalf("length truncated: got %d want %d", decoded.PayloadLength, tc.length)
				}
			}
		})
	}
}

func TestSendPacketRejectsOversizedPayload(t *testing.T) {
	d := NewDaemon(Config{DeviceID: 1})
	transport := &iface.Interface{Type: iface.TypeSocket} // never dialed: guard must fire first
	header := Header{SourceID: 1, DestinationID: 2, Type: PacketTypeRPC}

	if err := d.sendPacket(transport, header, make([]byte, MaxPacketPayload+1)); err == nil {
		t.Fatal("sendPacket accepted a payload larger than the 10-bit field")
	}
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                     M4 — Malformed Frames / Final Pkt
 *---------------------------------------------------------------------------------------------------*/

func TestDecodeHeaderShortBufferNoPanic(t *testing.T) {
	for size := 0; size < HeaderSize; size++ {
		size := size
		t.Run(strconv.Itoa(size)+"-bytes", func(t *testing.T) {
			defer func() {
				if r := recover(); r != nil {
					t.Fatalf("DecodeHeader panicked on %d-byte buffer: %v", size, r)
				}
			}()
			if _, err := DecodeHeader(make([]byte, size)); err == nil {
				t.Fatalf("DecodeHeader(%d bytes): expected error", size)
			}
		})
	}
}

// TestReceiveLoopResync feeds an unknown-but-well-formed packet, a valid packet
// split across two writes, and a final valid packet, and asserts framing stays
// in sync (both services learned) with no panic.
func TestReceiveLoopResync(t *testing.T) {
	d := NewDaemon(Config{DeviceID: 0x00AA})
	server, client, cleanup := connectedPair(t)
	defer cleanup()

	loopDone := make(chan struct{})
	go func() {
		d.receiveLoop(0, server)
		close(loopDone)
	}()

	// 1. A well-formed packet of an unhandled type must not desync the stream.
	if _, _, _, err := client.Send(rawPacket(t, Header{SourceID: 0x00BB, Type: PacketTypeEvent}, []byte{1, 2, 3})); err != nil {
		t.Fatalf("send unknown: %v", err)
	}
	// 2. A valid SD packet split across two TCP writes must reassemble.
	sd55 := sdPacketBytes(t, 0x00BB, 55, 0x00BB, "svc55")
	if _, _, _, err := client.Send(sd55[:5]); err != nil {
		t.Fatalf("send split-a: %v", err)
	}
	time.Sleep(20 * time.Millisecond)
	if _, _, _, err := client.Send(sd55[5:]); err != nil {
		t.Fatalf("send split-b: %v", err)
	}
	// 3. Another valid packet afterwards proves continued sync.
	if _, _, _, err := client.Send(sdPacketBytes(t, 0x00BB, 66, 0x00BB, "svc66")); err != nil {
		t.Fatalf("send third: %v", err)
	}

	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		learned := d.Services()
		if learned[55] == 0x00BB && learned[66] == 0x00BB {
			cleanup()
			<-loopDone
			return
		}
		time.Sleep(25 * time.Millisecond)
	}
	t.Fatalf("framing desynced: services=%v", d.Services())
}

// TestReceiveLoopTruncatedThenClose sends fragments smaller than a full frame
// then closes; the loop must return without panic.
func TestReceiveLoopTruncatedThenClose(t *testing.T) {
	cases := map[string][]byte{
		"short-header": {0x00, 0x01, 0x02}, // < HeaderSize
		"header-claims-unarrived-payload": func() []byte { // valid header, payload never comes
			h := Header{SourceID: 0x00BB, Type: PacketTypeSD, Flags: FlagSDBroadcast, PayloadLength: 900}
			b := make([]byte, HeaderSize)
			_ = h.EncodeHeader(b)
			return append(b, 1, 2, 3) // header + a few payload bytes only
		}(),
	}
	for name, frag := range cases {
		frag := frag
		t.Run(name, func(t *testing.T) {
			d := NewDaemon(Config{DeviceID: 0x00AA})
			server, client, cleanup := connectedPair(t)
			defer cleanup()

			loopDone := make(chan struct{})
			go func() {
				d.receiveLoop(0, server)
				close(loopDone)
			}()

			if _, _, _, err := client.Send(frag); err != nil {
				t.Fatalf("send: %v", err)
			}
			time.Sleep(20 * time.Millisecond)
			_ = client.Close()

			select {
			case <-loopDone:
			case <-time.After(2 * time.Second):
				t.Fatal("receiveLoop did not return after peer close")
			}
			if len(d.Services()) != 0 {
				t.Fatalf("incomplete frame was dispatched: %v", d.Services())
			}
		})
	}
}

// TestReceiveLoopFinalPacketBeforeClose guards M4: a packet sent immediately
// before the peer closes must still be processed (bytes appended before EOF).
func TestReceiveLoopFinalPacketBeforeClose(t *testing.T) {
	for attempt := 0; attempt < 20; attempt++ {
		d := NewDaemon(Config{DeviceID: 0x00AA})
		server, client, cleanup := connectedPair(t)

		loopDone := make(chan struct{})
		go func() {
			d.receiveLoop(0, server)
			close(loopDone)
		}()

		if _, _, _, err := client.Send(sdPacketBytes(t, 0x00BB, 55, 0x00BB, "final")); err != nil {
			t.Fatalf("send: %v", err)
		}
		_ = client.Close() // close right behind the write to race data+EOF coalescing

		select {
		case <-loopDone:
		case <-time.After(2 * time.Second):
			t.Fatal("receiveLoop did not return")
		}
		if d.Services()[55] != 0x00BB {
			t.Fatalf("attempt %d: final packet before close was dropped: %v", attempt, d.Services())
		}
		cleanup()
	}
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                    M5 — Stream Reassembly Keying
 *---------------------------------------------------------------------------------------------------*/

// TestConcurrentStreamsSameID interleaves two streams that share a stream id but
// come from different sources; each must reassemble + checksum independently.
func TestConcurrentStreamsSameID(t *testing.T) {
	d := NewDaemon(Config{DeviceID: 0x00AA})

	const sharedID uint16 = 7
	const srcA, srcB uint16 = 0x0001, 0x0002
	dataA := patternBytes(5000, 1)
	dataB := patternBytes(4000, 2)

	// Both START (same id, different source).
	d.handleStreamPacket(streamHdr(srcA, sharedID, FlagStreamStart), streamStartPayload(len(dataA), sharedID))
	d.handleStreamPacket(streamHdr(srcB, sharedID, FlagStreamStart), streamStartPayload(len(dataB), sharedID))

	// Interleave DATA chunks A,B,A,B,...
	const chunk = 500
	for off := 0; off < len(dataA) || off < len(dataB); off += chunk {
		if off < len(dataA) {
			end := off + chunk
			if end > len(dataA) {
				end = len(dataA)
			}
			d.handleStreamPacket(streamHdr(srcA, sharedID, FlagStreamData), dataA[off:end])
		}
		if off < len(dataB) {
			end := off + chunk
			if end > len(dataB) {
				end = len(dataB)
			}
			d.handleStreamPacket(streamHdr(srcB, sharedID, FlagStreamData), dataB[off:end])
		}
	}

	d.handleStreamPacket(streamHdr(srcA, sharedID, FlagStreamEnd), streamEndPayload(dataA))
	statsA, _ := d.LastStreamRx()
	d.handleStreamPacket(streamHdr(srcB, sharedID, FlagStreamEnd), streamEndPayload(dataB))
	statsB, _ := d.LastStreamRx()

	if !statsA.ChecksumOK || statsA.ReceivedLen != uint32(len(dataA)) {
		t.Fatalf("stream A clobbered: %+v", statsA)
	}
	if !statsB.ChecksumOK || statsB.ReceivedLen != uint32(len(dataB)) {
		t.Fatalf("stream B clobbered: %+v", statsB)
	}
}

// TestConcurrentStreamsGoroutines runs two same-id streams from separate goroutines
// to exercise the reassembly map + mutex under -race.
func TestConcurrentStreamsGoroutines(t *testing.T) {
	d := NewDaemon(Config{DeviceID: 0x00AA})
	var wg sync.WaitGroup
	for _, src := range []uint16{0x0001, 0x0002} {
		src := src
		wg.Add(1)
		go func() {
			defer wg.Done()
			feedStream(d, src, 9, patternBytes(3000, byte(src)), 400)
		}()
	}
	wg.Wait()

	d.streamMutex.Lock()
	completions := d.streamCompletions
	d.streamMutex.Unlock()
	if completions != 2 {
		t.Fatalf("expected 2 completions, got %d", completions)
	}
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                             M6 — RPC Pending Keying
 *---------------------------------------------------------------------------------------------------*/

func waitPendingLen(t *testing.T, d *Daemon, want int) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		d.rpcMutex.Lock()
		n := len(d.rpcPending)
		d.rpcMutex.Unlock()
		if n == want {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("pending count never reached %d", want)
}

func rpcResponse(src, svc uint16, op uint8, payload []byte) Header {
	return Header{SourceID: src, ServiceID: svc, OperationID: op, Type: PacketTypeRPC, Flags: FlagRPCResponse}
}

func TestRPCDistinctDevicesGetOwnReply(t *testing.T) {
	const svc uint16 = 100
	const op uint8 = 1
	const devA, devB uint16 = 0x0001, 0x0003

	d := NewDaemon(Config{DeviceID: 0x00AA})
	tA, cleanupA := sinkTransport(t)
	tB, cleanupB := sinkTransport(t)
	defer cleanupA()
	defer cleanupB()
	d.recordRoute(devA, tA)
	d.recordRoute(devB, tB)

	type result struct {
		payload []byte
		err     error
	}
	resA := make(chan result, 1)
	resB := make(chan result, 1)
	go func() { p, e := d.CallRPC(devA, svc, op, []byte("reqA"), 3*time.Second); resA <- result{p, e} }()
	go func() { p, e := d.CallRPC(devB, svc, op, []byte("reqB"), 3*time.Second); resB <- result{p, e} }()

	waitPendingLen(t, d, 2)

	// Deliver replies with the responder's SourceID set to each device.
	d.completeRPC(rpcResponse(devA, svc, op, nil), []byte("ansA"))
	d.completeRPC(rpcResponse(devB, svc, op, nil), []byte("ansB"))

	got := <-resA
	if got.err != nil || string(got.payload) != "ansA" {
		t.Fatalf("device A got %q / %v, want ansA", got.payload, got.err)
	}
	got = <-resB
	if got.err != nil || string(got.payload) != "ansB" {
		t.Fatalf("device B got %q / %v, want ansB", got.payload, got.err)
	}
}

func TestRPCTimeoutDoesNotEvictConcurrent(t *testing.T) {
	const svc uint16 = 100
	const op uint8 = 1
	const devA, devB uint16 = 0x0001, 0x0003

	d := NewDaemon(Config{DeviceID: 0x00AA})
	tA, cleanupA := sinkTransport(t)
	tB, cleanupB := sinkTransport(t)
	defer cleanupA()
	defer cleanupB()
	d.recordRoute(devA, tA)
	d.recordRoute(devB, tB)

	errA := make(chan error, 1)
	resB := make(chan []byte, 1)
	go func() { _, e := d.CallRPC(devA, svc, op, []byte("reqA"), 150*time.Millisecond); errA <- e }()
	go func() { p, _ := d.CallRPC(devB, svc, op, []byte("reqB"), 3*time.Second); resB <- p }()

	waitPendingLen(t, d, 2)

	// Let A time out (its deferred cleanup must delete only A's token).
	if e := <-errA; e == nil {
		t.Fatal("expected device A call to time out")
	}
	// B's slot must survive A's timeout+cleanup.
	d.completeRPC(rpcResponse(devB, svc, op, nil), []byte("ansB"))
	if p := <-resB; string(p) != "ansB" {
		t.Fatalf("device B got %q, want ansB (evicted by A's timeout?)", p)
	}
}

func TestRPCLateReplyDropped(t *testing.T) {
	const svc uint16 = 100
	const op uint8 = 1
	const devA uint16 = 0x0001

	d := NewDaemon(Config{DeviceID: 0x00AA})
	tA, cleanupA := sinkTransport(t)
	defer cleanupA()
	d.recordRoute(devA, tA)

	_, err := d.CallRPC(devA, svc, op, []byte("reqA"), 100*time.Millisecond)
	if err == nil {
		t.Fatal("expected timeout")
	}
	waitPendingLen(t, d, 0)

	// A reply arriving after the caller gave up must be dropped, not panic.
	d.completeRPC(rpcResponse(devA, svc, op, nil), []byte("late"))

	d.rpcMutex.Lock()
	n := len(d.rpcPending)
	d.rpcMutex.Unlock()
	if n != 0 {
		t.Fatalf("late reply left pending state dirty: %d", n)
	}
}

func TestRPCCrossDeviceReplyIgnored(t *testing.T) {
	const svc uint16 = 100
	const op uint8 = 1
	const devB, devX uint16 = 0x0003, 0x0001

	d := NewDaemon(Config{DeviceID: 0x00AA})
	tB, cleanupB := sinkTransport(t)
	defer cleanupB()
	d.recordRoute(devB, tB)

	resB := make(chan []byte, 1)
	go func() { p, _ := d.CallRPC(devB, svc, op, []byte("reqB"), 2*time.Second); resB <- p }()
	waitPendingLen(t, d, 1)

	// A reply from device X (not the target) must NOT complete B's call.
	d.completeRPC(rpcResponse(devX, svc, op, nil), []byte("wrong"))

	d.rpcMutex.Lock()
	stillPending := len(d.rpcPending)
	d.rpcMutex.Unlock()
	if stillPending != 1 {
		t.Fatalf("cross-device reply consumed B's pending slot")
	}

	// The correct reply still completes B.
	d.completeRPC(rpcResponse(devB, svc, op, nil), []byte("ansB"))
	if p := <-resB; string(p) != "ansB" {
		t.Fatalf("device B got %q, want ansB", p)
	}
}

// sinkTransport returns a connected client Interface usable as a send route; its
// peer accepts but never reads (small RPC requests just buffer in the kernel).
func sinkTransport(t *testing.T) (*iface.Interface, func()) {
	t.Helper()
	server, client, cleanup := connectedPair(t)
	_ = server
	return client, cleanup
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                          C6 — Handshake Split Reads
 *---------------------------------------------------------------------------------------------------*/

// TestHandshakeSplitReads writes the 2-byte version one byte at a time so a
// single Recv cannot satisfy it; readFull must loop until both bytes arrive.
func TestHandshakeSplitReads(t *testing.T) {
	d := NewDaemon(Config{DeviceID: 0x00AA})
	server, client, cleanup := connectedPair(t)
	defer cleanup()

	result := make(chan bool, 1)
	go func() { result <- d.handshakeDownlink(server) }()

	// ProtocolVersion big-endian, one byte per write with a gap between them.
	version := []byte{byte(ProtocolVersion >> 8), byte(ProtocolVersion & 0xFF)}
	if _, _, _, err := client.Send(version[:1]); err != nil {
		t.Fatalf("send byte 1: %v", err)
	}
	time.Sleep(30 * time.Millisecond)
	if _, _, _, err := client.Send(version[1:]); err != nil {
		t.Fatalf("send byte 2: %v", err)
	}

	// The downlink answers with one boolean byte; read it so it doesn't linger.
	answer := make([]byte, 1)
	if _, _, _, err := client.Recv(answer); err != nil {
		t.Fatalf("recv answer: %v", err)
	}

	select {
	case ok := <-result:
		if !ok {
			t.Fatal("handshakeDownlink failed on split reads")
		}
		if answer[0] != 1 {
			t.Fatalf("expected accept byte, got %d", answer[0])
		}
	case <-time.After(2 * time.Second):
		t.Fatal("handshakeDownlink hung on split reads")
	}
}

// TestReadFullAcrossManyReads exercises readFull directly with a payload dribbled
// one byte at a time.
func TestReadFullAcrossManyReads(t *testing.T) {
	server, client, cleanup := connectedPair(t)
	defer cleanup()

	want := []byte("handshake-and-then-some")
	go func() {
		for _, b := range want {
			_, _, _, _ = client.Send([]byte{b})
			time.Sleep(2 * time.Millisecond)
		}
	}()

	got := make([]byte, len(want))
	if err := readFull(server, got); err != nil {
		t.Fatalf("readFull: %v", err)
	}
	if string(got) != string(want) {
		t.Fatalf("readFull got %q want %q", got, want)
	}
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                    C6 — Stop / Wait / No Leak
 *---------------------------------------------------------------------------------------------------*/

func waitReturns(t *testing.T, d *Daemon, within time.Duration) {
	t.Helper()
	done := make(chan struct{})
	go func() { d.Wait(); close(done) }()
	select {
	case <-done:
	case <-time.After(within):
		t.Fatal("Wait did not return after Stop")
	}
}

// TestStopReturnsWaitNoLeak brings up a connected server+client daemon (with an
// extra client uplink stuck in the reconnect loop), then Stop must let Wait
// return and leave no goroutines behind.
func TestStopReturnsWaitNoLeak(t *testing.T) {
	time.Sleep(150 * time.Millisecond) // let any prior-test goroutines drain
	runtime.GC()
	baseline := runtime.NumGoroutine()

	serverPort := freePort(t)
	deadPort := freePort(t) // nothing listens here -> uplink stays in reconnect loop

	server := NewDaemon(Config{
		DeviceID:      0x0001,
		ServerIfaces:  []*iface.Interface{{Type: iface.TypeSocket, Link: iface.LinkTypeServer, Port: serverPort}},
		LocalServices: []Service{{ID: 1, Name: "srv", AllowedHops: 1}},
	})
	client := NewDaemon(Config{
		DeviceID: 0x0002,
		ClientIfaces: []*iface.Interface{
			{Type: iface.TypeSocket, Link: iface.LinkTypeClient, Host: "127.0.0.1", Port: serverPort, RecvTimeout: 500 * time.Millisecond},
			{Type: iface.TypeSocket, Link: iface.LinkTypeClient, Host: "127.0.0.1", Port: deadPort},
		},
		LocalServices: []Service{{ID: 2, Name: "cli", AllowedHops: 1}},
	})

	server.Start()
	client.Start()

	// Wait until the live uplink has established a route (both receiveLoops running).
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) && client.route(0x0001) == nil {
		time.Sleep(25 * time.Millisecond)
	}
	if client.route(0x0001) == nil {
		t.Fatal("client never connected to server")
	}

	server.Stop()
	client.Stop()
	waitReturns(t, server, 3*time.Second)
	waitReturns(t, client, 3*time.Second)

	// Idempotent Stop must be safe.
	server.Stop()
	client.Stop()

	// Poll until goroutines settle back to baseline.
	settleDeadline := time.Now().Add(3 * time.Second)
	var current int
	for time.Now().Before(settleDeadline) {
		runtime.GC()
		current = runtime.NumGoroutine()
		if current <= baseline+2 {
			return
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("goroutine leak: baseline=%d current=%d", baseline, current)
}
