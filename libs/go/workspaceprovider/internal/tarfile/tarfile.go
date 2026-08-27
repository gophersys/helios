// Package tarfile is the substrate-neutral single-file tar codec both adapters use to move
// one file in/out of a workspace (docker's CopyToContainer/CopyFromContainer tar plane and
// kubernetes' tar-over-exec plane are byte-identical at the archive level). It lives ONCE here
// (one concept, one home — 10 §9) so the docker and kubernetes adapters CITE it rather than each
// re-spelling the tar writer/reader. It also distinguishes an EMPTY/absent stream (io.EOF) from a
// genuinely CORRUPT tar (a wrapped header/body error), so a caller can map the two to the right
// error Kind instead of collapsing every read failure into NotFound.
package tarfile

import (
	"archive/tar"
	"bytes"
	stderrors "errors"
	"io"

	"github.com/gophersys/libs/go/errors"
)

// ErrEmpty is the sentinel One returns when a tar stream ends before any regular file is found
// (io.EOF at the first header) — an EMPTY archive, the "no such file" shape a caller maps to
// NotFound. It is DISTINCT from a corruption error (a wrapped KindInternal error), so the caller
// can branch: ErrEmpty → NotFound, anything else → the corruption's own Kind.
var ErrEmpty = stderrors.New("tarfile: empty archive (no regular file)")

// One builds a single-entry tar archive (name -> data) with the given unix mode, ready to feed
// CopyToContainer or `tar -x`. A write failure is wrapped with KindInternal (it is an in-memory
// buffer write, so a failure is a programming/OOM fault, never a substrate condition).
func One(name string, data []byte, mode int64) (io.Reader, error) {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)
	if err := tw.WriteHeader(&tar.Header{Name: name, Mode: mode, Size: int64(len(data))}); err != nil {
		return nil, errors.Wrap(errors.KindInternal, "tarfile: write tar header", err)
	}
	if _, err := tw.Write(data); err != nil {
		return nil, errors.Wrap(errors.KindInternal, "tarfile: write tar body", err)
	}
	if err := tw.Close(); err != nil {
		return nil, errors.Wrap(errors.KindInternal, "tarfile: close tar writer", err)
	}
	return &buf, nil
}

// Single reads the FIRST regular file from a tar stream and returns its bytes. It returns
// ErrEmpty when the stream ends before any regular file (an absent path — the NotFound shape),
// and a wrapped KindInternal error when the tar itself is CORRUPT (a malformed header or a
// truncated body) — so the caller distinguishes "not there" from "there but corrupt" rather than
// reporting both as NotFound (masking corruption). The distinction is the whole reason this lives
// in one place: both adapters get the same faithful classification.
func Single(r io.Reader) ([]byte, error) {
	tr := tar.NewReader(r)
	for {
		header, err := tr.Next()
		if stderrors.Is(err, io.EOF) {
			return nil, ErrEmpty
		}
		if err != nil {
			return nil, errors.Wrap(errors.KindInternal, "tarfile: read tar header", err)
		}
		if header.Typeflag == tar.TypeReg {
			data, rerr := io.ReadAll(tr)
			if rerr != nil {
				return nil, errors.Wrap(errors.KindInternal, "tarfile: read tar entry", rerr)
			}
			return data, nil
		}
	}
}
