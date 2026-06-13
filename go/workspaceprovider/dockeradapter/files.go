package dockeradapter

import (
	"archive/tar"
	"bytes"
	"context"
	"io"
	"path"
	"strings"

	"github.com/docker/docker/api/types/container"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
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
// directory (docker's CopyToContainer API). The unix mode is honored.
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
	if cerr := f.adapter.client.CopyToContainer(ctx, f.id, dir, archive, container.CopyToContainerOptions{}); cerr != nil {
		if isNotFound(cerr) {
			return &workspaceprovider.NotFoundError{Handle: f.handle, Path: dir}
		}
		return classifyDockerError("copy to container", cerr)
	}
	return nil
}

// Get reads p back out by untarring docker's CopyFromContainer stream and returning the
// single file's bytes. NotFoundError if the path does not exist.
func (f *files) Get(ctx context.Context, p string) (io.ReadCloser, error) {
	rc, _, err := f.adapter.client.CopyFromContainer(ctx, f.id, p)
	if err != nil {
		if isNotFound(err) {
			return nil, &workspaceprovider.NotFoundError{Handle: f.handle, Path: p}
		}
		return nil, classifyDockerError("copy from container", err)
	}
	defer func() { _ = rc.Close() }() //nolint:errcheck // closing a fully-read tar stream has no actionable error.
	data, uerr := untarSingle(rc)
	if uerr != nil {
		return nil, &workspaceprovider.NotFoundError{Handle: f.handle, Path: p}
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

// tarOneFile builds a single-entry tar archive (name -> data) with the given mode, ready
// for CopyToContainer.
func tarOneFile(name string, data []byte, mode workspaceprovider.FileMode) (io.Reader, error) {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)
	if err := tw.WriteHeader(&tar.Header{
		Name: name,
		Mode: int64(mode),
		Size: int64(len(data)),
	}); err != nil {
		return nil, errors.Wrap(errors.KindInternal, "dockeradapter: write tar header", err)
	}
	if _, err := tw.Write(data); err != nil {
		return nil, errors.Wrap(errors.KindInternal, "dockeradapter: write tar body", err)
	}
	if err := tw.Close(); err != nil {
		return nil, errors.Wrap(errors.KindInternal, "dockeradapter: close tar writer", err)
	}
	return &buf, nil
}

// untarSingle reads the first regular file from a tar stream and returns its bytes (the
// CopyFromContainer response is a tar of the requested path).
func untarSingle(r io.Reader) ([]byte, error) {
	tr := tar.NewReader(r)
	for {
		header, err := tr.Next()
		if err == io.EOF {
			return nil, io.EOF
		}
		if err != nil {
			return nil, errors.Wrap(errors.KindInternal, "dockeradapter: read tar header", err)
		}
		if header.Typeflag == tar.TypeReg {
			data, rerr := io.ReadAll(tr)
			if rerr != nil {
				return nil, errors.Wrap(errors.KindInternal, "dockeradapter: read tar entry", rerr)
			}
			return data, nil
		}
	}
}
