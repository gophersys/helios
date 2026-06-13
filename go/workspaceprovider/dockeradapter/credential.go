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
const credentialEnvVar = "EDEN_WORKLOAD_CREDENTIAL"

// credentialFilePath is the tmpfs path a VehicleFile workload credential is written to (the
// workload reads it). It lives on a tmpfs mount so it never hits an image layer (07 §2).
const credentialFilePath = "/run/eden/credential"

// injectCredential places the resolved workload credential where the workload reads it,
// per the spec's Vehicle, at the injection site ONLY. For VehicleEnv it returns the
// "K=V" env entry for the child exec; for VehicleFile it writes the value to a tmpfs file
// and returns no env. The value is read via Secret.Use (the sole read path) and never
// logged, never returned, never placed in the spec. It returns the env to add to the exec.
//
//nolint:gocritic // resolved is heavy but mirrors the frozen Resolved seam; spec is read once for its Vehicle.
func (c *connection) injectCredential(ctx context.Context, spec workspaceprovider.RunSpec, resolved workspaceprovider.Resolved) ([]string, error) {
	if resolved.Workload == nil {
		return nil, nil
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
		return nil, nil
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

// registryAuth builds docker's base64-encoded X-Registry-Auth header value from the
// resolved pull-secret. The secret value is read via Secret.Use (the sole read path); it
// is expected to be a registry auth token (the "identitytoken"/"password" forms docker
// accepts). The value never leaves this function except as the opaque header docker
// requires.
func registryAuth(pullSecret *secrets.Secret) (string, error) {
	header, err := secrets.Use1(pullSecret, func(plaintext []byte) (string, error) {
		authConfig := registry.AuthConfig{Password: string(plaintext)}
		encoded, merr := json.Marshal(authConfig)
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
