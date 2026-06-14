package vaultadapter

import (
	"context"
	"os"

	vaultapi "github.com/hashicorp/vault/api"

	"github.com/gophersys/libs/go/errors"
)

// realTransport is the production Transport: a thin wrapper over *vaultapi.Client.Logical(). It is
// the ONLY code that touches the Vault SDK at run time. Each method is a 1:1 translation of the
// adapter's narrow need onto the SDK; the SDK's transport errors flow up unwrapped so
// mapTransportError can inspect the *vaultapi.ResponseError status code.
type realTransport struct {
	client *vaultapi.Client
}

// newRealTransport builds the production Vault client from Config. It performs NO I/O (matching
// New's purity): api.NewClient only constructs the HTTP client and parses the address; the first
// network call is the login/read on Resolve.
func newRealTransport(configuration Config) (*realTransport, error) {
	apiConfig := vaultapi.DefaultConfig()
	apiConfig.Address = configuration.Address
	client, err := vaultapi.NewClient(apiConfig)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "vaultadapter: constructing the Vault API client", err)
	}
	if configuration.Namespace != "" {
		client.SetNamespace(configuration.Namespace)
	}
	return &realTransport{client: client}, nil
}

// Login writes the userpass login request and extracts the issued client token.
func (t *realTransport) Login(ctx context.Context, path string, data map[string]any) (string, error) {
	secret, err := t.client.Logical().WriteWithContext(ctx, path, data)
	if err != nil {
		return "", err //nolint:wrapcheck // the raw SDK error is mapped by mapTransportError, which inspects *vaultapi.ResponseError.
	}
	if secret == nil || secret.Auth == nil || secret.Auth.ClientToken == "" {
		return "", errors.New(errors.KindUnavailable, "vaultadapter: Vault login returned no client token")
	}
	return secret.Auth.ClientToken, nil
}

// SetToken installs the token for subsequent reads.
func (t *realTransport) SetToken(token string) { t.client.SetToken(token) }

// ReadKeyValue reads the raw KV v2 secret data at apiPath ("<mount>/data/<path>"). A nil *Secret
// (HTTP 404 surfaced as nil,nil by the SDK) maps to a nil data map — the adapter reads that as
// NotFound. A real transport error flows up for mapTransportError.
func (t *realTransport) ReadKeyValue(ctx context.Context, apiPath string) (map[string]any, error) {
	secret, err := t.client.Logical().ReadWithContext(ctx, apiPath)
	if err != nil {
		return nil, err //nolint:wrapcheck // raw SDK error mapped by mapTransportError on the *vaultapi.ResponseError status.
	}
	if secret == nil {
		return nil, nil //nolint:nilnil // (nil map, nil err) is the documented "no such secret" sentinel; Resolve maps it to NotFound.
	}
	return secret.Data, nil
}

// osReadFile is the production token-file reader (the ModeTokenFile default). A test injects its
// own reader over a temp file.
func osReadFile(path string) ([]byte, error) {
	b, err := os.ReadFile(path) // #nosec G304 -- the token path is operator-supplied Config (the sidecar /vault/secrets/token), not consumer input.
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "vaultadapter: reading the token file", err)
	}
	return b, nil
}

// compile-time: realTransport is a Transport.
var _ Transport = (*realTransport)(nil)
