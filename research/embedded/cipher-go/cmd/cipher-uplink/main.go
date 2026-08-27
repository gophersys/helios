// cipher-uplink: a Go cipher client node. Dials a downlink (firmware or Go),
// handshakes, exchanges service discovery, and reports what it learned.
package main

import (
	"flag"
	"fmt"
	"log"
	"time"

	"github.com/gophersys/cipher-go/cipher"
	"github.com/gophersys/cipher-go/iface"
)

func main() {
	host := flag.String("host", "cipher-server.local", "downlink host (name or IPv4)")
	port := flag.Uint("port", 5555, "downlink port")
	deviceID := flag.Uint("device-id", 0x0003, "this node's device id")
	collector := flag.String("collector", "", "analyzer UDP collector address (host:port)")
	runFor := flag.Duration("run-for", 15*time.Second, "how long to stay connected")
	flag.Parse()

	analyzer, err := cipher.NewAnalyzer(true, *collector)
	if err != nil {
		log.Fatalf("analyzer: %v", err)
	}

	uplink := &iface.Interface{
		Type:        iface.TypeSocket,
		Link:        iface.LinkTypeClient,
		Host:        *host,
		Port:        uint16(*port),
		RecvTimeout: *runFor,
	}

	daemon := cipher.NewDaemon(cipher.Config{
		DeviceID:     uint16(*deviceID),
		ClientIfaces: []*iface.Interface{uplink},
		LocalServices: []cipher.Service{
			{ID: 77, Name: "go-uplink-probe", AllowedHops: 1},
		},
		Analyzer: analyzer,
	})

	log.Printf("cipher uplink node booting (device id 0x%04x -> %s:%d)", *deviceID, *host, *port)
	daemon.Start()

	deadline := time.After(*runFor)
	ticker := time.NewTicker(2 * time.Second)
	for {
		select {
		case <-deadline:
			services := daemon.Services()
			fmt.Printf("RESULT services_learned=%d %v\n", len(services), services)
			return
		case <-ticker.C:
			if services := daemon.Services(); len(services) > 0 {
				fmt.Printf("RESULT services_learned=%d %v\n", len(services), services)
				return
			}
		}
	}
}
