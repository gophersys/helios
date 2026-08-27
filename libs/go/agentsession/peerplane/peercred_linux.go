//go:build linux

package peerplane

import (
	"net"
	"syscall"
)

// peerCredSupported reports that this platform can kernel-verify the peer on an accepted unix
// socket (Linux SO_PEERCRED). Listen fails closed where it is false.
const peerCredSupported = true

// peerUID reads the connecting process's kernel-verified uid via SO_PEERCRED and pins it to the
// connection. ok=false when the socket cannot supply credentials, which serveConn treats as a
// rejected connection — never "trust the socket".
func peerUID(conn net.Conn) (uint32, bool) {
	unixConn, ok := conn.(*net.UnixConn)
	if !ok {
		return 0, false
	}
	raw, err := unixConn.SyscallConn()
	if err != nil {
		return 0, false
	}
	var ucred *syscall.Ucred
	var sockErr error
	controlErr := raw.Control(func(fd uintptr) {
		ucred, sockErr = syscall.GetsockoptUcred(int(fd), syscall.SOL_SOCKET, syscall.SO_PEERCRED)
	})
	if controlErr != nil || sockErr != nil || ucred == nil {
		return 0, false
	}
	return ucred.Uid, true
}
