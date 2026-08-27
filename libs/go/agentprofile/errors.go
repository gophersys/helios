package agentprofile

import (
	"encoding/json"
	"strconv"

	"github.com/gophersys/libs/go/errors"
)

// NotImplementedError is the typed cause a declared-but-unbuilt harness renderer returns. It is a
// distinct type, not a message, so a caller can branch on it with errors.IsType and read WHICH cell
// of the matrix is unbuilt from the value rather than from prose. Every renderer that cannot emit
// returns this; none returns an empty FileSet.
type NotImplementedError struct {
	// Harness names the harness whose renderer is declared but not built.
	Harness Harness
}

// Error implements error. It names the harness, so a caller that only ever logs the message still
// learns which renderer is missing. It carries no package prefix of its own: this type is always
// surfaced as the CAUSE of an *errors.Error that already prefixes the chain, unlike a port's
// top-level error type, which self-prefixes because nothing else will.
func (e NotImplementedError) Error() string {
	return "no renderer is implemented for harness " + string(e.Harness)
}

// notImplemented builds the failure a declared-but-unbuilt renderer returns: the typed
// NotImplementedError as the cause, under KindInternal — an unbuilt renderer is a gap we own, not
// bad input from the caller and not a transient the caller could retry past. Each layer of the
// chain adds one thing: the caller's operation, this classification, then the harness.
func notImplemented(harness Harness) *errors.Error {
	return errors.Wrap(errors.KindInternal, "agentprofile: unbuilt harness renderer",
		NotImplementedError{Harness: harness}).WithField("harness", string(harness))
}

// invalid builds the typed error a malformed Config, Deps or profile document yields. KindInvalid
// is the caller's half of the taxonomy: the input this library was handed cannot be honored.
func invalid(message string) *errors.Error {
	return errors.New(errors.KindInvalid, "agentprofile: "+message)
}

// notFound builds the typed error an address that names no cell of the matrix yields — an unknown
// role, a harness the role does not declare, an overlay the document does not carry, or a harness no
// injected Renderer claims.
func notFound(message string) *errors.Error {
	return errors.New(errors.KindNotFound, "agentprofile: "+message)
}

// rendererFault builds the typed error a Renderer that broke this library's emission invariants
// yields. KindInternal, not KindInvalid: the caller's document was fine and the defect is on our
// side of the port.
func rendererFault(message string) *errors.Error {
	return errors.New(errors.KindInternal, "agentprofile: "+message)
}

// parseFault wraps a decoder failure and names WHERE the document is wrong. encoding/json reports a
// byte offset; a human editing a profile document needs a line and a column, and converting it here
// is the difference between a fixable error and a re-read of the whole file.
func parseFault(raw []byte, cause error) *errors.Error {
	message := "agentprofile: parse profile document"
	if offset, located := faultOffset(cause); located {
		line, column := lineColumn(raw, offset)
		message += " at line " + strconv.Itoa(line) + ", column " + strconv.Itoa(column)
	}
	return errors.Wrap(errors.KindInvalid, message, cause)
}

// faultOffset extracts the byte offset from the two encoding/json error types that carry one. Typed
// inspection, never a string match: the messages are Go's to change, the types are not.
func faultOffset(cause error) (offset int, located bool) {
	if syntaxFault, ok := errors.AsType[*json.SyntaxError](cause); ok {
		return int(syntaxFault.Offset), true
	}
	if typeFault, ok := errors.AsType[*json.UnmarshalTypeError](cause); ok {
		return int(typeFault.Offset), true
	}
	return 0, false
}

// lineColumn converts a byte offset into a 1-based line and column. encoding/json reports the offset
// just PAST the byte it rejected, so the position names the character the decoder choked on rather
// than the one before it.
func lineColumn(raw []byte, offset int) (line, column int) {
	line, column = 1, 1
	for i := 0; i < offset && i < len(raw); i++ {
		if raw[i] == '\n' {
			line++
			column = 1
			continue
		}
		column++
	}
	return line, column
}
