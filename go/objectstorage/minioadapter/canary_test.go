package minioadapter_test

import (
	"context"
	"fmt"
	"strings"
	"testing"

	minio "github.com/minio/minio-go/v7"

	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// credentialCanary is the redaction needle for the S3 backend (ADR-0020 dimension (f)): a fake
// credential VALUE seeded as the access-key/secret-key. It must appear in NO surfaced artifact —
// not any Backend error, not an ObjectInfo, not a presigned URL, not a log. One leak fails the
// lane. High-entropy + self-labeling so a real gitleaks match would be unambiguous.
const credentialCanary = "OBJSTORE-CANARY-secretkey-c0ffee-d34db33f-do-not-leak" // #nosec G101 -- a deliberate redaction NEEDLE, not a real credential.

// canarySecrets seeds BOTH credential references with the canary so the adapter resolves it at
// construction; the assertions then prove the canary never re-surfaces. Returns the concrete fake
// (return concrete — 10 §9).
func canarySecrets() *secretstest.Provider {
	return secretstest.New(map[string]string{
		accessRef.String(): credentialCanary,
		secretRef.String(): credentialCanary,
	})
}

// TestCanary_CredentialNeverLeaksThroughErrors forces every Backend error path and asserts no
// surfaced error message ever carries the credential canary, even though the adapter resolved it at
// construction — the redaction half of the contract for the backend's failure paths.
func TestCanary_CredentialNeverLeaksThroughErrors(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	r := mustRef(t, "eden", "k.bin")

	client := newFakeS3()
	client.statErr = minio.ErrorResponse{StatusCode: 403, Message: "AccessDenied"}
	client.putErr = minio.ErrorResponse{StatusCode: 403, Message: "AccessDenied"}
	client.rmErr = minio.ErrorResponse{StatusCode: 500}
	client.signErr = minio.ErrorResponse{StatusCode: 400}
	client.listErr = minio.ErrorResponse{StatusCode: 403}

	adapter, err := newAdapter(client, canarySecrets())
	if err != nil {
		t.Fatalf("New error = %v", err)
	}

	_, putErr := adapter.PutObject(ctx, r, strings.NewReader("x"), 1, "")
	_, _, getErr := adapter.GetObject(ctx, r)
	delErr := adapter.DeleteObject(ctx, r)
	_, signErr := adapter.PresignObject(ctx, r, objectstorage.MethodGet, 60_000_000_000)
	_, listErr := adapter.ListObjects(ctx, "eden", "")

	for name, e := range map[string]error{"Put": putErr, "Get": getErr, "Delete": delErr, "Presign": signErr, "List": listErr} {
		if e == nil {
			continue
		}
		surface := e.Error() + " | " + fmt.Sprintf("%v %+v", e, e)
		if strings.Contains(surface, credentialCanary) {
			t.Fatalf("%s error path leaked the credential canary: %q", name, surface)
		}
	}
}

// TestCanary_CredentialNeverLeaksThroughPresignedURL resolves the canary credential at construction
// and asserts a successfully presigned URL carries no trace of it — the presigned URL is signed,
// not credential-bearing, so it is safe to log and hand to an untrusted client.
func TestCanary_CredentialNeverLeaksThroughPresignedURL(t *testing.T) {
	t.Parallel()
	adapter, err := newAdapter(newFakeS3(), canarySecrets())
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	signed, perr := adapter.PresignObject(context.Background(), mustRef(t, "eden", "p.bin"), objectstorage.MethodGet, 60_000_000_000)
	if perr != nil {
		t.Fatalf("PresignObject error = %v", perr)
	}
	if strings.Contains(signed.String(), credentialCanary) {
		t.Fatalf("presigned URL leaked the credential canary: %q", signed.String())
	}
}
