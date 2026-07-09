// cipher-ota: streams a firmware image to a cipher OTA node. The node receives
// the stream (stream id = OTA_STREAM_ID), writes it into its MCUboot secondary
// slot via flash_img, verifies the checksum, and reboots to swap A/B. Designed
// to run as a Go service in a Kubernetes pod that serves firmware to fleet nodes.
package main

import (
	"crypto/sha256"
	"flag"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/gophersys/cipher-go/cipher"
	"github.com/gophersys/cipher-go/iface"
)

// OTA_STREAM_ID must match the firmware's ota_node (0x00F0).
const otaStreamID = 0x00F0

func main() {
	host := flag.String("host", "", "OTA node host/IP")
	port := flag.Int("port", 5555, "cipher port")
	nodeDev := flag.Int("node-dev", 0x000A, "target node cipher device id")
	selfDev := flag.Int("device-id", 0x00E0, "this server's cipher device id")
	fwPath := flag.String("firmware", "", "path to the signed firmware image")
	chunk := flag.Int("chunk", 1024, "stream chunk size")
	flag.Parse()

	if *host == "" || *fwPath == "" {
		log.Fatal("usage: cipher-ota -host <ip> -firmware <signed.bin> [-node-dev 0xNNNN]")
	}

	fw, err := os.ReadFile(*fwPath)
	if err != nil {
		log.Fatalf("read firmware: %v", err)
	}
	sum := sha256.Sum256(fw)
	fmt.Printf("firmware: %s\n  %d bytes, sha256=%x\n", *fwPath, len(fw), sum[:8])

	uplink := &iface.Interface{
		Type: iface.TypeSocket, Link: iface.LinkTypeClient,
		Host: *host, Port: uint16(*port), RecvTimeout: 15 * time.Second,
	}
	d := cipher.NewDaemon(cipher.Config{
		DeviceID:     uint16(*selfDev),
		ClientIfaces: []*iface.Interface{uplink},
		LocalServices: []cipher.Service{{ID: 0xE0, Name: "ota-server", AllowedHops: 1}},
	})
	d.Start()

	// Wait for the route (handshake + SD) to the node.
	fmt.Printf("connecting to OTA node 0x%04x at %s:%d ...\n", *nodeDev, *host, *port)
	deadline := time.Now().Add(30 * time.Second)
	for time.Now().Before(deadline) && d.Route(uint16(*nodeDev)) == nil {
		time.Sleep(200 * time.Millisecond)
	}
	if d.Route(uint16(*nodeDev)) == nil {
		log.Fatalf("no route to node 0x%04x after 30s", *nodeDev)
	}

	fmt.Printf("streaming firmware (%d bytes, %d-byte chunks) ...\n", len(fw), *chunk)
	t0 := time.Now()
	sent, err := d.SendStream(uint16(*nodeDev), otaStreamID, fw, *chunk)
	dt := time.Since(t0)
	if err != nil {
		log.Fatalf("stream failed after %d/%d bytes: %v", sent, len(fw), err)
	}
	rate := float64(sent) / 1024 / dt.Seconds()
	fmt.Printf("OTA stream complete: %d bytes in %.1fs = %.1f KiB/s\n", sent, dt.Seconds(), rate)
	fmt.Println("node will verify checksum, write slot1, and reboot to swap A/B.")
	time.Sleep(500 * time.Millisecond) // graceful-close flush margin for the END packet
}
