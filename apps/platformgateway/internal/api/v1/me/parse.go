package me

import "net/http"

// parse decodes the request into the typed Request. /me carries no body, no path, no query — the
// caller is the verified token's subject (read in execute from the Identity), so there is nothing to
// decode here; parse returns the empty Request. It touches no port (the PARSE stage contract).
func parse(_ *http.Request) (Request, error) {
	return Request{}, nil
}
