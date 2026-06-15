package minioadapter

import (
	minio "github.com/minio/minio-go/v7"

	"github.com/gophersys/libs/go/errors"
)

// realNewClient is the production S3 builder (the Deps.NewClient default). It constructs the real
// *minio.Client from the endpoint + options. *minio.Client already satisfies BOTH the narrow S3
// seam (PutObject/GetObject/StatObject/RemoveObject/PresignHeader) and the lister extension
// (ListObjects) by method-set, so no wrapper is needed — the SDK type IS the seam implementation,
// and this file is the one compilation unit (besides minioadapter.go's import) that names it.
//
// minio.New performs NO network I/O — it constructs the HTTP client and parses the endpoint; the
// first request is the first Backend method, preserving New's purity contract.
//
//nolint:ireturn // intentional: this IS the Deps.NewClient seam (func(...) (S3, error)); it must return the S3 interface so a test can swap a fake.
func realNewClient(endpoint string, options *minio.Options) (S3, error) {
	client, err := minio.New(endpoint, options)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "minioadapter: constructing the minio client", err)
	}
	return client, nil
}

// compile-time: the real SDK client satisfies BOTH seams the adapter drives.
var (
	_ S3     = (*minio.Client)(nil)
	_ lister = (*minio.Client)(nil)
)
