package dockeradapter

import (
	"context"
	"io"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/image"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// EphemeralDaemonConfig configures the throwaway, isolated docker context the real-substrate test
// harness spins. LabelNamespace scopes a dedicated ownership domain so the Cleanup reaps
// exactly what this run created (and nothing a parallel run did); PrePullImages warms the
// image cache so per-test provisions are fast and offline-safe.
type EphemeralDaemonConfig struct {
	LabelNamespace string
	PrePullImages  []string
}

// NewEphemeral builds a docker Adapter bound to the local daemon under a dedicated label
// namespace, pings the daemon to confirm it is reachable (returning a
// SubstrateUnavailableError the harness maps to a Skip when it is not), pre-pulls the
// requested images, and returns the Adapter plus a cleanup that force-removes every
// container the namespace authored (the C23 forced-teardown discipline — it runs on
// failure too, deletes on a unique namespace so parallel/abandoned runs never collide).
func NewEphemeral(ctx context.Context, configuration EphemeralDaemonConfig) (*Adapter, func() error, error) {
	adapter, err := New(Config{LabelNamespace: configuration.LabelNamespace})
	if err != nil {
		return nil, nil, err
	}
	if _, perr := adapter.client.Ping(ctx); perr != nil {
		_ = adapter.client.Close() //nolint:errcheck // closing a client we are discarding on a ping failure has no actionable error.
		return nil, nil, errors.Wrap(errors.KindUnavailable, "dockeradapter.NewEphemeral: ping docker daemon", perr)
	}
	for _, ref := range configuration.PrePullImages {
		if pErr := adapter.prePull(ctx, ref); pErr != nil {
			_ = adapter.client.Close() //nolint:errcheck // closing a client we are discarding on a pre-pull failure has no actionable error.
			return nil, nil, pErr
		}
	}
	cleanup := func() error {
		return adapter.reapNamespace(context.WithoutCancel(ctx))
	}
	return adapter, cleanup, nil
}

// prePull pulls ref into the daemon cache and marks it pre-pulled so a later Create skips
// the network pull.
func (a *Adapter) prePull(ctx context.Context, ref string) error {
	if a.imagePresent(ctx, ref) {
		a.prePulled[ref] = true
		return nil
	}
	rc, err := a.client.ImagePull(ctx, ref, image.PullOptions{})
	if err != nil {
		return &workspaceprovider.ImageError{Image: ref}
	}
	defer func() { _ = rc.Close() }() //nolint:errcheck // closing a fully-drained pull stream has no actionable error.
	if _, derr := io.Copy(io.Discard, rc); derr != nil {
		return &workspaceprovider.ImageError{Image: ref}
	}
	a.prePulled[ref] = true
	return nil
}

// reapNamespace force-removes every container AND every per-workspace egress network this
// adapter's namespace authored — the Cleanup that guarantees zero orphans (containers first,
// then networks, since a still-attached container blocks network removal). It also closes
// the docker client.
func (a *Adapter) reapNamespace(ctx context.Context) error {
	defer func() { _ = a.client.Close() }() //nolint:errcheck // closing the client after reaping has no actionable error.
	args := filters.NewArgs()
	args.Add("label", ownerLabel+"=true")
	if a.namespace != "" {
		args.Add("label", namespaceLabel+"="+a.namespace)
	}
	summaries, err := a.client.ContainerList(ctx, container.ListOptions{All: true, Filters: args})
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "dockeradapter.reapNamespace: list", err)
	}
	var reapErr error
	for i := range summaries {
		if rmErr := a.client.ContainerRemove(ctx, summaries[i].ID, container.RemoveOptions{Force: true, RemoveVolumes: true}); rmErr != nil && !isNotFound(rmErr) {
			reapErr = errors.Wrap(errors.KindUnavailable, "dockeradapter.reapNamespace: remove "+summaries[i].ID, rmErr)
		}
	}
	networks, nerr := a.ownedEgressNetworks(ctx)
	if nerr != nil {
		return errors.Wrap(errors.KindUnavailable, "dockeradapter.reapNamespace: list networks", nerr)
	}
	for _, name := range networks {
		if rmErr := a.removeEgressNetwork(ctx, name); rmErr != nil {
			reapErr = errors.Wrap(errors.KindUnavailable, "dockeradapter.reapNamespace: remove network "+name, rmErr)
		}
	}
	return reapErr
}

// RemoveImageForTest force-removes a locally-cached image so the next pull must hit the registry
// (the B7 pull-secret test purges the just-pulled private image before the WITHOUT-secret pull,
// so the daemon cannot serve the cached layer and mask the denial). It also clears the
// pre-pulled marker. Test-support only.
func (a *Adapter) RemoveImageForTest(ctx context.Context, ref string) error {
	delete(a.prePulled, ref)
	if _, err := a.client.ImageRemove(ctx, ref, image.RemoveOptions{Force: true, PruneChildren: true}); err != nil {
		return classifyDockerError("remove image", err)
	}
	return nil
}

// CountOwned reports how many containers this adapter's namespace currently owns — the
// harness's orphan re-scan asserts this is zero after Teardown (the C23 leak check).
func (a *Adapter) CountOwned(ctx context.Context) (int, error) {
	args := filters.NewArgs()
	args.Add("label", ownerLabel+"=true")
	if a.namespace != "" {
		args.Add("label", namespaceLabel+"="+a.namespace)
	}
	summaries, err := a.client.ContainerList(ctx, container.ListOptions{All: true, Filters: args})
	if err != nil {
		return 0, classifyDockerError("count owned", err)
	}
	return len(summaries), nil
}

// ContainerEnvForTest returns the hold container's PERSISTED environment (ContainerInspect's
// Config.Env) for the workspace named by handle. The real-injection canary scan (finding #4) asserts
// a VehicleEnv workload credential never lands here — the value rides the TRANSIENT exec child, not
// the long-lived container's env — so a leak into Config.Env is a redaction failure. Test-support
// only.
func (a *Adapter) ContainerEnvForTest(ctx context.Context, handle workspaceprovider.Handle) ([]string, error) {
	inspect, err := a.client.ContainerInspect(ctx, containerID(handle))
	if err != nil {
		return nil, classifyDockerError("inspect container env", err)
	}
	if inspect.Config == nil {
		return nil, nil
	}
	return inspect.Config.Env, nil
}
