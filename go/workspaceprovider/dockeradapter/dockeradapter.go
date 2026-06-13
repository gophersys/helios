// Package dockeradapter is the workspaceprovider Adapter for the docker daemon — the ONLY
// place the Docker SDK is imported (05 §1). It realizes the one WorkspaceSpec vocabulary on
// docker primitives: a workspace is a long-lived container (a sleep-holding "infra"
// process) the library drives Run/Exec/Files/Status over; mounts become bind mounts /
// tmpfs; Resources become cgroup limits; egress becomes recorded firewall intent (docker's
// default-deny is CapPartial — see Manifest). It translates docker's native objects ↔ the
// workspaceprovider vocabulary and owns rollback on partial failure; the LIBRARY owns Handle
// assignment, idempotency, the state machine, status normalization, and secret-resolution
// timing.
package dockeradapter

import (
	"strings"

	"github.com/docker/docker/client"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// ownerLabel marks every container/volume this adapter authors so List/Destroy scan
// exactly the ownership domain (05 §5) and the ephemeral test harness reaps zero orphans.
const (
	ownerLabel     = "eden.workspaceprovider"
	namespaceLabel = "eden.namespace"
	nameLabel      = "eden.name"
	orgLabel       = "eden.org"
	projectLabel   = "eden.project"
	workdirLabel   = "eden.workdir"
)

// Config is the docker adapter's immutable construction input (the configuration pattern).
// It is parsed at the edge and frozen; New reads no env and dials no daemon.
type Config struct {
	// Host overrides the docker daemon endpoint (empty == the SDK's FromEnv default:
	// DOCKER_HOST else the local socket). The central/local/BYO posture sets this at the
	// composition root.
	Host string
	// LabelNamespace scopes the ownership domain (the eden.namespace label value); empty
	// for single-tenant local.
	LabelNamespace string
}

// Adapter is the docker workspaceprovider.Adapter. It holds a live docker client (created
// at New) and the ownership-domain namespace. Safe for concurrent use (the docker client
// is). Construct via New.
type Adapter struct {
	client    dockerClient
	namespace string
	prePulled map[string]bool
}

// Static assertion: *Adapter satisfies the workspaceprovider.Adapter port.
var _ workspaceprovider.Adapter = (*Adapter)(nil)

// New constructs the docker Adapter. It creates the docker client with API-version
// negotiation (the one piece of edge wiring the SDK requires) but performs NO daemon I/O —
// the first daemon call happens at Create/Dial/List/Destroy. It returns a wrapped
// SubstrateUnavailableError if the client cannot even be constructed.
func New(configuration Config) (*Adapter, error) {
	opts := []client.Opt{client.FromEnv, client.WithAPIVersionNegotiation()}
	if configuration.Host != "" {
		opts = append(opts, client.WithHost(configuration.Host))
	}
	cli, err := client.NewClientWithOpts(opts...)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "dockeradapter.New: construct docker client", err)
	}
	return &Adapter{
		client:    cli,
		namespace: configuration.LabelNamespace,
		prePulled: map[string]bool{},
	}, nil
}

// Manifest declares the docker substrate's capabilities (05 §3). docker has full bind
// mounts, resource limits (cgroups), PTY exec, log streaming, and re-attach (a container
// survives a control-plane restart); CapMultiTenant/CapPersistentVolume/CapHibernate are
// CapAbsent (no native quota plane / persistent-volume plane).
//
// CapEgressPolicy is CapPartial, and the Partial is TRUTHFUL, not a placeholder: a
// zero-egress workspace is attached to a per-workspace `--internal` docker network, which
// the daemon enforces as genuine DEFAULT-DENY (no NAT/forwarding → off-host dial-out is
// "Network is unreachable") — the clean-room 07 §4 posture, verified against the REAL daemon
// by the conformance suite's egress case. What docker CANNOT do via the daemon API is
// default-deny + SELECTIVE allow (allow only api.anthropic.com): an `--internal` bridge is
// all-or-nothing, so a workspace that DECLARES egress rules runs on the default bridge (its
// declared hosts are reachable, but so is everything else). That residual gap is exactly what
// CapPartial declares and the engine/UI flag (C18) — never silently claimed as enforced.
// (kubernetesadapter keeps CapEgressPolicy=CapAbsent: k3d/kind ship flannel, which does not
// enforce NetworkPolicy — the honest divergence the conformance case Skips on.)
func (a *Adapter) Manifest() workspaceprovider.CapabilityManifest {
	return workspaceprovider.CapabilityManifest{
		Distro: "docker 29.x",
		Capabilities: map[workspaceprovider.Capability]workspaceprovider.CapStatus{
			workspaceprovider.CapExecPTY:          workspaceprovider.CapFull,
			workspaceprovider.CapBindMount:        workspaceprovider.CapFull,
			workspaceprovider.CapResourceLimits:   workspaceprovider.CapFull,
			workspaceprovider.CapLogStream:        workspaceprovider.CapFull,
			workspaceprovider.CapReattach:         workspaceprovider.CapFull,
			workspaceprovider.CapEgressPolicy:     workspaceprovider.CapPartial,
			workspaceprovider.CapPersistentVolume: workspaceprovider.CapAbsent,
			workspaceprovider.CapMultiTenant:      workspaceprovider.CapAbsent,
			workspaceprovider.CapHibernate:        workspaceprovider.CapAbsent,
		},
	}
}

// ownerLabels builds the label set every authored container carries.
func (a *Adapter) ownerLabels(spec *workspaceprovider.WorkspaceSpec, workDir string) map[string]string {
	labels := map[string]string{
		ownerLabel:     "true",
		namespaceLabel: a.namespace,
		nameLabel:      spec.Name,
		workdirLabel:   workDir,
	}
	if org := spec.Labels[workspaceprovider.LabelOrganization]; org != "" {
		labels[orgLabel] = org
	}
	if proj := spec.Labels[workspaceprovider.LabelProject]; proj != "" {
		labels[projectLabel] = proj
	}
	// Carry through the caller's ownership-domain labels too (so List by them works).
	for k, v := range spec.Labels {
		if _, taken := labels[k]; !taken {
			labels[k] = v
		}
	}
	return labels
}

// containerName derives the docker container name for a workspace within this namespace.
// docker names must match [a-zA-Z0-9][a-zA-Z0-9_.-]+. It shares deriveContainerName with
// containerID so Create's name and Dial/Destroy's address are byte-identical.
func (a *Adapter) containerName(name string) string {
	return deriveContainerName(a.namespace, name)
}

// deriveContainerName is the single source of a workspace's deterministic docker container
// name from (namespace, name). Both Create (via the adapter's own namespace) and Dial/
// Destroy (via the Handle's namespace) call it, so the native address round-trips exactly.
func deriveContainerName(namespace, name string) string {
	base := "eden"
	if namespace != "" {
		base += "-" + namespace
	}
	return SanitizeNamespace(base + "-" + name)
}

// SanitizeNamespace makes s a valid docker name/label-value fragment: lowercase, only
// [a-z0-9_.-], collapsing other runs to a single '-'. Exported so the test harness derives
// a collision-proof per-test namespace from a test name.
func SanitizeNamespace(s string) string {
	var b strings.Builder
	prevDash := false
	for _, r := range strings.ToLower(s) {
		switch {
		case (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '.' || r == '_':
			b.WriteRune(r)
			prevDash = false
		default:
			if !prevDash {
				b.WriteByte('-')
				prevDash = true
			}
		}
	}
	out := strings.Trim(b.String(), "-._")
	if out == "" {
		return "eden"
	}
	return out
}

// IsDaemonUnavailable reports whether err signals an unreachable docker daemon (so the
// real-substrate harness can Skip rather than Fail on a machine without docker).
func IsDaemonUnavailable(err error) bool {
	if err == nil {
		return false
	}
	if errors.KindOf(err) == errors.KindUnavailable {
		return true
	}
	if client.IsErrConnectionFailed(err) {
		return true
	}
	msg := err.Error()
	return strings.Contains(msg, "Cannot connect to the Docker daemon") ||
		strings.Contains(msg, "connection refused") ||
		strings.Contains(msg, "no such host")
}
