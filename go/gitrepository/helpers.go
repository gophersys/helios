package gitrepository

import (
	"context"
	"sync"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// newLockTable builds the empty per-worktree serialization table.
func newLockTable() map[string]*sync.Mutex { return make(map[string]*sync.Mutex) }

// asType is a thin generic re-export of errors.AsType so internal call sites inspect a
// typed error without each reaching for the errors package directly.
func asType[E error](err error) (E, bool) { return errors.AsType[E](err) }

// contextErr maps a canceled/expired context to the right errors.Kind so a verb returns
// early without spawning a git process. Returns nil for a live context.
func contextErr(ctx context.Context) error {
	if err := errors.FromContext(ctx); err != nil {
		return err
	}
	return nil
}

// zeroize wipes a resolved credential after a network op. It is the defer idiom at every
// credential use site; a nil Secret (the public/local op) is a no-op.
func zeroize(secret *secrets.Secret) {
	if secret != nil {
		secret.Zeroize()
	}
}

// wrapBackend wraps an error a Backend returned as it crosses back into the library. A
// Backend already returns typed gitrepository errors wrapped with their Kind (the system-git
// backend classifies stderr; the fake returns typed values directly), so wrapBackend only
// re-wraps a still-bare error to keep the chain inspectable and never flattens a classified
// one. A nil error stays nil (the happy path reads linearly).
func wrapBackend(err error) error {
	if err == nil {
		return nil
	}
	// If the error already classifies (a gitrepository-typed error, wrapped or bare), preserve
	// it: Wrap with KindUnknown inherits the existing Kind rather than clobbering it.
	return errors.Wrap(errors.KindUnknown, "gitrepository: backend operation failed", err)
}
