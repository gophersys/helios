package edenhttp

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"strings"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// hmacAlgorithm is the only signing algorithm the dev-JWT verifier accepts (HS256). It is checked
// against the token header so a token cannot down-negotiate to "none" or smuggle an asymmetric alg
// — the classic JWT confusion attack. A non-HS256 header is rejected.
const hmacAlgorithm = "HS256"

// jwtHeader is the minimal JOSE header the dev-JWT carries. Only alg is load-bearing (typ is
// advisory). A header whose alg is not exactly hmacAlgorithm is rejected before any HMAC work.
type jwtHeader struct {
	Algorithm string `json:"alg"`
	Type      string `json:"typ,omitempty"`
}

// jwtClaims is the dev-JWT claim set the verifier authenticates. Sub is the audit subject; Grants
// is the namespace:action string list folded into the Identity; Exp/Nbf are the standard Unix-second
// validity window (0 == unset, so a dev token may omit them). Claims are intentionally minimal —
// this is a DEV token (ADR-0022 #3: "behind auth even locally"), not a full IdP token.
type jwtClaims struct {
	Subject   string   `json:"sub"`
	Grants    []string `json:"grants,omitempty"`
	ExpiresAt int64    `json:"exp,omitempty"`
	NotBefore int64    `json:"nbf,omitempty"`
}

// HMACVerifier is the in-lib TokenVerifier for the dev-JWT path: it authenticates an HS256 JWT
// signed with a shared secret (the value named by EDEN_GATEWAY_JWT_SECRET, resolved by the
// composition root and handed to New — the verifier never reads the env). It is the concrete
// realization of the TokenVerifier port; a production deployment may bind a real IdP verifier
// behind the same port without touching the middleware.
//
// Construct via NewHMACVerifier. Safe for concurrent use (the secret is immutable; Verify allocates
// no shared state). It holds the secret value, so it is never logged or surfaced.
type HMACVerifier struct {
	secret []byte
}

// NewHMACVerifier builds the dev-JWT verifier over the shared HMAC secret. An empty secret is a
// construction error (KindInvalid) — an unsigned/blank-secret verifier would admit forged tokens,
// the exact failure ADR-0022 #3's "behind auth even locally" forbids.
func NewHMACVerifier(secret string) (*HMACVerifier, error) {
	if secret == "" {
		return nil, errors.Wrap(errors.KindInvalid, "edenhttp: NewHMACVerifier",
			ConfigError{Field: "secret", Message: "a non-empty HMAC secret is required (EDEN_GATEWAY_JWT_SECRET)"})
	}
	return &HMACVerifier{secret: []byte(secret)}, nil
}

// Verify authenticates a raw HS256 JWT and returns the caller Identity, or a typed
// KindUnauthenticated error on ANY fault (malformed structure, wrong alg, bad signature, expired /
// not-yet-valid). The signature is checked with a constant-time compare; the alg is pinned to
// HS256 (no alg-confusion downgrade); now is the spine's injected clock instant so expiry is
// deterministic under test. A grant string that fails to parse fails the whole token (a token with
// a malformed grant is not trustworthy), surfaced as KindUnauthenticated.
//
//nolint:cyclop // a JWT verify is an irreducible sequence of structural + cryptographic checks; each is one guard.
func (v *HMACVerifier) Verify(token string, now time.Time) (Identity, error) {
	headerSegment, claimsSegment, signatureSegment, ok := splitToken(token)
	if !ok {
		return Identity{}, unauthenticated("token must have three dot-separated segments")
	}

	var header jwtHeader
	if err := decodeSegment(headerSegment, &header); err != nil {
		return Identity{}, unauthenticated("token header is not valid base64url JSON")
	}
	if header.Algorithm != hmacAlgorithm {
		return Identity{}, unauthenticated("token alg must be " + hmacAlgorithm)
	}

	if !v.signatureValid(headerSegment, claimsSegment, signatureSegment) {
		return Identity{}, unauthenticated("token signature does not verify")
	}

	var claims jwtClaims
	if err := decodeSegment(claimsSegment, &claims); err != nil {
		return Identity{}, unauthenticated("token claims are not valid base64url JSON")
	}
	if claims.Subject == "" {
		return Identity{}, unauthenticated("token has no subject (sub)")
	}
	if err := validateWindow(claims, now); err != nil {
		return Identity{}, err
	}

	grants, err := parseGrantStrings(claims.Grants)
	if err != nil {
		return Identity{}, unauthenticated("token carries a malformed grant")
	}
	return Identity{Subject: claims.Subject, Grants: grants}, nil
}

// signatureValid recomputes the HS256 signature over "<header>.<claims>" and compares it to the
// presented signature in constant time (hmac.Equal), so a verify never leaks timing about how many
// signature bytes matched.
func (v *HMACVerifier) signatureValid(headerSegment, claimsSegment, signatureSegment string) bool {
	presented, err := base64.RawURLEncoding.DecodeString(signatureSegment)
	if err != nil {
		return false
	}
	mac := hmac.New(sha256.New, v.secret)
	//nolint:errcheck // hash.Write never returns an error (documented invariant of the hash interface).
	_, _ = mac.Write([]byte(headerSegment + "." + claimsSegment))
	return hmac.Equal(presented, mac.Sum(nil))
}

// Sign produces a dev-JWT (HS256) for the given claims, signed with this verifier's secret. It is
// the SYMMETRIC half of Verify — the gateway's dev composition + tests mint a token with it, and
// Verify authenticates exactly what Sign produced. It is a dev-token minter (ADR-0022 #3), never a
// production credential service.
func (v *HMACVerifier) Sign(subject string, grants []Grant, expiresAt time.Time) (string, error) {
	grantStrings := make([]string, 0, len(grants))
	for _, grant := range grants {
		grantStrings = append(grantStrings, grant.String())
	}
	claims := jwtClaims{Subject: subject, Grants: grantStrings}
	if !expiresAt.IsZero() {
		claims.ExpiresAt = expiresAt.Unix()
	}
	headerSegment, err := encodeSegment(jwtHeader{Algorithm: hmacAlgorithm, Type: "JWT"})
	if err != nil {
		return "", errors.Wrap(errors.KindInternal, "edenhttp: sign jwt header", err)
	}
	claimsSegment, err := encodeSegment(claims)
	if err != nil {
		return "", errors.Wrap(errors.KindInternal, "edenhttp: sign jwt claims", err)
	}
	mac := hmac.New(sha256.New, v.secret)
	//nolint:errcheck // hash.Write never returns an error.
	_, _ = mac.Write([]byte(headerSegment + "." + claimsSegment))
	signatureSegment := base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
	return headerSegment + "." + claimsSegment + "." + signatureSegment, nil
}

// splitToken splits a compact JWS into its three segments. It returns ok=false unless there are
// exactly three non-empty dot-separated segments.
func splitToken(token string) (headerSegment, claimsSegment, signatureSegment string, ok bool) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 || parts[0] == "" || parts[1] == "" || parts[2] == "" {
		return "", "", "", false
	}
	return parts[0], parts[1], parts[2], true
}

// validateWindow enforces the exp/nbf validity window against now (Unix seconds; 0 == unset). An
// expired or not-yet-valid token is KindUnauthenticated.
func validateWindow(claims jwtClaims, now time.Time) error {
	nowUnix := now.Unix()
	if claims.ExpiresAt != 0 && nowUnix >= claims.ExpiresAt {
		return unauthenticated("token has expired")
	}
	if claims.NotBefore != 0 && nowUnix < claims.NotBefore {
		return unauthenticated("token is not yet valid")
	}
	return nil
}

// parseGrantStrings folds the claim's grant strings into typed Grants; any malformed grant fails.
func parseGrantStrings(raw []string) ([]Grant, error) {
	grants := make([]Grant, 0, len(raw))
	for _, value := range raw {
		grant, err := ParseGrant(value)
		if err != nil {
			return nil, err
		}
		grants = append(grants, grant)
	}
	return grants, nil
}

// decodeSegment base64url-decodes one JWT segment and JSON-unmarshals it into out.
func decodeSegment(segment string, out any) error {
	decoded, err := base64.RawURLEncoding.DecodeString(segment)
	if err != nil {
		return errors.Wrap(errors.KindInvalid, "edenhttp: decode jwt segment", err)
	}
	if err := json.Unmarshal(decoded, out); err != nil {
		return errors.Wrap(errors.KindInvalid, "edenhttp: unmarshal jwt segment", err)
	}
	return nil
}

// encodeSegment JSON-marshals value and base64url-encodes it as one JWT segment.
func encodeSegment(value any) (string, error) {
	encoded, err := json.Marshal(value)
	if err != nil {
		return "", errors.Wrap(errors.KindInternal, "edenhttp: marshal jwt segment", err)
	}
	return base64.RawURLEncoding.EncodeToString(encoded), nil
}

// unauthenticated builds the typed KindUnauthenticated error the verifier returns on any
// authentication fault. The reason is operator-safe (never the token value).
func unauthenticated(reason string) error {
	return errors.Wrap(errors.KindUnauthenticated, "edenhttp: verify token", RequestError{Reason: reason})
}

// compile-time assertion: *HMACVerifier is a TokenVerifier.
var _ TokenVerifier = (*HMACVerifier)(nil)
