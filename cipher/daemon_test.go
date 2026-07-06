package cipher

import (
	"testing"
	"time"

	"github.com/gophersys/cipher-go/iface"
)

// TestGoToGoE2E runs a Go downlink and a Go uplink against each other over
// loopback: full handshake + bidirectional service discovery. This is the
// same flow the firmware interop test exercises against the Nucleo board.
func TestGoToGoE2E(t *testing.T) {
	const port = 45555

	server := NewDaemon(Config{
		DeviceID: 0x00AA,
		ServerIfaces: []*iface.Interface{{
			Type: iface.TypeSocket,
			Link: iface.LinkTypeServer,
			Port: port,
		}},
		LocalServices: []Service{{ID: 88, Name: "go-echo", AllowedHops: 1}},
	})
	server.Start()
	time.Sleep(200 * time.Millisecond) // listener up

	client := NewDaemon(Config{
		DeviceID: 0x00BB,
		ClientIfaces: []*iface.Interface{{
			Type:        iface.TypeSocket,
			Link:        iface.LinkTypeClient,
			Host:        "127.0.0.1",
			Port:        port,
			RecvTimeout: 3 * time.Second,
		}},
		LocalServices: []Service{{ID: 77, Name: "go-probe", AllowedHops: 1}},
	})
	client.Start()

	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		clientLearned := client.Services()
		serverLearned := server.Services()
		if len(clientLearned) == 1 && len(serverLearned) == 1 {
			if device, ok := clientLearned[88]; !ok || device != 0x00AA {
				t.Fatalf("client learned wrong mapping: %v", clientLearned)
			}
			if device, ok := serverLearned[77]; !ok || device != 0x00BB {
				t.Fatalf("server learned wrong mapping: %v", serverLearned)
			}
			return // both sides discovered each other — E2E pass
		}
		time.Sleep(100 * time.Millisecond)
	}

	t.Fatalf("discovery incomplete: client=%v server=%v", client.Services(), server.Services())
}
