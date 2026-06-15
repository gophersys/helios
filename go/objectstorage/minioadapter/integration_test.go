//go:build integration

// Package minioadapter_test's integration suite runs against a REAL MinIO — the OFFICIAL
// minio/minio container, booted in server mode with a root credential, per the real-substrate rule
// (ADR-0016 §2: "mocks are not acceptable substitutes"). It is gated behind the `integration` build
// tag so the default `go test` (and the pre-commit hook) stays fast; run it with
//
//	go test -tags integration ./...
//
// The container is reaped on t.Cleanup (on failure too) under a unique per-test name, so parallel
// or abandoned runs never leak. The adapter stores/reads through its REAL minio-go transport —
// never a mock. docker-out-of-docker: the devcontainer reaches the sibling MinIO container by its
// docker-bridge IP (docker inspect), so no published port is needed.
package minioadapter_test

import (
	"bytes"
	"context"
	"os/exec"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/objectstorage/minioadapter"
	"github.com/gophersys/libs/go/objectstorage/objectstoragetest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// minioImage is the OFFICIAL image. It is pre-pulled in the devcontainer.
const minioImage = "minio/minio:latest"

// the credential references the integration adapter resolves; the secretstest fake seeds them with
// the REAL container's root credential, so the adapter's resolve→Use→static-credential path runs
// for real against a real MinIO.
//
// CREDENTIAL SEMANTICS (load-bearing): in S3 SigV4 the ACCESS-KEY ID is a public identifier — it
// legitimately appears in a presigned URL's `X-Amz-Credential` scope (like a username), and the
// integration lane PROVED that empirically. The SECRET KEY is the value that must NEVER surface: a
// presigned URL carries only the derived `X-Amz-Signature`, never the secret. So the redaction
// needle is the SECRET key (secretCanary); the access-key ID is a non-secret identifier.
const (
	accessKeyID  = "eden-it-access-key-id" // public S3 identifier; may appear in a presign credential scope
	secretCanary = "OBJSTORE-REALMINIO-secretkey-9c0ffee-d34db33f-do-not-leak"
)

var (
	itAccessRef = secrets.Ref("vault://eden/objectstore#real-access-key")
	itSecretRef = secrets.Ref("vault://eden/objectstore#real-secret-key")
)

// realMinio is a booted MinIO container the adapter resolves against.
type realMinio struct {
	name     string
	endpoint string // <bridge-ip>:9000, reachable from the devcontainer
	bucket   string
}

// TestIntegration_RealMinioConformance runs THE exported ObjectStore conformance suite (the REAL
// binding of the two-binding suite, 08 §2) against a *objectstorage.Client wired to a minioadapter
// over a REAL MinIO container. The SAME RunStoreSuite that the fake passes (conformance_test.go in
// the root) must pass here — round-trip byte-for-byte, typed NotFound/Invalid, idempotent delete,
// list-by-prefix, credential-free presign — over real S3 I/O. No mock anywhere on this path.
//
//nolint:paralleltest // boots a real container; serial by design so the bridge-IP/bootstrap is deterministic.
func TestIntegration_RealMinioConformance(t *testing.T) {
	requireDocker(t)
	m := startRealMinio(t)

	// secretCanary is threaded as the suite's redaction needle: the REAL secret key the adapter
	// resolved through the secretstest fake. The suite's presign assertion now hunts for the value
	// the real system was actually seeded with (not a stale constant), so the redaction property is
	// LIVE on the real binding — the audit's "vacuous needle" fix.
	objectstoragetest.RunStoreSuite(t, func() objectstorage.ObjectStore {
		return newRealStore(t, m)
	}, m.bucket, secretCanary)
}

// TestIntegration_RealMinioRoundTripByteForByte is the load-bearing real-MinIO proof: it Puts a
// payload (the round-trip needle) into a REAL bucket and Gets it back, asserting byte-for-byte
// equality through real S3 I/O, and that the resolved credential (the canary) appears in NO surfaced
// artifact (the ObjectInfo, the presigned URL).
//
//nolint:paralleltest // shares the real-container, serial-by-design discipline.
func TestIntegration_RealMinioRoundTripByteForByte(t *testing.T) {
	requireDocker(t)
	m := startRealMinio(t)
	objectStore := newRealStore(t, m)
	ctx := context.Background()

	ref, err := objectstorage.NewRef(m.bucket, "integration/round-trip.bin")
	if err != nil {
		t.Fatalf("NewRef error = %v", err)
	}
	payload := bytes.Repeat([]byte("byte-for-byte-real-minio-payload\n"), 4096) // ~132 KiB, multi-part-ish

	info, err := objectStore.Put(ctx, ref, bytes.NewReader(payload), objectstorage.PutOptions{
		ContentType: "application/octet-stream",
		Size:        int64(len(payload)),
	})
	if err != nil {
		t.Fatalf("Put against real MinIO: %v", err)
	}
	if info.Size != int64(len(payload)) {
		t.Errorf("Put ObjectInfo.Size = %d, want %d", info.Size, len(payload))
	}

	reader, getInfo, err := objectStore.Get(ctx, ref)
	if err != nil {
		t.Fatalf("Get against real MinIO: %v", err)
	}
	got := readAllAndClose(t, reader)
	if !bytes.Equal(got, payload) {
		t.Fatalf("real-MinIO round-trip mismatch: got %d bytes, want %d (byte-for-byte is the load-bearing property)", len(got), len(payload))
	}
	if getInfo.ETag == "" {
		t.Error("Get ObjectInfo carries no ETag from real MinIO")
	}

	// The SECRET key (the sensitive credential) never surfaces through the object metadata or a
	// presigned URL — a presign carries only the derived X-Amz-Signature, never the secret. (The
	// access-key ID is a public SigV4 identifier and legitimately appears in the credential scope;
	// that is asserted SEPARATELY below, the distinction the integration lane surfaced empirically.)
	signed, err := objectStore.Presign(ctx, ref, objectstorage.PresignOptions{Method: objectstorage.MethodGet, Expiry: 10 * time.Minute})
	if err != nil {
		t.Fatalf("Presign against real MinIO: %v", err)
	}
	// One redaction home: the presign surface's secret-key absence is proven by the shared
	// RunStoreSuite assertion above (threaded with secretCanary). Here we additionally assert the
	// secret never surfaces through the ObjectInfo rendering — a surface the suite does not cover —
	// via the SAME AssertNoCredentialLeak helper, so the needle is the value the system resolved.
	for surface, rendered := range map[string]string{
		"ObjectInfo": getInfo.Ref.String() + getInfo.ETag + getInfo.ContentType,
		"presign":    signed.String(),
	} {
		objectstoragetest.AssertNoCredentialLeak(t, "real-minio-"+surface, rendered, secretCanary)
	}
	// The presigned URL DOES carry the access-key ID in its SigV4 credential scope (a public
	// identifier) — assert that, so the distinction (secret-never, identifier-maybe) is documented
	// and pinned by a real-MinIO test, not just prose.
	if !strings.Contains(signed.String(), accessKeyID) {
		t.Errorf("presigned URL %q does not carry the access-key ID in its SigV4 credential scope (unexpected for real MinIO)", signed.String())
	}

	if err := objectStore.Delete(ctx, ref); err != nil {
		t.Errorf("Delete against real MinIO: %v", err)
	}
	if _, _, gerr := objectStore.Get(ctx, ref); !errors.IsType[objectstorage.NotFoundError](gerr) {
		t.Errorf("Get after Delete = %v, want NotFoundError from real MinIO", gerr)
	}
}

// TestIntegration_RealMinioTypedErrors proves the taxonomy holds against REAL MinIO: a get on a
// missing object is a real 404 mapped to NotFoundError, and an operation on a non-existent bucket
// is mapped to NotFoundError — the real S3 status mapped to the contract's typed errors, not strings.
//
//nolint:paralleltest // real container, serial by design.
func TestIntegration_RealMinioTypedErrors(t *testing.T) {
	requireDocker(t)
	m := startRealMinio(t)
	objectStore := newRealStore(t, m)
	ctx := context.Background()

	missing, err := objectstorage.NewRef(m.bucket, "integration/never-put.bin")
	if err != nil {
		t.Fatalf("NewRef error = %v", err)
	}
	if _, _, gerr := objectStore.Get(ctx, missing); !errors.IsType[objectstorage.NotFoundError](gerr) {
		t.Errorf("Get(absent) against real MinIO = %v, want NotFoundError", gerr)
	}

	absentBucket, err := objectstorage.NewRef("eden-no-such-bucket-"+randomSuffix(), "k.bin")
	if err != nil {
		t.Fatalf("NewRef error = %v", err)
	}
	if _, _, gerr := objectStore.Get(ctx, absentBucket); !errors.IsType[objectstorage.NotFoundError](gerr) {
		t.Errorf("Get(absent bucket) against real MinIO = %v, want NotFoundError", gerr)
	}
}

// ── real-MinIO harness (official image, server mode, bucket bootstrap, reaped) ──────────────────.

// newRealStore builds a *objectstorage.Client over a minioadapter pointed at the real container, with
// the root credential seeded into a secretstest fake (so the adapter's resolve→Use→static path runs
// for real). The credential is the canary, proving it is resolved yet never re-surfaced.
//
//nolint:ireturn // the conformance newStore factory returns the ObjectStore port (the suite's seam).
func newRealStore(t *testing.T, m realMinio) objectstorage.ObjectStore {
	t.Helper()
	provider := secretstest.New(map[string]string{
		itAccessRef.String(): accessKeyID,
		itSecretRef.String(): secretCanary,
	})
	adapter, err := minioadapter.New(
		minioadapter.Config{Endpoint: m.endpoint, AccessKeyRef: itAccessRef, SecretKeyRef: itSecretRef},
		minioadapter.Deps{Secrets: provider},
	)
	if err != nil {
		t.Fatalf("minioadapter.New against real MinIO: %v", err)
	}
	objectStore, err := objectstorage.New(objectstorage.Config{}, objectstorage.Deps{Backend: adapter})
	if err != nil {
		t.Fatalf("objectstorage.New: %v", err)
	}
	return objectStore
}

// startRealMinio boots the official MinIO image with the canary root credential, waits for health,
// resolves the bridge IP, creates a bucket via a one-shot `mc` against the container, and reaps
// everything on t.Cleanup. It returns the endpoint/bucket the adapter resolves against.
func startRealMinio(t *testing.T) realMinio {
	t.Helper()
	name := "eden-objectstorage-it-" + sanitize(t.Name()) + "-" + randomSuffix()
	bucket := "eden-it-" + randomSuffix()

	runDocker(t, "run", "-d", "--name", name,
		"-e", "MINIO_ROOT_USER="+accessKeyID,
		"-e", "MINIO_ROOT_PASSWORD="+secretCanary,
		minioImage, "server", "/data")
	t.Cleanup(func() { _ = exec.Command("docker", "rm", "-f", name).Run() }) //nolint:errcheck,gosec // best-effort reap; name is a harness-generated container name, not consumer input.

	ip := bridgeIP(t, name)
	endpoint := ip + ":9000"
	waitForMinioReady(t, endpoint)

	// Create the bucket with a one-shot mc container on the same docker network, aliasing the root
	// credential. mc is the official MinIO client; this is harness bootstrap, not the code under test.
	makeBucket(t, endpoint, bucket)

	return realMinio{name: name, endpoint: endpoint, bucket: bucket}
}

// makeBucket runs a throwaway `minio/mc` container that aliases the running server and makes the
// bucket. It shares the docker bridge so it reaches the server by the same IP the adapter uses.
func makeBucket(t *testing.T, endpoint, bucket string) {
	t.Helper()
	script := strings.Join([]string{
		"mc alias set it http://" + endpoint + " " + accessKeyID + " " + secretCanary,
		"mc mb --ignore-existing it/" + bucket,
	}, " && ")
	runDocker(t, "run", "--rm", "--entrypoint", "sh", minioMcImage, "-c", script)
}

const minioMcImage = "minio/mc:latest"

// requireDocker fails (not skips) when docker is absent — in the devcontainer it is guaranteed
// present, so absence is a gate FAILURE, not a skip (ADR-0020 FAIL-NOT-SKIP).
func requireDocker(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Fatalf("docker not on PATH — the integration lane requires a real docker daemon (ADR-0020 FAIL-NOT-SKIP): %v", err)
	}
}

// runDocker runs `docker <args...>` and fails the test on a non-zero exit, surfacing stderr.
func runDocker(t *testing.T, args ...string) string {
	t.Helper()
	cmd := exec.Command("docker", args...) // #nosec G204 -- harness driving the docker CLI; args are fixed test literals + harness-generated names, never consumer input.
	var out, errb bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errb
	if err := cmd.Run(); err != nil {
		t.Fatalf("docker %s: %v\nstderr: %s", strings.Join(args, " "), err, errb.String())
	}
	return out.String()
}

// bridgeIP returns the container's docker-bridge IP, the address the devcontainer dials.
func bridgeIP(t *testing.T, name string) string {
	t.Helper()
	out := runDocker(t, "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name)
	ip := strings.TrimSpace(out)
	if ip == "" {
		t.Fatalf("docker inspect returned an empty bridge IP for %s", name)
	}
	return ip
}

// waitForMinioReady polls MinIO's health endpoint over HTTP from the devcontainer until it is live,
// so the adapter's first call does not race the boot.
func waitForMinioReady(t *testing.T, endpoint string) {
	t.Helper()
	deadline := time.Now().Add(60 * time.Second)
	for time.Now().Before(deadline) {
		cmd := exec.Command("curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", //nolint:gosec // fixed health URL, harness-internal.
			"http://"+endpoint+"/minio/health/live")
		out, _ := cmd.CombinedOutput() //nolint:errcheck // a not-yet-ready MinIO returns a non-200/refused; the HTTP code in stdout is the signal.
		if strings.TrimSpace(string(out)) == "200" {
			return
		}
		time.Sleep(500 * time.Millisecond)
	}
	t.Fatalf("real MinIO at %s did not become healthy within the deadline", endpoint)
}

// readAllAndClose drains and closes a reader, failing the test on a read or close error.
func readAllAndClose(t *testing.T, reader interface {
	Read([]byte) (int, error)
	Close() error
},
) []byte {
	t.Helper()
	var buffer bytes.Buffer
	chunk := make([]byte, 32*1024)
	for {
		n, err := reader.Read(chunk)
		if n > 0 {
			buffer.Write(chunk[:n])
		}
		if err != nil {
			break
		}
	}
	if cerr := reader.Close(); cerr != nil {
		t.Errorf("reader.Close error = %v", cerr)
	}
	return buffer.Bytes()
}

// sanitize maps a test name to a docker-safe container-name fragment.
func sanitize(name string) string {
	var b strings.Builder
	for _, r := range strings.ToLower(name) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
		} else {
			b.WriteByte('-')
		}
	}
	return b.String()
}

// randomSuffix is a short, collision-resistant suffix so parallel/abandoned runs never share a
// container/bucket name. It uses the nanosecond clock — sufficient for serial integration runs.
func randomSuffix() string {
	return strings.NewReplacer(".", "", ":", "").Replace(time.Now().Format("150405.000000000"))
}
