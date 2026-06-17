package ping

import (
	"net/http"
)

// Request is the typed input GET /v1/ping decodes to. The ping route takes no body or path params,
// so it is empty — but it is still a named type, because a resource's input shape is part of its
// contract and a generated app fills it (path ids, query filters, the decoded JSON body) without
// changing the route's five-file shape.
type Request struct{}

// Response is the typed output the execute stage produces and the pipeline writes as the success
// Envelope. It carries the caller's subject and the server's observed time — enough to prove the
// authenticated round-trip end to end.
type Response struct {
	// Subject is the authenticated principal that called (echoed from the verified Identity).
	Subject string `json:"subject"`
	// ObservedAt is the RFC3339 server timestamp the execute stage stamped.
	ObservedAt string `json:"observedAt"`
}

// parse decodes the request into the typed Request. The PARSE stage owns ONLY decoding — no
// validation, no business logic. GET /v1/ping has no body, so parse returns the zero Request; a
// resource with a body uses edenhttp.DecodeJSONBody here, a resource with a path id reads
// request.PathValue here.
func parse(_ *http.Request) (Request, error) {
	return Request{}, nil
}
