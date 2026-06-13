package workspaceprovider

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"strconv"
	"strings"
)

// SpecFingerprintLabel is the ownership-domain label the LIBRARY stamps onto every
// provisioned workspace carrying a hash of the idempotency-bearing fields of its
// WorkspaceSpec (image, resources, egress, mounts, non-secret env). The adapter persists
// it as a native label/annotation alongside the tenancy keys; List returns it on the
// Descriptor's Labels, and Provision's idempotency check reads it back to decide whether a
// same-Name re-Provision is COMPATIBLE (same fingerprint → re-dial the existing handle) or
// INCOMPATIBLE (different fingerprint → ConflictError, Kind=Conflict). It is loggable by
// design (a hash, never a secret value — the secrets.References are NOT folded in).
const SpecFingerprintLabel = "eden.workspaceprovider/spec-fingerprint"

// specFingerprint hashes the idempotency-bearing fields of a spec into a stable, loggable
// hex digest. Two specs with the same Name but a different Image/Resources/Egress/Mounts/
// Env yield different fingerprints, which the idempotency check turns into a ConflictError
// (contract §2: "same Name, incompatible spec"). Fields that do NOT affect the realized
// workspace's identity (Substrate routing, the tenancy Labels themselves, the
// ProvisionTimeout) are deliberately excluded; secret VALUES are never present (only the
// loggable secrets.Reference strings participate, so the digest stays leak-safe).
func specFingerprint(spec *WorkspaceSpec) string {
	h := sha256.New()
	write := func(parts ...string) {
		for _, p := range parts {
			h.Write([]byte(p))
			h.Write([]byte{0}) // a NUL field separator so "a"+"b" != "ab"
		}
	}

	write("image", spec.Image)
	write("imagepull", spec.ImagePull.String())

	write(
		"resources",
		strconv.FormatInt(spec.Resources.CPUMilli, 10),
		strconv.FormatInt(spec.Resources.MemoryBytes, 10),
		strconv.FormatInt(spec.Resources.StorageBytes, 10),
		strconv.FormatInt(spec.Resources.PIDs, 10),
	)

	// Mounts and Egress are order-significant to the realized workspace but a consumer may
	// build them in any order; sort canonically so a re-order is not a false conflict.
	mounts := make([]string, 0, len(spec.Mounts))
	for i := range spec.Mounts {
		m := spec.Mounts[i]
		mounts = append(mounts, strconv.Itoa(int(m.Kind))+"|"+m.Target+"|"+m.Source+"|"+m.Ref.String()+"|"+strconv.FormatBool(m.ReadOnly))
	}
	sort.Strings(mounts)
	write(append([]string{"mounts"}, mounts...)...)

	egress := make([]string, 0, len(spec.Egress))
	for i := range spec.Egress {
		e := spec.Egress[i]
		ports := make([]string, len(e.Ports))
		for j, p := range e.Ports {
			ports[j] = strconv.Itoa(p)
		}
		sort.Strings(ports)
		egress = append(egress, e.Host+"|"+strings.Join(ports, ",")+"|"+e.Ref.String())
	}
	sort.Strings(egress)
	write(append([]string{"egress"}, egress...)...)

	env := make([]string, 0, len(spec.Env))
	for i := range spec.Env {
		env = append(env, spec.Env[i].Name+"="+spec.Env[i].Value)
	}
	sort.Strings(env)
	write(append([]string{"env"}, env...)...)

	return hex.EncodeToString(h.Sum(nil))
}
