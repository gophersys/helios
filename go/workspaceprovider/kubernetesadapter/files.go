package kubernetesadapter

import (
	"archive/tar"
	"bytes"
	"context"
	"io"
	"path"
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
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
		return &workspaceprovider.NotReadyError{Handle: f.handle, State: workspaceprovider.StateReady, Op: "Files.Put(read source)"}
	}
	dir, base := path.Split(strings.TrimRight(p, "/"))
	if dir == "" {
		dir = "/"
	}
	archive, terr := tarOneFile(base, data, mode)
	if terr != nil {
		return &workspaceprovider.NotReadyError{Handle: f.handle, State: workspaceprovider.StateReady, Op: "Files.Put(tar)"}
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
	data, uerr := untarSingle(&out)
	if uerr != nil {
		return nil, &workspaceprovider.NotFoundError{Handle: f.handle, Path: p}
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

// tarOneFile builds a single-entry tar archive (name -> data) with the given mode, ready to be
// piped into `tar -x`.
func tarOneFile(name string, data []byte, mode workspaceprovider.FileMode) (io.Reader, error) {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)
	if err := tw.WriteHeader(&tar.Header{
		Name: name,
		Mode: int64(mode),
		Size: int64(len(data)),
	}); err != nil {
		return nil, errors.Wrap(errors.KindInternal, "kubernetesadapter: write tar header", err)
	}
	if _, err := tw.Write(data); err != nil {
		return nil, errors.Wrap(errors.KindInternal, "kubernetesadapter: write tar body", err)
	}
	if err := tw.Close(); err != nil {
		return nil, errors.Wrap(errors.KindInternal, "kubernetesadapter: close tar writer", err)
	}
	return &buf, nil
}

// untarSingle reads the first regular file from a tar stream and returns its bytes (the `tar -c`
// response is a tar of the requested path).
func untarSingle(r io.Reader) ([]byte, error) {
	tr := tar.NewReader(r)
	for {
		header, err := tr.Next()
		if err == io.EOF {
			return nil, io.EOF
		}
		if err != nil {
			return nil, errors.Wrap(errors.KindInternal, "kubernetesadapter: read tar header", err)
		}
		if header.Typeflag == tar.TypeReg {
			data, rerr := io.ReadAll(tr)
			if rerr != nil {
				return nil, errors.Wrap(errors.KindInternal, "kubernetesadapter: read tar entry", rerr)
			}
			return data, nil
		}
	}
}
