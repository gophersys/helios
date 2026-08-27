package dockeradapter

import (
	"context"
	"strconv"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/go-connections/nat"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// editorLabel marks every read-only editor sibling container this adapter authors (ADR-0027) so
// the ownership scan + the harness reaper see it, in addition to the shared ownerLabel.
const editorLabel = "eden.workspaceprovider/editor"

// defaultEditorImage / defaultEditorPort are the adapter defaults a zero EditorSpec field
// substitutes (an explicit Image/Port on the spec overrides them). code-server serves VS Code in
// the browser; 8080 is its conventional bind port.
const (
	defaultEditorImage = "codercom/code-server:latest"
	defaultEditorPort  = 8080
	maxPort            = 65535
)

// editorContainerName derives the DETERMINISTIC docker name of a workspace's read-only editor
// sibling from (namespace, name), so Create's sibling and Destroy's address are byte-identical
// (the namespace already scopes the workspace 1:1, so a constant "-editor" suffix is unambiguous).
func editorContainerName(namespace, name string) string {
	return deriveContainerName(namespace, name) + "-editor"
}

// editorPort resolves the editor's served/published port: the spec's Port when in (0, maxPort],
// else the adapter default. It is the single source the container port and the publish binding
// agree on.
func editorPort(editor *workspaceprovider.EditorSpec) int {
	if editor != nil && editor.Port > 0 && editor.Port <= maxPort {
		return editor.Port
	}
	return defaultEditorPort
}

// startEditorSibling creates+starts the read-only editor sibling for spec when spec.Editor is set,
// then inspects it to read the published host port and returns the editor's externally-reachable
// origin ("http://127.0.0.1:<host-port>"). It shares the workspace container's workdir volume
// READ-ONLY via `--volumes-from <workspace-container>:ro` (the docker analog of the kubernetes
// read-only volumeMount — read-only is STRUCTURAL: the sibling cannot write the worktree) and
// publishes the editor's container port to an ephemeral host port (docker assigns it; the inspect
// reads it back) — this is the docker adapter's FIRST port-publish path. A nil Editor returns ""
// (no sibling): the workspace is byte-identical.
func (a *Adapter) startEditorSibling(ctx context.Context, spec *workspaceprovider.WorkspaceSpec, workspaceID string) (string, error) {
	if spec.Editor == nil {
		return "", nil
	}
	workDir := defaultWorkDir(spec)
	port := editorPort(spec.Editor)
	image := spec.Editor.Image
	if image == "" {
		image = defaultEditorImage
	}
	containerPort, perr := nat.NewPort("tcp", strconv.Itoa(port))
	if perr != nil {
		return "", &workspaceprovider.IsolationError{Detail: "editor sibling: bad port: " + perr.Error()}
	}

	name := editorContainerName(a.namespace, spec.Name)
	createResp, err := a.client.ContainerCreate(
		ctx,
		&container.Config{
			Image: image,
			// code-server with auth disabled (the read-only editor carries no credential — access
			// is gated by the published origin, not a code-server password), bound on all
			// interfaces so the published port reaches it, serving the read-only worktree.
			Cmd:          []string{"--auth", "none", "--bind-addr", "0.0.0.0:" + strconv.Itoa(port), workDir},
			WorkingDir:   workDir,
			ExposedPorts: nat.PortSet{containerPort: struct{}{}},
			Labels:       a.editorLabels(spec, workDir),
		},
		&container.HostConfig{
			// Share the workspace's workdir volume READ-ONLY: the editor process cannot write it.
			VolumesFrom: []string{workspaceID + ":ro"},
			// Publish the editor port to an ephemeral host port (empty HostPort == docker picks).
			PortBindings: nat.PortMap{containerPort: []nat.PortBinding{{HostIP: "127.0.0.1", HostPort: ""}}},
			AutoRemove:   false,
		},
		nil, nil, name,
	)
	if err != nil {
		return "", &workspaceprovider.IsolationError{Detail: "editor sibling: create: " + err.Error()}
	}
	if serr := a.client.ContainerStart(ctx, createResp.ID, container.StartOptions{}); serr != nil {
		_ = a.client.ContainerRemove(ctx, createResp.ID, container.RemoveOptions{Force: true}) //nolint:errcheck // best-effort rollback; the start error is the one returned.
		return "", &workspaceprovider.IsolationError{Detail: "editor sibling: start: " + serr.Error()}
	}

	origin, oerr := a.editorOrigin(ctx, createResp.ID, containerPort)
	if oerr != nil {
		return "", oerr
	}
	return origin, nil
}

// editorOrigin inspects the started editor sibling to read the host port docker published its
// editor port to, and forms the externally-reachable origin "http://127.0.0.1:<host-port>". A
// missing binding is an IsolationError (the publish did not take — fail-closed rather than return a
// workspace whose editor is unreachable).
func (a *Adapter) editorOrigin(ctx context.Context, editorID string, containerPort nat.Port) (string, error) {
	inspect, err := a.client.ContainerInspect(ctx, editorID)
	if err != nil {
		return "", classifyDockerError("inspect editor sibling", err)
	}
	if inspect.NetworkSettings == nil {
		return "", &workspaceprovider.IsolationError{Detail: "editor sibling: no network settings (publish did not take)"}
	}
	bindings := inspect.NetworkSettings.Ports[containerPort]
	if len(bindings) == 0 || bindings[0].HostPort == "" {
		return "", &workspaceprovider.IsolationError{Detail: "editor sibling: editor port was not published"}
	}
	return "http://127.0.0.1:" + bindings[0].HostPort, nil
}

// editorLabels builds the label set the editor sibling carries: the shared ownership labels (so
// List/CountOwned/the reaper see it) plus the editor marker.
func (a *Adapter) editorLabels(spec *workspaceprovider.WorkspaceSpec, workDir string) map[string]string {
	labels := a.ownerLabels(spec, workDir)
	labels[editorLabel] = "true"
	return labels
}

// removeEditorSibling removes the editor sibling for spec by its deterministic name (idempotent —
// an absent sibling, e.g. a nil-Editor workspace, is a no-op). Used by Create's rollback.
func (a *Adapter) removeEditorSibling(ctx context.Context, spec *workspaceprovider.WorkspaceSpec) error {
	return a.removeEditorByName(ctx, editorContainerName(a.namespace, spec.Name))
}

// removeEditorByName removes the editor sibling container by name (idempotent: an already-gone /
// never-created sibling is nil). It removes any volumes the sibling owns of its own (it owns none —
// the shared workdir volume belongs to the workspace container and is reaped with it).
func (a *Adapter) removeEditorByName(ctx context.Context, name string) error {
	if err := a.client.ContainerRemove(ctx, name, container.RemoveOptions{Force: true}); err != nil && !isNotFound(err) {
		return classifyDockerError("remove editor sibling", err)
	}
	return nil
}
