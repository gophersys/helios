package projectcreate

// export_test.go is the white-box seam (the house idiom): it re-exports the package's PURE unexported
// helpers so the external _test package exercises them WITHOUT widening the public surface. Only the
// pure slug helpers are exposed — no port, no I/O.

// DeriveRepositorySlugForTest re-exports deriveRepositorySlug for the external test.
func DeriveRepositorySlugForTest(name, projectID string) string {
	return deriveRepositorySlug(name, projectID)
}

// SlugifyHNS1ForTest re-exports slugifyHNS1 for the external test.
func SlugifyHNS1ForTest(name string) string { return slugifyHNS1(name) }

// DeriveTenancyUUIDForTest re-exports deriveTenancyUUID for the external test (the name->UUID mapping the
// orchestrator's UUID tenancy columns require).
func DeriveTenancyUUIDForTest(name string) string { return deriveTenancyUUID(name) }
