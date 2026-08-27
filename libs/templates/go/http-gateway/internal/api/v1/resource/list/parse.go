package list

import (
	"net/http"
	"strconv"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// parse reads the ?limit and ?offset query parameters into the resolved pagination window. An absent
// limit defaults to defaultLimit and a too-large one is clamped to maxLimit (a permissive default);
// a present-but-unparseable value is a typed 400 (the parse owns decoding, not silent coercion). It
// touches no port.
func parse(request *http.Request) (Request, error) {
	query := request.URL.Query()

	limit, err := parseInt32(query.Get("limit"), defaultLimit)
	if err != nil {
		return Request{}, edenhttp.RequestError{Reason: "limit must be an integer"}
	}
	if limit > maxLimit {
		limit = maxLimit
	}

	offset, err := parseInt32(query.Get("offset"), 0)
	if err != nil {
		return Request{}, edenhttp.RequestError{Reason: "offset must be an integer"}
	}

	return Request{Limit: limit, Offset: offset}, nil
}

// parseInt32 parses a query value into an int32, returning fallback for an empty value and a typed
// error for an unparseable one. It is the route-local decode helper the parse stage uses.
func parseInt32(raw string, fallback int32) (int32, error) {
	if raw == "" {
		return fallback, nil
	}
	value, err := strconv.ParseInt(raw, 10, 32)
	if err != nil {
		return 0, errors.Wrap(errors.KindInvalid, "list: parse pagination", err)
	}
	return int32(value), nil
}
