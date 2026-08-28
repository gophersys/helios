package dockeradapter

import (
	"context"

	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/network"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// networkLabel marks every per-workspace egress network this adapter authors so Destroy and
// the test-harness reaper reclaim it alongside the container (no orphaned networks).
const networkLabel = "eden.workspaceprovider/egress-network"

// egressNetworkName derives the DETERMINISTIC docker network name for a workspace's egress
// network from (namespace, name), so Create's network and Destroy's address are byte-identical.
func egressNetworkName(namespace, name string) string {
	return deriveContainerName(namespace, name) + "-egress"
}

// egressMode is what the docker adapter can GENUINELY enforce for a spec's declared egress.
// docker's only robustly-daemon-enforced network isolation is the `--internal` network: it
// installs NO NAT/forwarding for the bridge, so a container on it reaches NOTHING off-host
// (verified: external IPs are "Network is unreachable"). That is real DEFAULT-DENY — but it
// is all-or-nothing: docker cannot selectively allow only api.anthropic.com via the daemon
// API (that needs per-destination iptables rules we do not own). So the HONEST capability is:
//
//   - zero declared egress  → an `--internal` network → genuine default-deny (the clean-room
//     07 §4 posture: "dials out to nothing"). This is what CapEgressPolicy=CapPartial
//     truthfully covers and the conformance suite verifies against the REAL daemon.
//   - declared egress rules → docker cannot provide default-deny + SELECTIVE allow, so the
//     workspace runs on the default bridge (the declared hosts ARE reachable, but so is
//     everything else). This is the PARTIAL gap the manifest declares and the UI flags
//     (C18) — never silently claimed as enforced.
type egressMode uint8

const (
	egressDefaultDeny egressMode = iota // zero declared rules: genuine `--internal` default-deny
	egressUnenforced                    // declared rules present: bridge (Partial — flagged, not enforced)
)

// modeFor reports which egress mode the adapter can genuinely honor for spec.
func modeFor(spec *workspaceprovider.WorkspaceSpec) egressMode {
	if len(spec.Egress) == 0 {
		return egressDefaultDeny
	}
	return egressUnenforced
}

// ensureEgressNetwork creates the per-workspace `--internal` network for the genuine
// default-deny posture and returns its name (the container attaches to it). For the
// unenforced (declared-egress) mode it returns "" so the container uses the default bridge.
// Rollback is the caller's: it removes the network on any later Create failure.
func (a *Adapter) ensureEgressNetwork(ctx context.Context, spec *workspaceprovider.WorkspaceSpec) (string, error) {
	if modeFor(spec) != egressDefaultDeny {
		return "", nil
	}
	name := egressNetworkName(a.namespace, spec.Name)
	// Idempotency: a re-create races a stale same-named network; remove it first so the
	// fresh `--internal` network is the one the container attaches to.
	_ = a.removeEgressNetwork(ctx, name) //nolint:errcheck // best-effort pre-clean; the create below is the authority.
	_, err := a.client.NetworkCreate(ctx, name, network.CreateOptions{
		Driver:   "bridge",
		Internal: true, // the genuine default-deny: no NAT/forwarding → no off-host egress.
		Labels: map[string]string{
			ownerLabel:     "true",
			namespaceLabel: a.namespace,
			networkLabel:   "true",
			nameLabel:      spec.Name,
		},
	})
	if err != nil {
		return "", &workspaceprovider.IsolationError{Detail: "create default-deny egress network: " + err.Error()}
	}
	return name, nil
}

// removeEgressNetwork removes the workspace's egress network by name (idempotent: an
// already-gone network is nil). A container still attached blocks removal, so callers remove
// the container first.
func (a *Adapter) removeEgressNetwork(ctx context.Context, name string) error {
	if name == "" {
		return nil
	}
	if err := a.client.NetworkRemove(ctx, name); err != nil {
		if isNotFound(err) {
			return nil
		}
		return errors.Wrap(errors.KindUnavailable, "dockeradapter: remove egress network", err)
	}
	return nil
}

// networkingFor builds the container's NetworkingConfig for an attached egress network. An
// empty name (the unenforced mode) returns nil so docker uses the default bridge.
func networkingFor(name string) *network.NetworkingConfig {
	if name == "" {
		return nil
	}
	return &network.NetworkingConfig{
		EndpointsConfig: map[string]*network.EndpointSettings{
			name: {},
		},
	}
}

// ownedEgressNetworks lists the egress networks this adapter's namespace authored (for the
// harness reaper's no-orphan-network guarantee).
func (a *Adapter) ownedEgressNetworks(ctx context.Context) ([]string, error) {
	args := filters.NewArgs()
	args.Add("label", networkLabel+"=true")
	if a.namespace != "" {
		args.Add("label", namespaceLabel+"="+a.namespace)
	}
	summaries, err := a.client.NetworkList(ctx, network.ListOptions{Filters: args})
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "dockeradapter: list egress networks", err)
	}
	names := make([]string, 0, len(summaries))
	for i := range summaries {
		names = append(names, summaries[i].Name)
	}
	return names, nil
}
