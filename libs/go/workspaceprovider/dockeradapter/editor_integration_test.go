//go:build integration

package dockeradapter_test

import (
	"context"
	"os/exec"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/dockeradapter"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// editorImage is the read-only code-server image the editor-sidecar integration test provisions. It
// is pre-pulled by the harness (WithImages) so the per-test provision is fast and offline-safe.
const editorImage = "codercom/code-server:latest"

// TestDocker_EditorSidecarServesWorktreeReadOnly is the ADR-0027 editor-sidecar proof on the REAL
// docker daemon: a spec.Editor runs a read-only code-server SIBLING that shares the workspace's
// workdir READ-ONLY (`--volumes-from <workspace>:ro` — the docker analog of the kubernetes
// readOnly:true volumeMount), so a human opens the agent's LIVE worktree in a view-only VS Code. It
// asserts, against the live daemon, ALL of:
//
//	(a) the editor sibling is REACHABLE and serving: it answers HTTP 200 on /healthz AND the
//	    open-folder URL /?folder=<workDir>. The editor is reached by its CONTAINER IP (the address a
//	    peer container — the test's own devcontainer — can reach; the published 127.0.0.1:<host-port>
//	    origin is reachable from the docker HOST, not a sibling, so the IP is the right address here);
//	(b) the editor sibling SEES a sentinel the workspace container wrote into the shared workdir —
//	    the LIVE worktree is the thing served, not an empty layer;
//	(c) READ-ONLY is STRUCTURAL: a write from INSIDE the editor sibling to the shared workdir fails
//	    with "Read-only file system" (EROFS — the `:ro` share the kernel enforces), while the
//	    workspace side stays writable;
//	(d) Teardown removes the editor sibling FIRST then the workspace → CountOwned()==0, no orphan.
//
// The editor sibling is reached/exercised via `docker exec` into the editor container (the one reach
// the Adapter's Connection.Exec port does not offer — it execs the workspace container only). No
// mock — a real daemon, a real code-server, a real kernel-enforced read-only share (ADR-0016 §2).
//
// WEAKEN-TO-CONFIRM the read-only assertion is non-vacuous: drop the `:ro` suffix on VolumesFrom in
// startEditorSibling (share read-WRITE) and step (c)'s editor-side write SUCCEEDS → this test then
// FAILS on "editor write to a read-only worktree unexpectedly succeeded" (proven in the report).
//
//nolint:gocognit,cyclop,paralleltest // a deliberate linear real-substrate editor-sidecar walk; serial by design (spins real containers).
func TestDocker_EditorSidecarServesWorktreeReadOnly(t *testing.T) {
	ctx := t.Context()
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(testImage, editorImage))
	prov := newProvider(t, adapter)

	editorSpec := &workspaceprovider.EditorSpec{Image: editorImage, Port: 8080}
	spec := workspaceprovider.WorkspaceSpec{
		Name:      "ws-editor",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     testImage,
		Mounts:    []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/workspace"}},
		Editor:    editorSpec,
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: "org-editor",
			workspaceprovider.LabelProject:      "proj-editor",
		},
	}

	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		t.Fatalf("Provision (Editor) against real docker: %v", err)
	}
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), ws.Handle()) }) //nolint:errcheck // best-effort cleanup; Teardown is idempotent and the harness re-scan asserts no orphan.

	// The non-editor workspace must still be Ready/Running (the sidecar is additive).
	if st, serr := ws.Status(ctx); serr != nil {
		t.Fatalf("Status: %v", serr)
	} else if st.State != workspaceprovider.StateReady && st.State != workspaceprovider.StateRunning {
		t.Errorf("an Editor-sidecar workspace must be Ready/Running (the sidecar is additive), got %v", st.State)
	}

	owner, ok := adapter.(*dockeradapter.Adapter)
	if !ok {
		t.Fatalf("expected the dockeradapter.Adapter to expose EditorContainerForTest")
	}
	editorName, editorEndpoint, eerr := owner.EditorContainerForTest(ctx, ws.Handle(), editorSpec)
	if eerr != nil {
		t.Fatalf("locate the editor sibling: %v", eerr)
	}

	// (a) The editor sibling is REACHABLE and serving: 200 on /healthz and the open-folder URL. The
	// curl runs from INSIDE the editor container (it has curl on PATH), reaching code-server over the
	// pod-local 127.0.0.1 — robust regardless of the test process's network position.
	if code := dockerEditorHTTPStatus(ctx, t, editorName, "http://127.0.0.1:8080/healthz"); code != "200" {
		t.Errorf("editor /healthz HTTP status = %q, want 200 (the editor must be reachable + serving)", code)
	}
	if code := dockerEditorHTTPStatus(ctx, t, editorName, "http://127.0.0.1:8080/?folder=/workspace"); code != "200" {
		t.Errorf("editor /?folder=/workspace HTTP status = %q, want 200 (the open-folder URL the gateway forms)", code)
	}
	// The CONTAINER-IP endpoint is also reachable from a peer container (the address the gateway's
	// in-cluster equivalent uses) — assert it is well-formed (ip:port) so the helper is exercised.
	if !strings.Contains(editorEndpoint, ":8080") {
		t.Errorf("editor endpoint = %q, want a reachable <ip>:8080", editorEndpoint)
	}

	// (b) The editor sibling SEES the sentinel the workspace wrote — the LIVE worktree is served. The
	// sentinel is seeded through the workspace's own Files seam (the adapter-owned write path onto the
	// shared workdir volume), then read from the editor side to prove the share carries it live.
	const sentinel = "EDITOR-SENTINEL-docker-9c2f1a-do-not-lose"
	if perr := ws.Files().Put(ctx, "/workspace/sentinel.txt", strings.NewReader(sentinel+"\n"), 0o644); perr != nil {
		t.Fatalf("seed sentinel via Files.Put: %v", perr)
	}
	gotSentinel, serr := dockerExecContainer(ctx, editorName, "cat", "/workspace/sentinel.txt")
	if serr != nil {
		t.Fatalf("editor read sentinel: %v (%s)", serr, gotSentinel)
	}
	if !strings.Contains(gotSentinel, sentinel) {
		t.Errorf("editor served worktree does not contain the workspace's sentinel: got %q, want it to contain %q", strings.TrimSpace(gotSentinel), sentinel)
	}

	// (c) READ-ONLY is STRUCTURAL: a write from INSIDE the editor sibling to the shared workdir fails
	// EROFS, while the workspace side stays writable.
	wOut, wErr := dockerExecContainer(ctx, editorName, "sh", "-c", "echo tampered > /workspace/evil.txt")
	if wErr == nil {
		t.Errorf("editor write to a read-only worktree unexpectedly succeeded — the `:ro` share is not enforced (weaken-to-confirm: a rw share makes this succeed)")
	} else if !strings.Contains(wOut, "Read-only file system") {
		t.Errorf("editor write failed but NOT with EROFS: %v (%s); the read-only proof must be the read-only share, not an incidental failure", wErr, wOut)
	}
	// The workspace side stays writable (the agent writes; only the editor is read-only).
	if perr := ws.Files().Put(ctx, "/workspace/second.txt", strings.NewReader("more\n"), 0o644); perr != nil {
		t.Errorf("the workspace must stay writable (only the editor is read-only): %v", perr)
	}

	// (d) Teardown reaps the editor sibling FIRST then the workspace → CountOwned()==0.
	if terr := prov.Teardown(ctx, ws.Handle()); terr != nil {
		t.Fatalf("Teardown: %v", terr)
	}
	if owned, cerr := owner.CountOwned(ctx); cerr != nil {
		t.Errorf("CountOwned: %v", cerr)
	} else if owned != 0 {
		t.Errorf("Teardown left %d orphaned container(s) (the editor sibling must be reaped with the workspace)", owned)
	}
}

// dockerExecContainer runs `docker exec` against a named container and returns the combined output +
// any error. It is how the editor SIBLING is reached (the Connection.Exec port targets the workspace
// container only). Combined output surfaces an EROFS message (on stderr) to the read-only assertion.
func dockerExecContainer(ctx context.Context, container string, command ...string) (string, error) {
	args := append([]string{"exec", container}, command...)
	out, err := exec.CommandContext(ctx, "docker", args...).CombinedOutput() // #nosec G204 -- a test harness driving `docker exec` against an ephemeral container is exec-by-design; args are fixed harness literals + the test's own command, never consumer input.
	return string(out), err
}

// dockerEditorHTTPStatus curls a URL from INSIDE the editor container (which has curl on PATH and
// reaches code-server over its own 127.0.0.1) and returns the HTTP status code string, retrying
// briefly while code-server's listener comes up.
func dockerEditorHTTPStatus(ctx context.Context, t *testing.T, container, url string) string {
	t.Helper()
	deadline := time.Now().Add(60 * time.Second)
	var last string
	for time.Now().Before(deadline) {
		out, err := dockerExecContainer(ctx, container,
			"curl", "-s", "-m", "5", "-o", "/dev/null", "-w", "%{http_code}", url)
		last = strings.TrimSpace(out)
		if err == nil && last == "200" {
			return last
		}
		time.Sleep(2 * time.Second)
	}
	return last
}
