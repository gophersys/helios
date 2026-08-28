package codeinsight

import (
	"strconv"

	"github.com/gophersys/libs/go/errors"
)

// The error taxonomy is a set of distinct types, each carrying the offending input — NEVER a
// secret, NEVER raw stderr — and each mapping to a stable errors.Kind so the transport boundary
// needs no per-port table (errors.md §5, 10 §9). Inspected via errors.AsType; classified via
// errors.KindOf after the library wraps them with wrapKind. The History/MetricProvider ports and
// the library return them wrapped with %w so callers branch on type, not on a string match.

type (
	// InvalidInputError reports a malformed Config or Deps (an empty repository path, a missing
	// port) — the pure constructor's validation guard.
	InvalidInputError struct{ What string }

	// HistoryError reports a failure walking the commit history (the History port could not read
	// the repository log). It carries the offending repository identifier, never a credential.
	HistoryError struct{ Repository string }
)

// Error renders an operator-safe message; none of these ever interpolates a secret value.

func (e *InvalidInputError) Error() string {
	return "codeinsight: invalid input " + strconv.Quote(e.What)
}

func (e *HistoryError) Error() string {
	return "codeinsight: history walk failed for " + strconv.Quote(e.Repository)
}

// Each error exposes Kind() mapping it to the errors.md taxonomy (10 §9). This method is the SINGLE
// home for the type→Kind mapping: kindOf below reads it through the kindCarrier seam rather than
// re-deriving a parallel switch, so KindOf(err) classifies without string matching.

// Kind reports the stable errors.Kind for an InvalidInputError.
func (e *InvalidInputError) Kind() errors.Kind { return errors.KindInvalid }

// Kind reports the stable errors.Kind for a HistoryError.
func (e *HistoryError) Kind() errors.Kind { return errors.KindUnavailable }

// kindCarrier is the classification seam: a typed error that carries its own stable errors.Kind via
// the Kind() method declared above. Every codeinsight error type implements it (the data IS its
// classification), so kindOf reads the carrier instead of re-deriving a parallel table — ONE home.
type kindCarrier interface{ Kind() errors.Kind }

// kindOf is the TOTAL classifier the library wraps with (wrapKind), so the transport boundary reads
// errors.KindOf without a codeinsight-specific table. It reads the error's OWN Kind() method (the
// single source of truth declared per type above); a non-carrier error is KindUnknown.
//
// kindOf is only ever called by wrapKind on a freshly-minted, UNWRAPPED codeinsight error the
// library is about to wrap; classification of an already-WRAPPED chain is errors.KindOf.
//
//nolint:errorlint // kindOf classifies an unwrapped leaf the library just minted; the wrapped-chain path is errors.KindOf via errors.AsType.
func kindOf(err error) errors.Kind {
	if carrier, ok := err.(kindCarrier); ok {
		return carrier.Kind()
	}
	return errors.KindUnknown
}

// wrapKind wraps a typed codeinsight error with its stable errors.Kind so the transport boundary
// maps it without a per-port table (10 §9). Returns nil for a nil error (the happy path reads
// linearly).
func wrapKind(err error) error {
	if err == nil {
		return nil
	}
	return errors.Wrap(kindOf(err), err.Error(), err)
}
