package gateway_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// TestWorkspaceListsRealFilesAndRejectsTraversal proves GET /sessions/{id}/workspace lists
// the REAL files under the configured workspace root as RELATIVE, sorted paths — and that
// the listing never escapes the root: dotfiles/.git are skipped and a symlink pointing OUT
// of the workspace is not reported (its out-of-root target can never reach the wire).
func TestWorkspaceListsRealFilesAndRejectsTraversal(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	// Real files the "agent" produced, including a nested directory.
	writeFile(t, filepath.Join(root, "main.go"), "package main")
	writeFile(t, filepath.Join(root, "internal", "app", "app.go"), "package app")
	// Noise that MUST be skipped: a dotfile and a .git subtree (a secret-bearing surface).
	writeFile(t, filepath.Join(root, ".env"), "SECRET=should-never-list")
	writeFile(t, filepath.Join(root, ".git", "config"), "[core]")
	writeFile(t, filepath.Join(root, "internal", ".hidden"), "nope")

	// A sibling tree OUTSIDE the root holding a secret, reached by a symlink placed INSIDE
	// the root. The walk must not follow it (symlinks are non-regular and dropped), so the
	// out-of-root path can never appear in the listing — the no-traversal guarantee.
	outside := t.TempDir()
	writeFile(t, filepath.Join(outside, "leaked.txt"), "TOP SECRET")
	if runtime.GOOS != "windows" {
		if err := os.Symlink(outside, filepath.Join(root, "escape")); err != nil {
			t.Fatalf("symlink: %v", err)
		}
		if err := os.Symlink(filepath.Join(outside, "leaked.txt"), filepath.Join(root, "leak-file")); err != nil {
			t.Fatalf("symlink file: %v", err)
		}
	}

	server := newWorkspaceServer(t, root)
	paths := getWorkspacePaths(t, server.URL+"/sessions/agent-x/workspace")

	wantPresent := []string{"main.go", "internal/app/app.go"}
	for _, p := range wantPresent {
		if !containsString(paths, p) {
			t.Fatalf("expected %q in workspace listing, got %v", p, paths)
		}
	}
	wantAbsent := []string{".env", ".git/config", "internal/.hidden", "escape", "leak-file"}
	for _, p := range wantAbsent {
		if containsString(paths, p) {
			t.Fatalf("path %q must NOT appear in the listing (dotfile/.git/symlink), got %v", p, paths)
		}
	}
	// No emitted path is absolute, escapes the root via "..", or leaks the outside secret name.
	for _, p := range paths {
		if filepath.IsAbs(p) || strings.HasPrefix(p, "..") || strings.Contains(p, "..") {
			t.Fatalf("listing escaped the workspace root: %q (all: %v)", p, paths)
		}
		if strings.Contains(p, "leaked.txt") {
			t.Fatalf("listing leaked an out-of-root path: %q", p)
		}
	}

	// Sorted ascending (the wire contract the UI renders in order).
	for i := 1; i < len(paths); i++ {
		if paths[i-1] > paths[i] {
			t.Fatalf("workspace listing is not sorted: %v", paths)
		}
	}
}

// TestWorkspaceEmptyWhenRootMissing proves an unwritten workspace (the root does not exist
// yet) is an honest empty listing, not a 5xx — the agent simply has not produced a file.
func TestWorkspaceEmptyWhenRootMissing(t *testing.T) {
	t.Parallel()

	root := filepath.Join(t.TempDir(), "not-created-yet")
	server := newWorkspaceServer(t, root)

	status, body := getWorkspace(t, server.URL+"/sessions/agent-x/workspace")
	if status != http.StatusOK {
		t.Fatalf("expected 200 for a missing workspace root, got %d (%v)", status, body)
	}
	files, ok := body["files"].([]any)
	if !ok {
		t.Fatalf("expected a files array, got %v", body["files"])
	}
	if len(files) != 0 {
		t.Fatalf("expected an empty listing for a missing root, got %v", files)
	}
}

// newWorkspaceServer builds a gateway whose configured workspace root is dir and serves it
// over httptest (the same real record + live planes the main harness uses, only the
// Workspace differs). Reaped on cleanup.
func newWorkspaceServer(t *testing.T, dir string) *httptest.Server {
	t.Helper()

	provider := secretstest.New(map[string]string{credentialRef: agentsessiontest.SeededCanary})
	transcript := agentsessiontest.NewTranscript()
	routing := map[agentsession.RouteKey]agentsession.Route{
		gatewayRouteKey(): {Harness: "fake", Model: "fake-fable-5"},
	}
	pool, err := agentsession.New(
		agentsession.Config{Routing: routing},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": agentsessiontest.New()},
			Secrets:    provider,
			Transcript: transcript,
			Clock:      fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("agentsession.New: %v", err)
	}

	g, err := gateway.New(
		gateway.Config{
			Credential: secrets.Ref(credentialRef),
			Routing:    gatewayRouteKey(),
			Workspace:  dir,
		},
		gateway.Deps{
			Manager:    orchestratortest.New(orchestratortest.WithTemplate(orchestratortest.DefaultTemplate())),
			Sessions:   pool,
			Transcript: transcript,
			Clock:      fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("gateway.New: %v", err)
	}

	server := httptest.NewServer(g.Handler())
	t.Cleanup(func() {
		server.Close()
		_ = g.Close(context.Background()) //nolint:errcheck // test cleanup reap; a close fault is not a test signal.
	})
	return server
}

// getWorkspace GETs the workspace route and returns the status + decoded body.
func getWorkspace(t *testing.T, url string) (status int, body map[string]any) {
	t.Helper()
	request, err := http.NewRequestWithContext(context.Background(), http.MethodGet, url, http.NoBody)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	return doDecode(t, request)
}

// getWorkspacePaths GETs the workspace route and projects the file paths, failing on a non-200.
func getWorkspacePaths(t *testing.T, url string) []string {
	t.Helper()
	status, body := getWorkspace(t, url)
	if status != http.StatusOK {
		t.Fatalf("workspace: status %d (%v)", status, body)
	}
	files, ok := body["files"].([]any)
	if !ok {
		t.Fatalf("workspace: missing files array (%v)", body)
	}
	paths := make([]string, 0, len(files))
	for _, f := range files {
		entry, ok := f.(map[string]any)
		if !ok {
			t.Fatalf("workspace: file entry is not an object: %v", f)
		}
		path, ok := entry["path"].(string)
		if !ok {
			t.Fatalf("workspace: file entry missing path: %v", entry)
		}
		paths = append(paths, path)
	}
	return paths
}

// writeFile writes content to path, creating parent directories.
func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
		t.Fatalf("mkdir %s: %v", filepath.Dir(path), err)
	}
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

// containsString reports whether haystack contains needle.
func containsString(haystack []string, needle string) bool {
	for _, s := range haystack {
		if s == needle {
			return true
		}
	}
	return false
}
