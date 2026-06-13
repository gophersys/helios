package workspaceprovidertest

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// clusterTimeout bounds an ephemeral cluster's create/ready handshake (image pull + node boot).
// A k3d/kind cluster boots in well under this on a warm docker daemon; the ceiling exists so a
// wedged create rolls back rather than hanging the suite.
const clusterTimeout = 4 * time.Minute

// ephemeralCluster is a live, throwaway local kubernetes cluster (k3d or kind) the harness stood
// up for ONE conformance run: Name is the unique cluster name (eden-wp-<tool>-<ts>-<rand>) so
// parallel/abandoned runs never collide; Kubeconfig is the path to its ISOLATED kubeconfig file
// (the user's ~/.kube/config is never touched); Distro is the truthful manifest identity; delete
// tears the WHOLE cluster down (a leaked cluster is unacceptable — C23).
type ephemeralCluster struct {
	Name       string
	Kubeconfig string
	Distro     string
	delete     func() error
}

// k3dAvailable reports whether the k3d and docker binaries are both on PATH (so the harness
// Skips rather than Fails on a machine without them).
func k3dAvailable() bool { return onPath("k3d") && onPath("docker") }

// kindAvailable reports whether the kind and docker binaries are both on PATH.
func kindAvailable() bool { return onPath("kind") && onPath("docker") }

// onPath reports whether bin resolves on PATH.
func onPath(bin string) bool {
	_, err := exec.LookPath(bin)
	return err == nil
}

// uniqueClusterName derives a collision-proof, RFC-1123-valid cluster name from a tool tag, a
// unix-nanos remainder, and 4 random bytes (eden-wp-<tool>-<ts>-<rand>). k3d/kind require a
// short DNS-label-safe name, which this is by construction (C23 unique-suffix discipline).
func uniqueClusterName(tool string) string {
	var b [4]byte
	_, _ = rand.Read(b[:]) //nolint:errcheck // crypto/rand.Read never short-reads on these platforms; a zero suffix is still usable.
	return "eden-wp-" + tool + "-" + time.Now().Format("150405") + "-" + hex.EncodeToString(b[:])
}

// createK3dCluster stands up an ephemeral k3d cluster (k3s-in-docker — the DEFAULT distro,
// ADR-0016 §4) and returns it with a delete closure that removes the WHOLE cluster (the C23
// forced-teardown discipline). It disables traefik + metrics-server + the load balancer (none
// are needed for workspace pods) so the boot is fast, --wait blocks until the server is Ready,
// and the kubeconfig lands in an ISOLATED file (NOT the default ~/.kube/config). The requested
// images are pre-imported so per-test pod provisions are fast and offline-safe.
func createK3dCluster(ctx context.Context, images []string) (*ephemeralCluster, error) {
	name := uniqueClusterName("k3d")
	kubeconfig, err := tempKubeconfig(name)
	if err != nil {
		return nil, err
	}
	cleanup := func() error { return deleteK3dCluster(name, kubeconfig) }

	createCtx, cancel := context.WithTimeout(ctx, clusterTimeout)
	defer cancel()
	if out, cerr := runCommand(
		createCtx,
		"k3d", "cluster", "create", name,
		"--no-lb",
		"--wait",
		"--timeout", clusterTimeout.String(),
		"--kubeconfig-update-default=false",
		"--kubeconfig-switch-context=false",
		"--k3s-arg", "--disable=traefik@server:0",
		"--k3s-arg", "--disable=metrics-server@server:0",
	); cerr != nil {
		_ = cleanup() //nolint:errcheck // best-effort rollback of a partial create; the create error is the one returned.
		return nil, errors.Wrap(errors.KindUnavailable, "k3d cluster create: "+out, cerr)
	}
	if out, kerr := runCommand(createCtx, "k3d", "kubeconfig", "get", name); kerr != nil {
		_ = cleanup() //nolint:errcheck // best-effort rollback; the kubeconfig error is the one returned.
		return nil, errors.Wrap(errors.KindUnavailable, "k3d kubeconfig get", kerr)
	} else if werr := os.WriteFile(kubeconfig, []byte(out), 0o600); werr != nil {
		_ = cleanup() //nolint:errcheck // best-effort rollback; the write error is the one returned.
		return nil, errors.Wrap(errors.KindInternal, "write k3d kubeconfig", werr)
	}
	importImages(createCtx, images, func(refs []string) (string, error) {
		args := append([]string{"image", "import", "--cluster", name}, refs...)
		return runCommand(createCtx, "k3d", args...)
	})
	return &ephemeralCluster{Name: name, Kubeconfig: kubeconfig, Distro: "k3d " + toolVersion(ctx, "k3d") + " / k3s", delete: cleanup}, nil
}

// createKindCluster stands up an ephemeral kind cluster (the SECOND conformance target,
// ADR-0016 §4) with an isolated kubeconfig and an image pre-load, returning a delete closure
// that removes the WHOLE cluster.
func createKindCluster(ctx context.Context, images []string) (*ephemeralCluster, error) {
	name := uniqueClusterName("kind")
	kubeconfig, err := tempKubeconfig(name)
	if err != nil {
		return nil, err
	}
	cleanup := func() error { return deleteKindCluster(name, kubeconfig) }

	createCtx, cancel := context.WithTimeout(ctx, clusterTimeout)
	defer cancel()
	if out, cerr := runCommand(
		createCtx,
		"kind", "create", "cluster",
		"--name", name,
		"--kubeconfig", kubeconfig,
		"--wait", clusterTimeout.String(),
	); cerr != nil {
		_ = cleanup() //nolint:errcheck // best-effort rollback; the create error is the one returned.
		return nil, errors.Wrap(errors.KindUnavailable, "kind create cluster: "+out, cerr)
	}
	importImages(createCtx, images, func(refs []string) (string, error) {
		var lastOut string
		for _, ref := range refs {
			out, lerr := runCommand(createCtx, "kind", "load", "docker-image", ref, "--name", name)
			if lerr != nil {
				return out, lerr
			}
			lastOut = out
		}
		return lastOut, nil
	})
	return &ephemeralCluster{Name: name, Kubeconfig: kubeconfig, Distro: "kind " + toolVersion(ctx, "kind"), delete: cleanup}, nil
}

// importImages pulls each image on the host then hands the present set to the distro loader. It
// is best-effort: a cluster can still pull an image from the network at pod-create, so a missing
// import only slows the first provision (offline-only environments lose the fallback, which the
// suite tolerates by skipping on an unpullable image at Provision).
func importImages(ctx context.Context, images []string, load func(refs []string) (string, error)) {
	if len(images) == 0 {
		return
	}
	var present []string
	for _, ref := range images {
		if _, perr := runCommand(ctx, "docker", "pull", ref); perr == nil {
			present = append(present, ref)
		}
	}
	if len(present) > 0 {
		_, _ = load(present) //nolint:errcheck // best-effort image import; the cluster falls back to a network pull at pod-create.
	}
}

// deleteK3dCluster removes the whole k3d cluster and its isolated kubeconfig dir. IDEMPOTENT: an
// already-gone cluster is not an error.
func deleteK3dCluster(name, kubeconfig string) error {
	out, err := runCommand(context.Background(), "k3d", "cluster", "delete", name)
	removeKubeconfig(kubeconfig)
	if err != nil && !strings.Contains(strings.ToLower(out), "no clusters found") {
		return errors.Wrap(errors.KindUnavailable, "k3d cluster delete: "+out, err)
	}
	return nil
}

// deleteKindCluster removes the whole kind cluster and its isolated kubeconfig dir. IDEMPOTENT.
func deleteKindCluster(name, kubeconfig string) error {
	out, err := runCommand(context.Background(), "kind", "delete", "cluster", "--name", name, "--kubeconfig", kubeconfig)
	removeKubeconfig(kubeconfig)
	if err != nil && !strings.Contains(strings.ToLower(out), "unknown cluster") {
		return errors.Wrap(errors.KindUnavailable, "kind delete cluster: "+out, err)
	}
	return nil
}

// tempKubeconfig returns an isolated kubeconfig path for a cluster (in a fresh temp dir, named
// by the cluster) so a test NEVER mutates the developer's ~/.kube/config.
func tempKubeconfig(name string) (string, error) {
	dir, err := os.MkdirTemp("", "eden-wp-kubeconfig-")
	if err != nil {
		return "", errors.Wrap(errors.KindInternal, "create kubeconfig temp dir", err)
	}
	return filepath.Join(dir, name+".yaml"), nil
}

// removeKubeconfig deletes the isolated kubeconfig file + its temp dir (best-effort).
func removeKubeconfig(kubeconfig string) {
	if kubeconfig == "" {
		return
	}
	_ = os.RemoveAll(filepath.Dir(kubeconfig)) //nolint:errcheck // best-effort temp-dir cleanup; a leftover temp file is harmless.
}

// runCommand runs bin with args, returning the combined output (for diagnostics) and any error.
func runCommand(ctx context.Context, bin string, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, bin, args...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return string(out), errors.Wrap(errors.KindUnavailable, "run "+bin, err)
	}
	return string(out), nil
}

// toolVersion best-effort reads a CLI's version field for the manifest's truthful Distro string
// (telemetry/UI only). A failure yields "vX" so the Distro is still non-empty.
func toolVersion(ctx context.Context, bin string) string {
	out, err := runCommand(ctx, bin, "version")
	if err != nil {
		return "vX"
	}
	for _, line := range strings.Split(out, "\n") {
		for _, field := range strings.Fields(line) {
			if strings.HasPrefix(field, "v") && len(field) > 1 && field[1] >= '0' && field[1] <= '9' {
				return field
			}
		}
	}
	return "vX"
}
