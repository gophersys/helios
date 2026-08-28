package tarfile_test

import (
	"archive/tar"
	"bytes"
	stderrors "errors"
	"io"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider/internal/tarfile"
)

// TestRoundTrip proves One -> Single returns the original bytes (the Files.Put/Get happy path).
func TestRoundTrip(t *testing.T) {
	t.Parallel()
	want := []byte("artifact-bytes\n")
	r, err := tarfile.One("out.txt", want, 0o644)
	if err != nil {
		t.Fatalf("One: %v", err)
	}
	got, serr := tarfile.Single(r)
	if serr != nil {
		t.Fatalf("Single: %v", serr)
	}
	if !bytes.Equal(got, want) {
		t.Errorf("round-trip: got %q want %q", got, want)
	}
}

// TestEmptyArchiveIsErrEmpty proves an empty (no-regular-file) stream is ErrEmpty — the NotFound
// shape a caller maps to NotFoundError.
func TestEmptyArchiveIsErrEmpty(t *testing.T) {
	t.Parallel()
	var empty bytes.Buffer
	tw := tar.NewWriter(&empty)
	if err := tw.Close(); err != nil {
		t.Fatalf("close empty tar: %v", err)
	}
	_, err := tarfile.Single(&empty)
	if !stderrors.Is(err, tarfile.ErrEmpty) {
		t.Errorf("Single(empty archive) err = %v, want ErrEmpty", err)
	}
}

// TestCorruptStreamIsNotErrEmpty is the executable form of finding #7: a CORRUPT tar must NOT be
// collapsed into the empty/NotFound shape — it must surface as a distinct, internally-Kinded error
// carrying the corruption cause, so a caller maps it to KindInternal rather than masking it as
// NotFound. WEAKEN-TO-CONFIRM: if Single returned io.EOF/ErrEmpty for a malformed header (the old
// behavior, "every untar error -> NotFound"), stderrors.Is(err, ErrEmpty) would be TRUE and this
// fails.
func TestCorruptStreamIsNotErrEmpty(t *testing.T) {
	t.Parallel()
	// A truncated/garbage stream that is NOT a valid tar header: tar.Reader.Next returns a non-EOF
	// error (e.g. unexpected EOF / bad header), which Single must wrap as KindInternal, not ErrEmpty.
	corrupt := bytes.NewReader([]byte("this-is-not-a-valid-tar-header-stream-but-long-enough-to-parse-as-one-block"))
	_, err := tarfile.Single(corrupt)
	if err == nil {
		t.Fatalf("Single(corrupt) returned nil, want a wrapped corruption error")
	}
	if stderrors.Is(err, tarfile.ErrEmpty) {
		t.Fatalf("Single(corrupt) returned ErrEmpty (masking corruption as NotFound — the finding #7 bug)")
	}
	if errors.KindOf(err) != errors.KindInternal {
		t.Errorf("Single(corrupt) Kind = %v, want KindInternal (corruption is internal, not NotFound)", errors.KindOf(err))
	}
}

// TestTruncatedBodyIsCorrupt proves a header that promises N bytes but whose body is short surfaces
// as a wrapped corruption error (not ErrEmpty) — the read-entry failure path.
func TestTruncatedBodyIsCorrupt(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)
	// Declare a 100-byte file but write only 4 bytes, then DON'T close (so the body is truncated).
	if err := tw.WriteHeader(&tar.Header{Name: "f", Mode: 0o644, Size: 100}); err != nil {
		t.Fatalf("WriteHeader: %v", err)
	}
	if _, err := tw.Write([]byte("abcd")); err != nil {
		t.Fatalf("Write: %v", err)
	}
	// Feed only the bytes written so far (a truncated archive) — flush the writer's buffer first.
	_ = tw.Flush() //nolint:errcheck // best-effort flush of the partial archive for the truncation test.
	_, err := tarfile.Single(io.LimitReader(&buf, int64(buf.Len())))
	if err == nil {
		t.Fatalf("Single(truncated body) returned nil, want a corruption error")
	}
	if stderrors.Is(err, tarfile.ErrEmpty) {
		t.Errorf("Single(truncated body) returned ErrEmpty, want a wrapped corruption error")
	}
}
