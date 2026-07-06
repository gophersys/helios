// cipher-bench: drives RPC and stream workloads against a remote cipher node
// (firmware or Go) for interop verification and benchmarking.
package main

import (
	"encoding/binary"
	"flag"
	"fmt"
	"log"
	"sort"
	"time"

	"github.com/gophersys/cipher-go/cipher"
	"github.com/gophersys/cipher-go/iface"
)

func main() {
	host := flag.String("host", "10.168.0.97", "remote host")
	port := flag.Uint("port", 5555, "remote port")
	deviceID := flag.Uint("device-id", 0x0009, "this node's device id")
	remoteID := flag.Uint("remote-id", 0x0001, "remote device id")
	mode := flag.String("mode", "stream", "stream | rpc")
	streamBytes := flag.Int("stream-bytes", 256*1024, "stream payload size")
	streamChunk := flag.Int("stream-chunk", 1000, "stream chunk size")
	rpcService := flag.Uint("rpc-service", 100, "rpc service id")
	rpcOp := flag.Uint("rpc-op", 1, "rpc op id")
	rpcCount := flag.Int("rpc-count", 1000, "rpc calls for latency distribution")
	flag.Parse()

	client := &iface.Interface{Type: iface.TypeSocket, Link: iface.LinkTypeClient,
		Host: *host, Port: uint16(*port), RecvTimeout: 10 * time.Second}
	daemon := cipher.NewDaemon(cipher.Config{
		DeviceID:      uint16(*deviceID),
		ClientIfaces:  []*iface.Interface{client},
		LocalServices: []cipher.Service{{ID: 9, Name: "go-bench", AllowedHops: 1}},
	})
	log.Printf("cipher-bench booting (device 0x%04x -> %s:%d, mode=%s)", *deviceID, *host, *port, *mode)
	daemon.Start()

	// Wait for a route to the remote device (learned from its SD broadcast).
	deadline := time.Now().Add(8 * time.Second)
	for time.Now().Before(deadline) && daemon.Route(uint16(*remoteID)) == nil {
		time.Sleep(100 * time.Millisecond)
	}
	if daemon.Route(uint16(*remoteID)) == nil {
		log.Fatalf("no route to remote 0x%04x", *remoteID)
	}

	switch *mode {
	case "stream":
		blob := make([]byte, *streamBytes)
		for i := range blob {
			blob[i] = byte(i*31 + 7)
		}
		t0 := time.Now()
		sent, err := daemon.SendStream(uint16(*remoteID), 1, blob, *streamChunk)
		dt := time.Since(t0)
		if err != nil {
			log.Fatalf("stream: %v", err)
		}
		mbps := float64(sent) / 1024.0 / 1024.0 / dt.Seconds()
		fmt.Printf("RESULT stream bytes=%d chunk=%d dur_ms=%d send_MBps=%.2f\n",
			sent, *streamChunk, dt.Milliseconds(), mbps)

	case "rpc":
		latencies := make([]time.Duration, 0, *rpcCount)
		var failures int
		for i := 0; i < *rpcCount; i++ {
			request := make([]byte, 8)
			binary.LittleEndian.PutUint32(request[0:4], uint32(i))
			binary.LittleEndian.PutUint32(request[4:8], uint32(i*2))
			t0 := time.Now()
			response, err := daemon.CallRPC(uint16(*remoteID), uint16(*rpcService), uint8(*rpcOp), request, 3*time.Second)
			latencies = append(latencies, time.Since(t0))
			if err != nil {
				failures++
				continue
			}
			if sum := binary.LittleEndian.Uint32(response); sum != uint32(i)+uint32(i*2) {
				log.Fatalf("rpc %d: add(%d,%d)=%d WRONG", i, i, i*2, sum)
			}
		}
		sort.Slice(latencies, func(a, b int) bool { return latencies[a] < latencies[b] })
		pct := func(p float64) int64 { return latencies[int(float64(len(latencies)-1)*p)].Microseconds() }
		var total time.Duration
		for _, l := range latencies {
			total += l
		}
		fmt.Printf("RESULT rpc count=%d failures=%d min_us=%d mean_us=%d p50_us=%d p99_us=%d max_us=%d\n",
			*rpcCount, failures, latencies[0].Microseconds(), (total / time.Duration(len(latencies))).Microseconds(),
			pct(0.50), pct(0.99), latencies[len(latencies)-1].Microseconds())
	}
}
