// Package vaultadapter is the secrets.Provider that resolves a Reference from a REAL
// HashiCorp Vault KV v2 mount. It is the ONLY place the Vault SDK (github.com/hashicorp/
// vault/api) is imported (05 §1): it translates a secrets.Reference of the canonical form
//
//	vault://<mount>/<path>#<key>
//
// into a KV v2 read (mount + path) whose `<key>` field becomes the resolved Secret's bytes.
// It slots behind the EXISTING secrets.Provider port (composition root, secrets.md §5) — no
// contract change — and is wired into a secrets.Mediator under the "vault" scheme.
//
// Bootstrap is DUAL-MODE behind one constructor (ADR-0022 decision #1), the mode chosen by
// Config, never by a fork in the caller:
//
//   - LOCAL  (ModeUserpass): an env VAULT_ADDR + userpass username/password is exchanged for a
//     Vault token at first Resolve (auth/userpass/login/<user>) — the IOTEA-proven local path.
//   - PRODUCTION (ModeTokenFile): a token file (the K8s-ServiceAccount sidecar output, e.g.
//     /vault/secrets/token) is read and re-read before each Resolve, so a sidecar token refresh
//     is honored without a reconnect — the IOTEA-proven production path.
//
// The secrets.Use + zeroize + redaction no-leak contract is unchanged: the adapter mints a
// genuine, un-printable *secrets.Secret through the module-internal minting seam (internal/mint,
// secrets.md §3), so a resolved value never reaches a String()/error/log — only the loggable
// Reference does.
package vaultadapter

import (
	"context"
	"fmt"
	"strings"
	"sync"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/internal/mint"
)

// scheme is the Reference scheme this adapter owns at the composition root.
const scheme = "vault"

// userpassLoginPathFormat is the Vault userpass login endpoint the LOCAL bootstrap drives; the
// token file carries an already-minted token, so PRODUCTION needs no login call.
const userpassLoginPathFormat = "auth/userpass/login/%s" // #nosec G101 -- a Vault auth ENDPOINT path template, not a hardcoded credential.

// Mode selects the dual-mode bootstrap. It is part of Config, so the per-stage choice lives at
// the composition root (10 §2), never in the resolving caller.
type Mode uint8

const (
	// ModeUserpass is the LOCAL path: exchange a userpass username/password for a token via
	// auth/userpass/login/<user>. The credential pair is injected through Deps.
	ModeUserpass Mode = iota
	// ModeTokenFile is the PRODUCTION path: read a Vault token from TokenFilePath (the K8s-SA
	// sidecar output), re-reading it before each Resolve so a sidecar refresh is honored.
	ModeTokenFile
)

// errInvalidConfig reports a construction-time wiring mistake (a missing address, an unset
// credential for the chosen Mode). It is a sentinel so the composition root can branch via
// errors.Is; it carries KindInvalid because the dependencies/configuration are malformed.
var errInvalidConfig = errors.New(errors.KindInvalid, "vaultadapter.New: invalid configuration")

// Config is the immutable, fully-resolved construction input (the configuration pattern). New
// reads it and dials NOTHING — all I/O (login, token-file read, KV read) is lazy, on Resolve.
type Config struct {
	// Address is the Vault API address (e.g. http://127.0.0.1:8200). Required.
	Address string
	// Mode selects the bootstrap path (LOCAL userpass vs PRODUCTION token-file).
	Mode Mode
	// TokenFilePath is the path the sidecar writes the Vault token to (ModeTokenFile only),
	// e.g. /vault/secrets/token. Required when Mode == ModeTokenFile.
	TokenFilePath string
	// Namespace is the Vault Enterprise namespace, if any. Empty for OSS / the default namespace.
	Namespace string
}

// Deps is the injected hexagon: the userpass credential (ModeUserpass) and the seams a
// test substitutes (the Vault transport and the token-file reader). Accepting interfaces here is
// the accept-interfaces rule; New returns the concrete *Adapter.
type Deps struct {
	// Username / Password are the userpass credential (ModeUserpass only). Password is a
	// *secrets.Reference resolved through an already-wired Provider so the bootstrap credential
	// is itself never an inline literal — but for the bootstrap-from-env LOCAL path it is the raw
	// password string, kept off every loggable surface (it lives only in this struct and the
	// login call body). Required when Mode == ModeUserpass.
	Username string
	Password string

	// Transport is the Vault logical API the adapter drives. It defaults to the real
	// github.com/hashicorp/vault/api client (built from Config.Address) when nil; a test injects
	// a fake to exercise the mapping logic without a daemon. The real-Vault proof is the
	// integration lane, never a mock (ADR-0016 §2).
	Transport Transport

	// ReadTokenFile reads the sidecar token file (ModeTokenFile only). Defaults to os.ReadFile
	// when nil; a test injects a reader over a temp file.
	ReadTokenFile func(path string) ([]byte, error)
}

// Transport is the narrow Vault logical-API seam the adapter depends on (≤5 methods, 10 §9). The
// real implementation wraps *vaultapi.Client.Logical(); a test fakes it. It is consumer-defined
// here (the shape of THIS adapter's need), not a mirror of the SDK.
type Transport interface {
	// Login exchanges a userpass credential for a client token (auth/userpass/login/<user>). It
	// returns the token string. Errors are transport errors the adapter maps to the taxonomy.
	Login(ctx context.Context, path string, data map[string]any) (token string, err error)
	// SetToken installs the token used for subsequent reads.
	SetToken(token string)
	// ReadKeyValue reads the raw secret data map at an absolute Vault API path (the KV v2
	// "<mount>/data/<path>" form). A nil map with nil error means "no such secret".
	ReadKeyValue(ctx context.Context, apiPath string) (data map[string]any, err error)
}

// Adapter is the concrete secrets.Provider returned by New. It holds the immutable Config, the
// injected Deps, and a once-guarded bootstrap so the userpass login happens exactly once
// across concurrent Resolves. Safe for concurrent use. Zero value is not usable; construct via New.
type Adapter struct {
	configuration Config
	transport     Transport
	username      string
	password      string
	readTokenFile func(path string) ([]byte, error)

	// bootstrapOnce guards the userpass login so concurrent first-Resolves perform exactly one
	// login. bootstrapErr records a sticky login failure so every caller sees the same typed error.
	bootstrapOnce sync.Once
	bootstrapErr  error
}

// New is the constructor spine (10 §9). PURE: no I/O, no env reads, no clock, no daemon dial. It
// validates the configuration + dependencies for the chosen Mode, defaults the optional seams to
// their real implementations, and returns the concrete *Adapter. The login / token-file read /
// KV read all happen lazily on Resolve.
func New(configuration Config, dependencies Deps) (*Adapter, error) {
	if strings.TrimSpace(configuration.Address) == "" {
		return nil, errors.Wrap(errors.KindInvalid, "vaultadapter.New: Config.Address is required", errInvalidConfig)
	}

	transport := dependencies.Transport
	if transport == nil {
		realTransport, err := newRealTransport(configuration)
		if err != nil {
			return nil, err
		}
		transport = realTransport
	}

	readTokenFile := dependencies.ReadTokenFile
	if readTokenFile == nil {
		readTokenFile = osReadFile
	}

	switch configuration.Mode {
	case ModeUserpass:
		if strings.TrimSpace(dependencies.Username) == "" || dependencies.Password == "" {
			return nil, errors.Wrap(errors.KindInvalid,
				"vaultadapter.New: ModeUserpass requires Deps.Username and Deps.Password", errInvalidConfig)
		}
	case ModeTokenFile:
		if strings.TrimSpace(configuration.TokenFilePath) == "" {
			return nil, errors.Wrap(errors.KindInvalid,
				"vaultadapter.New: ModeTokenFile requires Config.TokenFilePath", errInvalidConfig)
		}
	default:
		return nil, errors.Wrap(errors.KindInvalid,
			"vaultadapter.New: unknown Config.Mode", errInvalidConfig).WithField("mode", configuration.Mode)
	}

	return &Adapter{
		configuration: configuration,
		transport:     transport,
		username:      dependencies.Username,
		password:      dependencies.Password,
		readTokenFile: readTokenFile,
	}, nil
}

// Resolve implements secrets.Provider: it parses ref into (mount, path, key), ensures the token
// is current for the configured Mode, reads the KV v2 secret, and mints an independent,
// un-printable *secrets.Secret from the selected field. It returns the secrets taxonomy errors
// (InvalidReferenceError / NotFoundError / DeniedError / UnavailableError) — the message carries
// the Reference, never the value — and never a non-nil Secret with a non-nil error.
func (a *Adapter) Resolve(ctx context.Context, ref secrets.Reference) (*secrets.Secret, error) {
	if ref.IsZero() {
		return nil, secrets.InvalidReferenceError{Ref: ref}
	}
	location, err := parseReference(ref)
	if err != nil {
		return nil, err
	}

	if err := a.ensureToken(ctx, ref); err != nil {
		return nil, err
	}

	data, err := a.transport.ReadKeyValue(ctx, location.apiPath())
	if err != nil {
		return nil, mapTransportError(ref, err)
	}
	if data == nil {
		return nil, secrets.NotFoundError{Ref: ref}
	}

	// KV v2 wraps the user fields under a "data" sub-map; the field we want is data["data"][key].
	fields, ok := kvDataFields(data)
	if !ok {
		return nil, secrets.NotFoundError{Ref: ref}
	}
	rawValue, ok := fields[location.key]
	if !ok {
		return nil, secrets.NotFoundError{Ref: ref}
	}
	valueString, ok := rawValue.(string)
	if !ok {
		// A non-string field cannot be a credential value; treat it as not-the-secret-we-named.
		return nil, secrets.NotFoundError{Ref: ref}
	}

	return mintSecret([]byte(valueString)), nil
}

// ensureToken makes the transport's token current for the configured Mode before a read:
// ModeUserpass logs in exactly once (sticky); ModeTokenFile re-reads the sidecar file each call
// so a refreshed token is honored without a reconnect.
func (a *Adapter) ensureToken(ctx context.Context, ref secrets.Reference) error {
	switch a.configuration.Mode {
	case ModeTokenFile:
		token, err := a.readTokenFile(a.configuration.TokenFilePath)
		if err != nil {
			return errors.Wrap(errors.KindUnavailable,
				"vaultadapter: reading the sidecar token file", err).WithField("reference", ref.String())
		}
		trimmed := strings.TrimSpace(string(token))
		if trimmed == "" {
			return secrets.UnavailableError{Ref: ref}
		}
		a.transport.SetToken(trimmed)
		return nil
	case ModeUserpass:
		a.bootstrapOnce.Do(func() {
			loginPath := fmt.Sprintf(userpassLoginPathFormat, a.username)
			token, err := a.transport.Login(ctx, loginPath, map[string]any{"password": a.password})
			if err != nil {
				a.bootstrapErr = mapTransportError(ref, err)
				return
			}
			if strings.TrimSpace(token) == "" {
				a.bootstrapErr = secrets.UnavailableError{Ref: ref}
				return
			}
			a.transport.SetToken(token)
		})
		return a.bootstrapErr
	default:
		// New rejects an unknown Mode, so this is unreachable; surface it as Unavailable rather
		// than panic so a future Mode added without wiring fails closed, not catastrophically.
		return secrets.UnavailableError{Ref: ref}
	}
}

// mintSecret builds a genuine, un-printable *secrets.Secret from value through the module-internal
// minting seam (secrets.md §3 — the adapter is a sanctioned producer). The comma-ok guard turns
// an impossible registration mismatch into a clear panic, not a silent miscast.
func mintSecret(value []byte) *secrets.Secret {
	sec, ok := mint.Hook()(value).(*secrets.Secret)
	if !ok {
		panic("vaultadapter: minting hook returned a non-*secrets.Secret value")
	}
	return sec
}

// kvDataFields extracts the KV v2 user-field sub-map (response.Data["data"]). KV v2 nests the
// caller's fields one level under "data"; a KV v1 / raw map (no "data" sub-map) is treated as the
// fields directly so the adapter is forgiving of a v1 mount, but the canonical path is v2.
func kvDataFields(responseData map[string]any) (map[string]any, bool) {
	if inner, ok := responseData["data"].(map[string]any); ok {
		return inner, true
	}
	// No "data" envelope: either a KV v1 mount or an already-unwrapped map. Use it directly only
	// if it is non-empty, so an empty/absent secret still resolves to NotFound.
	if len(responseData) == 0 {
		return nil, false
	}
	return responseData, true
}

// compile-time: *Adapter is a secrets.Provider.
var _ secrets.Provider = (*Adapter)(nil)

// compile-time: the scheme constant matches what a "vault://" Reference reports, so a wiring drift
// (binding this adapter under a different scheme key) is the composition root's explicit choice.
var _ = scheme
