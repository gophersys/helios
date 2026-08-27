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

// registryTimeout bounds the local-registry spin + image build/push handshake.
const registryTimeout = 3 * time.Minute

// LocalRegistry is a throwaway, password-protected docker registry the B7 (pull-secret) tests
// push a tiny PRIVATE image into and then assert both adapters can pull WITH the resolved
// pull-secret and fail with ImageError WITHOUT it (07 §2 / contract §2: "a denied pull-secret
// yields ImageError"). Reference is the private image's full ref (host:port/name:tag); Password
// is the htpasswd password (the secret the pull-secret resolves to — username is the fixed
// "eden"); Network is the docker network the registry is attached to (so a k3d/kind cluster can
// be joined to it for in-cluster pulls); delete tears EVERYTHING down (registry container,
// network, htpasswd dir, pushed image) — a leaked authed registry is unacceptable (C23).
type LocalRegistry struct {
	Reference string
	Password  string
	Network   string
	host      string // the host:port the registry publishes on the host (for the docker-daemon pull)
	container string
	authDir   string
	delete    func()
}

// registryUser is the basic-auth username both adapters present (the docker adapter's
// registryAuth and the kubernetes adapter's dockerconfigjson both use "eden"); the pull-secret
// resolves to the PASSWORD only, so the two substrates authenticate identically.
const registryUser = "eden"

// NewLocalRegistry stands up a registry:2 with htpasswd basic auth on a dedicated docker
// network, builds a tiny private image FROM the pre-pulled base, and pushes it under auth. It
// returns the registry (with the private ref + password) and a cleanup. It SKIPS (via a typed
// unavailable error the caller maps to t.Skip) when docker/htpasswd is missing or the daemon is
// unreachable, so a machine without the tooling degrades rather than fails. baseImage is the
// public image the private image is derived FROM (busybox), already on the daemon.
func NewLocalRegistry(ctx context.Context, baseImage string) (*LocalRegistry, error) {
	if !onPath("docker") || !onPath("htpasswd") {
		return nil, errors.New(errors.KindUnavailable, "local registry needs docker + htpasswd on PATH")
	}
	suffix := randomSuffix()
	reg := &LocalRegistry{
		Network:   "eden-reg-net-" + suffix,
		container: "eden-registry-" + suffix,
		Password:  "pw-" + randomSuffix(),
	}
	ctx, cancel := context.WithTimeout(ctx, registryTimeout)
	defer cancel()

	if err := reg.start(ctx, baseImage); err != nil {
		reg.teardown()
		return nil, err
	}
	return reg, nil
}

// Delete tears the whole registry down (idempotent). The caller registers it on t.Cleanup.
func (r *LocalRegistry) Delete() {
	if r.delete != nil {
		r.delete()
	}
}

// HostReference is the image ref reachable from the DOCKER DAEMON (the host-published port). The
// docker adapter pulls this.
func (r *LocalRegistry) HostReference() string { return r.Reference }

// ClusterReference is the image ref reachable from INSIDE a cluster joined to the registry's
// network (the registry container's name resolves on that network); the kubernetes adapter pulls
// this.
func (r *LocalRegistry) ClusterReference() string { return r.container + ":5000/eden/private:1" }

// start writes the htpasswd file, creates the network, runs the registry, waits for it to
// answer, then builds + pushes the private image under auth.
func (r *LocalRegistry) start(ctx context.Context, baseImage string) error {
	authDir, err := os.MkdirTemp("", "eden-registry-auth-")
	if err != nil {
		return errors.Wrap(errors.KindInternal, "registry: temp auth dir", err)
	}
	r.authDir = authDir
	r.delete = r.teardown

	htpasswd, herr := runCmd(ctx, "htpasswd", "-Bbn", registryUser, r.Password)
	if herr != nil {
		return errors.Wrap(errors.KindUnavailable, "registry: htpasswd: "+htpasswd, herr)
	}
	if werr := os.WriteFile(filepath.Join(authDir, "htpasswd"), []byte(htpasswd), 0o600); werr != nil {
		return errors.Wrap(errors.KindInternal, "registry: write htpasswd", werr)
	}

	if out, nerr := runCmd(ctx, "docker", "network", "create", r.Network); nerr != nil {
		return errors.Wrap(errors.KindUnavailable, "registry: create network: "+out, nerr)
	}

	// Run the registry on the dedicated network, publishing an ephemeral host port so the docker
	// daemon can pull it as 127.0.0.1:<port> (an insecure-by-default localhost registry).
	if out, rerr := runCmd(
		ctx,
		"docker", "run", "-d",
		"--name", r.container,
		"--network", r.Network,
		"-p", "127.0.0.1:0:5000",
		"-v", authDir+":/auth",
		"-e", "REGISTRY_AUTH=htpasswd",
		"-e", "REGISTRY_AUTH_HTPASSWD_REALM=Registry Realm",
		"-e", "REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd",
		"registry:2",
	); rerr != nil {
		return errors.Wrap(errors.KindUnavailable, "registry: run: "+out, rerr)
	}

	port, perr := r.publishedPort(ctx)
	if perr != nil {
		return perr
	}
	r.host = "127.0.0.1:" + port
	r.Reference = r.host + "/eden/private:1"

	if werr := r.waitReady(ctx); werr != nil {
		return werr
	}
	return r.buildAndPush(ctx, baseImage)
}

// publishedPort reads the host port docker assigned the registry's 5000/tcp.
func (r *LocalRegistry) publishedPort(ctx context.Context) (string, error) {
	out, err := runCmd(ctx, "docker", "port", r.container, "5000/tcp")
	if err != nil {
		return "", errors.Wrap(errors.KindUnavailable, "registry: read published port: "+out, err)
	}
	// `docker port` prints e.g. "127.0.0.1:54321"; take the last colon-segment of the first line.
	line := strings.TrimSpace(strings.SplitN(out, "\n", 2)[0])
	idx := strings.LastIndex(line, ":")
	if idx < 0 {
		return "", errors.New(errors.KindUnavailable, "registry: unexpected docker port output: "+line)
	}
	return line[idx+1:], nil
}

// waitReady polls the registry's /v2/ endpoint (a 401 under auth is "up") until it answers.
func (r *LocalRegistry) waitReady(ctx context.Context) error {
	deadline := time.Now().Add(45 * time.Second)
	for {
		// A wget from a throwaway busybox on the host network reaches the published port; a 401
		// (auth required) or 200 both mean the registry is answering. The error is expected (a 401
		// makes wget exit non-zero) — the readiness signal is the HTTP code in the output.
		out, _ := runCmd(ctx, "docker", "run", "--rm", "--network", "host", "busybox:1.36", //nolint:errcheck // a 401 (auth required) makes wget exit non-zero; readiness is read from the HTTP code in out, not the exit.
			"wget", "-q", "-S", "-O", "/dev/null", "http://"+r.host+"/v2/")
		if strings.Contains(out, "401") || strings.Contains(out, "200") {
			return nil
		}
		if time.Now().After(deadline) || ctx.Err() != nil {
			return errors.New(errors.KindUnavailable, "registry: did not become ready: "+out)
		}
		time.Sleep(time.Second)
	}
}

// buildAndPush tags the base image as the private ref, logs in, and pushes it under auth (so the
// image exists ONLY behind the password). It pushes BOTH the host ref (for the docker daemon)
// and the in-cluster ref (registryContainer:5000, for a cluster joined to the network).
func (r *LocalRegistry) buildAndPush(ctx context.Context, baseImage string) error {
	if out, lerr := runCmdStdin(ctx, r.Password, "docker", "login", "-u", registryUser, "--password-stdin", r.host); lerr != nil {
		return errors.Wrap(errors.KindUnavailable, "registry: docker login: "+out, lerr)
	}
	defer func() { _, _ = runCmd(context.WithoutCancel(ctx), "docker", "logout", r.host) }() //nolint:errcheck // best-effort logout; a lingering credential in the test's docker config is reaped with the daemon.

	for _, ref := range []string{r.Reference, r.ClusterReference()} {
		if out, terr := runCmd(ctx, "docker", "tag", baseImage, ref); terr != nil {
			return errors.Wrap(errors.KindUnavailable, "registry: tag "+ref+": "+out, terr)
		}
	}
	// Only the host ref is pushable from the host (the cluster ref's hostname does not resolve on
	// the host); the cluster ref shares the same digest, so one push under the host ref populates
	// the registry for both names.
	if out, perr := runCmd(ctx, "docker", "push", r.Reference); perr != nil {
		return errors.Wrap(errors.KindUnavailable, "registry: push: "+out, perr)
	}
	return nil
}

// JoinCluster connects a cluster's nodes (the docker containers named by nodeContainers) to the
// registry's network so an in-cluster pod can pull r.ClusterReference(). It is best-effort: a
// node already on the network is fine.
func (r *LocalRegistry) JoinCluster(ctx context.Context, nodeContainers []string) {
	for _, node := range nodeContainers {
		_, _ = runCmd(ctx, "docker", "network", "connect", r.Network, node) //nolint:errcheck // best-effort join; an already-connected node errors harmlessly and the pull still resolves.
	}
}

// RegistriesYAML renders a k3s registries.yaml that tells containerd to reach this registry over
// plain HTTP (containerd otherwise refuses a non-TLS registry). It deliberately carries NO auth
// block — the endpoint/TLS config only tells containerd HOW to reach the registry, while the
// CREDENTIALS still come from the Pod's ImagePullSecret (the B7 fix under test). That keeps the
// negative case honest: an unauthenticated pull (no pull-secret) is still DENIED by the registry.
// The cluster reaches the registry by its container name on the joined network.
func (r *LocalRegistry) RegistriesYAML() string {
	host := r.container + ":5000"
	return strings.Join([]string{
		"mirrors:",
		"  \"" + host + "\":",
		"    endpoint:",
		"      - \"http://" + host + "\"",
	}, "\n") + "\n"
}

// WriteRegistriesYAML writes RegistriesYAML to a temp file and returns its path (the caller
// passes it to k3d cluster create --registry-config). The file is reaped with the registry.
func (r *LocalRegistry) WriteRegistriesYAML() (string, error) {
	if r.authDir == "" {
		return "", errors.New(errors.KindInternal, "registry: not started")
	}
	pathName := filepath.Join(r.authDir, "registries.yaml")
	if err := os.WriteFile(pathName, []byte(r.RegistriesYAML()), 0o600); err != nil {
		return "", errors.Wrap(errors.KindInternal, "registry: write registries.yaml", err)
	}
	return pathName, nil
}

// teardown removes the registry container, the network, the local tags, and the htpasswd dir.
func (r *LocalRegistry) teardown() {
	bg := context.Background()
	_, _ = runCmd(bg, "docker", "rm", "-f", r.container)           //nolint:errcheck // best-effort cleanup.
	_, _ = runCmd(bg, "docker", "network", "rm", r.Network)        //nolint:errcheck // best-effort cleanup.
	_, _ = runCmd(bg, "docker", "rmi", "-f", r.Reference)          //nolint:errcheck // best-effort cleanup.
	_, _ = runCmd(bg, "docker", "rmi", "-f", r.ClusterReference()) //nolint:errcheck // best-effort cleanup.
	if r.authDir != "" {
		_ = os.RemoveAll(r.authDir) //nolint:errcheck // best-effort cleanup of the htpasswd temp dir.
	}
}

// randomSuffix returns 4 random hex bytes for a collision-proof name.
func randomSuffix() string {
	var b [4]byte
	_, _ = rand.Read(b[:]) //nolint:errcheck // crypto/rand never short-reads here; a zero suffix is still usable.
	return hex.EncodeToString(b[:])
}

// runCmd runs bin with args, returning combined output + any error (a thin sibling of cluster.go's
// runCommand kept here so the registry harness is self-contained).
func runCmd(ctx context.Context, bin string, args ...string) (string, error) {
	out, err := exec.CommandContext(ctx, bin, args...).CombinedOutput() // #nosec G204 -- a test harness driving the docker/htpasswd CLIs is exec-by-design; bin/args are fixed harness-internal command literals, never consumer input.
	if err != nil {
		return string(out), errors.Wrap(errors.KindUnavailable, "run "+bin, err)
	}
	return string(out), nil
}

// runCmdStdin runs bin with args feeding stdin on stdin (for `docker login --password-stdin`, so
// the password never rides the argv/process list).
func runCmdStdin(ctx context.Context, stdin, bin string, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, bin, args...) // #nosec G204 -- a test harness driving `docker login --password-stdin` is exec-by-design; bin/args are fixed harness-internal command literals, never consumer input.
	cmd.Stdin = strings.NewReader(stdin)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return string(out), errors.Wrap(errors.KindUnavailable, "run "+bin, err)
	}
	return string(out), nil
}

// ClusterNodes returns the docker container names of a k3d/kind cluster's nodes (so the registry
// network can be joined to them for in-cluster pulls). It reads `docker ps` by the cluster label
// each tool stamps. An empty result means the nodes could not be identified (the caller then
// skips the in-cluster pull, keeping the docker pull assertion).
func ClusterNodes(ctx context.Context, clusterName string) []string {
	// k3d labels nodes `k3d.cluster=<name>`; kind labels them `io.x-k8s.kind.cluster=<name>`.
	var nodes []string
	for _, label := range []string{"k3d.cluster=" + clusterName, "io.x-k8s.kind.cluster=" + clusterName} {
		out, err := runCmd(ctx, "docker", "ps", "--filter", "label="+label, "--format", "{{.Names}}")
		if err != nil {
			continue
		}
		nodes = append(nodes, strings.Fields(out)...)
	}
	return nodes
}
