package kubernetesadapter

import (
	"bytes"
	"context"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// credentialEnvVar is the env var name a VehicleEnv workload credential is placed under on the
// CHILD process only (the harness reads it). It mirrors the agentsession / docker-adapter seam.
const credentialEnvVar = "EDEN_WORKLOAD_CREDENTIAL"

// credentialFilePath is the tmpfs path a VehicleFile workload credential is written to (the
// workload reads it). It lives on a Memory-medium emptyDir so it never persists past the pod
// (07 §2).
const credentialFilePath = "/run/eden/credential"

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
