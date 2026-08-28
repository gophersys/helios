package testing_test

import (
	"bytes"
	"context"
	"strings"
	gotest "testing"

	testingpkg "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/testing/testingtest"
)

// seededCanary is the redaction needle (ADR-0020 dimension (f), generalising the house
// SeededCanary): a value that, once handed to the conformance machinery, must appear in NO
// surfaced artifact it was not explicitly recorded on. `testing` owns no credential or secret
// PORT — it has no Spec/Handle/Status to redact — so its canary obligation is narrower but
// real: the structured Result a clean run hands engine/evidence must carry ONLY the messages
// the case author recorded, never operator content the machinery saw and echoed on its own.
const seededCanary = "SEEDED-CANARY-dGVzdGluZw-d34db33f-do-not-leak"

// TestCanary_PassingCaseLeaksNoContent asserts that a PASSING case produces a CaseResult with
// EMPTY Messages — the machinery does not echo the case name, the capability the harness was
// given, or anything else into the surfaced Result. A regression that started folding e.g. the
// harness's seed or a capability string into a passing case's Messages could surface a secret a
// caller named a capability after; this pins Messages to the case-author-recorded set only.
func TestCanary_PassingCaseLeaksNoContent(t *gotest.T) {
	t.Parallel()
	r, err := testingpkg.New(
		testingpkg.Config{RequireCapabilities: []string{seededCanary}}, // capability NAMED after the needle
		testingpkg.Deps{},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	cases := []testingpkg.Case[int]{
		{Name: "clean", Run: func(_ int, h testingpkg.Harness, _ testingpkg.Report) {
			_ = h.Has(seededCanary) // the case OBSERVES the canary-named capability but records nothing
		}},
	}
	suite := testingpkg.Suite[int]{Name: "canarysuite", Cases: testingtest.CaseSeq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)

	if res.Failed != 0 {
		t.Fatalf("clean case should pass; got %+v", res)
	}
	// The Suite name, the CaseResult name, and every recorded message must be canary-free —
	// the machinery surfaced nothing the case did not record.
	surfaces := []string{res.Suite}
	for _, c := range res.Cases {
		surfaces = append(surfaces, c.Name, c.Panic)
		surfaces = append(surfaces, c.Messages...)
	}
	for _, s := range surfaces {
		if strings.Contains(s, seededCanary) {
			t.Fatalf("canary leaked into a surfaced Result artifact: %q", s)
		}
	}
}

// TestRedact_RandomSourceNeverEchoesSeed asserts the deterministic entropy stream never
// surfaces a planted needle: the RandomSource derives its bytes from the seed via a one-way
// PRNG, so a recognizable marker handed to the Runner as the seed-bearing Config must NOT
// appear verbatim in the produced bytes. This is the entropy-path analog of the redaction
// property — a generator that leaked its seed material into its output would be a real defect.
func TestRedact_RandomSourceNeverEchoesSeed(t *gotest.T) {
	t.Parallel()
	// A high-entropy recognizable seed; its little-endian bytes must NOT appear in the stream.
	const seed uint64 = 0xDEADBEEFCAFEBABE
	r, err := testingpkg.New(testingpkg.Config{Seed: seed}, testingpkg.Deps{})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	out := make([]byte, 4096)
	if _, err := r.Fakes().Random.Read(out); err != nil {
		t.Fatalf("Read: %v", err)
	}
	needle := []byte{0xBE, 0xBA, 0xFE, 0xCA, 0xEF, 0xBE, 0xAD, 0xDE} // seed, little-endian
	if i := bytes.Index(out, needle); i >= 0 {
		t.Fatalf("seed bytes echoed verbatim into the entropy stream at offset %d — PRNG leaks its seed", i)
	}
}
