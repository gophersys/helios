package cipher

import (
	"encoding/binary"
	"testing"
	"time"

	"github.com/gophersys/cipher-go/iface"
)

// startPair brings up a server daemon and a client daemon connected over
// loopback, returning once service discovery has established routes both ways.
func startPair(t *testing.T, port uint16, serverCfg, clientCfg Config) (*Daemon, *Daemon) {
	t.Helper()

	serverCfg.ServerIfaces = []*iface.Interface{{Type: iface.TypeSocket, Link: iface.LinkTypeServer, Port: port}}
	if len(serverCfg.LocalServices) == 0 {
		serverCfg.LocalServices = []Service{{ID: 1, Name: "srv", AllowedHops: 1}}
	}
	server := NewDaemon(serverCfg)
	server.Start()
	time.Sleep(150 * time.Millisecond)

	clientCfg.ClientIfaces = []*iface.Interface{{
		Type: iface.TypeSocket, Link: iface.LinkTypeClient,
		Host: "127.0.0.1", Port: port, RecvTimeout: 5 * time.Second,
	}}
	if len(clientCfg.LocalServices) == 0 {
		clientCfg.LocalServices = []Service{{ID: 2, Name: "cli", AllowedHops: 1}}
	}
	client := NewDaemon(clientCfg)
	client.Start()

	// Wait until the client has learned a route to the server device.
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if client.route(serverCfg.DeviceID) != nil {
			return server, client
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatal("client never learned a route to the server")
	return nil, nil
}

// TestRPCGoToGo exercises a full request -> handler -> response round trip.
func TestRPCGoToGo(t *testing.T) {
	const svc, op uint16 = 100, 1

	serverCfg := Config{
		DeviceID: 0x0001,
		RPCHandlers: map[uint32]RPCHandler{
			RPCKey(svc, uint8(op)): func(request []byte) ([]byte, error) {
				a := binary.LittleEndian.Uint32(request[0:4])
				b := binary.LittleEndian.Uint32(request[4:8])
				response := make([]byte, 4)
				binary.LittleEndian.PutUint32(response, a+b)
				return response, nil
			},
		},
		LocalServices: []Service{{ID: svc, Name: "math", AllowedHops: 1, NumOps: 1}},
	}
	server, client := startPair(t, 47100, serverCfg, Config{DeviceID: 0x0002})
	_ = server
	_ = client

	request := make([]byte, 8)
	binary.LittleEndian.PutUint32(request[0:4], 5)
	binary.LittleEndian.PutUint32(request[4:8], 7)

	response, err := client.CallRPC(0x0001, svc, uint8(op), request, 3*time.Second)
	if err != nil {
		t.Fatalf("CallRPC: %v", err)
	}
	if sum := binary.LittleEndian.Uint32(response); sum != 12 {
		t.Fatalf("add(5,7) = %d, want 12", sum)
	}
}

// TestStreamGoToGo streams a large blob and verifies length + checksum on the
// receiving daemon.
func TestStreamGoToGo(t *testing.T) {
	server, client := startPair(t, 47101, Config{DeviceID: 0x0001}, Config{DeviceID: 0x0002})
	_ = server
	_ = client

	const size = 256 * 1024
	blob := make([]byte, size)
	for i := range blob {
		blob[i] = byte(i*31 + 7)
	}

	sent, err := client.SendStream(0x0001, 1, blob, 1000)
	if err != nil {
		t.Fatalf("SendStream: %v", err)
	}
	if sent != size {
		t.Fatalf("sent %d bytes, want %d", sent, size)
	}

	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if stats, ok := server.LastStreamRx(); ok && stats.ReceivedLen == size {
			if !stats.ChecksumOK {
				t.Fatalf("checksum mismatch: got 0x%08x over %d bytes", stats.Checksum, stats.ReceivedLen)
			}
			if stats.NumChunks == 0 {
				t.Fatal("no chunks recorded")
			}
			return // stream received, reassembled, checksum verified
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatal("stream never completed on the receiver")
}
