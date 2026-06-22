package projectcreate_test

import (
	"testing"

	"github.com/gophersys/eden/apps/agentgateway/internal/projectcreate"
)

// These exercise the pure slug derivation through the white-box export seam. They prove the slug is
// HNS-1-legal, carries the human prefix, and inherits the project id's uniqueness so two like-named
// projects never collide.

func TestDeriveRepositorySlug_CarriesNamePrefixAndUniqueSuffix(t *testing.T) {
	t.Parallel()
	const id = "project-aabbccddeeff001122"
	slug := projectcreate.DeriveRepositorySlugForTest("Pay Backend!!", id)

	if got := projectcreate.SlugifyHNS1ForTest(slug); got != slug {
		t.Errorf("slug is not HNS-1-legal: %q (re-slugified to %q)", slug, got)
	}
	if !hasPrefix(slug, "pay-backend-") {
		t.Errorf("slug = %q, want the slugified name prefix", slug)
	}
	// The suffix is the id's unique hex tail (collision-free across like-named projects).
	if !hasSuffix(slug, "aabbccddeeff001122") {
		t.Errorf("slug = %q, want the project id hex suffix", slug)
	}
}

func TestDeriveRepositorySlug_DistinctIDsNeverCollide(t *testing.T) {
	t.Parallel()
	a := projectcreate.DeriveRepositorySlugForTest("invoice service", "project-1111111111aaaaaaaa")
	b := projectcreate.DeriveRepositorySlugForTest("invoice service", "project-2222222222bbbbbbbb")
	if a == b {
		t.Fatalf("two like-named projects produced the same slug: %q", a)
	}
}

func TestDeriveRepositorySlug_EmptyNameFallsBack(t *testing.T) {
	t.Parallel()
	slug := projectcreate.DeriveRepositorySlugForTest("!!!", "project-deadbeefdeadbeef00")
	if !hasPrefix(slug, "eden-project-") {
		t.Errorf("empty-name slug = %q, want the eden-project fallback", slug)
	}
	if got := projectcreate.SlugifyHNS1ForTest(slug); got != slug {
		t.Errorf("fallback slug not HNS-1-legal: %q", slug)
	}
}

func hasPrefix(s, prefix string) bool { return len(s) >= len(prefix) && s[:len(prefix)] == prefix }
func hasSuffix(s, suffix string) bool {
	return len(s) >= len(suffix) && s[len(s)-len(suffix):] == suffix
}
