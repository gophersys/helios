package cipher

import (
	"encoding/binary"
	"fmt"
	"io"
	"log"
	"sync"
	"time"

	"github.com/gophersys/cipher-go/iface"
)

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Daemon
 *---------------------------------------------------------------------------------------------------*/

// Service is a service this node offers or has learned about.
type Service struct {
	ID          uint16
	Name        string
	AllowedHops uint8
	NumOps      uint8
}

// Config is the user configuration for a daemon node (cipher_daemon_config_t).
type Config struct {
	DeviceID      uint16
	ClientIfaces  []*iface.Interface    // Uplinks: this node dials out
	ServerIfaces  []*iface.Interface    // Downlinks: this node accepts
	LocalServices []Service             // Broadcast to peers on connect
	RPCHandlers   map[uint32]RPCHandler // key: rpcKey(service, op) — server-side RPCs
	Analyzer      *Analyzer             // Optional observability (nil = off)
}

// Daemon is a running cipher node.
type Daemon struct {
	config Config

	registryMutex sync.Mutex
	registry      map[uint16]remoteService // key: service id

	routesMutex sync.Mutex
	routes      map[uint16]*iface.Interface // device id -> transport that reaches it

	rpcMutex   sync.Mutex
	rpcPending map[uint64]*rpcPendingEntry // key: per-call unique token
	rpcToken   uint64                      // monotonic token generator (under rpcMutex)

	streamMutex       sync.Mutex
	streamRx          map[uint32]*streamReassembly // key: streamKey(src, stream id)
	lastStreamRx      StreamStats
	lastStreamSet     bool
	streamCompletions uint32

	waitGroup sync.WaitGroup

	// Shutdown coordination: Stop closes done once, which lets the uplink
	// reconnect loops and downlink accept loops exit so Wait can return.
	stopOnce sync.Once
	done     chan struct{}
}

type remoteService struct {
	service  Service
	deviceID uint16
}

// NewDaemon builds (but does not start) a daemon. Mirrors cipher_daemon_init.
func NewDaemon(config Config) *Daemon {
	return &Daemon{
		config:     config,
		registry:   make(map[uint16]remoteService),
		routes:     make(map[uint16]*iface.Interface),
		rpcPending: make(map[uint64]*rpcPendingEntry),
		streamRx:   make(map[uint32]*streamReassembly),
		done:       make(chan struct{}),
	}
}

// Start launches one goroutine per interface (the Go analogue of the
// firmware's per-interface thread groups). Mirrors cipher_daemon_start.
func (d *Daemon) Start() {
	for index, serverInterface := range d.config.ServerIfaces {
		d.waitGroup.Add(1)
		go d.runDownlink(index, serverInterface)
	}
	for index, clientInterface := range d.config.ClientIfaces {
		d.waitGroup.Add(1)
		go d.runUplink(index, clientInterface)
	}
}

// Wait blocks until every interface goroutine has exited. Without Stop the
// uplink reconnect loops run forever, so Wait only returns after Stop.
func (d *Daemon) Wait() { d.waitGroup.Wait() }

// Stop signals every interface goroutine to exit and closes the transports to
// unblock any in-flight Accept/Recv. It is safe to call more than once. After
// Stop, Wait returns once all goroutines have drained.
func (d *Daemon) Stop() {
	d.stopOnce.Do(func() {
		close(d.done)
		// Closing the transports unblocks a goroutine parked in Accept/Recv.
		// Interface.Close is now internally synchronized, so this is race-free
		// against the owning goroutine's own Create/Connect/Recv/Close calls.
		for _, serverInterface := range d.config.ServerIfaces {
			_ = serverInterface.Close()
		}
		for _, clientInterface := range d.config.ClientIfaces {
			_ = clientInterface.Close()
		}
	})
}

// stopped reports whether Stop has been called (non-blocking).
func (d *Daemon) stopped() bool {
	select {
	case <-d.done:
		return true
	default:
		return false
	}
}

// sleepOrStop waits for the given backoff but returns true immediately if Stop
// is called, so shutdown never has to wait out a reconnect backoff.
func (d *Daemon) sleepOrStop(backoff time.Duration) (stopped bool) {
	select {
	case <-d.done:
		return true
	case <-time.After(backoff):
		return false
	}
}

// Services returns a snapshot of the learned remote services.
func (d *Daemon) Services() map[uint16]uint16 {
	d.registryMutex.Lock()
	defer d.registryMutex.Unlock()

	snapshot := make(map[uint16]uint16, len(d.registry))
	for id, remote := range d.registry {
		snapshot[id] = remote.deviceID
	}
	return snapshot
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Interface
 *---------------------------------------------------------------------------------------------------*/

func (d *Daemon) runDownlink(index int, transport *iface.Interface) {
	defer d.waitGroup.Done()

	if err := transport.Create(); err != nil {
		log.Printf("downlink %d: create: %v", index, err)
		return
	}
	defer transport.Close()

	for {
		if d.stopped() {
			return
		}
		timedOut, err := transport.Accept()
		if err != nil {
			// A listener deadline (idle timeout) is not fatal — the server must
			// stay reachable, so keep accepting instead of going deaf.
			if timedOut {
				continue
			}
			// Stop closes the listener, which surfaces here as a non-timeout
			// error; treat that as a clean shutdown rather than a crash.
			if d.stopped() {
				return
			}
			log.Printf("downlink %d: accept: %v", index, err)
			return
		}
		d.config.Analyzer.IfaceEvent("accept", int32(index))

		if !d.handshakeDownlink(transport) {
			continue
		}

		d.broadcastLocalServices(transport)
		d.receiveLoop(index, transport)
		// The peer that used this transport is gone; drop its routes so senders
		// fail cleanly instead of racing a transport that is about to be reused.
		d.invalidateRoutesVia(transport)
	}
}

func (d *Daemon) runUplink(index int, transport *iface.Interface) {
	defer d.waitGroup.Done()

	// Reconnect loop: a client keeps (re)dialing so a transient failure (stale
	// ARP on a WiFi peer, the peer rebooting) or a dropped connection recovers on
	// its own, instead of the route being lost for the process lifetime.
	for {
		if d.stopped() {
			return
		}
		if err := transport.Create(); err != nil {
			log.Printf("uplink %d: create: %v", index, err)
			if d.sleepOrStop(2 * time.Second) {
				return
			}
			continue
		}

		if _, err := transport.Connect(); err != nil {
			log.Printf("uplink %d: connect: %v (retrying)", index, err)
			transport.Close()
			if d.sleepOrStop(2 * time.Second) {
				return
			}
			continue
		}
		d.config.Analyzer.IfaceEvent("connect", int32(index))

		if d.handshakeUplink(transport) {
			d.broadcastLocalServices(transport)
			d.receiveLoop(index, transport)
		}
		// Invalidate routes BEFORE closing so an in-flight sender observes "no
		// route" (under routesMutex) instead of touching a transport that is
		// being closed and re-dialed on this goroutine.
		d.invalidateRoutesVia(transport)
		transport.Close()
		if d.sleepOrStop(1 * time.Second) { // brief backoff before re-dialing
			return
		}
	}
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Handshake
 *---------------------------------------------------------------------------------------------------*/

// handshakeUplink: send our protocol version (u16, network byte order),
// expect one boolean byte back. Wire-identical to handshake_uplink.
func (d *Daemon) handshakeUplink(transport *iface.Interface) bool {
	log.Printf("Handshaking uplink node")

	version := make([]byte, 2)
	binary.BigEndian.PutUint16(version, ProtocolVersion)
	if _, _, _, err := transport.Send(version); err != nil {
		log.Printf("uplink handshake send: %v", err)
		return false
	}

	// readFull loops across reads: TCP may split even a 1-byte reply behind
	// coalesced follow-on data, and a single Recv is not guaranteed to fill it.
	response := make([]byte, 1)
	if err := readFull(transport, response); err != nil {
		log.Printf("uplink handshake recv: %v", err)
		return false
	}
	if response[0] == 0 {
		log.Printf("server rejected protocol version %d", ProtocolVersion)
		return false
	}

	log.Printf("Uplink handshake succesful")
	return true
}

// handshakeDownlink: receive the client's version, answer with one boolean
// byte. Wire-identical to handshake_downlink.
func (d *Daemon) handshakeDownlink(transport *iface.Interface) bool {
	log.Printf("Handshaking downlink node")

	// Read EXACTLY the 2 version bytes. A single Recv can return fewer than 2
	// bytes (TCP segmentation), so loop with readFull; reading past the 2 bytes
	// would also swallow the peer's coalesced SD broadcast and break framing.
	version := make([]byte, 2)
	if err := readFull(transport, version); err != nil {
		log.Printf("downlink handshake recv: %v", err)
		return false
	}

	remoteVersion := binary.BigEndian.Uint16(version[:2])
	supported := remoteVersion == ProtocolVersion

	answer := []byte{0}
	if supported {
		answer[0] = 1
	}
	if _, _, _, err := transport.Send(answer); err != nil {
		log.Printf("downlink handshake send: %v", err)
		return false
	}
	if !supported {
		log.Printf("client protocol version %d unsupported (want %d)", remoteVersion, ProtocolVersion)
		return false
	}

	log.Printf("Downlink handshake succesful")
	return true
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Service Discovery
 *---------------------------------------------------------------------------------------------------*/

// broadcastLocalServices advertises every local service to the connected
// peer (the SD-B thread's on-connect behavior).
func (d *Daemon) broadcastLocalServices(transport *iface.Interface) {
	for _, service := range d.config.LocalServices {
		header := Header{
			SourceID:      d.config.DeviceID,
			DestinationID: DeviceIDBroadcast,
			Type:          PacketTypeSD,
			Flags:         FlagSDBroadcast,
			PayloadLength: SDBroadcastSize,
		}
		payload := SDBroadcast{
			Alive:       true,
			Name:        service.Name,
			ServiceID:   service.ID,
			DeviceID:    d.config.DeviceID,
			NumOps:      service.NumOps,
			AllowedHops: service.AllowedHops,
		}

		packet := make([]byte, HeaderSize+SDBroadcastSize)
		if err := header.EncodeHeader(packet); err != nil {
			log.Printf("sd encode header: %v", err)
			return
		}
		if err := payload.Encode(packet[HeaderSize:]); err != nil {
			log.Printf("sd encode payload: %v", err)
			return
		}

		d.config.Analyzer.CipherPacket(DirectionTX, header)
		if _, _, _, err := transport.Send(packet); err != nil {
			log.Printf("sd broadcast send: %v", err)
			return
		}
	}
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Receive Loop
 *---------------------------------------------------------------------------------------------------*/

// readFull reads exactly len(buffer) bytes from the transport, looping across
// multiple Recv calls because TCP may split a fixed-size message over several
// segments. Idle read timeouts are retried; a closed connection or a real error
// is returned. It is used only for the fixed-size handshake reads — the packet
// receiveLoop keeps its own stream accumulator and must NOT use this.
func readFull(transport *iface.Interface, buffer []byte) error {
	filled := 0
	for filled < len(buffer) {
		received, connClosed, timedOut, err := transport.Recv(buffer[filled:])
		filled += received // count bytes even when they arrive alongside EOF
		if filled >= len(buffer) {
			return nil
		}
		if connClosed || err == io.EOF {
			return fmt.Errorf("cipher: connection closed after %d/%d bytes", filled, len(buffer))
		}
		if timedOut {
			continue
		}
		if err != nil {
			return err
		}
	}
	return nil
}

// receiveLoop reads packets, decodes headers, and dispatches. One TCP read
// may carry several packets back to back (the firmware coalesces SD
// broadcasts), so the loop walks the buffer by header+payload strides.
func (d *Daemon) receiveLoop(index int, transport *iface.Interface) {
	readBuf := make([]byte, MaxPayloadSize)
	// acc holds bytes that have arrived but not yet formed a complete packet.
	// TCP is a byte stream, so a packet may span reads or several may coalesce.
	acc := make([]byte, 0, 2*MaxPayloadSize)

	for {
		received, connClosed, timedOut, err := transport.Recv(readBuf)

		// Append received bytes BEFORE acting on EOF/timeout. Recv can return
		// data together with io.EOF (or a timeout); handling the terminal
		// condition first would discard those bytes, losing the final packet(s)
		// and desyncing framing on the next connection.
		if received > 0 {
			acc = append(acc, readBuf[:received]...)

			// Frame every complete packet currently buffered.
			offset := 0
			for len(acc)-offset >= HeaderSize {
				header, decodeErr := DecodeHeader(acc[offset:])
				if decodeErr != nil {
					offset = len(acc) // desync guard: drop the buffer
					break
				}
				packetEnd := offset + HeaderSize + int(header.PayloadLength)
				if packetEnd > len(acc) {
					break // rest of this packet has not arrived yet
				}

				d.config.Analyzer.CipherPacket(DirectionRX, header)
				d.recordRoute(header.SourceID, transport)
				d.dispatch(header, acc[offset+HeaderSize:packetEnd])
				offset = packetEnd
			}

			// Slide any trailing partial packet to the front.
			if offset > 0 {
				acc = append(acc[:0], acc[offset:]...)
			}
		}

		if connClosed || err == io.EOF {
			log.Printf("iface %d: connection closed by peer", index)
			d.config.Analyzer.IfaceEvent("close", int32(index))
			return
		}
		if timedOut {
			continue // idle read timeout — keep the connection alive
		}
		if err != nil {
			log.Printf("iface %d: recv: %v", index, err)
			d.config.Analyzer.IfaceEvent("error", int32(index))
			return
		}
	}
}

// recordRoute learns which transport reaches a given device (like the C
// registry's device->interface map) so RPC/stream can be sent back.
func (d *Daemon) recordRoute(deviceID uint16, transport *iface.Interface) {
	d.routesMutex.Lock()
	d.routes[deviceID] = transport
	d.routesMutex.Unlock()
}

// invalidateRoutesVia drops every route that points at transport. It runs under
// routesMutex (the same lock senders take in route()) so that once a transport
// is about to be closed/re-dialed, in-flight senders observe "no route" and
// fail cleanly instead of racing the transport's connection state.
func (d *Daemon) invalidateRoutesVia(transport *iface.Interface) {
	d.routesMutex.Lock()
	for deviceID, routed := range d.routes {
		if routed == transport {
			delete(d.routes, deviceID)
		}
	}
	d.routesMutex.Unlock()
}

// Route returns the transport that reaches a device, or nil.
func (d *Daemon) Route(deviceID uint16) *iface.Interface { return d.route(deviceID) }

func (d *Daemon) route(deviceID uint16) *iface.Interface {
	d.routesMutex.Lock()
	defer d.routesMutex.Unlock()
	return d.routes[deviceID]
}

// sendPacket encodes a header + raw payload and writes it to the transport.
func (d *Daemon) sendPacket(transport *iface.Interface, header Header, payload []byte) error {
	if len(payload) > MaxPacketPayload {
		return fmt.Errorf("cipher: payload length %d exceeds 10-bit max %d", len(payload), MaxPacketPayload)
	}
	header.PayloadLength = uint16(len(payload))
	packet := make([]byte, HeaderSize+len(payload))
	if err := header.EncodeHeader(packet); err != nil {
		return err
	}
	copy(packet[HeaderSize:], payload)
	d.config.Analyzer.CipherPacket(DirectionTX, header)
	_, _, _, err := transport.Send(packet)
	return err
}

func (d *Daemon) dispatch(header Header, payload []byte) {
	switch header.Type {
	case PacketTypeSD:
		if header.Flags&FlagSDBroadcast == 0 {
			return
		}
		broadcast, err := DecodeSDBroadcast(payload)
		if err != nil {
			log.Printf("sd decode: %v", err)
			return
		}

		d.registryMutex.Lock()
		d.registry[broadcast.ServiceID] = remoteService{
			service: Service{
				ID:          broadcast.ServiceID,
				Name:        broadcast.Name,
				AllowedHops: broadcast.AllowedHops,
				NumOps:      broadcast.NumOps,
			},
			deviceID: broadcast.DeviceID,
		}
		d.registryMutex.Unlock()

		log.Printf("registry: learned service %q (id %d) at device 0x%04x",
			broadcast.Name, broadcast.ServiceID, broadcast.DeviceID)

	case PacketTypeRPC:
		d.handleRPCPacket(header, payload)

	case PacketTypeStream:
		d.handleStreamPacket(header, payload)

	default:
		log.Printf("unhandled packet: %s", header)
	}
}

var _ = fmt.Sprintf // keep fmt for future handlers
