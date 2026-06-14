package kubernetesadapter

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"path"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// credentialEnvVar is the env var name a VehicleEnv workload credential is placed under on the
// CHILD process only (the harness reads it). It mirrors the agentsession / docker-adapter seam.
const credentialEnvVar = "EDEN_WORKLOAD_CREDENTIAL" // #nosec G101 -- the NAME of an env var, not a credential value; the value is resolved server-side and never appears here.

// credentialFilePath is the tmpfs path a VehicleFile workload credential is written to (the
// workload reads it). It lives on a Memory-medium emptyDir so it never persists past the pod
// (07 §2).
const credentialFilePath = "/run/eden/credential" // #nosec G101 -- a filesystem PATH, not a credential value; the value is written here at the injection site only.

// secretValueKey is the single data key every MountSecret corev1.Secret stores its value under;
// the secret volume projects this key AS the Target's basename so reading the Target returns the
// value. secretFileMode is the restrictive owner-read-only mode (0400) the projected file gets —
// kubernetes secret volumes are tmpfs-backed, so the bytes never persist past the pod (07 §2).
const (
	secretValueKey = "value"
	secretFileMode = 0o400
	// pullSecretKey is the data key a dockerconfigjson pull-secret stores its config under (the
	// fixed key kubernetes' kubelet reads for kubernetes.io/dockerconfigjson secrets).
	pullSecretKey = corev1.DockerConfigJsonKey
)

// createSecrets materializes the library-resolved credentials as native kubernetes Secrets in
// the workspace namespace and returns their NAMES (never their bytes) for buildPod to mount: a
// corev1.Secret per MountSecret (value under secretValueKey) and, when the spec named a private
// image, a kubernetes.io/dockerconfigjson Secret for Pod.Spec.ImagePullSecrets. The value is
// read via Secret.Use (the sole read path) and placed into the apiserver-stored Secret object;
// it NEVER enters the pod spec, a label, or a log. The library Zeroizes the resolved Secrets
// after Create returns. A failure to place declared credential material is fail-closed (an
// IsolationError for a mount, an ImageError for the pull-secret) so the caller rolls the
// namespace back rather than returning a workspace missing its credential.
//
//nolint:gocritic // resolved mirrors the frozen Resolved seam; spec is pointer-passed for its Mounts/Image.
func (a *Adapter) createSecrets(ctx context.Context, spec *workspaceprovider.WorkspaceSpec, namespace string, resolved workspaceprovider.Resolved) (podCredentials, error) {
	creds := podCredentials{mountSecretNames: map[string]string{}}

	for i := range spec.Mounts {
		mount := spec.Mounts[i]
		if mount.Kind != workspaceprovider.MountSecret {
			continue
		}
		secret := resolved.Mounts[mount.Target]
		if secret == nil {
			return podCredentials{}, &workspaceprovider.IsolationError{Detail: "resolved MountSecret material missing for target " + mount.Target}
		}
		name := mountSecretName(i)
		if cerr := a.createOpaqueSecret(ctx, namespace, name, secret); cerr != nil {
			return podCredentials{}, &workspaceprovider.IsolationError{Detail: "create MountSecret for target " + mount.Target}
		}
		creds.mountSecretNames[mount.Target] = name
	}

	if resolved.PullSecret != nil {
		name := pullSecretObjectName
		if cerr := a.createPullSecret(ctx, namespace, name, spec.Image, resolved.PullSecret); cerr != nil {
			return podCredentials{}, &workspaceprovider.ImageError{Image: spec.Image, Ref: spec.ImagePull}
		}
		creds.pullSecretName = name
	}

	return creds, nil
}

// pullSecretObjectName is the fixed name of the per-workspace dockerconfigjson pull-secret (one
// per namespace, so a constant name is collision-free within the workspace's own namespace).
const pullSecretObjectName = "eden-pull-secret"

// mountSecretName derives the deterministic corev1.Secret name for the i-th MountSecret in a
// spec (one namespace per workspace, so an index suffix is collision-free).
func mountSecretName(index int) string {
	return "eden-mount-secret-" + strconv.Itoa(index)
}

// createOpaqueSecret creates an Opaque corev1.Secret storing the resolved value under
// secretValueKey, reading the value via Secret.Use (the sole read path) and wiping the local
// copy immediately after. The value rides the apiserver-stored Secret object, never a log.
func (a *Adapter) createOpaqueSecret(ctx context.Context, namespace, name string, secret *secrets.Secret) error {
	var value []byte
	if uerr := secret.Use(func(plaintext []byte) error {
		value = append(value[:0], plaintext...)
		return nil
	}); uerr != nil {
		return errors.Wrap(errors.KindPermission, "kubernetesadapter: read MountSecret for injection", uerr)
	}
	obj := &corev1.Secret{
		ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: namespace, Labels: map[string]string{ownerLabel: "true"}},
		Type:       corev1.SecretTypeOpaque,
		Data:       map[string][]byte{secretValueKey: value},
	}
	_, cerr := a.client.CreateSecret(ctx, namespace, obj)
	for i := range value {
		value[i] = 0 // best-effort wipe of the local copy (the apiserver now holds it)
	}
	if cerr != nil {
		return classifyAPIError("create mount secret", cerr)
	}
	return nil
}

// createPullSecret creates a kubernetes.io/dockerconfigjson Secret from the resolved pull-secret
// so the kubelet authenticates the private-image pull. The resolved value is treated as the
// registry password (the docker-adapter's registryAuth convention) under the image's registry
// host; the .dockerconfigjson is assembled inside Secret.Use and the local copy wiped after.
func (a *Adapter) createPullSecret(ctx context.Context, namespace, name, image string, pullSecret *secrets.Secret) error {
	configJSON, err := secrets.Use1(pullSecret, func(plaintext []byte) ([]byte, error) {
		return dockerConfigJSON(registryHost(image), string(plaintext))
	})
	if err != nil {
		return errors.Wrap(errors.KindPermission, "kubernetesadapter: build dockerconfigjson pull-secret", err)
	}
	obj := &corev1.Secret{
		ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: namespace, Labels: map[string]string{ownerLabel: "true"}},
		Type:       corev1.SecretTypeDockerConfigJson,
		Data:       map[string][]byte{pullSecretKey: configJSON},
	}
	_, cerr := a.client.CreateSecret(ctx, namespace, obj)
	for i := range configJSON {
		configJSON[i] = 0 // best-effort wipe (the apiserver now holds it)
	}
	if cerr != nil {
		return classifyAPIError("create pull secret", cerr)
	}
	return nil
}

// dockerConfigJSON assembles a kubernetes-compatible .dockerconfigjson for one registry host
// from a single auth token (used as the registry password under user "eden"; the auth field is
// the base64 of "user:password" the kubelet sends). The token is the only secret here; it is
// confined to this function and the returned bytes.
func dockerConfigJSON(host, token string) ([]byte, error) {
	encodedAuth := base64.StdEncoding.EncodeToString([]byte("eden:" + token))
	doc := dockerConfig{Auths: map[string]dockerAuthEntry{host: {
		Username: "eden",
		Password: token,
		Auth:     encodedAuth,
	}}}
	out, merr := json.Marshal(doc)
	if merr != nil {
		return nil, errors.Wrap(errors.KindInternal, "kubernetesadapter: marshal dockerconfigjson", merr)
	}
	return out, nil
}

// dockerConfig / dockerAuthEntry are the minimal shape of a ~/.docker/config.json the kubelet
// reads from a kubernetes.io/dockerconfigjson Secret.
type dockerConfig struct {
	Auths map[string]dockerAuthEntry `json:"auths"`
}

type dockerAuthEntry struct {
	Username string `json:"username"`
	Password string `json:"password"`
	Auth     string `json:"auth"`
}

// registryHost extracts the registry host from an image reference (the segment before the first
// "/" when it looks like a host — contains a "." or ":"), else docker hub's index host (the
// default registry kubelet auth keys on for unqualified images).
func registryHost(image string) string {
	first, _, ok := strings.Cut(image, "/")
	if ok && (strings.Contains(first, ".") || strings.Contains(first, ":") || first == "localhost") {
		return first
	}
	return "https://index.docker.io/v1/"
}

// secretMountDir is the directory a MountSecret's secret volume mounts at: the Target's parent,
// so the projected value file lands AT the Target. A Target with no parent mounts at "/".
func secretMountDir(target string) string {
	dir := path.Dir(strings.TrimRight(target, "/"))
	if dir == "" || dir == "." {
		return "/"
	}
	return dir
}

// secretBaseName is the file name a MountSecret's value is projected as inside its volume (the
// Target's basename), so the value appears exactly at the Target.
func secretBaseName(target string) string {
	return path.Base(strings.TrimRight(target, "/"))
}

// injectCredential places the resolved workload credential where the workload reads it, per the
// spec's Vehicle, at the injection site ONLY, and returns the command the Run exec should run.
// For VehicleEnv it prepends `env KEY=value` to the command (the credential reaches the child
// process env without ever entering the spec or a log); for VehicleFile it writes the value to
// a tmpfs file via the Files seam and returns the command unchanged. The value is read via
// Secret.Use (the sole read path) and never logged, never returned, never placed in the spec.
//
//nolint:gocritic // resolved is heavy but mirrors the frozen Resolved seam; spec is read once for its command/Vehicle.
func (c *connection) injectCredential(ctx context.Context, spec workspaceprovider.RunSpec, resolved workspaceprovider.Resolved) ([]string, error) {
	if resolved.Workload == nil {
		return spec.Command, nil
	}
	switch spec.Vehicle {
	case workspaceprovider.VehicleFile:
		var value []byte
		if uerr := resolved.Workload.Use(func(plaintext []byte) error {
			value = append(value[:0], plaintext...)
			return nil
		}); uerr != nil {
			return nil, &workspaceprovider.IsolationError{Handle: c.handle, Detail: "resolve workload credential for file vehicle"}
		}
		ferr := c.Files().Put(ctx, credentialFilePath, bytes.NewReader(value), 0o600)
		for i := range value {
			value[i] = 0 // best-effort wipe of the local copy
		}
		if ferr != nil {
			return nil, &workspaceprovider.IsolationError{Handle: c.handle, Detail: "write workload credential to tmpfs"}
		}
		return spec.Command, nil
	default: // VehicleEnv
		entry, uerr := secrets.Use1(resolved.Workload, func(plaintext []byte) (string, error) {
			return credentialEnvVar + "=" + string(plaintext), nil
		})
		if uerr != nil {
			return nil, &workspaceprovider.IsolationError{Handle: c.handle, Detail: "resolve workload credential for env vehicle"}
		}
		// Prepend `env KEY=value` so the credential reaches ONLY the child process the workload
		// runs (env runs the command with the extra variable, scrubbed from the exec record).
		command := append([]string{"env", entry}, spec.Command...)
		return command, nil
	}
}
