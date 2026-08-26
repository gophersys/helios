package agentsession

import (
	"context"
	"encoding/json"
	"sync"

	"github.com/gophersys/libs/go/errors"
)

// The two peer host tools the LIBRARY injects into its own copy of Spec.HostTools at Open.
// They live here rather than in an adapter because an Adapter cannot reach the plane: Spawn
// carries no PeerLink and Pool.Open spawns before it joins. They ride each harness's existing
// host-tool router unchanged. The names are the model-facing contract.
const (
	peerSendToolName = "eden_peer_send"
	peerListToolName = "eden_peer_list"
)

// The parameter schemas the harness advertises to the model. eden_peer_send takes the two
// fields the plane needs and nothing else — no msg id (the PLANE mints it), no from (a sender
// does not get to name itself), no verified flag (a kernel fact, never a claim).
var (
	peerSendSchema = []byte(`{"type":"object","properties":{` +
		`"to":{"type":"string","description":"the peer session name to deliver to"},` +
		`"body":{"type":"string","description":"the message body"}},` +
		`"required":["to","body"]}`)

	peerListSchema = []byte(`{"type":"object","properties":{}}`)
)

// peerRosterRow is what eden_peer_list renders for ONE peer: the five roster fields and
// nothing else. It exists so the answer is assembled field by field instead of marshaling a
// record the library holds — a roster that renders a struct leaks whatever else that struct
// grows, straight into the model's context. The roster answers WHO exists, never WHAT was said.
type peerRosterRow struct {
	Name       string `json:"name"`
	Parent     string `json:"parent"`
	Harness    string `json:"harness"`
	Live       bool   `json:"live"`
	Generation int    `json:"generation"`
}

// peerToolset is the identity and the ports the two peer host tools close over. The link is
// MUTABLE because the injection and the join cannot happen in the same order: Pool.Open must
// put the tools in the Spec it hands Spawn before it can Join, so for that window every handler
// holds no link at all. bind closes the window; until then a handler answers a typed
// KindUnavailable — never a nil dereference, which inside a harness's tool router is a broken
// transport rather than a failed tool.
type peerToolset struct {
	name  string
	plane PeerPlane

	mu   sync.Mutex
	link PeerLink
}

// newPeerToolset builds the toolset for one session. A nil link is the pre-Join state.
//
//nolint:ireturn // link is the injected PeerLink port; the toolset holds the abstraction it was handed.
func newPeerToolset(name string, plane PeerPlane, link PeerLink) *peerToolset {
	return &peerToolset{name: name, plane: plane, link: link}
}

// bind publishes the link Join returned, so every already-injected handler starts working.
func (s *peerToolset) bind(link PeerLink) {
	s.mu.Lock()
	s.link = link
	s.mu.Unlock()
}

// linkOrUnavailable returns the session's link, or the ONE typed KindUnavailable a handler
// answers before Join — the Kind a caller branches on for "not ready yet, retry".
//
//nolint:ireturn // returns the injected PeerLink port (the contract surface).
func (s *peerToolset) linkOrUnavailable(tool string) (PeerLink, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.link == nil {
		return nil, errors.Wrap(errors.KindUnavailable, "agentsession: "+tool,
			UnreachableError{Name: s.name, Reason: "session has not joined the peer plane yet"})
	}
	return s.link, nil
}

// hostTools renders the injectable set. It is EMPTY without a plane or without a name: a tool
// offered to a model that can never succeed is worse than an absent one — the model spends
// turns on it and the transcript fills with failures that were structurally guaranteed.
func (s *peerToolset) hostTools() []HostTool {
	if s.plane == nil || s.name == "" {
		return nil
	}
	return []HostTool{
		{
			Name:        peerSendToolName,
			Description: "Send a message to another Eden agent session by name.",
			Schema:      peerSendSchema,
			Handler:     s.send,
		},
		{
			Name:        peerListToolName,
			Description: "List the Eden agent sessions this session can message.",
			Schema:      peerListSchema,
			Handler:     s.list,
		},
	}
}

// send drives the session's own PeerLink and answers the model with the MsgID the PLANE minted
// — the id the receiver will see as its origin, so the model can reference what it just sent.
// A locally-invented id would correlate with nothing on the plane.
func (s *peerToolset) send(ctx context.Context, args []byte) ([]byte, error) {
	link, err := s.linkOrUnavailable(peerSendToolName)
	if err != nil {
		return nil, err
	}
	var request struct {
		To   string `json:"to"`
		Body string `json:"body"`
	}
	if err := json.Unmarshal(args, &request); err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "agentsession: "+peerSendToolName, err)
	}
	if request.To == "" || request.Body == "" {
		return nil, errors.New(errors.KindInvalid,
			"agentsession: "+peerSendToolName+`: "to" and "body" are both required`)
	}
	msgID, err := link.Send(ctx, PeerMessage{From: s.name, To: request.To, Body: request.Body})
	if err != nil {
		// KindUnknown inherits the plane's own classification, so an UnreachableError stays
		// not-found and a full inbox stays exhausted at the model's tool boundary.
		return nil, errors.Wrap(errors.KindUnknown, "agentsession: "+peerSendToolName, err)
	}
	answer, err := json.Marshal(map[string]string{"msg_id": msgID})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentsession: "+peerSendToolName, err)
	}
	return answer, nil
}

// list answers the roster. It requires the link for the same reason send does: a session that
// is not on the plane is not a member, and handing it a roster it does not appear in is exactly
// the silent non-membership this design removes.
func (s *peerToolset) list(ctx context.Context, _ []byte) ([]byte, error) {
	if _, err := s.linkOrUnavailable(peerListToolName); err != nil {
		return nil, err
	}
	roster, err := s.plane.Roster(ctx, s.name)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnknown, "agentsession: "+peerListToolName, err)
	}
	rows := make([]peerRosterRow, 0, len(roster))
	for i := range roster {
		rows = append(rows, peerRosterRow{
			Name:       roster[i].Name,
			Parent:     roster[i].Parent,
			Harness:    roster[i].Harness,
			Live:       roster[i].Live,
			Generation: roster[i].Generation,
		})
	}
	answer, err := json.Marshal(map[string][]peerRosterRow{"peers": rows})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentsession: "+peerListToolName, err)
	}
	return answer, nil
}

// peerHostTools builds the peer host-tool set for a session's name, plane and link. It is the
// pure form of what Pool.Open injects; a nil link is the pre-Join window, where every handler
// answers KindUnavailable rather than panicking into the harness's tool router.
//
//nolint:gocritic // PeerPlane/PeerLink are the injected ports; the builder takes what Open holds.
func peerHostTools(name string, plane PeerPlane, link PeerLink) []HostTool {
	return newPeerToolset(name, plane, link).hostTools()
}

// withPeerHostTools returns a NEW slice carrying the caller's host tools followed by Eden's.
// It never appends into callerTools: a slice with spare capacity would be written THROUGH into
// the caller's own backing array, so a caller reusing its Spec for a second session would find
// Eden's tools in its own set.
func withPeerHostTools(callerTools, peerTools []HostTool) []HostTool {
	combined := make([]HostTool, 0, len(callerTools)+len(peerTools))
	combined = append(combined, callerTools...)
	return append(combined, peerTools...)
}
