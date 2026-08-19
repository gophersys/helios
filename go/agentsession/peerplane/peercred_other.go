//go:build !linux

package peerplane

import "net"

// peerCredSupported is false off Linux: this build cannot kernel-verify the peer, so Listen fails
// CLOSED and named rather than trust an unverified socket. The in-process Join/Roster/Send path is
// unaffected — it opens no socket.
const peerCredSupported = false

// peerUID always reports "no credentials" off Linux; Listen never reaches serveConn because it
// fails closed first, so this is the belt-and-suspenders guard.
func peerUID(_ net.Conn) (uint32, bool) { return 0, false }
