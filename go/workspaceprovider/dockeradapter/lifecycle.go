package dockeradapter

import (
	"context"
	"io"
	"strings"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/api/types/mount"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// holdCommand keeps the workspace container alive as a long-lived "infra" process the
// library drives Run/Exec/Files/Status over (the pod model on docker). A primary workload
// (Connection.Run) and one-shot commands (Exec) are docker-execs INTO this container.
var holdCommand = []string{"sleep", "infinity"}

// Create provisions the native docker objects for a workspace: it pulls the image (with
// the resolved pull-secret if present), creates a labeled container with the spec's
// mounts/resource-limits/env, and starts it. ROLLBACK is the adapter's obligation: a
// partial failure removes the container so no orphan is left (the all-or-nothing contract,
// 07 §3). It returns a HandleData whose Connection drives the workload plane.
//
//nolint:gocritic // contract §2 fixes Adapter.Create's spec/resolved by value; the port surface is frozen.
func (a *Adapter) Create(ctx context.Context, spec workspaceprovider.WorkspaceSpec, resolved workspaceprovider.Resolved) (workspaceprovider.HandleData, error) {
	workDir := defaultWorkDir(&spec)

	if err := a.pullImage(ctx, &spec, resolved); err != nil {
		return workspaceprovider.HandleData{}, err
	}

	mounts, ensureDirs, isolationErr := buildMounts(&spec)
	if isolationErr != nil {
		return workspaceprovider.HandleData{}, isolationErr
	}

	// Egress: install a genuine default-deny `--internal` network for a zero-egress
	// (clean-room) workspace (the only egress isolation docker robustly enforces); declared
	// egress runs on the bridge (the Partial gap the manifest declares — see network.go).
	egressNet, eerr := a.ensureEgressNetwork(ctx, &spec)
	if eerr != nil {
		return workspaceprovider.HandleData{}, eerr
	}

	createResp, err := a.client.ContainerCreate(
		ctx,
		&container.Config{
			Image:      spec.Image,
			Cmd:        holdCommand,
			Labels:     a.ownerLabels(&spec, workDir),
			Env:        envList(spec.Env),
			WorkingDir: workDir,
		},
		&container.HostConfig{
			Mounts:     mounts,
			Resources:  buildResources(spec.Resources),
			AutoRemove: false,
		},
		networkingFor(egressNet), nil,
		a.containerName(spec.Name),
	)
	if err != nil {
		_ = a.removeEgressNetwork(ctx, egressNet) //nolint:errcheck // best-effort rollback of the just-created egress network; the create error is the one returned.
		return workspaceprovider.HandleData{}, classifyDockerError("create container", err)
	}

	if err := a.client.ContainerStart(ctx, createResp.ID, container.StartOptions{}); err != nil {
		// Rollback: remove the just-created container (then its egress network) so no orphan is left.
		_ = a.client.ContainerRemove(ctx, createResp.ID, container.RemoveOptions{Force: true}) //nolint:errcheck // best-effort rollback; the start error is the one returned.
		_ = a.removeEgressNetwork(ctx, egressNet)                                              //nolint:errcheck // best-effort rollback; the start error is the one returned.
		return workspaceprovider.HandleData{}, classifyDockerError("start container", err)
	}

	// Ensure the workspace's writable directories exist (workdir + read-only inputs roots
	// the Files seam seeds into). A failure here is a partial-isolation failure: roll back.
	if derr := a.ensureDirs(ctx, createResp.ID, ensureDirs); derr != nil {
		_ = a.client.ContainerRemove(ctx, createResp.ID, container.RemoveOptions{Force: true, RemoveVolumes: true}) //nolint:errcheck // best-effort rollback; the ensureDirs error is the one returned.
		_ = a.removeEgressNetwork(ctx, egressNet)                                                                   //nolint:errcheck // best-effort rollback; the ensureDirs error is the one returned.
		return workspaceprovider.HandleData{}, derr
	}

	handle := a.handleFor(&spec, workDir)
	return workspaceprovider.HandleData{
		Handle:     handle,
		Connection: a.connection(createResp.ID, handle),
	}, nil
}

// Dial re-attaches to an existing container by its handle's container id. NotFoundError if
// the container is gone (torn down, evicted, GC'd).
func (a *Adapter) Dial(ctx context.Context, handle workspaceprovider.Handle) (workspaceprovider.HandleData, error) {
	id := containerID(handle)
	if id == "" {
		return workspaceprovider.HandleData{}, &workspaceprovider.NotFoundError{Handle: handle}
	}
	inspect, err := a.client.ContainerInspect(ctx, id)
	if err != nil {
		if isNotFound(err) {
			return workspaceprovider.HandleData{}, &workspaceprovider.NotFoundError{Handle: handle}
		}
		return workspaceprovider.HandleData{}, classifyDockerError("inspect container", err)
	}
	if inspect.ID == "" {
		return workspaceprovider.HandleData{}, &workspaceprovider.NotFoundError{Handle: handle}
	}
	return workspaceprovider.HandleData{
		Handle:     handle,
		Connection: a.connection(id, handle),
	}, nil
}

// List enumerates the containers this adapter authored within its namespace that match the
// selector's labels (the ownership-domain scan, 05 §5). It returns Descriptors (metadata,
// not live handles).
func (a *Adapter) List(ctx context.Context, selector workspaceprovider.Selector) ([]workspaceprovider.Descriptor, error) {
	args := filters.NewArgs()
	args.Add("label", ownerLabel+"=true")
	if a.namespace != "" {
		args.Add("label", namespaceLabel+"="+a.namespace)
	}
	for k, v := range selector.Labels {
		args.Add("label", k+"="+v)
	}
	summaries, err := a.client.ContainerList(ctx, container.ListOptions{All: true, Filters: args})
	if err != nil {
		return nil, classifyDockerError("list containers", err)
	}
	out := make([]workspaceprovider.Descriptor, 0, len(summaries))
	for i := range summaries {
		s := summaries[i]
		workDir := s.Labels[workdirLabel]
		descSpec := descriptorSpec(s.Labels)
		handle := a.handleFor(&descSpec, workDir)
		out = append(out, workspaceprovider.Descriptor{
			Handle:    handle,
			Name:      s.Labels[nameLabel],
			Substrate: workspaceprovider.SubstrateDocker,
			State:     normalizeListState(s.State),
			Labels:    s.Labels,
			CreatedAt: time.Unix(s.Created, 0),
		})
	}
	return out, nil
}

// Destroy removes the container (and its anonymous volumes) named by handle, then its
// per-workspace egress network. IDEMPOTENT: an already-gone container/network is nil, not
// an error. The container is removed FIRST (a still-attached container blocks network
// removal), then the network — so no orphaned network is left.
func (a *Adapter) Destroy(ctx context.Context, handle workspaceprovider.Handle) error {
	id := containerID(handle)
	if id == "" {
		return nil
	}
	err := a.client.ContainerRemove(ctx, id, container.RemoveOptions{Force: true, RemoveVolumes: true})
	if err != nil && !isNotFound(err) {
		return classifyDockerError("remove container", err)
	}
	// removeEgressNetwork returns an already-Kinded (Unavailable) error on a hard failure, nil
	// on success or an already-gone network (idempotent).
	return a.removeEgressNetwork(ctx, egressNetworkName(handle.Namespace(), handle.Name()))
}

// ensureDirs creates the workspace's writable directories (workdir + inputs roots) via a
// single mkdir -p exec, so the Files seam can seed/read them. An empty list is a no-op.
func (a *Adapter) ensureDirs(ctx context.Context, containerID string, dirs []string) error {
	if len(dirs) == 0 {
		return nil
	}
	cmd := append([]string{"mkdir", "-p"}, dirs...)
	execResp, err := a.client.ContainerExecCreate(ctx, containerID, container.ExecOptions{Cmd: cmd})
	if err != nil {
		return &workspaceprovider.IsolationError{Detail: "create workspace directories: " + err.Error()}
	}
	attach, err := a.client.ContainerExecAttach(ctx, execResp.ID, container.ExecAttachOptions{})
	if err != nil {
		return &workspaceprovider.IsolationError{Detail: "create workspace directories: " + err.Error()}
	}
	_, _ = io.Copy(io.Discard, attach.Reader) //nolint:errcheck // draining mkdir output; its success is asserted by a later Files op, not here.
	attach.Close()
	return nil
}

// pullImage pulls spec.Image, using the resolved pull-secret as a registry credential when
// present (the credential seam — the adapter injects, never resolves). A pre-pulled image
// is skipped. An unpullable image is an ImageError carrying the ref, never the value.
//
//nolint:gocritic // resolved mirrors the frozen Resolved seam; spec is pointer-passed below at the call site.
func (a *Adapter) pullImage(ctx context.Context, spec *workspaceprovider.WorkspaceSpec, resolved workspaceprovider.Resolved) error {
	if a.prePulled[spec.Image] || a.imagePresent(ctx, spec.Image) {
		return nil
	}
	opts := image.PullOptions{}
	if resolved.PullSecret != nil {
		auth, aerr := registryAuth(resolved.PullSecret)
		if aerr != nil {
			return &workspaceprovider.ImageError{Image: spec.Image, Ref: spec.ImagePull}
		}
		opts.RegistryAuth = auth
	}
	rc, err := a.client.ImagePull(ctx, spec.Image, opts)
	if err != nil {
		return &workspaceprovider.ImageError{Image: spec.Image, Ref: spec.ImagePull}
	}
	defer func() { _ = rc.Close() }() //nolint:errcheck // closing a fully-drained pull stream has no actionable error.
	// Draining the pull stream is what blocks until the pull completes (or fails).
	if _, derr := io.Copy(io.Discard, rc); derr != nil {
		return &workspaceprovider.ImageError{Image: spec.Image, Ref: spec.ImagePull}
	}
	return nil
}

// imagePresent reports whether spec.Image is already on the daemon (so a re-provision /
// pre-pulled image skips the network pull and the test stays offline-safe).
func (a *Adapter) imagePresent(ctx context.Context, ref string) bool {
	args := filters.NewArgs()
	args.Add("reference", ref)
	summaries, err := a.client.ImageList(ctx, image.ListOptions{Filters: args})
	return err == nil && len(summaries) > 0
}

// buildMounts maps the spec's Mounts onto docker mounts, returning the docker mounts and
// the directory targets the adapter must create after start (source-less workdirs/inputs
// that live in the container's writable layer, NOT a tmpfs — a tmpfs masks CopyToContainer,
// so the Files seam could not seed/read them). A MountVolume docker cannot honor for the
// declared isolation is an IsolationError (fail-closed, never a degraded success).
func buildMounts(spec *workspaceprovider.WorkspaceSpec) ([]mount.Mount, []string, error) {
	var mounts []mount.Mount
	var ensureDirs []string
	for i := range spec.Mounts {
		m := spec.Mounts[i]
		switch m.Kind {
		case workspaceprovider.MountBind:
			if m.Source == "" {
				// A bind with no host source is the workspace's own writable workdir — a
				// plain directory in the container's writable layer (so the Files tar
				// plane can read/write it; a tmpfs would mask CopyToContainer).
				ensureDirs = append(ensureDirs, m.Target)
				continue
			}
			mounts = append(mounts, mount.Mount{Type: mount.TypeBind, Source: m.Source, Target: m.Target, ReadOnly: m.ReadOnly})
		case workspaceprovider.MountInputs:
			// A read-only inputs volume seeded via Files.Put: a plain directory the LIBRARY
			// marks read-only at the Files seam (07 §4). It is NOT a tmpfs (which would mask
			// the seed) and NOT a docker-read-only mount (which would block the seed itself).
			ensureDirs = append(ensureDirs, m.Target)
		case workspaceprovider.MountTmpfs, workspaceprovider.MountSecret:
			// An in-memory scratch / credential vehicle: a genuine tmpfs so it never hits
			// an image layer (07 §2). The resolved secret material is written by the
			// connection at Run time.
			mounts = append(mounts, mount.Mount{Type: mount.TypeTmpfs, Target: m.Target})
		case workspaceprovider.MountVolume:
			return nil, nil, &workspaceprovider.IsolationError{Detail: "docker substrate declares CapPersistentVolume absent; MountVolume is unsupported"}
		default:
			return nil, nil, &workspaceprovider.IsolationError{Detail: "unknown mount kind"}
		}
	}
	return mounts, ensureDirs, nil
}

// buildResources maps the spec's Resources onto docker cgroup limits (CapResourceLimits).
func buildResources(r workspaceprovider.Resources) container.Resources {
	res := container.Resources{}
	if r.CPUMilli > 0 {
		res.NanoCPUs = r.CPUMilli * 1_000_000 // milli-cores -> nano-cores
	}
	if r.MemoryBytes > 0 {
		res.Memory = r.MemoryBytes
	}
	if r.PIDs > 0 {
		pids := r.PIDs
		res.PidsLimit = &pids
	}
	return res
}

// envList renders NON-secret EnvVars into docker's "K=V" list.
func envList(env []workspaceprovider.EnvVar) []string {
	out := make([]string, 0, len(env))
	for _, e := range env {
		out = append(out, e.Name+"="+e.Value)
	}
	return out
}

// defaultWorkDir picks the harness workdir: the first Bind/Inputs mount target, else
// "/workspace".
func defaultWorkDir(spec *workspaceprovider.WorkspaceSpec) string {
	for i := range spec.Mounts {
		if spec.Mounts[i].Kind == workspaceprovider.MountBind || spec.Mounts[i].Kind == workspaceprovider.MountInputs {
			return spec.Mounts[i].Target
		}
	}
	return "/workspace"
}

// descriptorSpec reconstructs the minimal spec a List entry needs to re-derive a Handle
// from its container labels.
func descriptorSpec(labels map[string]string) workspaceprovider.WorkspaceSpec {
	return workspaceprovider.WorkspaceSpec{
		Name: labels[nameLabel],
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: labels[orgLabel],
			workspaceprovider.LabelProject:      labels[projectLabel],
		},
	}
}

// normalizeListState maps docker's coarse container state string onto a workspaceprovider
// State for List Descriptors.
func normalizeListState(state string) workspaceprovider.State {
	switch strings.ToLower(state) {
	case "running":
		return workspaceprovider.StateRunning
	case "created":
		return workspaceprovider.StateProvisioning
	case "exited", "dead", "removing":
		return workspaceprovider.StateGone
	default:
		return workspaceprovider.StateReady
	}
}

// classifyDockerError maps a docker SDK error onto a typed workspaceprovider error. A
// not-found is a NotFoundError; everything else from the daemon is a
// SubstrateUnavailableError (the one retryable signal). The op names the failing call.
func classifyDockerError(op string, err error) error {
	if isNotFound(err) {
		return &workspaceprovider.NotFoundError{}
	}
	return &workspaceprovider.SubstrateUnavailableError{Substrate: workspaceprovider.SubstrateDocker, Op: op}
}

// isNotFound reports whether err is a docker "no such container/image" 404.
func isNotFound(err error) bool {
	if err == nil {
		return false
	}
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "no such container") ||
		strings.Contains(msg, "no such image") ||
		strings.Contains(msg, "not found") ||
		strings.Contains(msg, "could not find the file") ||
		strings.Contains(msg, "no such file")
}
