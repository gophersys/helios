// cipher-downlink: a Go cipher server node. Accepts uplinks (firmware or Go),
// handshakes, and advertises its local services.
package main

import (
	"flag"
	"log"

	"github.com/gophersys/cipher-go/cipher"
	"github.com/gophersys/cipher-go/iface"
)

func main() {
	port := flag.Uint("port", 5555, "listen port")
	deviceID := flag.Uint("device-id", 0x0004, "this node's device id")
	collector := flag.String("collector", "", "analyzer UDP collector address (host:port)")
	flag.Parse()

	analyzer, err := cipher.NewAnalyzer(true, *collector)
	if err != nil {
		log.Fatalf("analyzer: %v", err)
	}

	downlink := &iface.Interface{
		Type: iface.TypeSocket,
		Link: iface.LinkTypeServer,
		Port: uint16(*port),
	}

	daemon := cipher.NewDaemon(cipher.Config{
		DeviceID:     uint16(*deviceID),
		ServerIfaces: []*iface.Interface{downlink},
		LocalServices: []cipher.Service{
			{ID: 88, Name: "go-echo", AllowedHops: 1},
		},
		Analyzer: analyzer,
	})

	log.Printf("cipher downlink node booting (device id 0x%04x, port %d)", *deviceID, *port)
	daemon.Start()
	daemon.Wait()
}
