package configurationtest

import (
	"context"
	"strings"

	"github.com/gophersys/libs/go/configuration"
)

// Parser is a scripted, deterministic fake configuration.Parser. Parse/Merge
// return whatever was staged per name; an unstaged name returns a *ParseError
// so missing-input paths are testable. Calls are recorded for assertion. The
// zero value is usable: every name is unstaged.
type Parser struct {
	Documents   map[string]configuration.Document    // name -> staged doc
	Diagnostics map[string]configuration.Diagnostics // name -> staged findings
	ReadErr     map[string]error                     // name -> staged I/O error
	ParseCalls  []string                             // recorded, in order
}

// Parse returns the staged document/diagnostics for name. A staged ReadErr (or
// an unstaged name) yields a *configuration.ParseError on the err channel,
// mirroring the real Parser's "couldn't read" discipline.
func (p *Parser) Parse(_ context.Context, name string) (configuration.Document, configuration.Diagnostics, error) {
	p.ParseCalls = append(p.ParseCalls, name)

	if p.ReadErr != nil {
		if err, ok := p.ReadErr[name]; ok && err != nil {
			return nil, configuration.Diagnostics{}, &configuration.ParseError{Source: name, Err: err}
		}
	}

	doc, staged := p.Documents[name]
	if !staged {
		return nil, configuration.Diagnostics{}, &configuration.ParseError{
			Source: name,
			Err:    errUnstaged{name: name},
		}
	}

	var diags configuration.Diagnostics
	if p.Diagnostics != nil {
		if d, ok := p.Diagnostics[name]; ok {
			diags.Append(d.All()...)
		}
	}
	return doc, diags, nil
}

// Merge is the scripted fold: it returns the overlay when present, else the
// base. The fake operates at document granularity (overlay wins wholesale),
// which is sufficient for tests that stage explicit Merge outcomes; the REAL
// Parser is the one that does per-Path, position-preserving folding.
func (p *Parser) Merge(_ context.Context, base, overlay configuration.Document) (configuration.Document, configuration.Diagnostics, error) {
	if overlay != nil {
		return overlay, configuration.Diagnostics{}, nil
	}
	return base, configuration.Diagnostics{}, nil
}

// errUnstaged is the cause wrapped by a *ParseError for an unstaged name.
type errUnstaged struct{ name string }

func (e errUnstaged) Error() string { return "configurationtest: no document staged for " + e.name }

// Source is a map-backed configuration.Source for driving the REAL Parser in
// tests without touching the filesystem.
type Source struct {
	Files map[string][]byte
	Err   map[string]error
}

// Read returns the staged bytes for name, a staged error, or a not-found error.
func (s Source) Read(_ context.Context, name string) ([]byte, error) {
	if s.Err != nil {
		if err, ok := s.Err[name]; ok && err != nil {
			return nil, err
		}
	}
	if s.Files != nil {
		if b, ok := s.Files[name]; ok {
			return b, nil
		}
	}
	return nil, errUnstaged{name: name}
}

// Diags returns the diagnostics at or under a Path, so a test can assert
// "exactly one SeverityError at engine.models[0].auth."
func Diags(d configuration.Diagnostics, under configuration.Path) []configuration.Diagnostic {
	var out []configuration.Diagnostic
	prefix := string(under)
	for _, dg := range d.All() {
		p := string(dg.Path)
		if p == prefix || strings.HasPrefix(p, prefix+".") || strings.HasPrefix(p, prefix+"[") {
			out = append(out, dg)
		}
	}
	return out
}
