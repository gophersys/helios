// Package iface is the Go implementation of the CoreKinect transport
// abstraction layer — the same contract as the Zephyr iface library
// (gophersys/zephyr-iface), so a Go node and a firmware node speak through
// identical semantics: create, connect/accept, send/recv with explicit
// timeout + connection-closed signaling, close.
//
// Only the socket transport is implemented; UART lands when the firmware
// UART transport is next exercised.
package iface

import (
	"errors"
	"fmt"
	"io"
	"net"
	"syscall"
	"time"
)

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Types
 *---------------------------------------------------------------------------------------------------*/

// Type enumerates the physical interfaces supported by the abstraction layer.
type Type int

const (
	TypeSocket Type = iota // Single socket connection
	TypeUART               // UART bus connection (not yet implemented in Go)
)

// LinkType is the connection role of the interface.
type LinkType int

const (
	LinkTypeServer LinkType = iota // Interface behaves as a server
	LinkTypeClient                 // Interface behaves as a client
)

// Interface is the transport configuration + state. Mirrors iface_t.
type Interface struct {
	Type Type     // The type of interface this configuration belongs to
	Link LinkType // The role of the interface

	// Sockets
	Host string // If CLIENT, the remote host (name or IPv4 literal) to connect to
	Port uint16 // CLIENT: remote port. SERVER: local port the listener binds to

	SendTimeout time.Duration // Zero means block forever
	RecvTimeout time.Duration // Zero means block forever

	listener   net.Listener
	connection net.Conn
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/

// Create prepares the interface: a bound listener for servers, nothing yet
// for clients (the socket is created at Connect, matching the C flow where
// resolution also happens on the connect path).
func (i *Interface) Create() error {
	if i.Type != TypeSocket {
		return errors.New("iface: only the socket transport is implemented")
	}
	if i.Port == 0 {
		return errors.New("iface: port cannot be zero")
	}

	if i.Link == LinkTypeServer {
		// SO_REUSEADDR is the Go net default — fast rebinds just work.
		listener, err := net.Listen("tcp4", fmt.Sprintf(":%d", i.Port))
		if err != nil {
			return fmt.Errorf("iface: bind/listen failed: %w", err)
		}
		i.listener = listener
	} else if i.Host == "" {
		return errors.New("iface: remote host cannot be empty")
	}

	return nil
}

// Connect dials the remote end point. Hostnames resolve through the OS
// resolver (the firmware side uses DNS/mDNS via zsock_getaddrinfo — same
// contract: numeric literals take the fast path).
func (i *Interface) Connect() (timedOut bool, err error) {
	dialer := net.Dialer{}
	if i.SendTimeout > 0 {
		dialer.Timeout = i.SendTimeout
	}

	connection, err := dialer.Dial("tcp4", net.JoinHostPort(i.Host, fmt.Sprintf("%d", i.Port)))
	if err != nil {
		var netErr net.Error
		if errors.As(err, &netErr) && netErr.Timeout() {
			return true, err
		}
		return false, fmt.Errorf("iface: connect failed: %w", err)
	}

	i.connection = connection
	return false, nil
}

// Accept blocks for one inbound connection (listen backlog of 1 in the C
// implementation; Go's listener queue behaves equivalently for this use).
func (i *Interface) Accept() (timedOut bool, err error) {
	if i.listener == nil {
		return false, errors.New("iface: Accept before Create")
	}

	if i.RecvTimeout > 0 {
		type deadliner interface{ SetDeadline(time.Time) error }
		if d, ok := i.listener.(deadliner); ok {
			_ = d.SetDeadline(time.Now().Add(i.RecvTimeout))
		}
	}

	connection, err := i.listener.Accept()
	if err != nil {
		var netErr net.Error
		if errors.As(err, &netErr) && netErr.Timeout() {
			return true, err
		}
		return false, fmt.Errorf("iface: accept failed: %w", err)
	}

	i.connection = connection
	return false, nil
}

// Send writes buffer to the connection. Reports (sent, connClosed, timedOut).
func (i *Interface) Send(buffer []byte) (sent int, connClosed bool, timedOut bool, err error) {
	if i.connection == nil {
		return 0, false, false, errors.New("iface: Send before Connect/Accept")
	}
	if i.SendTimeout > 0 {
		_ = i.connection.SetWriteDeadline(time.Now().Add(i.SendTimeout))
	}

	sent, err = i.connection.Write(buffer)
	return sent, isClosed(err), isTimeout(err), err
}

// Recv reads up to len(buffer) bytes. Reports (received, connClosed, timedOut).
func (i *Interface) Recv(buffer []byte) (received int, connClosed bool, timedOut bool, err error) {
	if i.connection == nil {
		return 0, false, false, errors.New("iface: Recv before Connect/Accept")
	}
	if i.RecvTimeout > 0 {
		_ = i.connection.SetReadDeadline(time.Now().Add(i.RecvTimeout))
	}

	received, err = i.connection.Read(buffer)
	return received, isClosed(err), isTimeout(err), err
}

// Close releases the connection and, for servers, the listener.
func (i *Interface) Close() error {
	var firstErr error
	if i.connection != nil {
		firstErr = i.connection.Close()
		i.connection = nil
	}
	if i.Link == LinkTypeServer && i.listener != nil {
		if err := i.listener.Close(); err != nil && firstErr == nil {
			firstErr = err
		}
		i.listener = nil
	}
	return firstErr
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

func isTimeout(err error) bool {
	var netErr net.Error
	return errors.As(err, &netErr) && netErr.Timeout()
}

func isClosed(err error) bool {
	if err == nil {
		return false
	}
	return errors.Is(err, io.EOF) ||
		errors.Is(err, net.ErrClosed) ||
		errors.Is(err, syscall.ECONNRESET) ||
		errors.Is(err, syscall.EPIPE)
}
