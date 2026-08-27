package kubernetesadapter

import (
	"bytes"
	"context"
	stderrors "errors"
	"io"
	"path"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/internal/tarfile"
)

// files is the kubernetes file seam. Put/Get use a tar-over-exec plane (Put pipes a one-entry
// tar into `tar -x` inside the pod; Get pipes `tar -c` out and untars the single file); List
// runs a one-shot `ls`-style exec so the engine collects a produced artifact set without a
// shell of its own. The read-only MountInputs guarantee is enforced by the LIBRARY's state
// machine (classifyingFiles), not here.
type files struct {
	conn   *connection
	handle workspaceprovider.Handle
}

// Static assertion: *files satisfies workspaceprovider.Files.
var _ workspaceprovider.Files = (*files)(nil)

// Put writes content to p inside the pod by streaming a one-entry tar into `tar -x` rooted at
// the parent directory (the same mechanism kubectl cp uses). The unix mode is honored. It first
// ensures the parent directory exists (mkdir -p) so a write into a not-yet-created subdir of a
// writable mount succeeds.
func (f *files) Put(ctx context.Context, p string, content io.Reader, mode workspaceprovider.FileMode) error {
	data, err := io.ReadAll(content)
	if err != nil {
		// A failure to READ the caller's source is wrapped WITH its io cause and classified
		// KindInvalid (bad input from the caller's reader) — not a synthetic NotReadyError that
		// drops the cause (the errors contract: preserve the chain via %w, the right Kind).
		return errors.Wrap(errors.KindInvalid, "kubernetesadapter: Files.Put read content source", err)
	}
	dir, base := path.Split(strings.TrimRight(p, "/"))
	if dir == "" {
		dir = "/"
	}
	archive, terr := tarfile.One(base, data, int64(mode))
	if terr != nil {
		return errors.Wrap(errors.KindInternal, "kubernetesadapter: Files.Put encode tar", terr)
	}
	// Ensure the destination directory exists; a failure here surfaces as the extract failure
	// below with a clearer signal, so the mkdir result is best-effort.
	_, _ = f.exec(ctx, []string{"mkdir", "-p", dir}, nil) //nolint:errcheck // best-effort parent create; the extract below is the authority.
	res, eerr := f.exec(ctx, []string{"tar", "-x", "-m", "-f", "-", "-C", dir}, archive)
	if eerr != nil {
		return eerr
	}
	if res.ExitCode != 0 {
		return &workspaceprovider.NotFoundError{Handle: f.handle, Path: dir}
	}
	return nil
}

// Get reads p back out by streaming `tar -c` of the path and untarring the single file's bytes.
// NotFoundError if the path does not exist (tar exits non-zero).
func (f *files) Get(ctx context.Context, p string) (io.ReadCloser, error) {
	dir, base := path.Split(strings.TrimRight(p, "/"))
	if dir == "" {
		dir = "/"
	}
	var out bytes.Buffer
	res, err := f.execTo(ctx, []string{"tar", "-c", "-f", "-", "-C", dir, base}, &out)
	if err != nil {
		return nil, err
	}
	if res.ExitCode != 0 {
		return nil, &workspaceprovider.NotFoundError{Handle: f.handle, Path: p}
	}
	data, uerr := tarfile.Single(&out)
	// An EMPTY archive (the path produced no regular file) is "not found"; a CORRUPT tar (a
	// malformed header / truncated body from a damaged stream) is NOT collapsed into NotFound — it
	// surfaces as a faithful internal error wrapping the corruption cause, rather than masking it.
	if stderrors.Is(uerr, tarfile.ErrEmpty) {
		return nil, &workspaceprovider.NotFoundError{Handle: f.handle, Path: p}
	}
	if uerr != nil {
		return nil, errors.Wrap(errors.KindInternal, "kubernetesadapter: Files.Get untar "+strconv.Quote(p), uerr)
	}
	return io.NopCloser(bytes.NewReader(data)), nil
}

// List enumerates the shallow entries under p via a one-shot exec (`ls -1Ap`), parsing the
// output into FileEntry values. A directory entry ends in "/".
func (f *files) List(ctx context.Context, p string) ([]workspaceprovider.FileEntry, error) {
	var out bytes.Buffer
	res, err := f.execTo(ctx, []string{"ls", "-1Ap", p}, &out)
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

// exec runs a command in the pod with an optional stdin, discarding stdout/stderr but capturing
// the exit code (the Put extract path).
func (f *files) exec(ctx context.Context, command []string, stdin io.Reader) (workspaceprovider.ExecResult, error) {
	return f.conn.Exec(ctx, workspaceprovider.ExecSpec{Command: command, Stdin: stdin})
}

// execTo runs a command in the pod capturing stdout into out (the Get/List read paths).
func (f *files) execTo(ctx context.Context, command []string, out io.Writer) (workspaceprovider.ExecResult, error) {
	return f.conn.Exec(ctx, workspaceprovider.ExecSpec{Command: command, Stdout: out})
}
