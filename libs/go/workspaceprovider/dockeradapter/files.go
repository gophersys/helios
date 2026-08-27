package dockeradapter

import (
	"bytes"
	"context"
	stderrors "errors"
	"io"
	"path"
	"strconv"
	"strings"

	"github.com/docker/docker/api/types/container"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/internal/tarfile"
)

// files is the docker file seam. Put/Get use docker's tar-over-copy plane
// (CopyToContainer/CopyFromContainer); List runs a one-shot `ls`-style exec so the engine
// collects a produced artifact set without a shell of its own. The read-only MountInputs
// guarantee is enforced by the LIBRARY's state machine, not here (docker tmpfs is writable).
type files struct {
	adapter *Adapter
	id      string
	handle  workspaceprovider.Handle
}

// Static assertion: *files satisfies workspaceprovider.Files.
var _ workspaceprovider.Files = (*files)(nil)

// Put writes content to p inside the container by streaming a one-entry tar to the parent
// directory (docker's CopyToContainer API). The unix mode is honored. A failure to READ the
// caller's content source is returned WRAPPING the real io cause with KindInvalid (bad input from
// the caller's reader) — not a synthetic, cause-dropping NotReadyError that masks the underlying
// read failure (07 §4 / the errors contract: preserve the chain via %w, classify by the right
// Kind).
func (f *files) Put(ctx context.Context, p string, content io.Reader, mode workspaceprovider.FileMode) error {
	data, err := io.ReadAll(content)
	if err != nil {
		return errors.Wrap(errors.KindInvalid, "dockeradapter: Files.Put read content source", err)
	}
	dir, base := path.Split(strings.TrimRight(p, "/"))
	if dir == "" {
		dir = "/"
	}
	archive, terr := tarfile.One(base, data, int64(mode))
	if terr != nil {
		return errors.Wrap(errors.KindInternal, "dockeradapter: Files.Put encode tar", terr)
	}
	if cerr := f.adapter.client.CopyToContainer(ctx, f.id, dir, archive, container.CopyToContainerOptions{}); cerr != nil {
		if isNotFound(cerr) {
			return &workspaceprovider.NotFoundError{Handle: f.handle, Path: dir}
		}
		return classifyDockerError("copy to container", cerr)
	}
	return nil
}

// Get reads p back out by untarring docker's CopyFromContainer stream and returning the
// single file's bytes. An ABSENT path is a NotFoundError; an EMPTY archive (tarfile.ErrEmpty) is
// also NotFound. A CORRUPT tar stream (a malformed header / truncated body) is NOT collapsed into
// NotFound — it is returned WRAPPING the corruption cause with KindInternal, so a real
// stream-corruption surfaces as a faithful internal error rather than masquerading as "not found"
// (the errors contract: the right Kind, the cause preserved via %w).
func (f *files) Get(ctx context.Context, p string) (io.ReadCloser, error) {
	rc, _, err := f.adapter.client.CopyFromContainer(ctx, f.id, p)
	if err != nil {
		if isNotFound(err) {
			return nil, &workspaceprovider.NotFoundError{Handle: f.handle, Path: p}
		}
		return nil, classifyDockerError("copy from container", err)
	}
	defer func() { _ = rc.Close() }() //nolint:errcheck // closing a fully-read tar stream has no actionable error.
	data, uerr := tarfile.Single(rc)
	if stderrors.Is(uerr, tarfile.ErrEmpty) {
		return nil, &workspaceprovider.NotFoundError{Handle: f.handle, Path: p}
	}
	if uerr != nil {
		return nil, errors.Wrap(errors.KindInternal, "dockeradapter: Files.Get untar "+strconv.Quote(p), uerr)
	}
	return io.NopCloser(bytes.NewReader(data)), nil
}

// List enumerates the shallow entries under p via a one-shot exec (`ls -1Ap`), parsing the
// output into FileEntry values. A directory entry ends in "/".
func (f *files) List(ctx context.Context, p string) ([]workspaceprovider.FileEntry, error) {
	conn := f.adapter.connection(f.id, f.handle)
	var out bytes.Buffer
	res, err := conn.Exec(ctx, workspaceprovider.ExecSpec{
		Command: []string{"ls", "-1Ap", p},
		Stdout:  &out,
	})
	if err != nil {
		return nil, err
	}
	if res.ExitCode != 0 {
		return nil, &workspaceprovider.NotFoundError{Handle: f.handle, Path: p}
	}
	var entries []workspaceprovider.FileEntry
	for _, line := range strings.Split(strings.TrimSpace(out.String()), "\n") {
		name := strings.TrimSpace(line)
		if name == "" {
			continue
		}
		isDir := strings.HasSuffix(name, "/")
		entries = append(entries, workspaceprovider.FileEntry{
			Name:  strings.TrimSuffix(name, "/"),
			IsDir: isDir,
			Mode:  0o644,
		})
	}
	return entries, nil
}
