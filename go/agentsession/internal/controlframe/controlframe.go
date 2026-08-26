// Package controlframe is the ONE HOME for the `eden:` control-frame grammar — the
// out-of-band frames agentsession tunnels to a harness through the ordinary control path.
// The producer (the library's resolved Decision), the consumer (an adapter's Send) and the
// fake's parser all cite this package, so the frame's shape is written down exactly once
// and cannot drift silently.
//
// The signatures are SCALAR-ONLY on purpose: agentsession imports this package, so taking
// an agentsession type here would cycle.
package controlframe

import (
	"errors"
	"strconv"
	"strings"
)

// PermissionPrefix tags the frame that answers a permission request, so an adapter's Send
// can tell a tunneled decision from a genuine human Steer interjection. It is already on
// the wire and cannot be renamed.
const PermissionPrefix = "eden:permission:"

// PeerPrefix tags the frame that tunnels an inbound peer message to a harness through the
// ordinary control path (the library's deliver goroutine issues it as a prompt/steer; the
// adapter unwraps it and synthesizes the normalized EventPeerMessage). It is a DISTINCT frame
// family from the permission frame, told apart by this prefix.
const PeerPrefix = "eden:peer:"

// peerEnvelopeTerminator is the closing tag of the model-facing delivery envelope
// (<eden-peer-message …>body</eden-peer-message>) an adapter renders from a decoded peer
// frame. A body carrying it could close the envelope early and smuggle instructions to the
// model, so EncodePeer REJECTS such a body at the earliest point (the sender's Send), never
// truncating it silently. It lives here as the grammar's one home.
const peerEnvelopeTerminator = "</eden-peer-message>"

// errPeerBodyEnvelopeTerminator is the loud rejection EncodePeer returns for a body that
// carries the envelope terminator (the prompt-injection guard).
var errPeerBodyEnvelopeTerminator = errors.New("controlframe: peer body carries the </eden-peer-message> envelope terminator")

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

// peerFieldSeparator delimits the header fields of a peer frame. It is the ASCII unit
// separator (0x1f), a byte that cannot appear in a peer name, a minted msg id, or the
// "true"/"false" verified flag — so the five header fields split cleanly and the body, taken as
// the whole remainder, keeps any 0x1f it happens to contain.
//
// That "cannot" is ENFORCED, not assumed. It used to be assumed, and it was false: a peer whose
// NAME carried the separator re-spelled the whole header and chose what the receiver read as
// `from` and as `verified`. Three checks now hold it, all of them ValidatePeerField:
//
//	the plane's register  — a joining name/parent, in-process and over the socket
//	EncodePeer            — all four identity fields, on every send
//	DecodePeer            — the same four again, on the way back (defense in depth)
const peerFieldSeparator = "\x1f"

// peerFieldMetacharacters are the bytes an identity field may not carry because the OTHER peer
// serializer — the model-facing <eden-peer-message> envelope each adapter renders — reads them
// as structure: `<` and `>` open and close a tag, `"` closes an attribute, and `&` opens an
// entity. The wire separator and every other control byte are refused by the control-byte test
// in ValidatePeerField rather than by this set.
const peerFieldMetacharacters = `<>"&`

// peerFieldError reports an identity field carrying a byte one of the two peer serializers
// would read as structure. It is unexported because no caller branches on the type: each
// ingress wraps it with the Kind that is the contract (KindInvalid at a send, a JoinError
// Reason at a join). It names the field and renders the offending byte as an escape — never
// the value, because writing a raw control byte into a log is how one reaches a terminal.
type peerFieldError struct {
	field     string
	offending byte
}

// Error renders the operator-safe message: which field, and which byte.
func (e peerFieldError) Error() string {
	return "controlframe: peer field " + e.field + " carries " + strconv.QuoteRune(rune(e.offending)) +
		", which a peer frame or a delivery envelope would read as structure"
}

// ValidatePeerField enforces the grammar of ONE peer identity field (from, to, msg_id,
// reply_to). It is the boundary check the whole peer path stands on, and it exists exactly
// once: a peer message is serialized TWICE — into the 0x1f-separated wire frame here, and into
// the model-facing envelope in each adapter — so ESCAPING one serializer is a fix that must be
// repeated for the next one, while REFUSING a structural byte where the field enters is a fix
// that need not be.
//
// The BODY is deliberately exempt. It is free agent prose, it rides LAST in the frame so no
// separator inside it can shift a boundary, and each adapter escapes it into the envelope; a
// check that refused the separator everywhere would start rejecting a peer who quotes a control
// frame in its message.
func ValidatePeerField(name, value string) error {
	for i := range len(value) {
		if c := value[i]; c < 0x20 || c == 0x7f || strings.IndexByte(peerFieldMetacharacters, c) >= 0 {
			return peerFieldError{field: name, offending: c}
		}
	}
	return nil
}

// validatePeerIdentity runs ValidatePeerField over all four identity fields in wire order, so
// the encoder and the decoder check the same set in the same way rather than each spelling it.
func validatePeerIdentity(from, to, msgID, replyTo string) error {
	for _, field := range [...]struct{ name, value string }{
		{"from", from}, {"to", to}, {"msg_id", msgID}, {"reply_to", replyTo},
	} {
		if err := ValidatePeerField(field.name, field.value); err != nil {
			return err
		}
	}
	return nil
}

// EncodePeer renders the peer control frame the library tunnels to a harness:
//
//	eden:peer:<from>\x1f<to>\x1f<msgID>\x1f<replyTo>\x1f<verified>\x1f<body>
//
// The body is placed LAST so it may contain any byte (the header fields cannot). It REJECTS a
// body carrying the model-facing envelope terminator so the untrusted body cannot close the
// <eden-peer-message> envelope an adapter later wraps it in — a loud error at the sender, never
// a silent truncation. It carries no secret and is bounded by the caller (MaxPeerBodyBytes).
//
// It also REFUSES any identity field carrying a structural byte, which is what makes the header
// fields' "cannot" true. This is the send-side half of the boundary: every send in the tree
// reaches it (the plane's route validates through this function before it mints an id), so a
// forged frame is never PRODUCED, not merely never decoded.
func EncodePeer(from, to, msgID, replyTo, body string, verified bool) (string, error) {
	if err := validatePeerIdentity(from, to, msgID, replyTo); err != nil {
		return "", err
	}
	if strings.Contains(body, peerEnvelopeTerminator) {
		return "", errPeerBodyEnvelopeTerminator
	}
	verifiedFlag := "false"
	if verified {
		verifiedFlag = "true"
	}
	header := strings.Join([]string{from, to, msgID, replyTo, verifiedFlag}, peerFieldSeparator)
	return PeerPrefix + header + peerFieldSeparator + body, nil
}

// DecodePeer reads a peer frame back. ok=false for any text that is not one, so a caller falls
// through to its ordinary interjection path. The body is the whole remainder after the fifth
// separator, so it survives whole even when it contains the separator byte. The scalar result set
// is wide by design: taking or returning an agentsession.PeerMessage would import-cycle
// (agentsession imports this package), so the fields are spelled out.
//
// It re-validates the four identity fields it decoded. Nothing that passed EncodePeer can fail
// that check, so a failure means the frame was corrupted or forged AFTER the encoder — and a
// decoded field carrying the separator is precisely a shifted boundary, the forgery itself. Such
// a frame is refused (ok=false), never handed up. A caller that must not fall through to its
// ordinary path on a refusal tests PeerPrefix itself; both adapters do, because writing the raw
// internal frame to a model is its own leak.
//
//nolint:gocritic // tooManyResults: the scalar signature is mandated to avoid an import cycle with agentsession.
func DecodePeer(frame string) (from, to, msgID, replyTo, body string, verified, ok bool) {
	if !strings.HasPrefix(frame, PeerPrefix) {
		return "", "", "", "", "", false, false
	}
	rest := strings.TrimPrefix(frame, PeerPrefix)
	parts := strings.SplitN(rest, peerFieldSeparator, 6)
	if len(parts) != 6 {
		return "", "", "", "", "", false, false
	}
	if validatePeerIdentity(parts[0], parts[1], parts[2], parts[3]) != nil {
		return "", "", "", "", "", false, false
	}
	return parts[0], parts[1], parts[2], parts[3], parts[5], parts[4] == "true", true
}
