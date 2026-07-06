package cipher

import (
	"errors"
	"fmt"
	"time"
)

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  RPC
 *---------------------------------------------------------------------------------------------------*/

// RPCError mirrors cipher_rpc_err_t.
type RPCError uint8

const (
	RPCErrOK RPCError = iota
	RPCErrTimeout
	RPCErrConnLost
	RPCErrNotFound
	RPCErrNotImplemented
)

func (e RPCError) String() string {
	switch e {
	case RPCErrOK:
		return "OK"
	case RPCErrTimeout:
		return "TIMEOUT"
	case RPCErrConnLost:
		return "CONNECTION_LOST"
	case RPCErrNotFound:
		return "NOT_FOUND"
	case RPCErrNotImplemented:
		return "NOT_IMPLEMENTED"
	default:
		return "UNKNOWN"
	}
}

// RPCHandler runs a server-side RPC: opaque request bytes in, response out.
// Returning an error maps to CIPHER_RPC_ERR_NOT_IMPLEMENTED on the wire.
type RPCHandler func(request []byte) ([]byte, error)

// RPCKey builds the map key the way the C registry keys entries: by service +
// operation id. (Same-op concurrent calls collide — same constraint as C.)
func RPCKey(serviceID uint16, opID uint8) uint32 {
	return uint32(serviceID)<<8 | uint32(opID)
}

type rpcReply struct {
	payload []byte
	rpcErr  RPCError
}

// CallRPC invokes a remote RPC and blocks for the response or timeout.
// request/response payloads are opaque bytes — the caller owns their layout
// (raw little-endian packed structs interoperate with the firmware).
func (d *Daemon) CallRPC(deviceID, serviceID uint16, opID uint8, request []byte, timeout time.Duration) ([]byte, error) {
	transport := d.route(deviceID)
	if transport == nil {
		return nil, fmt.Errorf("cipher: no route to device 0x%04x", deviceID)
	}

	key := RPCKey(serviceID, opID)
	replyCh := make(chan rpcReply, 1)

	d.rpcMutex.Lock()
	d.rpcPending[key] = replyCh
	d.rpcMutex.Unlock()
	defer func() {
		d.rpcMutex.Lock()
		delete(d.rpcPending, key)
		d.rpcMutex.Unlock()
	}()

	header := Header{
		SourceID:      d.config.DeviceID,
		DestinationID: deviceID,
		ServiceID:     serviceID,
		OperationID:   opID,
		Type:          PacketTypeRPC,
		Flags:         FlagRPCRequest,
	}
	if err := d.sendPacket(transport, header, request); err != nil {
		return nil, err
	}

	select {
	case reply := <-replyCh:
		if reply.rpcErr != RPCErrOK {
			return nil, fmt.Errorf("cipher: remote RPC error: %s", reply.rpcErr)
		}
		return reply.payload, nil
	case <-time.After(timeout):
		return nil, errors.New("cipher: RPC timeout")
	}
}

// handleRPCPacket dispatches a request to a local handler (server side) or a
// response back to the waiting caller (client side).
func (d *Daemon) handleRPCPacket(header Header, payload []byte) {
	switch {
	case header.Flags&FlagRPCRequest != 0:
		d.serveRPC(header, payload)
	case header.Flags&(FlagRPCResponse|FlagRPCError) != 0:
		d.completeRPC(header, payload)
	}
}

func (d *Daemon) serveRPC(header Header, payload []byte) {
	transport := d.route(header.SourceID)
	if transport == nil {
		return
	}

	respHeader := Header{
		SourceID:      d.config.DeviceID,
		DestinationID: header.SourceID,
		ServiceID:     header.ServiceID,
		OperationID:   header.OperationID,
		Type:          PacketTypeRPC,
	}

	handler := d.config.RPCHandlers[RPCKey(header.ServiceID, header.OperationID)]
	if handler == nil {
		respHeader.Flags = FlagRPCError
		_ = d.sendPacket(transport, respHeader, []byte{byte(RPCErrNotFound)})
		return
	}

	response, err := handler(append([]byte(nil), payload...))
	if err != nil {
		respHeader.Flags = FlagRPCError
		_ = d.sendPacket(transport, respHeader, []byte{byte(RPCErrNotImplemented)})
		return
	}

	respHeader.Flags = FlagRPCResponse
	_ = d.sendPacket(transport, respHeader, response)
}

func (d *Daemon) completeRPC(header Header, payload []byte) {
	d.rpcMutex.Lock()
	replyCh := d.rpcPending[RPCKey(header.ServiceID, header.OperationID)]
	d.rpcMutex.Unlock()
	if replyCh == nil {
		return
	}

	var reply rpcReply
	if header.Flags&FlagRPCError != 0 {
		reply.rpcErr = RPCErrNotFound
		if len(payload) > 0 {
			reply.rpcErr = RPCError(payload[0])
		}
	} else {
		reply.payload = append([]byte(nil), payload...)
	}

	select {
	case replyCh <- reply:
	default: // caller already gave up (timeout); drop
	}
}
