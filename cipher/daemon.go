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
	rpcPending map[uint32]chan rpcReply // key: rpcKey(service, op)

	streamMutex       sync.Mutex
	streamRx          map[uint16]*streamReassembly // key: stream id
	lastStreamRx      StreamStats
	lastStreamSet     bool
	streamCompletions uint32

	waitGroup sync.WaitGroup
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
		rpcPending: make(map[uint32]chan rpcReply),
		streamRx:   make(map[uint16]*streamReassembly),
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

// Wait blocks until every interface goroutine has exited.
func (d *Daemon) Wait() { d.waitGroup.Wait() }

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
		if _, err := transport.Accept(); err != nil {
			log.Printf("downlink %d: accept: %v", index, err)
			return
		}
		d.config.Analyzer.IfaceEvent("accept", int32(index))

		if !d.handshakeDownlink(transport) {
			continue
		}

		d.broadcastLocalServices(transport)
		d.receiveLoop(index, transport)
	}
}

func (d *Daemon) runUplink(index int, transport *iface.Interface) {
	defer d.waitGroup.Done()

	// Reconnect loop: a client keeps (re)dialing so a transient failure (stale
	// ARP on a WiFi peer, the peer rebooting) or a dropped connection recovers on
	// its own, instead of the route being lost for the process lifetime.
	for {
		if err := transport.Create(); err != nil {
			log.Printf("uplink %d: create: %v", index, err)
			time.Sleep(2 * time.Second)
			continue
		}

		if _, err := transport.Connect(); err != nil {
			log.Printf("uplink %d: connect: %v (retrying)", index, err)
			transport.Close()
			time.Sleep(2 * time.Second)
			continue
		}
		d.config.Analyzer.IfaceEvent("connect", int32(index))

		if d.handshakeUplink(transport) {
			d.broadcastLocalServices(transport)
			d.receiveLoop(index, transport)
		}
		transport.Close()
		time.Sleep(1 * time.Second) // brief backoff before re-dialing
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

	response := make([]byte, 1)
	received, _, _, err := transport.Recv(response)
	if err != nil || received != 1 {
		log.Printf("uplink handshake recv (%d bytes): %v", received, err)
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

	// Read EXACTLY the 2 version bytes so TCP cannot hand back coalesced
	// follow-on data (the peer's SD broadcast) and break framing.
	version := make([]byte, 2)
	received, _, _, err := transport.Recv(version)
	if err != nil || received != 2 {
		log.Printf("downlink handshake recv (%d bytes): %v", received, err)
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
		if connClosed || (err != nil && err == io.EOF) {
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
}

// recordRoute learns which transport reaches a given device (like the C
// registry's device->interface map) so RPC/stream can be sent back.
func (d *Daemon) recordRoute(deviceID uint16, transport *iface.Interface) {
	d.routesMutex.Lock()
	d.routes[deviceID] = transport
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
