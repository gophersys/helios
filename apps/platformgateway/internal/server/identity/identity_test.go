package identity_test

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/server/identity"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// fakeResolver is the in-memory GrantResolver the dbVerifier tests drive: it returns fixed grants or a
// typed error for any user id, recording the id it was asked for.
type fakeResolver struct {
	grants []edenhttp.Grant
	err    error
	gotID  uuid.UUID
}

func (f *fakeResolver) ResolveGrants(_ context.Context, userID uuid.UUID) ([]edenhttp.Grant, error) {
	f.gotID = userID
	return f.grants, f.err
}

// fakeMembership is the in-memory MembershipReader the RBACGrantResolver tests drive.
type fakeMembership struct {
	membership persistence.Membership
	err        error
}

func (f *fakeMembership) MembershipFor(_ context.Context, _ uuid.UUID) (persistence.Membership, error) {
	return f.membership, f.err
}

// signFor mints a dev-JWT (subject only) with the given subject through a verifier over key.
func signFor(t *testing.T, key, subject string) string {
	t.Helper()
	verifier, err := edenhttp.NewHMACVerifier(key)
	if err != nil {
		t.Fatalf("new verifier: %v", err)
	}
	signed, err := verifier.Sign(subject, nil, time.Now().Add(time.Hour))
	if err != nil {
		t.Fatalf("sign: %v", err)
	}
	return signed
}

const testKey = "test-signing-key-32-bytes-minimum!!"

// TestDBVerifier_LoadsGrantsFromResolver proves the verifier authenticates the subject via HMAC then takes
// the grants from the RESOLVER (not the token) — and that the resolver is asked for the subject's user id.
func TestDBVerifier_LoadsGrantsFromResolver(t *testing.T) {
	t.Parallel()
	hmac, err := edenhttp.NewHMACVerifier(testKey)
	if err != nil {
		t.Fatalf("hmac: %v", err)
	}
	userID := uuid.New()
	resolver := &fakeResolver{grants: []edenhttp.Grant{edenhttp.NewGrant("users", "read")}}
	verifier := identity.NewDBVerifier(hmac, resolver)

	id, err := verifier.Verify(signFor(t, testKey, userID.String()), time.Now())
	if err != nil {
		t.Fatalf("Verify = %v, want nil", err)
	}
	if id.Subject != userID.String() {
		t.Fatalf("Identity.Subject = %q, want %s", id.Subject, userID)
	}
	if resolver.gotID != userID {
		t.Fatalf("resolver asked for %s, want the token subject %s", resolver.gotID, userID)
	}
	if !id.HasGrant(edenhttp.NewGrant("users", "read")) {
		t.Fatalf("Identity grants = %v, want users:read from the resolver", id.Grants)
	}
}

// TestDBVerifier_IgnoresTokenGrants proves the grants EMBEDDED in a token are discarded: a token carrying
// admin "*" but a resolver returning NO grants yields an Identity with no grants (the DB is authoritative).
func TestDBVerifier_IgnoresTokenGrants(t *testing.T) {
	t.Parallel()
	hmac, err := edenhttp.NewHMACVerifier(testKey)
	if err != nil {
		t.Fatalf("hmac: %v", err)
	}
	userID := uuid.New()
	// Mint a token that DOES embed the wildcard grant.
	wildcard, parseErr := edenhttp.ParseGrant("*")
	if parseErr != nil {
		t.Fatalf("parse wildcard: %v", parseErr)
	}
	token, err := hmac.Sign(userID.String(), []edenhttp.Grant{wildcard}, time.Now().Add(time.Hour))
	if err != nil {
		t.Fatalf("sign: %v", err)
	}
	verifier := identity.NewDBVerifier(hmac, &fakeResolver{grants: nil})

	id, err := verifier.Verify(token, time.Now())
	if err != nil {
		t.Fatalf("Verify = %v, want nil", err)
	}
	if id.HasGrant(edenhttp.NewGrant("anything", "goes")) {
		t.Fatal("Identity honored the token's embedded wildcard grant; grants must come from the resolver")
	}
	if len(id.Grants) != 0 {
		t.Fatalf("Identity.Grants = %v, want empty (resolver returned none)", id.Grants)
	}
}

// TestDBVerifier_NonUUIDSubjectIsUnauthenticated proves a valid-signed token whose subject is not a uuid
// is rejected as unauthenticated (the verifier cannot resolve grants for a non-user subject).
func TestDBVerifier_NonUUIDSubjectIsUnauthenticated(t *testing.T) {
	t.Parallel()
	hmac, err := edenhttp.NewHMACVerifier(testKey)
	if err != nil {
		t.Fatalf("hmac: %v", err)
	}
	verifier := identity.NewDBVerifier(hmac, &fakeResolver{})

	_, err = verifier.Verify(signFor(t, testKey, "not-a-uuid"), time.Now())
	if errors.KindOf(err) != errors.KindUnauthenticated {
		t.Fatalf("Verify(non-uuid subject) Kind = %v, want KindUnauthenticated", errors.KindOf(err))
	}
}

// TestDBVerifier_ResolverErrorIsUnauthenticated proves a resolver fault (e.g. an unknown user) is
// collapsed to KindUnauthenticated so the spine answers 401, never a 500.
func TestDBVerifier_ResolverErrorIsUnauthenticated(t *testing.T) {
	t.Parallel()
	hmac, err := edenhttp.NewHMACVerifier(testKey)
	if err != nil {
		t.Fatalf("hmac: %v", err)
	}
	verifier := identity.NewDBVerifier(hmac, &fakeResolver{err: errors.New(errors.KindNotFound, "no membership")})

	_, err = verifier.Verify(signFor(t, testKey, uuid.NewString()), time.Now())
	if errors.KindOf(err) != errors.KindUnauthenticated {
		t.Fatalf("Verify(resolver error) Kind = %v, want KindUnauthenticated", errors.KindOf(err))
	}
}

// TestDBVerifier_BadSignatureIsUnauthenticated proves a token signed with a DIFFERENT key fails the HMAC
// authenticate (and the resolver is never consulted).
func TestDBVerifier_BadSignatureIsUnauthenticated(t *testing.T) {
	t.Parallel()
	hmac, err := edenhttp.NewHMACVerifier(testKey)
	if err != nil {
		t.Fatalf("hmac: %v", err)
	}
	verifier := identity.NewDBVerifier(hmac, &fakeResolver{})

	forged := signFor(t, "a-completely-different-key-32-bytes!!", uuid.NewString())
	if _, err := verifier.Verify(forged, time.Now()); errors.KindOf(err) != errors.KindUnauthenticated {
		t.Fatalf("Verify(bad signature) Kind = %v, want KindUnauthenticated", errors.KindOf(err))
	}
}

// TestRBACResolver_AdminGetsWildcard proves an admin membership confers the wildcard "*" grant even when
// the permission set did not list it (the IOTEA admin bypass) — so admin covers every namespace:action.
func TestRBACResolver_AdminGetsWildcard(t *testing.T) {
	t.Parallel()
	resolver := identity.NewRBACGrantResolver(&fakeMembership{membership: persistence.Membership{
		Role:        "admin",
		Permissions: []string{}, // empty set; the admin bypass still grants "*".
	}})

	grants, err := resolver.ResolveGrants(context.Background(), uuid.New())
	if err != nil {
		t.Fatalf("ResolveGrants = %v, want nil", err)
	}
	identityValue := edenhttp.Identity{Grants: grants}
	if !identityValue.HasGrant(edenhttp.NewGrant("anything", "goes")) {
		t.Fatalf("admin grants = %v, want the wildcard covering everything", grants)
	}
}

// TestRBACResolver_AdminWithExplicitWildcardNotDuplicated proves an admin whose permission set ALREADY
// lists "*" gets exactly one wildcard (the bypass is idempotent).
func TestRBACResolver_AdminWithExplicitWildcardNotDuplicated(t *testing.T) {
	t.Parallel()
	resolver := identity.NewRBACGrantResolver(&fakeMembership{membership: persistence.Membership{
		Role:        "admin",
		Permissions: []string{"*"},
	}})

	grants, err := resolver.ResolveGrants(context.Background(), uuid.New())
	if err != nil {
		t.Fatalf("ResolveGrants = %v, want nil", err)
	}
	if len(grants) != 1 {
		t.Fatalf("admin-with-explicit-wildcard grants = %v, want exactly one (no duplicate)", grants)
	}
}

// TestRBACResolver_MemberGetsExactGrants proves a plain member gets EXACTLY their permission strings (no
// wildcard) — so a member only holds what their set lists.
func TestRBACResolver_MemberGetsExactGrants(t *testing.T) {
	t.Parallel()
	resolver := identity.NewRBACGrantResolver(&fakeMembership{membership: persistence.Membership{
		Role:        "member",
		Permissions: []string{"users:read", "ping:read"},
	}})

	grants, err := resolver.ResolveGrants(context.Background(), uuid.New())
	if err != nil {
		t.Fatalf("ResolveGrants = %v, want nil", err)
	}
	value := edenhttp.Identity{Grants: grants}
	if !value.HasGrant(edenhttp.NewGrant("users", "read")) || !value.HasGrant(edenhttp.NewGrant("ping", "read")) {
		t.Fatalf("member grants = %v, want users:read + ping:read", grants)
	}
	if value.HasGrant(edenhttp.NewGrant("users", "write")) {
		t.Fatalf("member grants = %v, must NOT cover users:write (no wildcard for a member)", grants)
	}
}

// TestRBACResolver_MissingMembershipPropagatesKind proves a missing membership keeps its KindNotFound, so
// the dbVerifier's wrap turns it into a 401 (an unknown caller).
func TestRBACResolver_MissingMembershipPropagatesKind(t *testing.T) {
	t.Parallel()
	resolver := identity.NewRBACGrantResolver(&fakeMembership{err: errors.New(errors.KindNotFound, "membership not found")})

	_, err := resolver.ResolveGrants(context.Background(), uuid.New())
	if errors.KindOf(err) != errors.KindNotFound {
		t.Fatalf("ResolveGrants(missing) Kind = %v, want KindNotFound", errors.KindOf(err))
	}
}

// TestRBACResolver_MalformedPermissionIsInternal proves a permission string that does not parse is a
// KindInternal (a seed/data defect, not a caller fault).
func TestRBACResolver_MalformedPermissionIsInternal(t *testing.T) {
	t.Parallel()
	resolver := identity.NewRBACGrantResolver(&fakeMembership{membership: persistence.Membership{
		Role:        "member",
		Permissions: []string{"this:is:malformed"},
	}})

	_, err := resolver.ResolveGrants(context.Background(), uuid.New())
	if errors.KindOf(err) != errors.KindInternal {
		t.Fatalf("ResolveGrants(malformed permission) Kind = %v, want KindInternal", errors.KindOf(err))
	}
}
