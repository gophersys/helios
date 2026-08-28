// cipher-matrix: interop matrix orchestrator. Connects to every hardware node,
// then drives each cell double-sided — Go->node (push) and node->Go (pull via
// streamctl) — plus RPC latency and a concurrent bidirectional soak, verifying
// checksums throughout. Push results (node receiving) are read back from the
// node collector's JSONL; pull results (Go receiving) from the local daemon.
package main

import (
	"bufio"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"sync"
	"time"

	"github.com/gophersys/cipher-go/cipher"
	"github.com/gophersys/cipher-go/iface"
)

const goDevice = 0x0009
const collectorPath = "/tmp/ck-metrics.jsonl"

type Node struct {
	Name      string
	Host      string
	Dev       uint16
	Transport string
	// per-transport payload sizes
	StreamBytes int
	BigBytes    int
}

var nodes = []Node{
	{"nucleo", "10.168.0.97", 0x000B, "eth", 1 << 20, 100 << 20},    // 1MB / 100MB
	{"esp32-a", "10.168.0.155", 0x000A, "wifi", 128 << 10, 1 << 20}, // 256KB / 4MB
	{"esp32-b", "10.168.0.235", 0x000C, "wifi", 128 << 10, 1 << 20},
}

// collectorReader tails the node collector to pick up node-side stream results.
type collectorReader struct{ offset int64 }

func (c *collectorReader) mark() {
	if fi, err := os.Stat(collectorPath); err == nil {
		c.offset = fi.Size()
	}
}

// waitStream waits for a completed stream on `dev` of ~`bytes` since mark().
func (c *collectorReader) waitStream(dev uint16, bytes int, timeout time.Duration) (ok bool, checksum bool, kibs int) {
	want := fmt.Sprintf("0x%04x", dev)
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		f, err := os.Open(collectorPath)
		if err == nil {
			f.Seek(c.offset, 0)
			sc := bufio.NewScanner(f)
			for sc.Scan() {
				var m struct {
					Kind, Node  string
					Bytes, KibS int
					ChecksumOK  bool `json:"checksum_ok"`
				}
				if json.Unmarshal(sc.Bytes(), &m) != nil {
					continue
				}
				if m.Kind == "stream" && m.Node == want && m.Bytes == bytes {
					f.Close()
					return true, m.ChecksumOK, m.KibS
				}
			}
			f.Close()
		}
		time.Sleep(100 * time.Millisecond)
	}
	return false, false, 0
}

type cellResult struct {
	Node      string
	RPCMeanUs int64
	RPCP99Us  int64
	RPCFail   int
	PushOK    bool
	PushMBps  float64
	PullOK    bool
	PullMBps  float64
	BidiOK    bool
	BigOK     bool
	BigMBps   float64
}

var collector = &collectorReader{}

func rpcLatency(d *cipher.Daemon, dev uint16, n int) (mean, p99 int64, fails int) {
	lat := make([]time.Duration, 0, n)
	for i := 0; i < n; i++ {
		req := make([]byte, 8)
		binary.LittleEndian.PutUint32(req[0:4], uint32(i))
		binary.LittleEndian.PutUint32(req[4:8], uint32(i))
		t0 := time.Now()
		resp, err := d.CallRPC(dev, 100, 1, req, 5*time.Second)
		lat = append(lat, time.Since(t0))
		if err != nil || binary.LittleEndian.Uint32(resp) != uint32(i)+uint32(i) {
			fails++
		}
	}
	sort.Slice(lat, func(a, b int) bool { return lat[a] < lat[b] })
	var tot time.Duration
	for _, l := range lat {
		tot += l
	}
	return (tot / time.Duration(n)).Microseconds(), lat[int(float64(n-1)*0.99)].Microseconds(), fails
}

// push: Go streams `bytes` to the node; verify via the collector.
func push(d *cipher.Daemon, node Node, bytes int) (bool, float64) {
	blob := make([]byte, bytes)
	for i := range blob {
		blob[i] = byte(i*31 + 7)
	}
	collector.mark()
	t0 := time.Now()
	sent, err := d.SendStream(node.Dev, 1, blob, 1000)
	dt := time.Since(t0)
	if err != nil || sent != bytes {
		return false, 0
	}
	ok, csum, _ := collector.waitStream(node.Dev, bytes, 90*time.Second)
	return ok && csum, float64(bytes) / 1024 / 1024 / dt.Seconds()
}

// pull: ask the node to stream `bytes` to Go via streamctl; verify locally.
func pull(d *cipher.Daemon, node Node, bytes int) (bool, float64) {
	req := make([]byte, 8)
	binary.LittleEndian.PutUint16(req[0:2], goDevice)
	binary.LittleEndian.PutUint32(req[2:6], uint32(bytes))
	binary.LittleEndian.PutUint16(req[6:8], 1000)
	var baseline uint32
	if st, ok := d.LastStreamRx(); ok {
		baseline = st.CompletionID
	}
	if _, err := d.CallRPC(node.Dev, 101, 1, req, 10*time.Second); err != nil {
		return false, 0
	}
	deadline := time.Now().Add(90 * time.Second)
	for time.Now().Before(deadline) {
		if st, ok := d.LastStreamRx(); ok && st.CompletionID > baseline && int(st.ReceivedLen) == bytes {
			secs := float64(st.DurationMs) / 1000
			mbps := 0.0
			if secs > 0 {
				mbps = float64(st.ReceivedLen) / 1024 / 1024 / secs
			}
			return st.ChecksumOK, mbps
		}
		time.Sleep(100 * time.Millisecond)
	}
	return false, 0
}

// concurrent bidirectional: push and pull at the same time, both verified.
func bidi(d *cipher.Daemon, node Node, bytes int) bool {
	var wg sync.WaitGroup
	var pushOK, pullOK bool
	wg.Add(2)
	go func() { defer wg.Done(); pushOK, _ = push(d, node, bytes) }()
	go func() { defer wg.Done(); pullOK, _ = pull(d, node, bytes) }()
	wg.Wait()
	return pushOK && pullOK
}

func main() {
	var clients []*iface.Interface
	for _, n := range nodes {
		clients = append(clients, &iface.Interface{
			Type: iface.TypeSocket, Link: iface.LinkTypeClient,
			Host: n.Host, Port: 5555, RecvTimeout: 15 * time.Second,
		})
	}
	d := cipher.NewDaemon(cipher.Config{
		DeviceID:      goDevice,
		ClientIfaces:  clients,
		LocalServices: []cipher.Service{{ID: 9, Name: "orch", AllowedHops: 1}},
	})
	d.Start()

	var results []cellResult
	for _, n := range nodes {
		// Wait for THIS node's route (WiFi nodes can be slow to join); don't gate
		// the whole run on every node being up at the same instant.
		fmt.Printf("\n=== %s (0x%04x, %s): waiting for route... ===\n", n.Name, n.Dev, n.Transport)
		rdeadline := time.Now().Add(45 * time.Second)
		for time.Now().Before(rdeadline) && d.Route(n.Dev) == nil {
			time.Sleep(200 * time.Millisecond)
		}
		if d.Route(n.Dev) == nil {
			fmt.Printf("!! %s (0x%04x): no route after 45s — skipping\n", n.Name, n.Dev)
			continue
		}
		fmt.Printf("\n=== %s (0x%04x, %s) ===\n", n.Name, n.Dev, n.Transport)
		r := cellResult{Node: n.Name}
		r.RPCMeanUs, r.RPCP99Us, r.RPCFail = rpcLatency(d, n.Dev, 300)
		fmt.Printf("  rpc: mean %dus p99 %dus fails %d\n", r.RPCMeanUs, r.RPCP99Us, r.RPCFail)
		r.PushOK, r.PushMBps = push(d, n, n.StreamBytes)
		fmt.Printf("  push Go->%s: %v @ %.2f MB/s\n", n.Name, r.PushOK, r.PushMBps)
		r.PullOK, r.PullMBps = pull(d, n, n.StreamBytes)
		fmt.Printf("  pull %s->Go: %v @ %.2f MB/s\n", n.Name, r.PullOK, r.PullMBps)
		r.BidiOK = bidi(d, n, n.StreamBytes)
		fmt.Printf("  concurrent bidi: %v\n", r.BidiOK)
		r.BigOK, r.BigMBps = push(d, n, n.BigBytes)
		fmt.Printf("  BIG push Go->%s (%d MB): %v @ %.2f MB/s\n", n.Name, n.BigBytes>>20, r.BigOK, r.BigMBps)
		results = append(results, r)
	}

	out, _ := json.MarshalIndent(results, "", "  ")
	os.WriteFile("/tmp/matrix-results.json", out, 0644)
	fmt.Println("\n==== MATRIX SUMMARY ====")
	for _, r := range results {
		fmt.Printf("%-8s rpc=%dus push=%v/%.1fMBps pull=%v/%.1fMBps bidi=%v big=%v/%.1fMBps\n",
			r.Node, r.RPCMeanUs, r.PushOK, r.PushMBps, r.PullOK, r.PullMBps, r.BidiOK, r.BigOK, r.BigMBps)
	}
	fmt.Println("results -> /tmp/matrix-results.json")
}
