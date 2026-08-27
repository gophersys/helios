package dockeradapter

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"

	"github.com/docker/docker/api/types/registry"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// credentialEnvVar is the env var name a VehicleEnv workload credential is placed under on
// the CHILD process only (the harness reads it). It mirrors the agentsession seam.
const credentialEnvVar = "EDEN_WORKLOAD_CREDENTIAL" // #nosec G101 -- the NAME of an env var, not a credential value; the value is resolved server-side and never appears here.

// credentialFilePath is the tmpfs path a VehicleFile workload credential is written to (the
// workload reads it). It lives on a tmpfs mount so it never hits an image layer (07 §2).
const credentialFilePath = "/run/eden/credential" // #nosec G101 -- a filesystem PATH, not a credential value; the value is written here at the injection site only.

// injectCredential places the resolved workload credential where the workload reads it,
// per the spec's Vehicle, at the injection site ONLY. For VehicleEnv it returns the
// "K=V" env entry for the child exec; for VehicleFile it writes the value to a tmpfs file
// and returns no env. The value is read via Secret.Use (the sole read path) and never
// logged, never returned, never placed in the spec. It returns the env to add to the exec.
//
//nolint:gocritic // resolved is heavy but mirrors the frozen Resolved seam; spec is read once for its Vehicle.
func (c *connection) injectCredential(ctx context.Context, spec workspaceprovider.RunSpec, resolved workspaceprovider.Resolved) ([]string, error) {
	// noEnv is the explicit "no env entry to add" result the no-credential and VehicleFile paths
	// return — the credential reaches the workload via a tmpfs file there, NOT the child env.
	var noEnv []string
	if resolved.Workload == nil {
		return noEnv, nil
	}
	switch spec.Vehicle {
	case workspaceprovider.VehicleFile:
		// The credential file lives on a tmpfs (07 §2: it never hits an image layer). docker's
		// CopyToContainer (the Files.Put plane) CANNOT write into a tmpfs — a tmpfs masks the
		// container-layer copy plane — so the value is streamed in via the SAME in-container
		// exec+stdin mechanism MountSecret uses (writeSecretFile), not Files.Put.
		if ferr := writeSecretFile(ctx, c, credentialFilePath, resolved.Workload); ferr != nil {
			return noEnv, &workspaceprovider.IsolationError{Handle: c.handle, Detail: "write workload credential to tmpfs"}
		}
		return noEnv, nil
	default: // VehicleEnv
		entry, uerr := secrets.Use1(resolved.Workload, func(plaintext []byte) (string, error) {
			return credentialEnvVar + "=" + string(plaintext), nil
		})
		if uerr != nil {
			return nil, &workspaceprovider.IsolationError{Handle: c.handle, Detail: "resolve workload credential for env vehicle"}
		}
		return []string{entry}, nil
	}
}

// writeMountSecrets writes each resolved MountSecret's material into its tmpfs Target as a
// restrictive-mode file, so a workload reading the Target gets the secret VALUE (not an empty
// file). The mount is already a genuine tmpfs (buildMounts), so the bytes never hit an image
// layer (07 §2). The value is read via Secret.Use (the sole read path) and copied into the
// container through the tar plane; it is NEVER logged, labeled, or returned. The library
// Zeroizes the resolved Secret after Create returns. An empty resolved map is a no-op.
//
//nolint:gocritic // resolved mirrors the frozen Resolved seam; spec is pointer-passed for its Mounts.
func (a *Adapter) writeMountSecrets(ctx context.Context, containerID string, spec *workspaceprovider.WorkspaceSpec, resolved workspaceprovider.Resolved) error {
	if len(resolved.Mounts) == 0 {
		return nil
	}
	conn := a.connection(containerID, workspaceprovider.Handle{})
	for i := range spec.Mounts {
		mount := spec.Mounts[i]
		if mount.Kind != workspaceprovider.MountSecret {
			continue
		}
		secret := resolved.Mounts[mount.Target]
		if secret == nil {
			// The library validated a MountSecret carries a non-zero Ref and resolved it into
			// resolved.Mounts; a missing entry means the credential could not be placed.
			return &workspaceprovider.IsolationError{Detail: "resolved MountSecret material missing for target " + mount.Target}
		}
		if werr := writeSecretFile(ctx, conn, mount.Target, secret); werr != nil {
			return &workspaceprovider.IsolationError{Detail: "write MountSecret material to " + mount.Target}
		}
	}
	return nil
}

// writeSecretFile streams a resolved Secret's bytes onto the workspace's tmpfs Target via an
// exec that reads STDIN and writes the file with a restrictive umask — `sh -c 'umask 077; cat >
// "$1"' sh <target>`. The exec runs INSIDE the container, so it writes through the tmpfs mount
// (docker's CopyToContainer cannot — a tmpfs masks the container-layer copy plane). The command
// argv carries only the path (loggable); the secret VALUE rides stdin and never appears in the
// exec record, a label, or a log. The value is read via Secret.Use (the sole read path) and the
// local copy wiped immediately after; the library Zeroizes the resolved Secret after Create.
func writeSecretFile(ctx context.Context, conn *connection, target string, secret *secrets.Secret) error {
	var value []byte
	if uerr := secret.Use(func(plaintext []byte) error {
		value = append(value[:0], plaintext...)
		return nil
	}); uerr != nil {
		return errors.Wrap(errors.KindPermission, "dockeradapter: read MountSecret for injection", uerr)
	}
	res, eerr := conn.Exec(ctx, workspaceprovider.ExecSpec{
		// umask 077 makes the created file 0600 (owner read/write only); $1 is the path, fed as
		// an arg so it is never a shell-injection surface and the secret never rides the argv.
		Command: []string{"sh", "-c", "umask 077; cat > \"$1\"", "sh", target},
		Stdin:   bytes.NewReader(value),
	})
	for i := range value {
		value[i] = 0 // best-effort wipe of the local copy
	}
	if eerr != nil {
		return errors.Wrap(errors.KindInternal, "dockeradapter: write MountSecret to tmpfs", eerr)
	}
	if res.ExitCode != 0 {
		return errors.New(errors.KindInternal, "dockeradapter: MountSecret write exited non-zero")
	}
	return nil
}

// registryUsername is the fixed username both adapters present for a basic-auth registry pull,
// so a resolved pull-secret carries only the PASSWORD (the secret) and the two substrates
// authenticate identically against the same registry (the substitutability the conformance
// suite proves). The kubernetesadapter's dockerconfigjson uses the same username.
const registryUsername = "eden"

// registryAuth builds docker's base64-encoded X-Registry-Auth header value from the
// resolved pull-secret. The secret value is read via Secret.Use (the sole read path) and used
// as the registry PASSWORD under the fixed registryUsername (basic auth). The value never
// leaves this function except as the opaque header docker requires.
func registryAuth(pullSecret *secrets.Secret) (string, error) {
	header, err := secrets.Use1(pullSecret, func(plaintext []byte) (string, error) {
		authConfig := registry.AuthConfig{Username: registryUsername, Password: string(plaintext)}
		encoded, merr := json.Marshal(authConfig) // #nosec G117 -- registry.AuthConfig is the docker SDK's REQUIRED pull-secret carrier; the password is read only via the secret seam and immediately base64-encoded into the opaque X-Registry-Auth header docker demands, never logged or persisted.
		if merr != nil {
			return "", errors.Wrap(errors.KindInternal, "dockeradapter: marshal registry auth", merr)
		}
		return base64.URLEncoding.EncodeToString(encoded), nil
	})
	if err != nil {
		return "", errors.Wrap(errors.KindInternal, "dockeradapter: read pull-secret for registry auth", err)
	}
	return header, nil
}
