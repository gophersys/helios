package edenhttp

import (
	"strings"

	"github.com/gophersys/libs/go/errors"
)

// wildcard is the grant token that matches any action within a namespace (or, as the whole grant
// "*", any namespace+action). Adopted from the IOTEA RBAC vocabulary.
const wildcard = "*"

// grantSeparator splits a grant into its namespace and action halves ("sessions:control").
const grantSeparator = ":"

// Grant is one authorization token in the namespace:action grant grammar (IOTEA RBAC, adopted as
// ADR-0022 #3's per-tool sandbox + HTTP authz vocabulary). It names a Namespace (the resource
// family, e.g. "sessions") and an Action (the verb, e.g. "control"). A handler declares the Grant
// it requires; an Identity carries the set of Grants it holds; Authorize admits the request iff a
// held grant Covers the required one.
//
// This is the ONE home for the grant grammar (one concept, one home, 10 §9): parse/render/match
// live here, never re-spelled at a call site.
type Grant struct {
	// Namespace is the resource family (e.g. "sessions"). "*" as the whole grant string means any.
	Namespace string
	// Action is the verb within the namespace (e.g. "control", "read"). "*" matches any action.
	Action string
}

// NewGrant constructs a Grant from an explicit namespace + action (the typed builder a handler uses
// to declare its required grant without string-parsing).
func NewGrant(namespace, action string) Grant {
	return Grant{Namespace: namespace, Action: action}
}

// ParseGrant parses a "namespace:action" (or the bare "*") grant string into a Grant. A malformed
// string — empty, a missing half, or more than one separator — is a typed *errors.Error
// (KindInvalid) so the caller branches by Kind, never on the message. The bare "*" parses to the
// all-namespaces/all-actions grant {*, *}.
func ParseGrant(raw string) (Grant, error) {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return Grant{}, errors.New(errors.KindInvalid, "edenhttp: empty grant string")
	}
	if trimmed == wildcard {
		return Grant{Namespace: wildcard, Action: wildcard}, nil
	}
	namespace, action, found := strings.Cut(trimmed, grantSeparator)
	if !found {
		return Grant{}, errors.New(errors.KindInvalid, "edenhttp: grant must be namespace:action or *")
	}
	if namespace == "" || action == "" {
		return Grant{}, errors.New(errors.KindInvalid, "edenhttp: grant namespace and action must be non-empty")
	}
	if strings.Contains(action, grantSeparator) {
		return Grant{}, errors.New(errors.KindInvalid, "edenhttp: grant must have exactly one ':' separator")
	}
	return Grant{Namespace: namespace, Action: action}, nil
}

// String renders the Grant back to its canonical "namespace:action" form (the all grant renders
// "*"). Total: a zero Grant renders ":".
func (g Grant) String() string {
	if g.Namespace == wildcard && g.Action == wildcard {
		return wildcard
	}
	return g.Namespace + grantSeparator + g.Action
}

// Covers reports whether g (a HELD grant) authorizes required (a handler's REQUESTED grant). A held
// grant covers the request iff its namespace matches (equal, or g is the "*" namespace) AND its
// action matches (equal, or g's action is "*"). So "*" covers everything, "sessions:*" covers any
// action on sessions, and "sessions:control" covers only that exact pair. The match is asymmetric:
// only the HELD grant's wildcards widen; a request never widens itself.
func (g Grant) Covers(required Grant) bool {
	namespaceMatch := g.Namespace == wildcard || g.Namespace == required.Namespace
	actionMatch := g.Action == wildcard || g.Action == required.Action
	return namespaceMatch && actionMatch
}
