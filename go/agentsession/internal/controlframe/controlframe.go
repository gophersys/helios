// Package controlframe is the ONE HOME for the `eden:` control-frame grammar — the
// out-of-band frames agentsession tunnels to a harness through the ordinary control path.
// The producer (the library's resolved Decision), the consumer (an adapter's Send) and the
// fake's parser all cite this package, so the frame's shape is written down exactly once
// and cannot drift silently.
//
// The signatures are SCALAR-ONLY on purpose: agentsession imports this package, so taking
// an agentsession type here would cycle.
package controlframe

import "strings"

// PermissionPrefix tags the frame that answers a permission request, so an adapter's Send
// can tell a tunneled decision from a genuine human Steer interjection. It is already on
// the wire and cannot be renamed.
const PermissionPrefix = "eden:permission:"

// rationaleSeparator delimits the OPTIONAL audit rationale appended to a permission frame.
// It is the ASCII unit separator (0x1f), a byte that never appears in a request id, a
// verdict, or a By identity ("user:id" / "policy:name" / "advisor:name") — so a frame
// WITHOUT a rationale is byte-identical to the pre-separator form and a parser that
// predates the rationale reads it unchanged.
const rationaleSeparator = "\x1f"

// EncodePermission renders the answer frame for a resolved permission request: the request
// id, the allow/deny verdict, the deciding identity, and — when the decider supplied one —
// the audit rationale after the 0x1f separator. It carries NO secret and is bounded.
func EncodePermission(requestID string, allow bool, by, rationale string) string {
	verdict := "deny"
	if allow {
		verdict = "allow"
	}
	frame := PermissionPrefix + requestID + ":" + verdict + ":" + by
	if rationale != "" {
		frame += rationaleSeparator + rationale
	}
	return frame
}

// DecodePermission reads a permission answer frame back. ok=false for any text that is not
// one, so a caller falls through to its ordinary interjection path. Only the FIRST TWO ':'
// separators are structural (id, verdict), so a colon-bearing identity such as
// "policy:clean-room" survives whole; the optional rationale rides after the 0x1f separator
// a By can never contain.
func DecodePermission(frame string) (requestID string, allow bool, by, rationale string, ok bool) {
	if !strings.HasPrefix(frame, PermissionPrefix) {
		return "", false, "", "", false
	}
	rest := strings.TrimPrefix(frame, PermissionPrefix)
	requestID, afterID, ok := strings.Cut(rest, ":")
	if !ok {
		return "", false, "", "", false
	}
	verdict, byAndRationale, ok := strings.Cut(afterID, ":")
	if !ok {
		return "", false, "", "", false
	}
	if verdict != "allow" && verdict != "deny" {
		return "", false, "", "", false
	}
	by, rationale, _ = strings.Cut(byAndRationale, rationaleSeparator)
	return requestID, verdict == "allow", by, rationale, true
}
