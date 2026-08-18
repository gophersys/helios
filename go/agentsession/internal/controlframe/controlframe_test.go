package controlframe_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
)

// controlframe is the ONE HOME for the `eden:` control-frame grammar — the out-of-band frames
// the library tunnels to a harness through the ordinary control path. Today the permission
// frame's shape is written down THREE times: agentsession/identifiers.go:26,61 (the producer),
// claudeadapter/control.go:104,109 (the consumer), and agentsessiontest/events.go:17 (the fake's
// parser). Nothing but a black-box test pinning literals equal keeps them from drifting, and a
// drift is silent at the exact moment it matters: the adapter would stop recognizing a resolved
// decision and fall back to sending it to the model as a plain user turn.
//
// This file is the codec's own suite. It is written BEFORE the package exists — the one place
// in this change where a compile failure is the correct red, because there is no current
// behaviour to pin: the package is new, so `undefined` IS the contract gap. Everything else in
// this feature is proven behaviourally against the pre-R1 tree.
//
// PR-1a lands the PERMISSION family only. The peer family (EncodePeer/DecodePeer and the
// envelope-terminator rejection) is S4's; a scalar-only signature set is deliberate here,
// because taking an agentsession type would make agentsession import its own internal package
// through the adapter and cycle.

// TestEncodePermission_RoundTripsEveryField proves the codec is lossless across the whole frame:
// what EncodePermission writes, DecodePermission reads back field for field.
func TestEncodePermission_RoundTripsEveryField(t *testing.T) {
	t.Parallel()
	for _, testCase := range []struct {
		name      string
		requestID string
		allow     bool
		by        string
		rationale string
	}{
		{"human allow", "req-1", true, "user:mateo", ""},
		{"human deny", "req-2", false, "user:mateo", ""},
		{"policy allow with a colon-bearing identity", "req-3", true, "policy:clean-room", ""},
		{"advisor deny with an audited rationale", "req-4", false, "advisor:reviewer", "the tool writes outside the workspace"},
		{"risk clamp: colon identity AND rationale together", "req-5", false, "policy:risk-clamp", "high-risk tool: overridden to deny; original=advisor:reviewer"},
	} {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			frame := controlframe.EncodePermission(testCase.requestID, testCase.allow, testCase.by, testCase.rationale)
			if !strings.HasPrefix(frame, controlframe.PermissionPrefix) {
				t.Fatalf("frame %q does not carry the permission prefix %q", frame, controlframe.PermissionPrefix)
			}
			requestID, allow, by, rationale, ok := controlframe.DecodePermission(frame)
			if !ok {
				t.Fatalf("DecodePermission(%q) reported not-a-permission-frame", frame)
			}
			if requestID != testCase.requestID {
				t.Errorf("requestID = %q, want %q", requestID, testCase.requestID)
			}
			if allow != testCase.allow {
				t.Errorf("allow = %v, want %v", allow, testCase.allow)
			}
			if by != testCase.by {
				t.Errorf("by = %q, want %q — the deciding identity is the audit stamp and may itself contain ':'", by, testCase.by)
			}
			if rationale != testCase.rationale {
				t.Errorf("rationale = %q, want %q", rationale, testCase.rationale)
			}
		})
	}
}

// TestEncodePermission_NoRationaleIsByteIdenticalToThePreSeparatorForm is the NON-BREAKING
// guarantee the 0x1f separator was added under: a frame carrying no rationale must be exactly
// the historical `eden:permission:<id>:<verdict>:<by>` bytes, with no trailing separator. A
// parser that predates the rationale must read it unchanged.
func TestEncodePermission_NoRationaleIsByteIdenticalToThePreSeparatorForm(t *testing.T) {
	t.Parallel()
	for _, testCase := range []struct {
		requestID string
		allow     bool
		by        string
		want      string
	}{
		{"req-1", true, "user-7", "eden:permission:req-1:allow:user-7"},
		{"req-2", false, "policy:clean-room", "eden:permission:req-2:deny:policy:clean-room"},
	} {
		got := controlframe.EncodePermission(testCase.requestID, testCase.allow, testCase.by, "")
		if got != testCase.want {
			t.Errorf("EncodePermission(%q,%v,%q,\"\") = %q, want the pre-separator form %q",
				testCase.requestID, testCase.allow, testCase.by, got, testCase.want)
		}
		if strings.ContainsRune(got, '\x1f') {
			t.Errorf("a rationale-free frame must carry NO 0x1f separator: %q", got)
		}
	}
}

// TestDecodePermission_ByRetainsItsColons pins the parse rule the identity shape depends on:
// only the FIRST TWO ':' separators are structural (id, verdict), so a "policy:clean-room" or
// "advisor:reviewer" By survives whole. Splitting on every ':' would silently truncate the
// audit identity to "policy".
func TestDecodePermission_ByRetainsItsColons(t *testing.T) {
	t.Parallel()
	requestID, allow, by, rationale, ok := controlframe.DecodePermission("eden:permission:req-1:allow:policy:clean-room")
	if !ok {
		t.Fatal("a well-formed frame with a colon-bearing identity must decode")
	}
	if requestID != "req-1" || !allow || by != "policy:clean-room" || rationale != "" {
		t.Errorf("decoded (%q,%v,%q,%q), want (req-1,true,policy:clean-room,\"\")", requestID, allow, by, rationale)
	}
}

// TestDecodePermission_RejectsWhatIsNotAPermissionFrame is the NEGATIVE half, and it is
// load-bearing: the adapter's Send uses this predicate to decide whether a Steer frame is a
// tunnelled decision or a genuine human interjection. A false positive would swallow the
// operator's steer; a false negative would send the decision to the model as prose.
func TestDecodePermission_RejectsWhatIsNotAPermissionFrame(t *testing.T) {
	t.Parallel()
	for _, text := range []string{
		"",
		"focus on the tests",                        // a genuine Steer interjection
		"eden:budget-exceeded",                      // a different eden: control frame
		"eden:permission:",                          // prefix only
		"eden:permission:req-1",                     // no verdict
		"eden:permission:req-1:allow",               // no deciding identity
		"eden:permission:req-1:maybe:user-7",        // not a verdict
		"eden:peer:req-1:allow:user-7",              // a different frame family
		" eden:permission:req-1:allow:user-7",       // leading space: not the frame
		"prefix eden:permission:req-1:allow:user-7", // embedded, not prefixed
	} {
		if _, _, _, _, ok := controlframe.DecodePermission(text); ok {
			t.Errorf("DecodePermission(%q) reported a permission frame; it is not one", text)
		}
	}
}

// TestPermissionPrefix_IsTheGrammarsOneHome pins the literal exactly once, HERE. Every other
// site (the library's producer, the adapter's consumer, the fake's parser) must cite this
// constant rather than repeat the string — which is the entire point of the package.
func TestPermissionPrefix_IsTheGrammarsOneHome(t *testing.T) {
	t.Parallel()
	if controlframe.PermissionPrefix != "eden:permission:" {
		t.Errorf("PermissionPrefix = %q, want eden:permission: (the frame is already on the wire; it cannot be renamed)",
			controlframe.PermissionPrefix)
	}
}
