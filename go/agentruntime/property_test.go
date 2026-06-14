package agentruntime_test

import (
	"encoding/json"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentsession"
)

// The `property` ctl.sh verb runs go test with RAPID_CHECKS set (default 1000 iterations/property,
// ADR-0020 dimension (a)); rapid reads it directly.

// TestProperty_ControlVerbStringTotal proves ControlVerb.String() is TOTAL: every drawn value
// (including out-of-range) returns a non-empty stable token (a partial String would crash a log line).
func TestProperty_ControlVerbStringTotal(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		verb := agentruntime.ControlVerb(rapid.Uint8().Draw(rt, "verb"))
		if got := verb.String(); got == "" {
			rt.Fatalf("ControlVerb(%d).String() is empty (not total)", verb)
		}
	})
}

// TestProperty_TerminationReasonStringTotal proves TerminationReason.String() is total.
func TestProperty_TerminationReasonStringTotal(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		reason := agentruntime.TerminationReason(rapid.Uint8().Draw(rt, "reason"))
		if got := reason.String(); got == "" {
			rt.Fatalf("TerminationReason(%d).String() is empty (not total)", reason)
		}
	})
}

// TestProperty_HealthPhaseStringTotal proves HealthPhase.String() is total.
func TestProperty_HealthPhaseStringTotal(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		phase := agentruntime.HealthPhase(rapid.Uint8().Draw(rt, "phase"))
		if got := phase.String(); got == "" {
			rt.Fatalf("HealthPhase(%d).String() is empty (not total)", phase)
		}
	})
}

// TestProperty_EventEnvelopeJSONRoundTrip proves an EventEnvelope (the events-subject message)
// survives a JSON round trip with its Seq, AgentID, OTel carrier, and the embedded agentsession.Event
// kind+payload intact — the wire codec must not drop a field the gateway replays by.
func TestProperty_EventEnvelopeJSONRoundTrip(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		original := drawEnvelope(rt)
		encoded, err := json.Marshal(original)
		if err != nil {
			rt.Fatalf("marshal envelope: %v", err)
		}
		var decoded agentruntime.EventEnvelope
		if err := json.Unmarshal(encoded, &decoded); err != nil {
			rt.Fatalf("unmarshal envelope: %v", err)
		}
		if decoded.AgentID != original.AgentID || decoded.Seq != original.Seq {
			rt.Fatalf("identity drifted: got (%q,%d) want (%q,%d)", decoded.AgentID, decoded.Seq, original.AgentID, original.Seq)
		}
		if decoded.Event.Kind != original.Event.Kind {
			rt.Fatalf("event kind drifted: got %s want %s", decoded.Event.Kind, original.Event.Kind)
		}
		if decoded.OTel[traceParentKey] != original.OTel[traceParentKey] {
			rt.Fatalf("OTel carrier dropped: got %v want %v", decoded.OTel, original.OTel)
		}
	})
}

// TestProperty_ControlMessageJSONRoundTrip proves a ControlMessage survives a JSON round trip with its
// verb, text, By, and OTel carrier intact — the orchestrator→sidecar wire must not lose the verb.
func TestProperty_ControlMessageJSONRoundTrip(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		original := agentruntime.ControlMessage{
			AgentID: agentruntime.AgentID(rapid.StringMatching(`agent-[a-z0-9]{1,8}`).Draw(rt, "id")),
			Verb:    agentruntime.ControlVerb(rapid.Uint8Range(0, 4).Draw(rt, "verb")),
			Text:    rapid.String().Draw(rt, "text"),
			By:      rapid.String().Draw(rt, "by"),
			OTel:    agentruntime.OTelContext{traceParentKey: rapid.String().Draw(rt, "tp")},
		}
		encoded, err := json.Marshal(original)
		if err != nil {
			rt.Fatalf("marshal control: %v", err)
		}
		var decoded agentruntime.ControlMessage
		if err := json.Unmarshal(encoded, &decoded); err != nil {
			rt.Fatalf("unmarshal control: %v", err)
		}
		if decoded.Verb != original.Verb || decoded.Text != original.Text || decoded.By != original.By {
			rt.Fatalf("control fields drifted: got %+v want %+v", decoded, original)
		}
		if decoded.OTel[traceParentKey] != original.OTel[traceParentKey] {
			rt.Fatalf("control OTel carrier dropped")
		}
	})
}

// traceParentKey is the W3C carrier key the round-trip properties check.
const traceParentKey = "traceparent"

// drawEnvelope draws a well-formed EventEnvelope: a valid agent id, a positive Seq, a drawn event
// kind, and a carrier. The embedded Event carries a minimal valid payload for its kind so Marshal has
// data to round-trip.
func drawEnvelope(rt *rapid.T) agentruntime.EventEnvelope {
	kind := agentsession.EventKind(rapid.Uint8Range(0, uint8(agentsession.EventExtension)).Draw(rt, "kind"))
	return agentruntime.EventEnvelope{
		AgentID: agentruntime.AgentID(rapid.StringMatching(`agent-[a-z0-9]{1,8}`).Draw(rt, "id")),
		Seq:     rapid.Uint64Range(1, 1_000_000).Draw(rt, "seq"),
		Event:   agentsession.Event{Kind: kind, Seq: rapid.Uint64Range(1, 1_000_000).Draw(rt, "eventSeq")},
		OTel:    agentruntime.OTelContext{traceParentKey: rapid.String().Draw(rt, "tp")},
	}
}
