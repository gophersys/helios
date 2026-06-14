package vaultadapter

import (
	"net/http"
	"strings"

	vaultapi "github.com/hashicorp/vault/api"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// location is the parsed form of a vault Reference: the KV v2 mount, the secret path under it,
// and the field key selected by the "#<key>" fragment.
type location struct {
	mount string
	path  string
	key   string
}

// apiPath renders the KV v2 read endpoint for this location: "<mount>/data/<path>". KV v2 reads
// go through the "/data/" segment (writes/lists use "/metadata/"); a Reference always reads.
func (l location) apiPath() string {
	return l.mount + "/data/" + l.path
}

// parseReference splits a vault Reference into its (mount, path, key). The canonical form is
//
//	vault://<mount>/<path>#<key>
//
// where <mount> is the KV v2 mount, <path> the secret path under it (slash-separated, possibly
// nested), and <key> the field within the secret's data map. A malformed reference (missing
// scheme, mount, path, or key) yields a typed secrets.InvalidReferenceError carrying the
// Reference, never a fabricated value.
func parseReference(ref secrets.Reference) (location, error) {
	raw := ref.String()
	const schemePrefix = scheme + "://"
	if !strings.HasPrefix(raw, schemePrefix) {
		return location{}, secrets.InvalidReferenceError{Ref: ref}
	}
	rest := strings.TrimPrefix(raw, schemePrefix)

	hash := strings.IndexByte(rest, '#')
	if hash < 0 {
		// No "#<key>" fragment: the Reference does not name a field, so it is unresolvable here.
		return location{}, secrets.InvalidReferenceError{Ref: ref}
	}
	pathPart := rest[:hash]
	key := rest[hash+1:]
	if key == "" {
		return location{}, secrets.InvalidReferenceError{Ref: ref}
	}

	slash := strings.IndexByte(pathPart, '/')
	if slash < 0 {
		// A mount with no path under it is not a KV v2 secret location.
		return location{}, secrets.InvalidReferenceError{Ref: ref}
	}
	mount := pathPart[:slash]
	secretPath := strings.Trim(pathPart[slash+1:], "/")
	if mount == "" || secretPath == "" {
		return location{}, secrets.InvalidReferenceError{Ref: ref}
	}

	return location{mount: mount, path: secretPath, key: key}, nil
}

// mapTransportError maps a Vault transport error onto the secrets taxonomy so callers branch on
// AsType[…] across rewordings (secrets.md §6.6). It inspects the SDK's *vaultapi.ResponseError
// status code: 403 → DeniedError (no scope), 404 → NotFoundError, everything else (connection
// refused, 5xx, timeouts) → UnavailableError (the one retryable signal). The Reference is carried;
// the value never is.
func mapTransportError(ref secrets.Reference, err error) error {
	if err == nil {
		return nil
	}
	if responseError, ok := errors.AsType[*vaultapi.ResponseError](err); ok {
		switch responseError.StatusCode {
		case http.StatusForbidden:
			return secrets.DeniedError{Ref: ref}
		case http.StatusNotFound:
			return secrets.NotFoundError{Ref: ref}
		default:
			return secrets.UnavailableError{Ref: ref}
		}
	}
	// A non-HTTP transport error (dial failure, context deadline, TLS) is an availability problem.
	return secrets.UnavailableError{Ref: ref}
}
