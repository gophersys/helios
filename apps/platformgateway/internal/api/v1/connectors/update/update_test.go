package update

import (
	"testing"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/errors"
)

// TestValidate_ValueRequired asserts the pure validate stage rejects an empty new value (KindInvalid →
// 400) and accepts a present one. A PUT with no value has nothing to re-seal.
func TestValidate_ValueRequired(t *testing.T) {
	t.Parallel()
	if err := validate(Request{ID: uuid.New(), Value: ""}); errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("empty value: want KindInvalid, got %v", err)
	}
	if err := validate(Request{ID: uuid.New(), Value: "new-secret"}); err != nil {
		t.Fatalf("present value: want nil, got %v", err)
	}
}
