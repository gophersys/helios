package gateway

import (
	"io/fs"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"

	stderrors "errors"

	"github.com/gophersys/libs/go/errors"
)

// maxWorkspaceFiles caps the workspace listing so a runaway generation (a node_modules
// explosion, a build cache) can neither exhaust the response nor stall the UI. The cap is a
// sane ceiling on a "files the agent produced" view; the tool-derived artifact list in the
// UI covers the salient writes regardless.
const maxWorkspaceFiles = 500

// handleWorkspace serves GET /sessions/{id}/workspace — the REAL files the agent produced
// under its workspace directory, the ground-truth complement to the tool-derived artifact
// view the UI assembles from the event stream. It lists regular files under the configured
// workspace root (the harness CWD the gateway already names on Config.Workspace), returning
// each as a path RELATIVE to the root with its size and mtime. The id is the canonical
// route shape (every per-session route carries it) but the gateway holds ONE configured
// workspace root for its live composition, so the listing is root-scoped: the live-local
// composition runs one workspace per gateway (cmd/agentgateway-live's EDEN_WORKSPACE).
//
// Safety: dotfiles and .git are skipped (noise + a secret-bearing surface), the listing is
// sorted and capped at maxWorkspaceFiles, and every emitted path is verified to stay WITHIN
// the root (a cleaned relative path that neither is absolute nor escapes via ".." — no
// traversal can leak a path outside the workspace). The body carries only a path, a size,
// and a mtime; no field can hold a credential.
func (g *Gateway) handleWorkspace(w http.ResponseWriter, r *http.Request) {
	root := strings.TrimSpace(g.configuration.Workspace)
	if root == "" {
		g.writeError(w, errors.Wrap(errors.KindUnavailable, "gateway: workspace",
			RequestError{Reason: "no workspace root is configured for this gateway"}))
		return
	}

	files, err := listWorkspaceFiles(root)
	if err != nil {
		g.writeError(w, err)
		return
	}
	g.writeJSON(w, http.StatusOK, workspaceResponse{Files: files})
}

// listWorkspaceFiles walks root and returns every regular file beneath it as a
// workspaceFileView with a slash-separated path RELATIVE to root, sorted by path and capped
// at maxWorkspaceFiles. Dotfiles and dot-directories (notably .git) are skipped wholesale.
// A path that does not stay within root (an absolute or "..-escaping" relative path — only
// reachable via a symlink target, since WalkDir does not follow links) is dropped, never
// emitted: the root is never escaped. A missing root is not an error — it yields an empty
// listing (the workspace may not have been written to yet); any OTHER root fault (e.g. a
// permission denial on the root itself) IS surfaced rather than masqueraded as empty.
func listWorkspaceFiles(root string) ([]workspaceFileView, error) {
	cleanRoot := filepath.Clean(root)

	files := make([]workspaceFileView, 0, 64)
	walkErr := filepath.WalkDir(cleanRoot, func(path string, entry fs.DirEntry, err error) error {
		return collectWorkspaceFile(cleanRoot, path, entry, err, &files)
	})
	if walkErr != nil {
		// The only fault that propagates here is a root-entry fault the callback chose to
		// surface (a non-not-exist stat error on the root itself). A missing root never
		// reaches here — the callback maps it to an empty listing — so this is a genuine
		// fault worth a 5xx, not a workspace that simply has not been written to yet.
		return nil, errors.Wrap(errors.KindUnavailable, "gateway: workspace listing",
			RequestError{Reason: "the workspace root could not be read"})
	}

	sort.Slice(files, func(i, j int) bool { return files[i].Path < files[j].Path })
	if len(files) > maxWorkspaceFiles {
		files = files[:maxWorkspaceFiles]
	}
	return files, nil
}

// collectWorkspaceFile is the WalkDir visitor: it appends a regular, in-root, non-dotfile
// entry to files (skipping dotfiles/dot-directories, non-regular entries, and root-escaping
// paths) and classifies walk faults. A per-entry fault (an unreadable subtree, a stat race)
// is non-fatal — skipped so the best-effort ground-truth listing keeps going — but a fault on
// the ROOT entry that is NOT a not-exist (a missing workspace is the normal "not written yet"
// case, mapped to empty) is propagated, never swallowed, so a real root fault becomes a 5xx
// instead of a silently empty listing.
func collectWorkspaceFile(cleanRoot, path string, entry fs.DirEntry, err error, files *[]workspaceFileView) error {
	if err != nil {
		if path == cleanRoot && !stderrors.Is(err, os.ErrNotExist) {
			// A real fault on the root itself (e.g. a permission denial) — surface it; only a
			// missing root is the benign "not written yet" case mapped to an empty listing.
			return err
		}
		// An unreadable subtree (a permission fault on one directory) or a missing root must
		// not abort the listing: skip the subtree and continue best-effort.
		if entry != nil && entry.IsDir() {
			return fs.SkipDir
		}
		return nil //nolint:nilerr // a per-entry stat fault (or a missing root) is skipped, not fatal — the listing is best-effort ground truth.
	}
	name := entry.Name()
	if path != cleanRoot && strings.HasPrefix(name, ".") {
		// Skip dotfiles and dot-directories (.git, .cache, …) — noise and a
		// secret-bearing surface; pruning the directory avoids walking into it.
		if entry.IsDir() {
			return fs.SkipDir
		}
		return nil
	}
	if entry.IsDir() {
		return nil
	}
	if !entry.Type().IsRegular() {
		// Skip symlinks, devices, sockets — only real files the agent wrote are reported,
		// and a symlink is the one way a path could escape the root (its target is not walked).
		return nil
	}

	relative, ok := relativeWithinRoot(cleanRoot, path)
	if !ok {
		return nil
	}
	info, infoErr := entry.Info()
	if infoErr != nil {
		return nil //nolint:nilerr // a stat race (file removed mid-walk) drops the entry, never aborts the listing.
	}
	*files = append(*files, workspaceFileView{
		Path:         relative,
		Size:         info.Size(),
		ModifiedUnix: info.ModTime().Unix(),
	})
	return nil
}

// relativeWithinRoot returns path expressed RELATIVE to root with forward slashes, and
// whether it provably stays inside root. It rejects an absolute result and any path that
// escapes via a leading "..": the emitted path can never name a location outside the
// workspace root (no traversal). The returned path uses "/" separators so the wire DTO is
// platform-independent and the UI renders one tree shape.
func relativeWithinRoot(root, path string) (string, bool) {
	relative, err := filepath.Rel(root, path)
	if err != nil {
		return "", false
	}
	relative = filepath.Clean(relative)
	if relative == "." || relative == "" {
		return "", false
	}
	if filepath.IsAbs(relative) || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return "", false
	}
	return filepath.ToSlash(relative), true
}
