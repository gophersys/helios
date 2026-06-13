package secrets

import (
	"context"
	"fmt"
)

// New is the constructor spine. PURE: no I/O, no clocks, no env reads. It validates
// configuration and wires the (already-constructed) adapters from dependencies into the
// routing Mediator. Adapters do the I/O, lazily, on Resolve. Returns the concrete *Mediator.
func New(configuration Config, dependencies Deps) (*Mediator, error) {
	if len(dependencies.Resolvers) == 0 {
		return nil, fmt.Errorf("secrets.New: Deps.Resolvers requires at least one entry")
	}
	resolvers := make(map[string]Provider, len(dependencies.Resolvers))
	for scheme, p := range dependencies.Resolvers {
		if p == nil {
			return nil, fmt.Errorf("secrets.New: Deps.Resolvers[%q] is nil", scheme)
		}
		resolvers[scheme] = p
	}
	return &Mediator{
		defaultScheme: configuration.DefaultScheme,
		resolvers:     resolvers,
	}, nil
}

// Config is the immutable, fully-resolved input. The only knob the routing Mediator needs is
// the default scheme; references themselves arrive at Resolve time.
type Config struct {
	// DefaultScheme routes a Reference that carries no explicit scheme. Empty means "require
	// an explicit scheme" (a schemeless Reference then resolves to InvalidReferenceError).
	DefaultScheme string
}

// Deps is the injected hexagon: the resolver adapters keyed by scheme. Accepting Provider (an
// interface) here is the accept-interfaces rule; the Mediator returned is concrete.
type Deps struct {
	// Resolvers maps a Reference scheme to the adapter that serves it. At least one entry is
	// required; New returns an error otherwise.
	Resolvers map[string]Provider
}

// Mediator is the concrete Provider returned by New: it routes each Reference to the
// Deps.Resolvers entry for its scheme (or DefaultScheme) and is the type apps hold. Safe for
// concurrent use. Zero value is not usable; construct via New.
type Mediator struct {
	defaultScheme string
	// resolvers is read-only after New, so concurrent Resolve needs no lock.
	resolvers map[string]Provider
}

// Resolve implements Provider by routing ref to its scheme's adapter.
func (m *Mediator) Resolve(ctx context.Context, ref Reference) (*Secret, error) {
	if ref.IsZero() {
		return nil, InvalidReferenceError{Ref: ref}
	}
	scheme := ref.Scheme()
	if scheme == "" {
		scheme = m.defaultScheme
	}
	if scheme == "" {
		// Schemeless reference with no DefaultScheme: unroutable.
		return nil, InvalidReferenceError{Ref: ref}
	}
	adapter, ok := m.resolvers[scheme]
	if !ok {
		// No adapter bound for this scheme: the reference is unroutable, hence invalid for
		// this composition.
		return nil, fmt.Errorf("secrets: no adapter for scheme %q: %w", scheme, InvalidReferenceError{Ref: ref})
	}
	return adapter.Resolve(ctx, ref)
}

// compile-time: *Mediator is a Provider.
var _ Provider = (*Mediator)(nil)
